"""
Chat history routers.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .. import database
from ..models.chat import ChatSession, SavedExchange
from ..models.user import User


class UpdateSessionTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="New title for the session")


class SaveExchangeRequest(BaseModel):
    question: str = Field(..., description="The user's question")
    answer: str = Field(..., description="The assistant's answer")
    sources: Optional[list[dict[str, Any]]] = Field(default=None, description="Source documents metadata")
    model_used: Optional[str] = Field(default=None, description="LLM model used")
    response_mode: Optional[str] = Field(default=None, description="Response mode used")


def create_chat_history_router(
    *,
    auth_module: Any,
    logger: Any,
    get_current_user_optional_dep: Any,
    get_current_user_required_dep: Any,
    get_user_chat_sessions_fn: Any,
    get_chat_messages_fn: Any,
) -> APIRouter:
    router = APIRouter(tags=["chat-history"])

    @router.get("/api/chat/sessions")
    async def get_chat_sessions(
        request: Request,
        db: AsyncSession = Depends(database.get_db),
        limit: int = 20,
        offset: int = 0,
    ):
        token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(401, "Not authenticated")
        payload = auth_module.decode_access_token(token)
        if not payload or not payload.get("user_id"):
            raise HTTPException(401, "Invalid token")
        sessions = await get_user_chat_sessions_fn(db, payload["user_id"], limit, offset)
        return {"sessions": sessions, "count": len(sessions)}

    @router.get("/api/chat/sessions/{session_uuid}/messages")
    async def get_session_messages(
        session_uuid: str,
        request: Request,
        db: AsyncSession = Depends(database.get_db),
        limit: int = 50,
    ):
        token = request.cookies.get("access_token")
        user_id = None
        if token:
            payload = auth_module.decode_access_token(token)
            if payload:
                user_id = payload.get("user_id")

        result = await db.execute(select(ChatSession).where(ChatSession.session_uuid == session_uuid))
        chat_session = result.scalar_one_or_none()
        if not chat_session:
            raise HTTPException(404, "Session not found")
        if chat_session.user_id and chat_session.user_id != user_id:
            raise HTTPException(403, "Access denied")

        messages = await get_chat_messages_fn(db, session_uuid, limit)
        return {"session_uuid": session_uuid, "title": chat_session.title, "messages": messages}

    @router.delete("/api/chat/sessions/{session_uuid}")
    async def delete_chat_session(
        session_uuid: str,
        request: Request,
        db: AsyncSession = Depends(database.get_db),
    ):
        token = request.cookies.get("access_token")
        if not token:
            raise HTTPException(401, "Not authenticated")
        payload = auth_module.decode_access_token(token)
        if not payload:
            raise HTTPException(401, "Invalid token")

        result = await db.execute(select(ChatSession).where(ChatSession.session_uuid == session_uuid))
        chat_session = result.scalar_one_or_none()
        if not chat_session:
            raise HTTPException(404, "Session not found")
        if chat_session.user_id != payload.get("user_id"):
            raise HTTPException(403, "Access denied")

        chat_session.is_active = False
        await db.commit()
        return {"status": "deleted", "session_uuid": session_uuid}

    @router.patch("/api/chat/sessions/{session_uuid}")
    async def update_chat_session_title(
        session_uuid: str,
        payload: UpdateSessionTitleRequest,
        db: AsyncSession = Depends(database.get_db),
        user: User = Depends(get_current_user_required_dep),
    ):
        result = await db.execute(select(ChatSession).where(ChatSession.session_uuid == session_uuid))
        chat_session = result.scalar_one_or_none()
        if not chat_session:
            raise HTTPException(404, "Session not found")
        if chat_session.user_id != user.id:
            raise HTTPException(403, "Access denied")

        chat_session.title = payload.title
        await db.commit()
        return {"status": "updated", "session_uuid": session_uuid, "new_title": payload.title}

    @router.post("/api/chat/saved")
    async def save_exchange(
        payload: SaveExchangeRequest,
        db: AsyncSession = Depends(database.get_db),
        user: User = Depends(get_current_user_required_dep),
    ):
        saved = SavedExchange(
            user_id=user.id,
            question=payload.question,
            answer=payload.answer,
            sources_json=payload.sources,
            model_used=payload.model_used,
            response_mode=payload.response_mode,
        )
        db.add(saved)
        await db.commit()
        await db.refresh(saved)
        return {"status": "saved", "id": saved.id}

    @router.get("/api/chat/saved")
    async def get_saved_exchanges(
        db: AsyncSession = Depends(database.get_db),
        user: User = Depends(get_current_user_required_dep),
    ):
        result = await db.execute(
            select(SavedExchange).where(SavedExchange.user_id == user.id).order_by(SavedExchange.created_at.desc())
        )
        saved_items = result.scalars().all()
        return {
            "count": len(saved_items),
            "items": [
                {
                    "id": item.id,
                    "question": item.question,
                    "answer": item.answer,
                    "sources": item.sources_json,
                    "model_used": item.model_used,
                    "response_mode": item.response_mode,
                    "created_at": item.created_at.isoformat(),
                }
                for item in saved_items
            ],
        }

    @router.delete("/api/chat/saved/{saved_id}")
    async def delete_saved_exchange(
        saved_id: int,
        db: AsyncSession = Depends(database.get_db),
        user: User = Depends(get_current_user_required_dep),
    ):
        result = await db.execute(select(SavedExchange).where(SavedExchange.id == saved_id))
        saved = result.scalar_one_or_none()
        if not saved:
            raise HTTPException(404, "Saved item not found")
        if saved.user_id != user.id:
            raise HTTPException(403, "Access denied")
        await db.delete(saved)
        await db.commit()
        return {"status": "deleted", "id": saved_id}

    @router.post("/api/chat/sessions", response_model=dict)
    async def create_chat_session(
        request: Request,
        db: AsyncSession = Depends(database.get_db),
        user: Optional[User] = Depends(get_current_user_optional_dep),
    ):
        session_uuid = str(uuid.uuid4())
        try:
            chat_session = ChatSession(
                session_uuid=session_uuid,
                user_id=user.id if user else None,
                title="New conversation",
                message_count=0,
                is_active=True,
            )
            db.add(chat_session)
            await db.commit()
            logger.debug(
                f"Created new session: {session_uuid[:8]}... for user_id={user.id if user else None}"
            )
            return {"session_uuid": session_uuid, "user_id": user.id if user else None}
        except Exception as exc:
            logger.error(f"Failed to create session: {exc}")
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session",
            )

    return router
