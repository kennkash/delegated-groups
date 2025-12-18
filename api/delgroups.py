from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from services.v0.user_email import get_current_email

from ..models.delGroups import UserOwnerRequest, GroupOwnerRequest, NewGroupRequest
from ..models.psql_models import (
    SessionLocal,
    DgUser,
    DgManagedGroup,
    DgGroupOwner,
    DgGroupOwnerGroup,
)

router = APIRouter()

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
        .filter(DgUser.lower_email == requester_email.lower())
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
    """
    add_user_owner adds a direct USER_OWNER to an existing delegated group.

    Only existing effective owners of the delegated group may add/remove owners.
    Ownership verification is performed using the requester's email (smtp) from
    the EmployeeService identity payload.

    <details><summary><span>Parameters</span></summary>
    | Name | Type | Description |
    |------|------|-------------|
    | `req` | `UserOwnerRequest` | JSON body containing the app + delegated group + target user to add as a USER_OWNER |
    </details>

    <details><summary><span>UserOwnerRequest</span></summary>
    | Field | Type | Description |
    |------|------|-------------|
    | `app` | `str` | Application name: `jira` or `confluence` |
    | `group_name` | `str` | Delegated group name to update |
    | `username` | `str` | Username of the user to add as a direct owner |
    | `email` | `str \| null` | Optional email for the user (recommended to avoid duplicates) |
    </details>

    <details><summary><span>Returns</span></summary>

    A JSON object with a `status` field:

    * `status` – `"user owner added"` when inserted, or `"already exists"` if the row is already present
    </details>
    """
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
    """
    remove_user_owner removes a direct USER_OWNER from an existing delegated group.

    Only existing effective owners of the delegated group may add/remove owners.
    Ownership verification is performed using the requester's email (smtp) from
    the EmployeeService identity payload.

    <details><summary><span>Parameters</span></summary>
    | Name | Type | Description |
    |------|------|-------------|
    | `req` | `UserOwnerRequest` | JSON body containing the app + delegated group + target user to remove as a USER_OWNER |
    </details>

    <details><summary><span>UserOwnerRequest</span></summary>
    | Field | Type | Description |
    |------|------|-------------|
    | `app` | `str` | Application name: `jira` or `confluence` |
    | `group_name` | `str` | Delegated group name to update |
    | `username` | `str` | Username of the user to remove as a direct owner |
    | `email` | `str \| null` | Optional email for the user (if provided, removal is scoped to that identity) |
    </details>

    <details><summary><span>Returns</span></summary>

    A JSON object containing:

    * `removed_rows` – number of `dg_group_owner` rows deleted (0 or 1)
    </details>
    """
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
    """
    add_group_owner registers an owning group as a GROUP_OWNER for an existing delegated group.

    This endpoint registers the owning group rule in `dg_group_owner_group`.
    Member expansion into `dg_group_owner` rows is performed by the scheduled refresh job.

    Only existing effective owners of the delegated group may add/remove owners.
    Ownership verification is performed using the requester's email (smtp) from
    the EmployeeService identity payload.

    <details><summary><span>Parameters</span></summary>
    | Name | Type | Description |
    |------|------|-------------|
    | `req` | `GroupOwnerRequest` | JSON body containing the app + delegated group + owning group to register |
    </details>

    <details><summary><span>GroupOwnerRequest</span></summary>
    | Field | Type | Description |
    |------|------|-------------|
    | `app` | `str` | Application name: `jira` or `confluence` |
    | `group_name` | `str` | Delegated group name to update |
    | `owning_group_name` | `str` | Group whose members inherit ownership of the delegated group |
    </details>

    <details><summary><span>Returns</span></summary>

    A JSON object with a `status` field:

    * `status` – `"group owner added (refresh will expand members)"` when inserted, or `"already exists"` if the rule already exists
    </details>
    """
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
    """
    remove_group_owner removes an owning group as a GROUP_OWNER for an existing delegated group.

    This is an all-or-nothing removal:
    - deletes the owning-group rule from `dg_group_owner_group`
    - deletes all expanded member rows from `dg_group_owner` where:
        * `source_type='GROUP_OWNER'`
        * `via_group_name=<owning_group_name>`

    Only existing effective owners of the delegated group may add/remove owners.
    Ownership verification is performed using the requester's email (smtp) from
    the EmployeeService identity payload.

    <details><summary><span>Parameters</span></summary>
    | Name | Type | Description |
    |------|------|-------------|
    | `req` | `GroupOwnerRequest` | JSON body containing the app + delegated group + owning group to remove |
    </details>

    <details><summary><span>GroupOwnerRequest</span></summary>
    | Field | Type | Description |
    |------|------|-------------|
    | `app` | `str` | Application name: `jira` or `confluence` |
    | `group_name` | `str` | Delegated group name to update |
    | `owning_group_name` | `str` | Owning group to remove (all member-derived owners removed) |
    </details>

    <details><summary><span>Returns</span></summary>

    A JSON object containing:

    * `removed_group_rule_rows` – number of `dg_group_owner_group` rows deleted (0 or 1)
    * `removed_expanded_owner_rows` – number of expanded `dg_group_owner` rows deleted
    </details>
    """
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
    """
    create_group_with_owners creates a new delegated group and registers initial owners.

    This endpoint is OPEN (no owner permission check). Any user may create a delegated group.

    Behavior:
    - Creates a new `dg_managed_group` row for (app, group_name)
    - Inserts direct USER_OWNERS into `dg_group_owner` with `source_type='USER_OWNER'`
    - Registers GROUP_OWNER rules in `dg_group_owner_group`
      (member expansion happens during the scheduled refresh job)

    <details><summary><span>Parameters</span></summary>
    | Name | Type | Description |
    |------|------|-------------|
    | `req` | `NewGroupRequest` | JSON body containing the delegated group and its initial user/group owners |
    </details>

    <details><summary><span>NewGroupRequest</span></summary>
    | Field | Type | Description |
    |------|------|-------------|
    | `app` | `str` | Application name: `jira` or `confluence` |
    | `group_name` | `str` | Delegated group name to create |
    | `user_owners` | `list[UserOwner]` | Direct user owners to add immediately |
    | `group_owners` | `list[str]` | Owning group names to register as GROUP_OWNERS (refresh expands members) |
    </details>

    <details><summary><span>Returns</span></summary>

    A JSON object containing:

    * `status` – `"delegated group created"`
    * `app` – application name stored
    * `group_name` – delegated group name stored
    </details>
    """
    app = req.app.lower()
    lower_group_name = req.group_name.lower()

    exists = (
        db.query(DgManagedGroup.id)
        .filter(DgManagedGroup.app == app)
        .filter(DgManagedGroup.lower_group_name == lower_group_name)
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=409,
            detail="Delegated group already exists in this app",
        )

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


@router.get("/my-groups")
async def my_groups(
    requester_email: str = Depends(get_current_email),
    db: Session = Depends(get_db),
):
    """
    my_groups returns the delegated groups the current requester is an effective owner of.

    The requester identity is determined via email (smtp) resolved from EmployeeService
    using request headers. No request payload is required.

    <details><summary><span>Parameters</span></summary>
    | Name | Type | Description |
    |------|------|-------------|
    | `requester_email` | `str` | Injected by dependency; requester's smtp email resolved from EmployeeService |
    </details>

    <details><summary><span>Returns</span></summary>

    A JSON list of objects, each containing:

    * `app` – `jira` or `confluence`
    * `group_name` – delegated group name
    * `ownership_type` – `USER_OWNER` or `GROUP_OWNER`
    * `via_group_name` – owning group name that granted ownership for `GROUP_OWNER` rows (null for `USER_OWNER`)
    </details>
    """
    user = (
        db.query(DgUser)
        .filter(DgUser.lower_email == requester_email.lower())
        .one_or_none()
    )
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