# delGroups_mem_refresh/dg_service.py

from __future__ import annotations

from typing import Iterable, Optional, Tuple, Callable, Set

from sqlalchemy.orm import Session

from .psql_models import (
    SessionLocal,
    DgUser,
    DgManagedGroup,
    DgGroupOwner,
)

from prettiprint import ConsoleUtils

cu = ConsoleUtils(theme="dark", verbosity=2)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _normalize_identity(
    username: str, email: Optional[str]
) -> Tuple[str, Optional[str]]:
    """
    Normalize a user identity for comparisons / lookups.
    """
    lower_username = username.lower()
    lower_email = email.lower() if email else None
    return lower_username, lower_email


def get_or_create_user(
    session: Session,
    username: str,
    email: Optional[str] = None,
) -> DgUser:
    """
    Return an existing DgUser or create one based on (lower_username, lower_email).

    This matches the unique constraint on dg_user:
    (lower_username, lower_email)
    """
    lower_username, lower_email = _normalize_identity(username, email)

    q = session.query(DgUser).filter(DgUser.lower_username == lower_username)
    if lower_email is None:
        q = q.filter(DgUser.lower_email.is_(None))
    else:
        q = q.filter(DgUser.lower_email == lower_email)

    user = q.one_or_none()
    if user:
        # cu.success(f"Found user: {user.lower_username} (ID: {user.id})")
        return user

    user = DgUser(
        username=username,
        email=email,
        lower_username=lower_username,
        lower_email=lower_email,
    )
    session.add(user)
    cu.success(f"Created user: {user.lower_username} (ID: {user.id})")
    session.flush()  # assign id
    return user


def get_or_create_managed_group(
    session: Session,
    app: str,
    group_name: str,
) -> DgManagedGroup:
    """
    Return an existing DgManagedGroup or create one based on (app, lower_group_name).
    """
    app = app.lower()
    lower_group_name = group_name.lower()

    group = (
        session.query(DgManagedGroup)
        .filter(DgManagedGroup.app == app)
        .filter(DgManagedGroup.lower_group_name == lower_group_name)
        .one_or_none()
    )

    if group:
        cu.success(f"Found managed group: {group.group_name} (ID: {group.id})")
        return group

    group = DgManagedGroup(
        app=app,
        group_name=group_name,
        lower_group_name=lower_group_name,
    )
    session.add(group)
    cu.success(f"Created managed group: {group.group_name} (ID: {group.id})")
    session.flush()
    return group


# ---------------------------------------------------------------------------
# GROUP_OWNER bulk sync (for group membership changes)
# ---------------------------------------------------------------------------


