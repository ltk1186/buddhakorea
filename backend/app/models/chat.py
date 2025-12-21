"""
Chat History Models
====================
유저별 채팅 세션 및 메시지 영구 저장
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..database import Base


class ChatSession(Base):
    """채팅 세션 - 유저별 대화 세션 관리"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_uuid = Column(String(36), unique=True, index=True)  # Redis 세션 ID와 연결
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # 비로그인도 허용
    title = Column(String(200), nullable=True)  # 첫 질문 요약 (자동 생성)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_message_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)  # 삭제 대신 비활성화

    # Relationships
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """채팅 메시지 - 개별 메시지 저장"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)

    # 메타데이터
    model_used = Column(String(50), nullable=True)  # 사용된 LLM 모델
    sources_count = Column(Integer, default=0)  # 참조된 문헌 수
    response_mode = Column(String(20), nullable=True)  # 'normal', 'detailed', 'academic'

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
