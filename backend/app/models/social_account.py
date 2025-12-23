"""
Social Account Model
====================
OAuth 소셜 로그인 계정 관리 (Google, Naver, Kakao)
한 사용자가 여러 소셜 계정을 연동할 수 있도록 분리된 테이블
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base


class SocialAccount(Base):
    """소셜 로그인 계정 - 사용자별 OAuth 제공자 연결"""
    __tablename__ = "social_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Provider Info
    provider = Column(String(20), nullable=False)  # 'google', 'naver', 'kakao'
    provider_user_id = Column(String(255), nullable=False)  # 'sub' from Google, 'id' from Naver/Kakao
    provider_email = Column(String(255), nullable=True)  # Email from this specific provider

    # Optional: Store tokens for API calls on behalf of user (encrypted in production)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Full profile from provider (for debugging/future use)
    raw_profile = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="social_accounts")

    __table_args__ = (
        # One user can only have one account per provider
        UniqueConstraint('user_id', 'provider', name='uq_user_provider'),
        # Each provider user ID is unique within that provider
        UniqueConstraint('provider', 'provider_user_id', name='uq_provider_user_id'),
    )

    def __repr__(self):
        return f"<SocialAccount(user_id={self.user_id}, provider={self.provider})>"
