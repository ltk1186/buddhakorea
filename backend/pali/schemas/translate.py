"""Pydantic schemas for translation endpoints."""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

from ..config import settings


class TranslateRequest(BaseModel):
    """Request schema for translation endpoint."""
    literature_id: str
    segment_id: int
    force: bool = False  # 이미 번역된 세그먼트 덮어쓰기


class BatchTranslateRequest(BaseModel):
    """Request schema for batch translation endpoint."""
    literature_id: str
    segment_ids: List[int] = Field(..., min_length=1, max_length=settings.BATCH_MAX_SEGMENTS)
    force: bool = False

    @field_validator('segment_ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        if len(v) != len(set(v)):
            raise ValueError("Duplicate segment_ids not allowed")
        return v


class TranslationSentence(BaseModel):
    """Schema for a single translated sentence."""
    original_pali: str
    grammatical_analysis: str
    literal_translation: str
    free_translation: str
    explanation: str


class TranslationResult(BaseModel):
    """Schema for complete translation result."""
    sentences: List[TranslationSentence]
    summary: Optional[str] = None


class SSEStartEvent(BaseModel):
    """SSE start event data."""
    segment_id: int
    status: str = "translating"


class SSETokenEvent(BaseModel):
    """SSE token event data."""
    content: str


class SSESentenceCompleteEvent(BaseModel):
    """SSE sentence complete event data."""
    sentence_index: int
    translation: TranslationSentence


class SSEDoneEvent(BaseModel):
    """SSE done event data."""
    segment_id: int
    status: str = "completed"
    total_tokens: Optional[int] = None


class SSEErrorEvent(BaseModel):
    """SSE error event data."""
    error: str
    detail: Optional[str] = None
