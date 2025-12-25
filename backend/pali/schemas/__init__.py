"""Pydantic schemas package."""
from .literature import (
    LiteratureBase, LiteratureCreate, LiteratureResponse,
    SegmentBase, SegmentResponse, SegmentListResponse,
    PitakaStructure
)
from .translate import TranslateRequest, TranslationSentence, TranslationResult
from .chat import ChatRequest, ChatMessage
from .common import HealthResponse, ErrorResponse, PaginationParams

__all__ = [
    "LiteratureBase", "LiteratureCreate", "LiteratureResponse",
    "SegmentBase", "SegmentResponse", "SegmentListResponse",
    "PitakaStructure",
    "TranslateRequest", "TranslationSentence", "TranslationResult",
    "ChatRequest", "ChatMessage",
    "HealthResponse", "ErrorResponse", "PaginationParams"
]
