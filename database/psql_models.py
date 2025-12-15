# ops-utilities/delegated-groups/database/psql_models.py

from sqlalchemy import (
    create_engine,
    MetaData,
    Column,
    BigInteger,
    Text,
    DateTime,
    UniqueConstraint,
    ForeignKey,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from ..services.credentials.tokens import AtlassianToken

# creating connection to postegresql db
app = "psql-dev"
password = AtlassianToken(app).getCreds()
db_name = "AtlassianCloud"
user = "atlassian-bot.dev"
schema = "atlassian-admin.dev"

engine = create_engine(
    f"postgresql+psycopg2://{user}:{password}"
    "@psqldb-k-kashmiryclust-kkashmiry0641.dbuser:5432/"
    f"{db_name}"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base(metadata=MetaData(schema=schema))


class DgUser(Base):
    __tablename__ = "dg_user"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    username = Column(Text, nullable=False)
    email = Column(Text)
    lower_username = Column(Text, nullable=False)
    lower_email = Column(Text)

    __table_args__ = (
        UniqueConstraint(
            "lower_username",
            "lower_email",
            name="uq_user_identity",
        ),
    )

    owners = relationship("DgGroupOwner", back_populates="user")


class DgManagedGroup(Base):
    __tablename__ = "dg_managed_group"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    app = Column(Text, nullable=False)  # 'jira' or 'confluence'
    group_name = Column(Text, nullable=False)
    lower_group_name = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("app", "lower_group_name", name="uq_app_group"),
    )

    owners = relationship("DgGroupOwner", back_populates="managed_group")
    owner_groups = relationship("DgGroupOwnerGroup", back_populates="managed_group")


class DgGroupOwner(Base):
    __tablename__ = "dg_group_owner"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    managed_group_id = Column(
        BigInteger,
        ForeignKey("dg_managed_group.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        BigInteger,
        ForeignKey("dg_user.id", ondelete="CASCADE"),
        nullable=False,
    )

    source_type = Column(Text, nullable=False)  # USER_OWNER or GROUP_OWNER
    via_group_name = Column(Text)  # only for group owners (membership-expanded)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "managed_group_id",
            "user_id",
            "source_type",
            "via_group_name",
            name="uq_owner_row",
        ),
    )

    managed_group = relationship("DgManagedGroup", back_populates="owners")
    user = relationship("DgUser", back_populates="owners")


class DgGroupOwnerGroup(Base):
    """
    Stores the configured "group owners" for a delegated group.
    This does NOT expand members. The scheduled refresh job uses these rows
    to sync membership-expanded GROUP_OWNER rows in dg_group_owner.
    """
    __tablename__ = "dg_group_owner_group"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    managed_group_id = Column(
        BigInteger,
        ForeignKey("dg_managed_group.id", ondelete="CASCADE"),
        nullable=False,
    )

    owning_group_name = Column(Text, nullable=False)
    lower_owning_group_name = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "managed_group_id",
            "lower_owning_group_name",
            name="uq_owner_group_row",
        ),
    )

    managed_group = relationship("DgManagedGroup", back_populates="owner_groups")


# following line will create Base classes as tables, if they already exist nothing changes
Base.metadata.create_all(bind=engine)