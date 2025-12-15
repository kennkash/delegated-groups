# ops-utilities/delegated-groups/database/psql_views.py

from sqlalchemy import Column, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from .psql_models import schema

BaseView = declarative_base()


class VwDelegatedGroupOwners(BaseView):
    """
    Effective owners view:
    - One row per effective owner of a delegated group (USER_OWNER or GROUP_OWNER members).
    - Backed by dg_group_owner joined to dg_managed_group + dg_user.
    """
    __tablename__ = "vw_delegated_group_owners"
    __table_args__ = {"schema": schema}

    app = Column(Text, primary_key=True)
    delegated_group = Column(Text, primary_key=True)
    delegated_group_lower = Column(Text)

    owner_username = Column(Text, primary_key=True)
    owner_email = Column(Text)

    owner_type = Column(Text, primary_key=True)      # USER_OWNER or GROUP_OWNER
    via_group_name = Column(Text, primary_key=True)  # may be null
    owner_created_at = Column(DateTime(timezone=True))


class VwDelegatedGroupOwnerGroups(BaseView):
    """
    Configured group-owner relationships view:
    - One row per (delegated_group, owning_group_name) relationship.
    - Backed by dg_group_owner_group joined to dg_managed_group.
    """
    __tablename__ = "vw_delegated_group_owner_groups"
    __table_args__ = {"schema": schema}

    app = Column(Text, primary_key=True)
    delegated_group = Column(Text, primary_key=True)
    delegated_group_lower = Column(Text)

    owning_group_name = Column(Text, primary_key=True)
    owning_group_lower = Column(Text)

    created_at = Column(DateTime(timezone=True))