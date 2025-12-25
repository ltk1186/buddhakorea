"""
API dependencies for dependency injection.
"""
from typing import Generator, Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..services.literature_service import LiteratureService
from ..services.gemini_client import GeminiClient
from ..services.redis_client import redis_client, RedisClient
from ..config import settings


def get_literature_service(db: Session = Depends(get_db)) -> LiteratureService:
    """Get literature service instance."""
    return LiteratureService(db)


def get_gemini_client() -> GeminiClient:
    """Get Gemini client instance."""
    return GeminiClient()


async def get_redis() -> RedisClient:
    """Get Redis client instance."""
    return redis_client


def get_session_id(
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID")
) -> Optional[str]:
    """Extract session ID from header."""
    return x_session_id


def verify_admin_token(
    authorization: Optional[str] = Header(None)
) -> bool:
    """
    Verify admin token from Authorization header.
    Raises HTTPException if invalid.
    """
    if not settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication not configured"
        )

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )

    # Expected format: "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )

    if parts[1] != settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin token"
        )

    return True
