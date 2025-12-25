"""
Health check endpoint.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from ...db.database import get_db
from ...services.redis_client import redis_client
from ...schemas.common import HealthResponse
from ...config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """
    Check the health of the API and its dependencies.
    """
    # Check database connection
    db_status = "unknown"
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Check Redis connection
    redis_status = "unknown"
    try:
        if await redis_client.ping():
            redis_status = "connected"
        else:
            redis_status = "disconnected"
    except Exception:
        redis_status = "disconnected"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        version=settings.APP_VERSION,
        database=db_status,
        redis=redis_status
    )
