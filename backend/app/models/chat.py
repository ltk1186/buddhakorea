"""
Chat History Models
====================
유저별 채팅 세션 및 메시지 영구 저장
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base


class ChatSession(Base):
    """채팅 세션 - 유저별 대화 세션 관리"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_uuid = Column(String(36), unique=True, index=True)  # Redis 세션 ID와 연결
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # 비로그인도 허용

    # Session Info
    title = Column(String(200), nullable=True)  # 첫 질문 요약 (자동 생성)
    summary = Column(Text, nullable=True)  # AI-generated summary for search

    # Status
    is_active = Column(Boolean, default=True)  # Soft delete
    is_archived = Column(Boolean, default=False)  # User can archive sessions

    # Denormalized for fast display
    message_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_message_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # For soft delete auditing

    # Relationships
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
    user = relationship("User", back_populates="chat_sessions")

    def __repr__(self):
        return f"<ChatSession(uuid={self.session_uuid[:8]}..., user_id={self.user_id})>"


class ChatMessage(Base):
    """채팅 메시지 - 개별 메시지 저장"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)

    # Assistant Response Metadata (NULL for user messages)
    model_used = Column(String(50), nullable=True)  # 'gemini-2.5-pro', 'gemini-2.5-flash'
    sources_count = Column(Integer, default=0)  # 참조된 문헌 수
    sources_json = Column(JSON, nullable=True)  # Store source references for replay
    response_mode = Column(String(20), nullable=True)  # 'normal', 'detailed', 'academic'

    # Performance & Analytics
    tokens_used = Column(Integer, nullable=True)  # For billing/analytics
    latency_ms = Column(Integer, nullable=True)  # Response generation time

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage(session_id={self.session_id}, role={self.role})>"
