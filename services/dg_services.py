# delegated-groups/services/dg_service.py

from __future__ import annotations

from typing import Iterable, Optional, Tuple, Dict, Set

from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..database.psql_models import (
    SessionLocal,
    DgUser,
    DgManagedGroup,
    DgGroupOwner,
)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _normalize_identity(username: str, email: Optional[str]) -> Tuple[str, Optional[str]]:
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
        return user

    user = DgUser(
        username=username,
        email=email,
        lower_username=lower_username,
        lower_email=lower_email,
    )
    session.add(user)
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
        return group

    group = DgManagedGroup(
        app=app,
        group_name=group_name,
        lower_group_name=lower_group_name,
    )
    session.add(group)
    session.flush()
    return group


# ---------------------------------------------------------------------------
# USER_OWNER operations
# ---------------------------------------------------------------------------

def add_user_owner(
    app: str,
    delegated_group: str,
    owner_username: str,
    owner_email: Optional[str] = None,
) -> None:
    """
    Mark a user as a direct USER_OWNER of a delegated group.

    - Ensures the delegated group exists in dg_managed_group.
    - Ensures the user exists in dg_user.
    - Inserts a DgGroupOwner row with:
        source_type = 'USER_OWNER'
        via_group_name = NULL
    """
    with SessionLocal() as session:
        group = get_or_create_managed_group(session, app, delegated_group)
        user = get_or_create_user(session, owner_username, owner_email)

        existing = (
            session.query(DgGroupOwner)
            .filter(DgGroupOwner.managed_group_id == group.id)
            .filter(DgGroupOwner.user_id == user.id)
            .filter(DgGroupOwner.source_type == "USER_OWNER")
            .filter(DgGroupOwner.via_group_name.is_(None))
            .one_or_none()
        )

        if existing:
            # Already a USER_OWNER; nothing to do
            return

        owner_row = DgGroupOwner(
            managed_group_id=group.id,
            user_id=user.id,
            source_type="USER_OWNER",
            via_group_name=None,
        )
        session.add(owner_row)
        session.commit()


def remove_user_owner(
    app: str,
    delegated_group: str,
    owner_username: str,
) -> None:
    """
    Remove a user's direct USER_OWNER relationship for a delegated group.

    Deletes all DgGroupOwner rows matching:
      app, delegated_group, username, source_type='USER_OWNER', via_group_name IS NULL.
    """
    app = app.lower()
    lower_group = delegated_group.lower()
    lower_username = owner_username.lower()

    with SessionLocal() as session:
        q = (
            session.query(DgGroupOwner)
            .join(DgManagedGroup, DgManagedGroup.id == DgGroupOwner.managed_group_id)
            .join(DgUser, DgUser.id == DgGroupOwner.user_id)
            .filter(DgManagedGroup.app == app)
            .filter(DgManagedGroup.lower_group_name == lower_group)
            .filter(DgUser.lower_username == lower_username)
            .filter(DgGroupOwner.source_type == "USER_OWNER")
            .filter(DgGroupOwner.via_group_name.is_(None))
        )

        q.delete(synchronize_session=False)
        session.commit()


# ---------------------------------------------------------------------------
# GROUP_OWNER operations (per-user)
# ---------------------------------------------------------------------------

def add_group_owner_for_user(
    app: str,
    delegated_group: str,
    via_group_name: str,
    owner_username: str,
    owner_email: Optional[str] = None,
) -> None:
    """
    Mark a user as a GROUP_OWNER of a delegated group, via via_group_name.

    This represents:
      "user X is an owner of delegated_group because they are in via_group_name".
    """
    with SessionLocal() as session:
        group = get_or_create_managed_group(session, app, delegated_group)
        user = get_or_create_user(session, owner_username, owner_email)

        existing = (
            session.query(DgGroupOwner)
            .filter(DgGroupOwner.managed_group_id == group.id)
            .filter(DgGroupOwner.user_id == user.id)
            .filter(DgGroupOwner.source_type == "GROUP_OWNER")
            .filter(DgGroupOwner.via_group_name == via_group_name)
            .one_or_none()
        )

        if existing:
            # Already a GROUP_OWNER via this group; nothing to do
            return

        owner_row = DgGroupOwner(
            managed_group_id=group.id,
            user_id=user.id,
            source_type="GROUP_OWNER",
            via_group_name=via_group_name,
        )
        session.add(owner_row)
        session.commit()