def sync_group_owners_for_delegated_group(
    app: str,
    delegated_group: str,
    owning_group_name: str,
    members: Iterable[Tuple[str, Optional[str]]],
) -> None:
    """
    Reconcile GROUP_OWNER rows for a (delegated group, owning group) pair against
    a current list of group members.

    This is the "membership drift" solution:
    - Jira/Confluence membership for owning_group_name may change over time.
      - We receive the *current* members list from upstream (Jira/Confluence).
    - We make the GROUP_OWNER rows match that list exactly.

    Arguments:
    app: 'jira' or 'confluence'
    delegated_group: name of the delegated group being owned
    owning_group_name: the group that grants ownership (stored in via_group_name)
      members: iterable of (username, email) for *current* members of owning_group_name

    Behavior:
    - Ensures all current members exist as DgUser.
    - Adds GROUP_OWNER rows for members not yet in dg_group_owner.
    - Removes GROUP_OWNER rows for users that are no longer in the members list.
    """
    app = app.lower()
    delegated_lower = delegated_group.lower()
    via_group_name = owning_group_name

    members = list(members)  # in case a generator is passed

    cu.header(f"Starting sync for delegated group: {delegated_group} (app: {app})")
    cu.info(f" Processing {len(members)} members for owning group: {owning_group_name}")

    with SessionLocal() as session:
        # 1) Ensure the delegated group exists
        group = get_or_create_managed_group(session, app, delegated_group)

        # 2) Ensure all member users exist and build desired mapping
        desired_user_ids: Set[int] = set()
        for username, email in members:
            user = get_or_create_user(session, username, email)
            desired_user_ids.add(user.id)

        # 3) Load existing GROUP_OWNER rows for this (group, via_group_name)
        existing_rows = (
            session.query(DgGroupOwner)
            .filter(DgGroupOwner.managed_group_id == group.id)
            .filter(DgGroupOwner.source_type == "GROUP_OWNER")
            .filter(DgGroupOwner.via_group_name == via_group_name)
            .all()
        )

        existing_user_ids: Set[int] = {row.user_id for row in existing_rows}

        # 4) Compute differences
        to_add_ids = desired_user_ids - existing_user_ids
        to_remove_ids = existing_user_ids - desired_user_ids

        # 5) Add missing GROUP_OWNER rows
        if to_add_ids:
            cu.info(f" Adding {len(to_add_ids)} new GROUP_OWNER rows")
            # We already have user objects in the session from get_or_create,
            # but to be safe we re-load them here.
            users_to_add = session.query(DgUser).filter(DgUser.id.in_(to_add_ids)).all()
            for user in users_to_add:
                session.add(
                    DgGroupOwner(
                        managed_group_id=group.id,
                        user_id=user.id,
                        source_type="GROUP_OWNER",
                        via_group_name=via_group_name,
                    )
                )
                cu.event(f" Added new GROUP_OWNER row for {user.lower_username}", level="INFO")

        # 6) Remove stale GROUP_OWNER rows
        if to_remove_ids:
            cu.info(f" Removing {len(to_remove_ids)} stale GROUP_OWNER rows")
            (
                session.query(DgGroupOwner)
                .filter(DgGroupOwner.managed_group_id == group.id)
                .filter(DgGroupOwner.source_type == "GROUP_OWNER")
                .filter(DgGroupOwner.via_group_name == via_group_name)
                .filter(DgGroupOwner.user_id.in_(to_remove_ids))
                .delete(synchronize_session=False)
            )
            cu.info(f" Removed GROUP_OWNER rows for ids: {to_remove_ids}")
        session.commit()
        cu.event(
            f"Completed sync for delegated group: [b]{delegated_group}[/b]",
            level="SUCCESS",
        )
        cu.spacer()
        cu.rule()

from typing import Iterable, Optional, Tuple, Callable
from sqlalchemy.orm import Session

from .psql_models import (
    SessionLocal,
    DgManagedGroup,
    DgGroupOwner,
    DgGroupOwnerGroup,  # NEW
)

# ... keep the rest of your file unchanged ...


def sync_all_group_owners(
    fetch_members_for_group: Callable[[str, str], Iterable[Tuple[str, Optional[str]]]],
) -> None:
    """
    Run GROUP_OWNER membership reconciliation for *every* delegated group that
    has configured owning-groups in dg_group_owner_group.
    """
    cu.header("Starting sync_all_group_owners job")

    with SessionLocal() as session:
        rows = (
            session.query(
                DgManagedGroup.app,
                DgManagedGroup.group_name,
                DgGroupOwnerGroup.owning_group_name,
            )
            .join(
                DgManagedGroup,
                DgManagedGroup.id == DgGroupOwnerGroup.managed_group_id,
            )
            .distinct()
            .all()
        )

        cu.info(f" Found {len(rows)} (delegated_group, owning_group) relationships to process")

    # Cache: (app, owning_group_lower) -> member list
    app_group_cache: dict[Tuple[str, str], list[Tuple[str, Optional[str]]]] = {}

    for app, delegated_group, owning_group_name in rows:
        if not owning_group_name:
            continue

        cache_key = (app.lower(), owning_group_name.lower())
        if cache_key not in app_group_cache:
            members = list(fetch_members_for_group(app, owning_group_name))
            app_group_cache[cache_key] = members
        else:
            members = app_group_cache[cache_key]
            cu.info(f" Using cached members for {app}/{owning_group_name}")

        sync_group_owners_for_delegated_group(
            app=app,
            delegated_group=delegated_group,
            owning_group_name=owning_group_name,
            members=members,
        )

    cu.event("Completed sync_all_group_owners job", level="SUCCESS")

