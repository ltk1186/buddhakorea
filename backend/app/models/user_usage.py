"""
Usage Tracking Models
=====================
일일 사용량 추적 - 로그인 사용자 및 익명 사용자

Quotas:
- Anonymous (IP-based): 3 questions/day
- Registered users: 20 questions/day (beta period)
"""

from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime, date, timezone
from ..database import Base


class UserUsage(Base):
    """로그인 사용자 일일 사용량 추적"""
    __tablename__ = "user_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Daily counters
    usage_date = Column(Date, nullable=False, default=date.today)
    chat_count = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('user_id', 'usage_date', name='uq_user_usage_date'),
    )

    def __repr__(self):
        return f"<UserUsage(user_id={self.user_id}, date={self.usage_date}, count={self.chat_count})>"


class AnonymousUsage(Base):
    """익명 사용자 (IP 기반) 일일 사용량 추적"""
    __tablename__ = "anonymous_usage"

    id = Column(Integer, primary_key=True, index=True)

    # IP-based tracking (hashed for privacy)
    ip_hash = Column(String(64), nullable=False, index=True)  # SHA-256 of IP

    # Daily counters
    usage_date = Column(Date, nullable=False, default=date.today)
    chat_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('ip_hash', 'usage_date', name='uq_anon_ip_date'),
    )

    def __repr__(self):
        return f"<AnonymousUsage(ip_hash={self.ip_hash[:8]}..., date={self.usage_date}, count={self.chat_count})>"


# Quota Constants
ANONYMOUS_DAILY_LIMIT = 3
REGISTERED_DAILY_LIMIT = 20

# Quota Messages (Korean)
QUOTA_MESSAGE_ANONYMOUS = """오늘의 무료 체험 질문 수(3개)를 모두 사용하셨습니다.
구글/네이버/카카오로 1초 회원가입하면
하루 20개까지 무료로 질문할 수 있어요.
(베타 기간 동안은 전액 무료입니다.)"""

QUOTA_MESSAGE_REGISTERED = """오늘의 무료 질문 한도(20개)를 모두 사용하셨습니다.
Buddha Korea는 현재 베타 서비스로,
안정적인 운영을 위해 하루 질문 수를 제한하고 있습니다.
내일 다시 이용해 주세요 🙏"""
