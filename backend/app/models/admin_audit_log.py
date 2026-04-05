"""
Admin Audit Log Model
=====================
Tracks admin actions for accountability and change history.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from ..database import Base


class AdminAuditLog(Base):
    """Admin action log entry."""
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    action = Column(String(100), nullable=False)  # e.g., "user.update"
    target_type = Column(String(50), nullable=False)  # e.g., "user"
    target_id = Column(String(100), nullable=True)

    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    context = Column(JSON, nullable=True)

    ip_hash = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    admin_user = relationship("User")

    def __repr__(self) -> str:
        return f"<AdminAuditLog(id={self.id}, action={self.action}, admin_user_id={self.admin_user_id})>"
