"""
User Model
==========
사용자 프로필 관리

Migration Note:
- provider, social_id columns are deprecated
- Use social_accounts table for OAuth provider data
- These columns kept temporarily for backwards compatibility during migration
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base


class User(Base):
    """사용자 프로필 - 핵심 계정 정보"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)  # May be NULL for some providers
    nickname = Column(String(100), nullable=False)
    profile_img = Column(String(500), nullable=True)

    # Role & Status
    role = Column(String(20), default='user')  # 'user', 'admin', 'beta'
    is_active = Column(Boolean, default=True)

    # Quota (can be overridden per user for special cases)
    daily_chat_limit = Column(Integer, default=20)  # Default for registered users

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # ========================================
    # DEPRECATED - Keep for migration period
    # These will be removed after data migration to social_accounts
    # ========================================
    provider = Column(String(20), nullable=True)  # DEPRECATED: Use social_accounts
    social_id = Column(String(255), index=True, nullable=True)  # DEPRECATED: Use social_accounts

    # Relationships
    social_accounts = relationship(
        "SocialAccount",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    chat_sessions = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, nickname={self.nickname})>"

    @property
    def primary_provider(self) -> str:
        """Get the primary (first) OAuth provider for this user."""
        if self.social_accounts:
            return self.social_accounts[0].provider
        return self.provider or "unknown"
