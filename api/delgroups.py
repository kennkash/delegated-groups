from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.v0.deps.current_user import get_current_email  # <-- USE THE DEP

from .database.psql_models import (
    SessionLocal,
    DgUser,
    DgManagedGroup,
    DgGroupOwner,
    DgGroupOwnerGroup,
)

router = APIRouter(prefix="/delegated-groups", tags=["Delegated Groups"])


# ---------------------------------------------------------------------------
# DB dependency
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class UserOwnerRequest(BaseModel):
    app: str
    group_name: str
    username: str
    email: Optional[str] = None


class GroupOwnerRequest(BaseModel):
    app: str
    group_name: str
    owning_group_name: str


class NewGroupUserOwner(BaseModel):
    username: str
    email: Optional[str] = None


class NewGroupRequest(BaseModel):
    app: str
    group_name: str
    user_owners: List[NewGroupUserOwner] = []
    group_owners: List[str] = []


class FindGroupsByEmailRequest(BaseModel):
    email: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_or_create_user(db: Session, username: str, email: Optional[str]) -> DgUser:
    lower_username = username.lower()
    lower_email = email.lower() if email else None

    q = db.query(DgUser).filter(DgUser.lower_username == lower_username)
    if lower_email is None:
        q = q.filter(DgUser.lower_email.is_(None))
    else:
        q = q.filter(DgUser.lower_email == lower_email)

    user = q.one_or_none()
    if user:
        return user

    user = DgUser(
        username=username,
        email=email,
        lower_username=lower_username,
        lower_email=lower_email,
    )
    db.add(user)
    db.flush()
    return user


def get_managed_group(db: Session, app: str, group_name: str) -> DgManagedGroup:
    group = (
        db.query(DgManagedGroup)
        .filter(DgManagedGroup.app == app.lower())
        .filter(DgManagedGroup.lower_group_name == group_name.lower())
        .one_or_none()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Delegated group not found")
    return group


def require_owner_by_email(
    db: Session,
    requester_email: str,
    app: str,
    group_name: str,
) -> DgManagedGroup:
    managed_group = get_managed_group(db, app, group_name)

    requester = (
        db.query(DgUser)
        .filter(DgUser.lower_email == requester_email)
        .one_or_none()
    )
    if not requester:
        raise HTTPException(
            status_code=403,
            detail="Requester not found in dg_user by email; cannot verify ownership yet.",
        )

    is_owner = (
        db.query(DgGroupOwner.id)
        .filter(DgGroupOwner.managed_group_id == managed_group.id)
        .filter(DgGroupOwner.user_id == requester.id)
        .first()
    )
    if not is_owner:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: only current owners can add/remove owners for this delegated group.",
        )

    return managed_group


# ---------------------------------------------------------------------------
# Endpoints (OWNER-GATED)
# ---------------------------------------------------------------------------

@router.post("/owners/user")
async def add_user_owner(
    req: UserOwnerRequest,
    requester_email: str = Depends(get_current_email),
    db: Session = Depends(get_db),
):
    managed_group = require_owner_by_email(db, requester_email, req.app, req.group_name)
    user = get_or_create_user(db, req.username, req.email)

    exists = (
        db.query(DgGroupOwner)
        .filter(
            DgGroupOwner.managed_group_id == managed_group.id,
            DgGroupOwner.user_id == user.id,
            DgGroupOwner.source_type == "USER_OWNER",
            DgGroupOwner.via_group_name.is_(None),
        )
        .first()
    )
    if exists:
        return {"status": "already exists"}

    db.add(
        DgGroupOwner(
            managed_group_id=managed_group.id,
            user_id=user.id,
            source_type="USER_OWNER",
            via_group_name=None,
        )
    )
    db.commit()
    return {"status": "user owner added"}


