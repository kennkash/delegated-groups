from __future__ import annotations

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

from sqlalchemy.orm import Session

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
# "Current user" dependency (wire this to your real auth)
# ---------------------------------------------------------------------------

class CurrentIdentity(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None


def get_current_identity(
    # Example placeholders: replace with your actual auth integration.
    # You can also remove these headers and instead decode JWT/session, etc.
    x_user: Optional[str] = Header(default=None, alias="X-User"),
    x_email: Optional[str] = Header(default=None, alias="X-Email"),
) -> CurrentIdentity:
    """
    Replace this with your real identity provider.

    For now it supports:
      - X-User: username
      - X-Email: email

    Your UI/backend can send one or both.
    """
    if not x_user and not x_email:
        raise HTTPException(
            status_code=401,
            detail="Missing identity (provide X-User and/or X-Email, or wire real auth).",
        )
    return CurrentIdentity(username=x_user, email=x_email)


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
    group_owners: List[str] = []  # list of owning_group_names


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


def resolve_requester_user_id(db: Session, ident: CurrentIdentity) -> int:
    """
    Find the current requester in dg_user.

    Priority:
      1) match by lower_email if provided
      2) match by lower_username if provided

    This does NOT create a user.
    If the requester isn't in dg_user yet, they can't be an owner in this system.
    """
    if ident.email:
        u = db.query(DgUser).filter(DgUser.lower_email == ident.email.lower()).one_or_none()
        if u:
            return u.id

    if ident.username:
        u = db.query(DgUser).filter(DgUser.lower_username == ident.username.lower()).one_or_none()
        if u:
            return u.id

    raise HTTPException(
        status_code=403,
        detail="Requester not found in delegated-groups user table; cannot verify ownership.",
    )


def require_owner_of_group(
    db: Session,
    ident: CurrentIdentity,
    app: str,
    group_name: str,
) -> DgManagedGroup:
    """
    Permission check: requester must be an *effective owner* of (app, group_name).

    Effective owner means they have a row in dg_group_owner for that managed_group_id,
    regardless of whether it is USER_OWNER or GROUP_OWNER.
    """
    managed_group = get_managed_group(db, app, group_name)
    requester_user_id = resolve_requester_user_id(db, ident)

    is_owner = (
        db.query(DgGroupOwner.id)
        .filter(DgGroupOwner.managed_group_id == managed_group.id)
        .filter(DgGroupOwner.user_id == requester_user_id)
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
def add_user_owner(
    req: UserOwnerRequest,
    ident: CurrentIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    """
    Add a USER_OWNER to an existing delegated group.
    Permission: requester must already be an owner of that delegated group.
    """
    managed_group = require_owner_of_group(db, ident, req.app, req.group_name)

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
def remove_user_owner(
    req: UserOwnerRequest,
    ident: CurrentIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    """
    Remove a USER_OWNER from a delegated group.
    Permission: requester must already be an owner of that delegated group.
    """
    managed_group = require_owner_of_group(db, ident, req.app, req.group_name)

    # Find the target user row (by username primarily; email optional)
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
def add_group_owner(
    req: GroupOwnerRequest,
    ident: CurrentIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    """
    Add a GROUP_OWNER rule (does NOT expand members here).
    Refresh job will expand membership into dg_group_owner rows.
    Permission: requester must already be an owner of that delegated group.
    """
    managed_group = require_owner_of_group(db, ident, req.app, req.group_name)

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
def remove_group_owner(
    req: GroupOwnerRequest,
    ident: CurrentIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    """
    Remove a GROUP_OWNER rule (all-or-nothing) and delete all expanded membership rows
    for that owning group.
    Permission: requester must already be an owner of that delegated group.
    """
    managed_group = require_owner_of_group(db, ident, req.app, req.group_name)

    # 1) delete expanded GROUP_OWNER user rows
    expanded_deleted = (
        db.query(DgGroupOwner)
        .filter(
            DgGroupOwner.managed_group_id == managed_group.id,
            DgGroupOwner.source_type == "GROUP_OWNER",
            DgGroupOwner.via_group_name == req.owning_group_name,
        )
        .delete(synchronize_session=False)
    )

    # 2) delete the rule row
    rule_deleted = (
        db.query(DgGroupOwnerGroup)
        .filter(
            DgGroupOwnerGroup.managed_group_id == managed_group.id,
            DgGroupOwnerGroup.lower_owning_group_name == req.owning_group_name.lower(),
        )
        .delete(synchronize_session=False)
    )

    db.commit()
    return {"removed_group_rule_rows": rule_deleted, "removed_expanded_owner_rows": expanded_deleted}


# ---------------------------------------------------------------------------
# Endpoints (OPEN)
# ---------------------------------------------------------------------------

@router.post("/groups")
def create_group_with_owners(
    req: NewGroupRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new delegated group and assign initial user + group owners.

    Permission: OPEN (anyone can create a new group).
    """
    app = req.app.lower()
    lower_group_name = req.group_name.lower()

    # Prevent duplicates within the same app (matches uq_app_group)
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

    # USER owners (direct)
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

    # GROUP owners (rules only; refresh expands members)
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
def find_groups_by_email(
    req: FindGroupsByEmailRequest,
    db: Session = Depends(get_db),
):
    """
    Takes in a user's email and returns the groups they are an effective owner of
    for each application.

    Permission: OPEN.
    """
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
            "ownership_type": source_type,     # USER_OWNER or GROUP_OWNER
            "via_group_name": via_group_name,  # owning group for GROUP_OWNER, else null
        }
        for app, group_name, source_type, via_group_name in rows
    ]