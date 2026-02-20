# atlassian-db/db-main.py

def get_delegated_groups(app: str) -> pd.DataFrame:
    """
    DB-backed replacement for the old add-on getAll endpoint.

    Returns a DF with:
      - <column>_group : original group name (canonical)
      - group_lowercase
    """
    if app == "confluence":
        column = "conf"
    else:
        column = "jira"

    # pull from delegated groups DB
    rows = (
        session.query(DgManagedGroup.group_name, DgManagedGroup.lower_group_name)
        .filter(DgManagedGroup.app == app.lower())
        .all()
    )

    delegated_groups_dict = {lower: name for (name, lower) in rows}

    df = pd.DataFrame(list(delegated_groups_dict.items()), columns=["group_lowercase", f"{column}_group"])
    df = df[[f"{column}_group", "group_lowercase"]]
    return df

# atlassian-db/db-main.py

def prune_delegated_groups_db(app: str, existing_group_names: pd.Series) -> int:
    """
    Delete delegated-groups DB rows for groups that no longer exist in Jira/Confluence.

    Parameters
    ----------
    app : 'jira' or 'confluence'
    existing_group_names : pandas Series of canonical names from ScriptRunner pull (groups['<column>_group'])

    Returns
    -------
    int : number of managed groups deleted
    """
    app_lower = app.lower()
    existing_lower = set(existing_group_names.astype(str).str.lower().tolist())

    # Find managed groups that are NOT in the external group list
    stale = (
        session.query(DgManagedGroup)
        .filter(DgManagedGroup.app == app_lower)
        .filter(~DgManagedGroup.lower_group_name.in_(existing_lower))
        .all()
    )

    if not stale:
        return 0

    stale_ids = [g.id for g in stale]
    stale_names = [g.group_name for g in stale]
    print(f"[{app}] Deleting stale delegated managed groups: {stale_names}")

    # IMPORTANT: delete children first unless you have DB-level cascade
    session.query(DgGroupOwner).filter(DgGroupOwner.managed_group_id.in_(stale_ids)).delete(synchronize_session=False)
    session.query(DgGroupOwnerGroup).filter(DgGroupOwnerGroup.managed_group_id.in_(stale_ids)).delete(synchronize_session=False)

    # Now delete the managed groups
    session.query(DgManagedGroup).filter(DgManagedGroup.id.in_(stale_ids)).delete(synchronize_session=False)

    session.commit()
    return len(stale_ids)

def get_groups(app):
    if app == "confluence":
        column = "conf"
    else:
        column = "jira"

    groups = group_count(app)

    # NEW: prune delegated-groups DB against current real groups
    deleted = prune_delegated_groups_db(app, groups[f"{column}_group"])
    print(f"deleted stale delegated groups from delegated-groups DB ({app}): ", deleted)

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


# atlassian-db/models.py
# Add these below your existing models

class DgManagedGroup(Base):
    __tablename__ = "dg_managed_group"  # <-- CHANGE to your real table name
    id = db.Column(db.Integer, primary_key=True)
    app = db.Column(db.String(), nullable=False)  # 'jira' or 'confluence'
    group_name = db.Column(db.String(), nullable=False)
    lower_group_name = db.Column(db.String(), nullable=False, index=True)

class DgGroupOwner(Base):
    __tablename__ = "dg_group_owner"  # <-- CHANGE to your real table name
    id = db.Column(db.Integer, primary_key=True)
    managed_group_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=True)
    source_type = db.Column(db.String(), nullable=False)  # 'USER_OWNER' etc.

class DgGroupOwnerGroup(Base):
    __tablename__ = "dg_group_owner_group"  # <-- CHANGE to your real table name
    id = db.Column(db.Integer, primary_key=True)
    managed_group_id = db.Column(db.Integer, nullable=False, index=True)
    owning_group_name = db.Column(db.String(), nullable=False)
    lower_owning_group_name = db.Column(db.String(), nullable=False, index=True)

rows_to_delete = session.query(table).filter(~table.name.in_(final_df["name"].tolist()))