@router.delete("/owners/user")
async def remove_user_owner(
    req: UserOwnerRequest,
    requester_email: str = Depends(get_current_email),
    db: Session = Depends(get_db),
):
    managed_group = require_owner_by_email(db, requester_email, req.app, req.group_name)

    q = db.query(DgUser).filter(DgUser.lower_username == req.username.lower())
    if req.email:
        q = q.filter(DgUser.lower_email == req.email.lower())

    user = q.one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Target user not found")

    deleted = (
        db.query(DgGroupOwner)
        .filter(
            DgGroupOwner.managed_group_id == managed_group.id,
            DgGroupOwner.user_id == user.id,
            DgGroupOwner.source_type == "USER_OWNER",
            DgGroupOwner.via_group_name.is_(None),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"removed_rows": deleted}


@router.post("/owners/group")
async def add_group_owner(
    req: GroupOwnerRequest,
    requester_email: str = Depends(get_current_email),
    db: Session = Depends(get_db),
):
    managed_group = require_owner_by_email(db, requester_email, req.app, req.group_name)

    exists = (
        db.query(DgGroupOwnerGroup)
        .filter(
            DgGroupOwnerGroup.managed_group_id == managed_group.id,
            DgGroupOwnerGroup.lower_owning_group_name == req.owning_group_name.lower(),
        )
        .first()
    )
    if exists:
        return {"status": "already exists"}

    db.add(
        DgGroupOwnerGroup(
            managed_group_id=managed_group.id,
            owning_group_name=req.owning_group_name,
            lower_owning_group_name=req.owning_group_name.lower(),
        )
    )
    db.commit()
    return {"status": "group owner added (refresh will expand members)"}


@router.delete("/owners/group")
async def remove_group_owner(
    req: GroupOwnerRequest,
    requester_email: str = Depends(get_current_email),
    db: Session = Depends(get_db),
):
    managed_group = require_owner_by_email(db, requester_email, req.app, req.group_name)

    expanded_deleted = (
        db.query(DgGroupOwner)
        .filter(
            DgGroupOwner.managed_group_id == managed_group.id,
            DgGroupOwner.source_type == "GROUP_OWNER",
            DgGroupOwner.via_group_name == req.owning_group_name,
        )
        .delete(synchronize_session=False)
    )

    rule_deleted = (
        db.query(DgGroupOwnerGroup)
        .filter(
            DgGroupOwnerGroup.managed_group_id == managed_group.id,
            DgGroupOwnerGroup.lower_owning_group_name == req.owning_group_name.lower(),
        )
        .delete(synchronize_session=False)
    )

    db.commit()
    return {
        "removed_group_rule_rows": rule_deleted,
        "removed_expanded_owner_rows": expanded_deleted,
    }


# ---------------------------------------------------------------------------
# Endpoints (OPEN)
# ---------------------------------------------------------------------------

@router.post("/groups")
async def create_group_with_owners(
    req: NewGroupRequest,
    db: Session = Depends(get_db),
):
    app = req.app.lower()
    lower_group_name = req.group_name.lower()

    exists = (
        db.query(DgManagedGroup.id)
        .filter(DgManagedGroup.app == app)
        .filter(DgManagedGroup.lower_group_name == lower_group_name)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Delegated group already exists in this app")

    group = DgManagedGroup(
        app=app,
        group_name=req.group_name,
        lower_group_name=lower_group_name,
    )
    db.add(group)
    db.flush()

    for u in req.user_owners:
        user = get_or_create_user(db, u.username, u.email)
        db.add(
            DgGroupOwner(
                managed_group_id=group.id,
                user_id=user.id,
                source_type="USER_OWNER",
                via_group_name=None,
            )
        )

    for owning_group in req.group_owners:
        db.add(
            DgGroupOwnerGroup(
                managed_group_id=group.id,
                owning_group_name=owning_group,
                lower_owning_group_name=owning_group.lower(),
            )
        )

    db.commit()
    return {"status": "delegated group created", "app": app, "group_name": req.group_name}


@router.post("/my-groups")
async def find_groups_by_email(
    req: FindGroupsByEmailRequest,
    db: Session = Depends(get_db),
):
    user = db.query(DgUser).filter(DgUser.lower_email == req.email.lower()).one_or_none()
    if not user:
        return []

    rows = (
        db.query(
            DgManagedGroup.app,
            DgManagedGroup.group_name,
            DgGroupOwner.source_type,
            DgGroupOwner.via_group_name,
        )
        .join(DgGroupOwner, DgGroupOwner.managed_group_id == DgManagedGroup.id)
        .filter(DgGroupOwner.user_id == user.id)
        .order_by(DgManagedGroup.app, DgManagedGroup.group_name)
        .all()
    )

    return [
        {
            "app": app,
            "group_name": group_name,
            "ownership_type": source_type,
            "via_group_name": via_group_name,
        }
        for app, group_name, source_type, via_group_name in rows
    ]