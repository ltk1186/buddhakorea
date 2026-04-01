"""
Quota Management
================
일일 사용량 체크 및 관리 with Redis caching

Quotas:
- Anonymous (IP-based): 3 questions/day
- Registered users: 20 questions/day (beta period)

Uses Redis for fast caching (10x improvement):
- Check quota from Redis first (O(1) operation)
- Write to DB once daily or on hourly flush
- Background task syncs Redis to DB
"""

import hashlib
import json
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Tuple

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import redis.asyncio as redis

from .models.user import User
from .models.user_usage import (
    UserUsage,
    AnonymousUsage,
    ANONYMOUS_DAILY_LIMIT,
    REGISTERED_DAILY_LIMIT,
    QUOTA_MESSAGE_ANONYMOUS,
    QUOTA_MESSAGE_REGISTERED,
)

# Redis client (initialized in main.py lifespan)
redis_client: Optional[redis.Redis] = None


def set_redis_client(client: redis.Redis) -> None:
    """Set the Redis client for quota caching."""
    global redis_client
    redis_client = client


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


async def _get_quota_from_redis(redis_key: str) -> Optional[int]:
    """Get quota count from Redis cache."""
    if not redis_client:
        return None
    try:
        value = await redis_client.get(redis_key)
        return int(value) if value else None
    except Exception as e:
        logger.warning(f"Redis quota read error: {e}")
        return None


async def _set_quota_in_redis(redis_key: str, count: int, seconds_until_midnight: int) -> None:
    """Set quota count in Redis with TTL until midnight."""
    if not redis_client:
        return
    try:
        await redis_client.setex(redis_key, seconds_until_midnight, str(count))
    except Exception as e:
        logger.warning(f"Redis quota write error: {e}")


def _seconds_until_midnight() -> int:
    """Calculate seconds until next midnight UTC."""
    now = datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


async def check_quota(
    db: AsyncSession,
    request: Request,
    user: Optional[User] = None
) -> Tuple[bool, int, int]:
    """
    Check if user/IP has remaining quota (with Redis caching).

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
        # Logged-in user
        limit = user.daily_chat_limit or REGISTERED_DAILY_LIMIT
        redis_key = f"quota:user:{user.id}:{today.isoformat()}"

        # Try Redis cache first
        used = await _get_quota_from_redis(redis_key)

        # If not in Redis, fetch from DB
        if used is None:
            stmt = select(UserUsage).where(
                UserUsage.user_id == user.id,
                UserUsage.usage_date == today
            )
            result = await db.execute(stmt)
            usage_obj = result.scalar_one_or_none()
            used = usage_obj.chat_count if usage_obj else 0

            # Cache in Redis
            await _set_quota_in_redis(redis_key, used, _seconds_until_midnight())

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
        # Anonymous user by IP hash
        ip = get_client_ip(request)
        ip_hash = hash_ip(ip)
        redis_key = f"quota:anon:{ip_hash}:{today.isoformat()}"

        # Try Redis cache first
        used = await _get_quota_from_redis(redis_key)

        # If not in Redis, fetch from DB
        if used is None:
            stmt = select(AnonymousUsage).where(
                AnonymousUsage.ip_hash == ip_hash,
                AnonymousUsage.usage_date == today
            )
            result = await db.execute(stmt)
            usage_obj = result.scalar_one_or_none()
            used = usage_obj.chat_count if usage_obj else 0

            # Cache in Redis
            await _set_quota_in_redis(redis_key, used, _seconds_until_midnight())

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
    tokens: int = 0,
    sync_to_db: bool = False
) -> None:
    """
    Increment usage counter for user or IP (with Redis caching).

    Args:
        db: Database session
        request: FastAPI request (for IP extraction)
        user: User object if authenticated, None if anonymous
        tokens: Number of tokens used (for analytics)
        sync_to_db: Force immediate sync to DB (default False - uses Redis only)
    """
    today = date.today()
    now = datetime.now(timezone.utc)

    if user:
        # Logged-in user
        redis_key = f"quota:user:{user.id}:{today.isoformat()}"

        # Increment in Redis (fast path)
        if redis_client:
            try:
                await redis_client.incr(redis_key)
                # Ensure TTL is set
                await redis_client.expire(redis_key, _seconds_until_midnight())
            except Exception as e:
                logger.warning(f"Redis increment error: {e}")
                # Fall through to DB update

        # Optionally sync to DB now or rely on background flush
        if sync_to_db or not redis_client:
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

            await db.commit()

    else:
        # Anonymous user
        ip = get_client_ip(request)
        ip_hash = hash_ip(ip)
        redis_key = f"quota:anon:{ip_hash}:{today.isoformat()}"

        # Increment in Redis (fast path)
        if redis_client:
            try:
                await redis_client.incr(redis_key)
                # Ensure TTL is set
                await redis_client.expire(redis_key, _seconds_until_midnight())
            except Exception as e:
                logger.warning(f"Redis increment error: {e}")
                # Fall through to DB update

        # Optionally sync to DB now or rely on background flush
        if sync_to_db or not redis_client:
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