def remove_group_owner(
    app: str,
    delegated_group: str,
    via_group_name: str,
) -> None:
    """
    Remove a GROUP_OWNER relationship for a delegated group *as a whole*.

    This represents:
      "Group `via_group_name` is no longer an owner of `delegated_group` in `app`."

    Behavior:
      - Deletes ALL DgGroupOwner rows where:
          app == app
          delegated_group == delegated_group
          source_type == 'GROUP_OWNER'
          via_group_name == via_group_name

    If you want to reflect membership changes within an owning group
    (add/remove a single person while the group still owns the delegated group),
    use sync_group_owners_for_delegated_group() instead.
    """
    app = app.lower()
    lower_group = delegated_group.lower()

    with SessionLocal() as session:
        (
            session.query(DgGroupOwner)
            .join(DgManagedGroup, DgManagedGroup.id == DgGroupOwner.managed_group_id)
            .filter(DgManagedGroup.app == app)
            .filter(DgManagedGroup.lower_group_name == lower_group)
            .filter(DgGroupOwner.source_type == "GROUP_OWNER")
            .filter(DgGroupOwner.via_group_name == via_group_name)
            .delete(synchronize_session=False)
        )
        session.commit()

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
            # We already have user objects in the session from get_or_create,
            # but to be safe we re-load them here.
            users_to_add = (
                session.query(DgUser)
                .filter(DgUser.id.in_(to_add_ids))
                .all()
            )
            for user in users_to_add:
                session.add(
                    DgGroupOwner(
                        managed_group_id=group.id,
                        user_id=user.id,
                        source_type="GROUP_OWNER",
                        via_group_name=via_group_name,
                    )
                )

        # 6) Remove stale GROUP_OWNER rows
        if to_remove_ids:
            (
                session.query(DgGroupOwner)
                .filter(DgGroupOwner.managed_group_id == group.id)
                .filter(DgGroupOwner.source_type == "GROUP_OWNER")
                .filter(DgGroupOwner.via_group_name == via_group_name)
                .filter(DgGroupOwner.user_id.in_(to_remove_ids))
                .delete(synchronize_session=False)
            )

        session.commit()


# ---------------------------------------------------------------------------
# Convenience: create a new delegated group with its owners
# ---------------------------------------------------------------------------

def create_group_with_owners(
    app: str,
    group_name: str,
    user_owners: Iterable[Tuple[str, Optional[str]]] = (),
    group_owners: Iterable[Tuple[str, Iterable[Tuple[str, Optional[str]]]]] = (),
) -> None:
    """
    Create a new delegated group (if not exists) and attach USER_OWNERs
    and GROUP_OWNERs.

    Arguments:
      app: 'jira' or 'confluence'
      group_name: the delegated group being managed
      user_owners: iterable of (username, email) for direct USER_OWNERs
      group_owners: iterable of:
          (owning_group_name, [(username, email), ...])

    This is essentially the "new group + all owners" flow.
    """
    with SessionLocal() as session:
        group = get_or_create_managed_group(session, app, group_name)

        # USER_OWNERs
        for username, email in user_owners:
            user = get_or_create_user(session, username, email)

            exists = (
                session.query(DgGroupOwner)
                .filter(DgGroupOwner.managed_group_id == group.id)
                .filter(DgGroupOwner.user_id == user.id)
                .filter(DgGroupOwner.source_type == "USER_OWNER")
                .filter(DgGroupOwner.via_group_name.is_(None))
                .one_or_none()
            )
            if not exists:
                session.add(
                    DgGroupOwner(
                        managed_group_id=group.id,
                        user_id=user.id,
                        source_type="USER_OWNER",
                        via_group_name=None,
                    )
                )

        # GROUP_OWNERs (flattened per user)
        for owning_group_name, members in group_owners:
            via_group_name = owning_group_name
            for username, email in members:
                user = get_or_create_user(session, username, email)

                exists = (
                    session.query(DgGroupOwner)
                    .filter(DgGroupOwner.managed_group_id == group.id)
                    .filter(DgGroupOwner.user_id == user.id)
                    .filter(DgGroupOwner.source_type == "GROUP_OWNER")
                    .filter(DgGroupOwner.via_group_name == via_group_name)
                    .one_or_none()
                )
                if not exists:
                    session.add(
                        DgGroupOwner(
                            managed_group_id=group.id,
                            user_id=user.id,
                            source_type="GROUP_OWNER",
                            via_group_name=via_group_name,
                        )
                    )

        session.commit()
        
        
        
from typing import Callable, Iterable, Tuple, Optional


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
            .distinct()
            .all()
        )

    # Step 2: loop over each combo and reconcile membership
    for app, delegated_group, via_group_name in rows:
        if not via_group_name:
            # Shouldn't happen because of filter, but be safe
            continue

        # You implement this in your scheduled script
        members = list(fetch_members_for_group(app, via_group_name))

        # Re-use the existing sync logic for that one pair
        sync_group_owners_for_delegated_group(
            app=app,
            delegated_group=delegated_group,
            owning_group_name=via_group_name,
            members=members,
        )