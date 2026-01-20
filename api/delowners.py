from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/groups/{app}/{group_name}/owners")
async def get_delegated_group_owners(
    app: str,
    group_name: str,
    db: Session = Depends(get_db),
):
    """
    get_delegated_group_owners returns the direct owners for a delegated group (DB-backed).

    This endpoint returns:
    - USER_OWNER: users directly assigned as owners of the delegated group
    - GROUP_OWNER: the owning group(s) that grant inherited ownership (membership expansion handled elsewhere)

    <details><summary><span>Parameters</span></summary>
    | Name | Type | Description |
    |------|------|-------------|
    | `app` | `str` | Application name: `jira` or `confluence` |
    | `group_name` | `str` | Delegated group name within the application |
    </details>

    <details><summary><span>Returns</span></summary>

    A JSON object containing:

    * `app` – `jira` or `confluence`
    * `group_name` – delegated group name (original case as stored)
    * `user_owners` – list of direct user owners:
        * `username`
        * `email`
    * `group_owners` – list of owning group names (no member expansion here)
    </details>
    """
    app_lower = app.lower()
    if app_lower not in {"jira", "confluence"}:
        raise HTTPException(status_code=400, detail="app must be 'jira' or 'confluence'")

    managed_group = get_managed_group(db, app_lower, group_name)

    # USER_OWNER rows -> users
    user_owner_rows = (
        db.query(DgUser.username, DgUser.email)
        .join(DgGroupOwner, DgGroupOwner.user_id == DgUser.id)
        .filter(DgGroupOwner.managed_group_id == managed_group.id)
        .filter(DgGroupOwner.source_type == "USER_OWNER")
        .order_by(DgUser.lower_username)
        .all()
    )
    user_owners = [{"username": u, "email": e} for (u, e) in user_owner_rows]

    # GROUP_OWNER rules (owning groups)
    group_owner_rows = (
        db.query(DgGroupOwnerGroup.owning_group_name)
        .filter(DgGroupOwnerGroup.managed_group_id == managed_group.id)
        .order_by(DgGroupOwnerGroup.lower_owning_group_name)
        .all()
    )
    group_owners = [r[0] for r in group_owner_rows]

    return {
        "app": managed_group.app,
        "group_name": managed_group.group_name,
        "user_owners": user_owners,
        "group_owners": group_owners,
    }