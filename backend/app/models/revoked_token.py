"""
Revoked Token Model
===================
Tracks invalidated OAuth tokens for security
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base


class RevokedToken(Base):
    """Token revocation record - tracks invalidated OAuth tokens"""
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)

    social_account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    token_type = Column(String(20), nullable=False)  # 'access' or 'refresh'
    revoked_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    reason = Column(String(255), nullable=True)  # 'logout', 'reauth', 'compromise', etc.

    # Additional context about revocation (user agent, IP, etc.)
    metadata = Column(JSON, nullable=True)

    # Relationships
    social_account = relationship("SocialAccount")

    def __repr__(self):
        return f"<RevokedToken(social_account_id={self.social_account_id}, token_type={self.token_type}, reason={self.reason})>"
