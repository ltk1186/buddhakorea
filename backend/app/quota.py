"""
Quota Management
================
일일 사용량 체크 및 관리

Quotas:
- Anonymous (IP-based): 3 questions/day
- Registered users: 20 questions/day (beta period)
"""

import hashlib
from datetime import date, datetime, timezone
from typing import Optional, Tuple

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models.user import User
from .models.user_usage import (
    UserUsage,
    AnonymousUsage,
    ANONYMOUS_DAILY_LIMIT,
    REGISTERED_DAILY_LIMIT,
    QUOTA_MESSAGE_ANONYMOUS,
    QUOTA_MESSAGE_REGISTERED,
)


def hash_ip(ip: str) -> str:
    """Hash IP address for privacy-preserving tracking."""
    return hashlib.sha256(ip.encode()).hexdigest()


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header (when behind Nginx/proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain (original client)
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header (Nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct connection IP
    if request.client:
        return request.client.host

    return "unknown"


async def check_quota(
    db: AsyncSession,
    request: Request,
    user: Optional[User] = None
) -> Tuple[bool, int, int]:
    """
    Check if user/IP has remaining quota.

    Args:
        db: Database session
        request: FastAPI request (for IP extraction)
        user: User object if authenticated, None if anonymous

    Returns:
        Tuple of (has_remaining, used_count, limit)

    Raises:
        HTTPException 429 if quota exceeded
    """
    today = date.today()

    if user:
        # Logged-in user: Check user_usage table
        limit = user.daily_chat_limit or REGISTERED_DAILY_LIMIT

        stmt = select(UserUsage).where(
            UserUsage.user_id == user.id,
            UserUsage.usage_date == today
        )
        result = await db.execute(stmt)
        usage = result.scalar_one_or_none()

        used = usage.chat_count if usage else 0

        if used >= limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "quota_exceeded",
                    "message": QUOTA_MESSAGE_REGISTERED,
                    "used": used,
                    "limit": limit,
                    "is_anonymous": False
                }
            )

        return (True, used, limit)

    else:
        # Anonymous user: Check anonymous_usage table by IP hash
        ip = get_client_ip(request)
        ip_hash = hash_ip(ip)

        stmt = select(AnonymousUsage).where(
            AnonymousUsage.ip_hash == ip_hash,
            AnonymousUsage.usage_date == today
        )
        result = await db.execute(stmt)
        usage = result.scalar_one_or_none()

        used = usage.chat_count if usage else 0

        if used >= ANONYMOUS_DAILY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "quota_exceeded",
                    "message": QUOTA_MESSAGE_ANONYMOUS,
                    "used": used,
                    "limit": ANONYMOUS_DAILY_LIMIT,
                    "is_anonymous": True
                }
            )

        return (True, used, ANONYMOUS_DAILY_LIMIT)


async def increment_usage(
    db: AsyncSession,
    request: Request,
    user: Optional[User] = None,
    tokens: int = 0
) -> None:
    """
    Increment usage counter for user or IP.

    Args:
        db: Database session
        request: FastAPI request (for IP extraction)
        user: User object if authenticated, None if anonymous
        tokens: Number of tokens used (for analytics)
    """
    today = date.today()
    now = datetime.now(timezone.utc)

    if user:
        # Logged-in user
        stmt = select(UserUsage).where(
            UserUsage.user_id == user.id,
            UserUsage.usage_date == today
        )
        result = await db.execute(stmt)
        usage = result.scalar_one_or_none()

        if usage:
            usage.chat_count += 1
            usage.tokens_used += tokens
            usage.updated_at = now
        else:
            usage = UserUsage(
                user_id=user.id,
                usage_date=today,
                chat_count=1,
                tokens_used=tokens,
                created_at=now,
                updated_at=now
            )
            db.add(usage)

    else:
        # Anonymous user
        ip = get_client_ip(request)
        ip_hash = hash_ip(ip)

        stmt = select(AnonymousUsage).where(
            AnonymousUsage.ip_hash == ip_hash,
            AnonymousUsage.usage_date == today
        )
        result = await db.execute(stmt)
        usage = result.scalar_one_or_none()

        if usage:
            usage.chat_count += 1
            usage.updated_at = now
        else:
            usage = AnonymousUsage(
                ip_hash=ip_hash,
                usage_date=today,
                chat_count=1,
                created_at=now,
                updated_at=now
            )
            db.add(usage)

    await db.commit()


async def get_usage_info(
    db: AsyncSession,
    request: Request,
    user: Optional[User] = None
) -> dict:
    """
    Get current usage info for display to user.

    Returns:
        Dict with used, limit, remaining, is_anonymous
    """
    today = date.today()

    if user:
        limit = user.daily_chat_limit or REGISTERED_DAILY_LIMIT

        stmt = select(UserUsage).where(
            UserUsage.user_id == user.id,
            UserUsage.usage_date == today
        )
        result = await db.execute(stmt)
        usage = result.scalar_one_or_none()
        used = usage.chat_count if usage else 0

        return {
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
            "is_anonymous": False
        }

    else:
        ip = get_client_ip(request)
        ip_hash = hash_ip(ip)

        stmt = select(AnonymousUsage).where(
            AnonymousUsage.ip_hash == ip_hash,
            AnonymousUsage.usage_date == today
        )
        result = await db.execute(stmt)
        usage = result.scalar_one_or_none()
        used = usage.chat_count if usage else 0

        return {
            "used": used,
            "limit": ANONYMOUS_DAILY_LIMIT,
            "remaining": max(0, ANONYMOUS_DAILY_LIMIT - used),
            "is_anonymous": True
        }
