"""
Chat history persistence and retrieval helpers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .models.chat import ChatMessage, ChatSession


async def save_chat_to_db(
    db: AsyncSession,
    session_uuid: str,
    user_id: Optional[int],
    user_message: str,
    assistant_message: str,
    metadata: Dict[str, Any],
) -> None:
    """Save chat messages to database for permanent storage."""
    try:
        raw_sources = metadata.get("sources")
        serialized_sources = None
        if isinstance(raw_sources, list):
            serialized_sources = []
            for item in raw_sources:
                if hasattr(item, "model_dump"):
                    serialized_sources.append(item.model_dump())
                elif isinstance(item, dict):
                    serialized_sources.append(item)
                else:
                    serialized_sources.append({"value": str(item)})

        result = await db.execute(select(ChatSession).where(ChatSession.session_uuid == session_uuid))
        chat_session = result.scalar_one_or_none()

        if not chat_session:
            title = user_message[:100] + "..." if len(user_message) > 100 else user_message
            chat_session = ChatSession(
                session_uuid=session_uuid,
                user_id=user_id,
                title=title,
            )
            db.add(chat_session)
            await db.flush()

        db.add(
            ChatMessage(
                session_id=chat_session.id,
                role="user",
                content=user_message,
                response_mode=metadata.get("response_mode"),
            )
        )

        db.add(
            ChatMessage(
                session_id=chat_session.id,
                role="assistant",
                content=assistant_message,
                model_used=metadata.get("model"),
                sources_count=metadata.get("sources_count", 0),
                sources_json=serialized_sources,
                trace_json=metadata.get("query_trace"),
                response_mode=metadata.get("response_mode"),
                tokens_used=metadata.get("tokens_used"),
                latency_ms=metadata.get("latency_ms"),
            )
        )

        chat_session.message_count = (chat_session.message_count or 0) + 2
        chat_session.last_message_at = datetime.now(timezone.utc)
        chat_session.is_active = True

        await db.commit()
        logger.debug(
            f"Saved chat to DB: session={session_uuid[:8]}..., user_id={user_id}, message_count={chat_session.message_count}"
        )
    except Exception as exc:
        logger.error(f"Failed to save chat to DB: {exc}")
        await db.rollback()


async def get_user_chat_sessions(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get user's chat sessions ordered by most recent."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id, ChatSession.is_active == True)
        .order_by(ChatSession.last_message_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()
    return [
        {
            "id": session.id,
            "session_uuid": session.session_uuid,
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None,
        }
        for session in sessions
    ]


async def get_chat_messages(
    db: AsyncSession,
    session_uuid: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get messages for a specific chat session."""
    session_result = await db.execute(select(ChatSession).where(ChatSession.session_uuid == session_uuid))
    chat_session = session_result.scalar_one_or_none()
    if not chat_session:
        return []

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    messages = result.scalars().all()
    return [
        {
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "model_used": message.model_used,
            "sources_count": message.sources_count,
            "sources": message.sources_json or [],
        }
        for message in messages
    ]
