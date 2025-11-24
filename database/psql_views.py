# ops-utilities/delegated-groups/database/psql_views.py

from sqlalchemy import Column, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from .psql_models import schema

BaseView = declarative_base()


class VwDelegatedGroupOwners(BaseView):
    """
    ORM mapping for the vw_delegated_group_owners view.

    This is read-only and not part of the main Base metadata,
    so it will never be created as a physical table.
    """

    __tablename__ = "vw_delegated_group_owners"
    __table_args__ = {"schema": schema}

    # Columns from the view definition
    app = Column(Text, primary_key=True)  # 'jira' or 'confluence'
    delegated_group = Column(Text, primary_key=True)
    delegated_group_lower = Column(Text)

    owner_username = Column(Text, primary_key=True)
    owner_email = Column(Text)

    owner_type = Column(Text, primary_key=True)      # USER_OWNER or GROUP_OWNER
    via_group_name = Column(Text, primary_key=True)  # group that grants ownership; may be null in DB
    owner_created_at = Column(DateTime(timezone=True))