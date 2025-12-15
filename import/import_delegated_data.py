# ops-utilities/delegated-groups/import/import_delegated_data.py

from collections import OrderedDict
import csv

from sqlalchemy import text

from ..database import psql_models as models
from ..database.psql_models import DgUser, DgManagedGroup, DgGroupOwner, schema
from prettiprint import ConsoleUtils

cu = ConsoleUtils(theme="dark", verbosity=2)

CSV_PATH_JIRA = "/mnt/k.kashmiry/zdrive/effective_owners_jira.csv"
CSV_PATH_CONF = "/mnt/k.kashmiry/zdrive/effective_owners_conf.csv"


def read_csv_rows(path: str):
    """
    Read a CSV C file and normalize column values.

    Expected columns:
    app, group_name, lower_group_name,
    user_name, email_address, source_type, via_group_name
    """
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cu.info(f" Reading {path} with columns: {reader.fieldnames}")

        for row in reader:
            rows.append(
                {
                    "app": row["app"].lower(),
                    "group_name": row["group_name"],
                    "lower_group_name": row["lower_group_name"].lower(),
                    "user_name": row["user_name"],
                    "email_address": row.get("email_address") or None,
                    "source_type": row["source_type"],
                    "via_group_name": row.get("via_group_name") or None,
                }
            )
    cu.success(f"Loaded {len(rows)} rows from {path}")
    return rows


def create_or_replace_view(engine, schema):
    """
    Drops any existing table/view named vw_delegated_group_owners and
    creates the correct view definition.
    """
    VIEW_SQL = f"""
    CREATE OR REPLACE VIEW "{schema}".vw_delegated_group_owners AS
    SELECT
        mg.app                              AS app,
        mg.group_name                       AS delegated_group,
        mg.lower_group_name                 AS delegated_group_lower,

        u.username                          AS owner_username,
        u.email                             AS owner_email,

        go.source_type                      AS owner_type,
        go.via_group_name                   AS via_group_name,
        go.created_at                       AS owner_created_at

    FROM "{schema}".dg_group_owner AS go
    JOIN "{schema}".dg_managed_group AS mg
        ON mg.id = go.managed_group_id
    JOIN "{schema}".dg_user AS u
        ON u.id = go.user_id;
    """

    with engine.begin() as conn:
        cu.warning(
            ' Dropping any TABLE named vw_delegated_group_owners (if exists)...'
        )
        conn.execute(
            text(
                'DROP TABLE IF EXISTS "{schema}".vw_delegated_group_owners CASCADE;'
            )
        )
        cu.warning(' Dropping any VIEW named vw_delegated_group_owners (if exists)...')
        conn.execute(
            text(
                'DROP VIEW IF EXISTS "{schema}".vw_delegated_group_owners CASCADE;'
            )
        )
        cu.info(" Creating view vw_delegated_group_owners...")
        conn.execute(text(VIEW_SQL))

    cu.success('View "vw_delegated_group_owners" recreated successfully.')


def import_all():
    """
    Imports Jira and Confluence CSVs into the PostgreSQL tables and recreates the view.
    """

    # 1) Load all rows from both CSVs
    all_rows = []
    for path in (CSV_PATH_JIRA, CSV_PATH_CONF):
        all_rows.extend(read_csv_rows(path))

    cu.info(f" Total combined rows from Jira + Confluence: {len(all_rows)}")

    # 2) Build unique users (by identity) and unique groups (by app+lower_group_name)
    unique_users: OrderedDict[tuple, dict] = OrderedDict()   # (lower_username, lower_email_or_blank)
    unique_groups: OrderedDict[tuple, dict] = OrderedDict()  # (app, lower_group_name)

    for r in all_rows:
        lower_username = r["user_name"].lower()
        lower_email = (r["email_address"] or "").lower()
        identity = (lower_username, lower_email)

        if identity not in unique_users:
            unique_users[identity] = {
                "username": r["user_name"],
                "email": r["email_address"],
            }

        gkey = (r["app"], r["lower_group_name"])
        if gkey not in unique_groups:
            unique_groups[gkey] = {
                "group_name": r["group_name"],
            }

    cu.info(f" Unique users (by identity): {len(unique_users)}")
    cu.info(f" Unique groups: {len(unique_groups)}")

    session = models.SessionLocal()
    try:
        # 3) Insert / get users, deduped by identity
        user_objs: dict[tuple, DgUser] = {}  # identity -> DgUser

        # Preload existing users from DB
        existing_users = session.query(DgUser).all()
        for u in existing_users:
            identity = (u.lower_username, (u.lower_email or "").lower())
            user_objs[identity] = u

        new_users = 0
        for identity, data in unique_users.items():
            if identity in user_objs:
                continue

            username = data["username"]
            email = data["email"]

            user = DgUser(
                username=username,
                email=email,
                lower_username=username.lower(),
                lower_email=email.lower() if email else None,
            )
            session.add(user)
            user_objs[identity] = user
            new_users += 1

        cu.info(f" New users inserted: {new_users}")

        # 4) Insert / get groups (by app, lower_group_name)
        group_objs: dict[tuple, DgManagedGroup] = {}  # (app, lower_group_name) -> DgManagedGroup

        # Preload existing groups
        for g in session.query(DgManagedGroup).all():
            group_objs[(g.app, g.lower_group_name)] = g

        new_groups = 0
        for (app, lower_group_name), data in unique_groups.items():
            if (app, lower_group_name) in group_objs:
                continue

            g = DgManagedGroup(
                app=app,
                group_name=data["group_name"],
                lower_group_name=lower_group_name,
            )
            session.add(g)
            group_objs[(app, lower_group_name)] = g
            new_groups += 1

        cu.info(f" New groups inserted: {new_groups}")

        session.flush()  # populate IDs for new rows

        # 5) Insert ownership rows, deduped across all rows
        seen_owner_keys = set(
            session.query(
                DgGroupOwner.managed_group_id,
                DgGroupOwner.user_id,
                DgGroupOwner.source_type,
                DgGroupOwner.via_group_name,
            ).all()
        )

        owner_objs: list[DgGroupOwner] = []

        for r in all_rows:
            g = group_objs[(r["app"], r["lower_group_name"])]

            lower_username = r["user_name"].lower()
            lower_email = (r["email_address"] or "").lower()
            identity = (lower_username, lower_email)
            user = user_objs[identity]

            key = (g.id, user.id, r["source_type"], r["via_group_name"])
            if key in seen_owner_keys:
                continue
            seen_owner_keys.add(key)

            owner_objs.append(
                DgGroupOwner(
                    managed_group_id=g.id,
                    user_id=user.id,
                    source_type=r["source_type"],
                    via_group_name=r["via_group_name"],
                )
            )

        cu.info(f" New ownership rows to insert: {len(owner_objs)}")
        session.add_all(owner_objs)
        session.commit()
        cu.success(
            f"Import complete. Total users: {len(user_objs)}, "
            f"total groups: {len(group_objs)}, "
            f"total ownership keys: {len(seen_owner_keys)}"
        )

        # 6) (Re)create the view
        create_or_replace_view(models.engine, schema)

    finally:
        session.close()


if __name__ == "__main__":
    import_all()
