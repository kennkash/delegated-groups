def get_delegated_groups(app: str) -> pd.DataFrame:
    if app == "confluence":
        column = "conf"
    else:
        column = "jira"

    rows = (
        session.query(DgManagedGroup.group_name, DgManagedGroup.lower_group_name)
        .filter(DgManagedGroup.app == app.lower())
        .all()
    )

    # { lower: canonical }
    delegated_groups_dict = {lower: name for (name, lower) in rows}

    df = pd.DataFrame(
        list(delegated_groups_dict.items()),
        columns=["group_lowercase", f"{column}_group"],
    )

    return df[[f"{column}_group", "group_lowercase"]]

def prune_delegated_groups_db(app: str, existing_group_names: pd.Series) -> int:
    app_lower = app.lower()
    existing_lower = set(existing_group_names.astype(str).str.lower().tolist())

    stale_groups = (
        session.query(DgManagedGroup)
        .filter(DgManagedGroup.app == app_lower)
        .filter(~DgManagedGroup.lower_group_name.in_(existing_lower))
        .all()
    )

    if not stale_groups:
        return 0

    stale_names = [g.group_name for g in stale_groups]
    stale_ids = [g.id for g in stale_groups]
    print(f"[{app}] Deleting stale delegated groups: {stale_names}")

    # With ON DELETE CASCADE, deleting DgManagedGroup is enough.
    session.query(DgManagedGroup).filter(DgManagedGroup.id.in_(stale_ids)).delete(synchronize_session=False)
    session.commit()
    return len(stale_ids)
def get_groups(app):
    if app == "confluence":
        column = "conf"
    else:
        column = "jira"

    groups = group_count(app)

    deleted = prune_delegated_groups_db(app, groups[f"{column}_group"])
    print(f"deleted stale delegated groups from delegated-groups DB ({app}): {deleted}")

    delegated = get_delegated_groups(app)

    merged_df = pd.merge(groups, delegated, left_on=f"{column}_group", right_on="group_lowercase", how="left")

    merged_df["delegated"] = merged_df[f"{column}_group_y"].notna()
    merged_df["del_group"] = merged_df[f"{column}_group_y"]

    merged_df.drop(columns=["group_lowercase", f"{column}_group_y"], inplace=True)
    merged_df.rename(columns={f"{column}_group_x": "name"}, inplace=True)

    rows_added, new_count, update_count, delete_count = add_data_to_table(merged_df, app)
    print(rows_added)
    print(f"new rows added to {app}Groups: ", new_count)
    print(f"updated rows in {app}Groups: ", update_count)
    print(f"deleted rows in {app}Groups: ", delete_count)


