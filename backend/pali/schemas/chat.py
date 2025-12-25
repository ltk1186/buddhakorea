"""Pydantic schemas for chat endpoints."""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""
    literature_id: str
    segment_id: int
    question: str


class ChatMessage(BaseModel):
    """Schema for a chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime


class ChatHistory(BaseModel):
    """Schema for chat history."""
    session_id: str
    messages: List[ChatMessage]
    literature_id: Optional[str] = None
    segment_id: Optional[int] = None


class ChatStartEvent(BaseModel):
    """SSE start event for chat."""
    question_id: str
    status: str = "processing"


class ChatTokenEvent(BaseModel):
    """SSE token event for chat."""
    content: str


class ChatDoneEvent(BaseModel):
    """SSE done event for chat."""
    question_id: str
    total_tokens: Optional[int] = None
