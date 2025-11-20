import database.psql_models as models
from database.psql_models import DgUser, DgManagedGroup, DgGroupOwner
from prettiprint import ConsoleUtils
import csv
from collections import OrderedDict


cu = ConsoleUtils(theme="dark", verbosity=2)

CSV_PATH_JIRA = "/mnt/k.kashmiry/zdrive/effective_owners_jira.csv"
CSV_PATH_CONF = "/mnt/k.kashmiry/zdrive/effective_owners_conf.csv"


def read_csv_rows(path: str):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["app"] = row["app"].lower()
            row["delegation_id"] = int(row["delegation_id"])
            row["group_name"] = row["group_name"]
            row["lower_group_name"] = row["lower_group_name"].lower()
            row["user_key"] = row["user_key"]
            row["user_name"] = row["user_name"]
            row["email_address"] = row["email_address"] or None
            row["source_type"] = row["source_type"]
            row["via_group_name"] = row["via_group_name"] or None
            rows.append(row)
    return rows


def main():
    rows = read_csv_rows(CSV_PATH_JIRA)

    # Build unique users and groups
    unique_users = OrderedDict()
    unique_groups = OrderedDict()

    for r in rows:
        # Unique users
        if r["user_key"] not in unique_users:
            unique_users[r["user_key"]] = {
            "username": r["user_name"],
            "email": r["email_address"],
            }

        # Unique groups by (app, lower_group_name)
        gkey = (r["app"], r["lower_group_name"])
        if gkey not in unique_groups:
            unique_groups[gkey] = {
            "delegation_id": r["delegation_id"],
            "group_name": r["group_name"],
            }

    session = models.SessionLocal()
    try:

        # Insert users
        user_objs = {}
        for user_key, data in unique_users.items():
            u = DgUser(
            user_key=user_key,
            username=data["username"],
            email=data["email"],
            lower_username=data["username"].lower(),
            lower_email=data["email"].lower() if data["email"] else None,
            )
            session.add(u)
            user_objs[user_key] = u

        # Insert groups
        group_objs = {}
        for (app, lower_group_name), data in unique_groups.items():
            g = DgManagedGroup(
            app=app,
            group_name=data["group_name"],
            lower_group_name=lower_group_name,
            delegation_id=data["delegation_id"],
            )
            session.add(g)
            group_objs[(app, lower_group_name)] = g

        session.flush() # populate IDs

        # Insert ownership rows
        seen = set()
        owner_objs = []

        for r in rows:
            g = group_objs[(r["app"], r["lower_group_name"])]
            u = user_objs[r["user_key"]]

            key = (g.id, u.id, r["source_type"], r["via_group_name"])
            if key in seen:
                continue
            seen.add(key)

            o = DgGroupOwner(
            managed_group_id=g.id,
            user_id=u.id,
            source_type=r["source_type"],
            via_group_name=r["via_group_name"],
            )
            owner_objs.append(o)

        session.add_all(owner_objs)
        session.commit()

        print(
        f"Imported {len(unique_users)} users, "
        f"{len(unique_groups)} groups, "
        f"{len(owner_objs)} ownership rows."

        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
