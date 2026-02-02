from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    DateTime,
    ForeignKey,
    func,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB


class DgAuditLog(Base):
    __tablename__ = "dg_audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # who did it
    actor_username = Column(Text, nullable=False)
    actor_email = Column(Text)  # optional but useful

    # what happened
    action = Column(Text, nullable=False)  # e.g. ADD_USER_OWNER, DELETE_DELEGATED_GROUP
    status = Column(Text, nullable=False, server_default="SUCCESS")  # SUCCESS/FAILURE

    # where/what it affected
    app = Column(Text)  # jira/confluence (nullable for global actions)
    delegated_group_id = Column(
        BigInteger,
        ForeignKey("dg_managed_group.id", ondelete="SET NULL"),
        nullable=True,
    )
    delegated_group_name = Column(Text)  # store name for human readability even if group deleted

    # extra context
    details = Column(JSONB, nullable=False, server_default="{}")

    # request context (optional)
    request_id = Column(Text)
    ip = Column(Text)
    user_agent = Column(Text)


# Helpful indexes for querying audit trails
Index("ix_dg_audit_created_at", DgAuditLog.created_at)
Index("ix_dg_audit_actor_lower", func.lower(DgAuditLog.actor_username))
Index("ix_dg_audit_action", DgAuditLog.action)
Index("ix_dg_audit_group", DgAuditLog.delegated_group_id)
Index("ix_dg_audit_app", DgAuditLog.app)


from typing import Optional, Any, Dict
from sqlalchemy.orm import Session

def write_audit(
    db: Session,
    *,
    actor_username: str,
    actor_email: Optional[str],
    action: str,
    status: str = "SUCCESS",
    app: Optional[str] = None,
    delegated_group_id: Optional[int] = None,
    delegated_group_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    from ..models.psql_models import DgAuditLog  # adjust import path

    db.add(
        DgAuditLog(
            actor_username=actor_username,
            actor_email=actor_email,
            action=action,
            status=status,
            app=app,
            delegated_group_id=delegated_group_id,
            delegated_group_name=delegated_group_name,
            details=details or {},
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
        )
    )
    
    
write_audit(
            db,
            actor_username=actor_username,
            actor_email=actor_email,
            action="DELETE_DELEGATED_GROUP",
            status="SUCCESS",
            app=app,
            delegated_group_id=group.id,
            delegated_group_name=group.group_name,
            details={
                "input": req.model_dump(),
                "deleted_owner_rows": deleted_owner_rows,
                "deleted_group_owner_rules": deleted_group_owner_rules,
            },
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )