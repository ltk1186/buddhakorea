"""Shared API request/response schemas for the FastAPI app."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    query: str = Field(..., min_length=1, max_length=2000, description="User question")
    language: Optional[str] = Field(default="auto", description="Interface language (ko/en/auto)")
    collection: Optional[str] = Field(default="all", description="Text collection to search (all/chinese/english/korean)")
    max_sources: int = Field(default=5, ge=1, le=20, description="Maximum number of source citations")
    sutra_filter: Optional[str] = Field(default=None, description="Filter by specific sutra ID (e.g., 'T01n0001' for 장아함경)")
    tradition_filter: Optional[str] = Field(default=None, description="Filter by Buddhist tradition (초기불교, 대승불교, 선종, etc.)")
    detailed_mode: bool = Field(default=False, description="Enable detailed mode for comprehensive answers (activated by /자세히 prefix)")
    session_id: Optional[str] = Field(default=None, description="Session ID for follow-up questions (optional, created automatically if not provided)")
    is_followup: bool = Field(default=False, description="Whether this is a follow-up question in an existing conversation")


class SourceDocument(BaseModel):
    """Source document citation."""

    title: str
    text_id: str
    excerpt: str
    score: Optional[float] = None
    metadata: Dict[str, Any] = {}


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    response: str
    sources: List[SourceDocument]
    model: str
    latency_ms: int
    collection: str
    session_id: str = Field(..., description="Session ID for this conversation (use this for follow-up questions)")
    can_followup: bool = Field(default=True, description="Whether follow-up questions are supported for this response")
    conversation_depth: int = Field(default=1, description="Number of exchanges in this conversation (1 = first question)")
    from_cache: bool = Field(default=False, description="Whether this response was served from cache")


class CollectionInfo(BaseModel):
    """Information about a text collection."""

    name: str
    document_count: int
    language: str
    description: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    chroma_connected: bool
    llm_configured: bool


class CacheRequest(BaseModel):
    """Request model for adding to cache."""

    cache_key: str = Field(..., description="Unique identifier for this cached response")
    keywords: List[str] = Field(..., description="Keywords that trigger this cached response")
    response: str = Field(..., description="The response text to cache")
    sources: List[SourceDocument] = Field(..., description="Source documents for this response")
    model: str = Field(..., description="Model name used to generate the response")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CachedResponseInfo(BaseModel):
    """Information about a cached response."""

    cache_key: str
    keywords: List[str]
    response_preview: str
    model: str
    created_at: str
    hit_count: int
    last_hit: Optional[str]
