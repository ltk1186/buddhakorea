"""Common Pydantic schemas used across the API."""
from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = "ok"
    version: str
    database: str = "unknown"
    redis: str = "unknown"


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class PaginationParams(BaseModel):
    """Pagination parameters."""
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class PaginationMeta(BaseModel):
    """Pagination metadata in responses."""
    offset: int
    limit: int
    total: int
    has_more: bool
