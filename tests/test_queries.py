from sqlalchemy import select
import database.psql_models as models
from database.psql_models import DgUser, DgManagedGroup, DgGroupOwner
from sqlalchemy import create_engine



def get_my_groups(username: str):
    with models.SessionLocal() as session:
        stmt = (
        select(
        DgManagedGroup.app,
        DgManagedGroup.group_name,
        DgGroupOwner.source_type,
        DgGroupOwner.via_group_name,
        )
        .join(DgGroupOwner, DgGroupOwner.managed_group_id == DgManagedGroup.id)
        .join(DgUser, DgUser.id == DgGroupOwner.user_id)
        .where(DgUser.lower_username == username.lower())
        .order_by(DgManagedGroup.app, DgManagedGroup.group_name)
        )
    return session.execute(stmt).all()


def get_group_owners(app: str, group_name: str):
    with models.SessionLocal() as session:
        stmt = (
        select(
        DgUser.username,
        DgUser.email,
        DgGroupOwner.source_type,
        DgGroupOwner.via_group_name,
        )
        .join(DgGroupOwner, DgGroupOwner.user_id == DgUser.id)
        .join(DgManagedGroup, DgManagedGroup.id == DgGroupOwner.managed_group_id)
        .where(DgManagedGroup.app == app.lower())
        .where(DgManagedGroup.lower_group_name == group_name.lower())
        .order_by(DgGroupOwner.source_type, DgGroupOwner.via_group_name, DgUser.username)
        )
    return session.execute(stmt).all()



def main():
    kennedy = get_my_groups("kkashmiry0641")
    
    print(kennedy)
    
    owners = get_group_owners(app="confluence", group_name="local_gcs_chemical")
    
    print(owners)
    
if __name__ == "__main__":
    main()
