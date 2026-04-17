"""
Admin Query Review Model
========================
Tracks operator review state for problematic queries or answers.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from ..database import Base


class AdminQueryReview(Base):
    """Operator review state linked to one chat message."""

    __tablename__ = "admin_query_reviews"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="open")  # open, resolved, ignored
    reason = Column(String(50), nullable=True)
    note = Column(Text, nullable=True)
    created_by_admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    message = relationship("ChatMessage", back_populates="admin_review")
    created_by_admin = relationship("User", foreign_keys=[created_by_admin_id])
    updated_by_admin = relationship("User", foreign_keys=[updated_by_admin_id])

    def __repr__(self) -> str:
        return f"<AdminQueryReview(message_id={self.message_id}, status={self.status})>"
