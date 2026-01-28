@router.get("/groups/all-with-owners")
async def get_all_groups_with_owners(db: Session = Depends(get_db)):
    groups = (
        db.query(
            DgManagedGroup.id,
            DgManagedGroup.app,
            DgManagedGroup.group_name,
            DgManagedGroup.lower_group_name,
        )
        .order_by(DgManagedGroup.app, DgManagedGroup.lower_group_name)
        .all()
    )
    if not groups:
        return []

    group_ids = [g.id for g in groups]

    user_owner_rows = (
        db.query(
            DgGroupOwner.managed_group_id,
            DgUser.username,
            DgUser.email,
        )
        .join(DgUser, DgUser.id == DgGroupOwner.user_id)
        .filter(DgGroupOwner.managed_group_id.in_(group_ids))
        .filter(DgGroupOwner.source_type == "USER_OWNER")
        .order_by(DgGroupOwner.managed_group_id, DgUser.lower_username)
        .all()
    )

    group_owner_rows = (
        db.query(
            DgGroupOwnerGroup.managed_group_id,
            DgGroupOwnerGroup.owning_group_name,
        )
        .filter(DgGroupOwnerGroup.managed_group_id.in_(group_ids))
        .order_by(DgGroupOwnerGroup.managed_group_id, DgGroupOwnerGroup.lower_owning_group_name)
        .all()
    )

    owners_by_group: dict[int, list[dict]] = {gid: [] for gid in group_ids}

    for managed_group_id, username, email in user_owner_rows:
        owners_by_group[managed_group_id].append(
            {"type": "USER_OWNER", "label": username, "email": email}
        )

    for managed_group_id, owning_group_name in group_owner_rows:
        owners_by_group[managed_group_id].append(
            {"type": "GROUP_OWNER", "label": owning_group_name}
        )

    return [
        {
            "app": app,
            "group_name": group_name,
            "lower_group_name": lower_group_name,
            "owners": owners_by_group.get(gid, []),
        }
        for (gid, app, group_name, lower_group_name) in groups
    ]