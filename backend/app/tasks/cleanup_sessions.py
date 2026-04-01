"""
Scheduled task to clean up stale chat sessions.

Runs daily at 2 AM UTC to:
- Soft-delete inactive sessions (no messages for 30+ days)
- Archive old sessions to improve query performance
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from loguru import logger

from ..models.chat import ChatSession
from ..database import SessionLocal


async def cleanup_stale_sessions(db: AsyncSession, days_inactive: int = 30) -> int:
    """
    Soft-delete chat sessions that have been inactive for specified days.

    Args:
        db: Database session
        days_inactive: Number of days without activity before session is considered stale

    Returns:
        Number of sessions cleaned up
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_inactive)

    try:
        # Find stale sessions (inactive and marked for cleanup)
        stmt = select(ChatSession).where(
            and_(
                ChatSession.is_active == True,
                ChatSession.last_message_at < cutoff_date
            )
        )
        result = await db.execute(stmt)
        stale_sessions = result.scalars().all()

        count = 0
        for session in stale_sessions:
            session.is_active = False
            count += 1

        if count > 0:
            await db.commit()
            logger.info(f"Cleaned up {count} stale sessions (inactive for {days_inactive}+ days)")

        return count

    except Exception as e:
        logger.error(f"Error during session cleanup: {e}")
        await db.rollback()
        return 0


async def cleanup_deleted_sessions(db: AsyncSession, days_deleted: int = 90) -> int:
    """
    Permanently delete soft-deleted sessions older than specified days.
    Called less frequently (monthly) to allow recovery period.

    Args:
        db: Database session
        days_deleted: Number of days after soft-delete before permanent deletion

    Returns:
        Number of sessions permanently deleted
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_deleted)

    try:
        # Find deleted sessions to permanently remove
        stmt = select(ChatSession).where(
            and_(
                ChatSession.is_active == False,
                ChatSession.last_message_at < cutoff_date
            )
        )
        result = await db.execute(stmt)
        deleted_sessions = result.scalars().all()

        count = 0
        for session in deleted_sessions:
            # Could archive to separate table here if needed
            await db.delete(session)
            count += 1

        if count > 0:
            await db.commit()
            logger.info(f"Permanently deleted {count} sessions (soft-deleted {days_deleted}+ days ago)")

        return count

    except Exception as e:
        logger.error(f"Error during permanent session deletion: {e}")
        await db.rollback()
        return 0


async def run_cleanup():
    """Main cleanup function - called by scheduler."""
    async with SessionLocal() as db:
        logger.info("Starting scheduled session cleanup...")

        stale_count = await cleanup_stale_sessions(db, days_inactive=30)
        # Note: permanent deletion runs less frequently, skip for now
        # deleted_count = await cleanup_deleted_sessions(db, days_deleted=90)

        logger.info(f"Session cleanup completed: {stale_count} sessions soft-deleted")
