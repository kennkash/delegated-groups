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


def sync_all_group_owners(
    fetch_members_for_group: Callable[[str, str], Iterable[Tuple[str, Optional[str]]]],
) -> None:
    """
    Run GROUP_OWNER membership reconciliation for *every* delegated group that
    currently has GROUP_OWNER rows.

    This is intended to be called from a scheduled job.

    Arguments:
    fetch_members_for_group(app, owning_group_name) -> iterable of (username, email)
        - app: 'jira' or 'confluence'
        - owning_group_name: the group stored in via_group_name
        - returns the CURRENT members of that group in the source system
        (Jira/Confluence), as (username, email) tuples.

    Behavior:
    1. Query dg_group_owner + dg_managed_group for all distinct
        (app, delegated_group, via_group_name) where source_type='GROUP_OWNER'.
    2. For each (app, delegated_group, via_group_name):
        - call fetch_members_for_group(app, via_group_name)
        - call sync_group_owners_for_delegated_group(...) with that member list.
    """
    cu.header("Starting sync_all_group_owners job")
    # Step 1: collect all unique (app, delegated_group, via_group_name) combos
    with SessionLocal() as session:
        rows = (
            session.query(
                DgManagedGroup.app,
                DgManagedGroup.group_name,
                DgGroupOwner.via_group_name,
            )
            .join(
                DgManagedGroup,
                DgManagedGroup.id == DgGroupOwner.managed_group_id,
            )
            .filter(DgGroupOwner.source_type == "GROUP_OWNER")
            .filter(DgGroupOwner.via_group_name.isnot(None))
            # .filter(
            #     DgGroupOwner.via_group_name.in_(
            #         ["jira-administrators", "confluence-administrators"]
            #     )
            # )
            .distinct()
            .all()
        )
        cu.info(f" Found {len(rows)} delegated groups to process")

    # Step 2: Optimize by caching members for each (app, via_group_name) combo
    # to avoid redundant API calls
    app_group_cache: dict[Tuple[str, str], list[Tuple[str, Optional[str]]]] = {}

    # Step 3: loop over each combo and reconcile membership
    for app, delegated_group, via_group_name in rows:
        if not via_group_name:
            # Shouldn't happen because of filter, but be safe
            continue

        # Check if we already fetched members for this app/via_group_name combo
        cache_key = (app.lower(), via_group_name.lower())
        if cache_key not in app_group_cache:
            # Fetch and cache the members
            members = list(fetch_members_for_group(app, via_group_name))
            app_group_cache[cache_key] = members
            # cu.info(f" Fetched {len(members)} members for {app}/{via_group_name}")
        else:
            # Use cached members
            members = app_group_cache[cache_key]
            cu.spacer()
            cu.info(f" Using cached members for {app}/{via_group_name}")

        # cu.info(f" Processing group: {delegated_group} (app: {app}, via: {via_group_name})")

        # Re-use the existing sync logic for that one pair
        sync_group_owners_for_delegated_group(
            app=app,
            delegated_group=delegated_group,
            owning_group_name=via_group_name,
            members=members,
        )

    cu.event("Completed sync_all_group_owners job", level="SUCCESS")
