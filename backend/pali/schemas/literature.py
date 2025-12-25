"""Pydantic schemas for literature-related endpoints."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from .common import PaginationMeta


class LiteratureBase(BaseModel):
    """Base schema for literature data."""
    name: str
    pali_name: str
    pitaka: str
    nikaya: Optional[str] = None
    source_pdf: Optional[str] = None
    hierarchy_labels: Optional[Dict[str, str]] = None
    display_metadata: Optional[Dict[str, Any]] = None


class LiteratureCreate(LiteratureBase):
    """Schema for creating a new literature."""
    id: str


class LiteratureResponse(LiteratureBase):
    """Schema for literature response."""
    id: str
    status: str
    total_segments: int
    translated_segments: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LiteratureListResponse(BaseModel):
    """Schema for literature list response."""
    literatures: List[LiteratureResponse]
    pitaka_structure: Dict[str, Any]
    total_count: int


class SegmentBase(BaseModel):
    """Base schema for segment data."""
    vagga_id: Optional[int] = None
    vagga_name: Optional[str] = None
    sutta_id: Optional[int] = None
    sutta_name: Optional[str] = None
    page_number: Optional[int] = None
    paragraph_id: int
    original_text: str


class SegmentResponse(SegmentBase):
    """Schema for segment response."""
    id: int
    literature_id: str
    translation: Optional[Dict[str, Any]] = None
    is_translated: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SegmentListResponse(BaseModel):
    """Schema for segment list response with pagination."""
    segments: List[SegmentResponse]
    pagination: PaginationMeta


class VaggaInfo(BaseModel):
    """Information about a vagga (section)."""
    vagga_id: int
    vagga_name: str
    sutta_count: int


class PitakaStructure(BaseModel):
    """Tripitaka structure for navigation."""
    sutta: Dict[str, List[str]]  # nikaya -> literature_ids
    vinaya: List[str]
    abhidhamma: List[str]
