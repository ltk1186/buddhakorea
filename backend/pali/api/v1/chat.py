"""
Chat API with SSE streaming for follow-up questions.
"""
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...db.models import QueryLog
from ..deps import get_literature_service, get_gemini_client, get_session_id, get_redis
from ...services.literature_service import LiteratureService
from ...services.gemini_client import GeminiClient
from ...services.redis_client import RedisClient
from ...schemas.chat import ChatRequest

router = APIRouter()


async def generate_chat_stream(
    question_id: str,
    question: str,
    segment,
    gemini: GeminiClient,
    redis: RedisClient,
    session_id: str,
    db: Session
):
    """
    Generate SSE stream for chat response.
    """
    # Send start event
    yield f"event: start\ndata: {json.dumps({'question_id': question_id})}\n\n"

    try:
        full_answer = ""
        token_count = 0

        async for chunk in gemini.chat_stream(
            question=question,
            original_text=segment.original_text,
            translation=segment.translation or {}
        ):
            if chunk.get("type") == "token":
                content = chunk["content"]
                full_answer += content
                token_count += 1
                yield f"event: token\ndata: {json.dumps({'content': content})}\n\n"
            elif chunk.get("type") == "error":
                yield f"event: error\ndata: {json.dumps({'error': chunk['error']})}\n\n"
                return

        # Save to chat history in Redis
        if session_id:
            await redis.append_chat_message(session_id, {
                "role": "user",
                "content": question,
                "timestamp": datetime.utcnow().isoformat()
            })
            await redis.append_chat_message(session_id, {
                "role": "assistant",
                "content": full_answer,
                "timestamp": datetime.utcnow().isoformat()
            })

        # Log query to database
        query_log = QueryLog(
            session_id=session_id,
            literature_id=segment.literature_id,
            segment_id=segment.id,
            question=question,
            answer=full_answer,
            model="gemini",
            tokens_used=token_count
        )
        db.add(query_log)
        db.commit()

        # Send done event
        yield f"event: done\ndata: {json.dumps({'question_id': question_id, 'total_tokens': token_count})}\n\n"

    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@router.post("")
async def chat_with_segment(
    request: ChatRequest,
    db: Session = Depends(get_db),
    service: LiteratureService = Depends(get_literature_service),
    gemini: GeminiClient = Depends(get_gemini_client),
    redis: RedisClient = Depends(get_redis),
    session_id: str = Depends(get_session_id)
):
    """
    Ask a question about a specific segment.
    Returns SSE stream with the AI response.
    """
    # Get the segment
    segment = service.get_segment_by_id(request.literature_id, request.segment_id)

    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Segment {request.segment_id} not found"
        )

    # Generate unique question ID
    question_id = str(uuid.uuid4())[:8]

    # Generate or use existing session ID
    effective_session_id = session_id or str(uuid.uuid4())

    return StreamingResponse(
        generate_chat_stream(
            question_id=question_id,
            question=request.question,
            segment=segment,
            gemini=gemini,
            redis=redis,
            session_id=effective_session_id,
            db=db
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-ID": effective_session_id,
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/history")
async def get_chat_history(
    limit: int = 20,
    redis: RedisClient = Depends(get_redis),
    session_id: str = Depends(get_session_id)
):
    """
    Get chat history for the current session.
    """
    if not session_id:
        return {"messages": [], "session_id": None}

    messages = await redis.get_chat_history(session_id, limit)

    return {
        "messages": messages,
        "session_id": session_id
    }


@router.delete("/history")
async def clear_chat_history(
    redis: RedisClient = Depends(get_redis),
    session_id: str = Depends(get_session_id)
):
    """
    Clear chat history for the current session.
    """
    if session_id:
        await redis.clear_chat_history(session_id)

    return {"status": "cleared", "session_id": session_id}
