"""
LLM Response Caching Module

Redis-based caching for LLM responses to reduce API costs.
Expected to reduce Gemini API calls by ~40%.
"""

import hashlib
import json
import logging
from typing import Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL_HOURS = 24  # Cache entries expire after 24 hours
CACHE_VERSION = "v1"  # Increment when cache format changes


def get_cache_key(query: str, tradition: str) -> str:
    """Generate a cache key from query and tradition.

    Args:
        query: The user's question
        tradition: Buddhist tradition (theravada, mahayana, etc.)

    Returns:
        A unique cache key string
    """
    # Normalize the query for better cache hits
    normalized = f"{tradition.lower().strip()}:{query.strip().lower()}"
    hash_value = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
    return f"llm:{CACHE_VERSION}:{hash_value}"


async def get_cached_response(
    query: str,
    tradition: str,
    redis_client: Any
) -> Optional[dict]:
    """Retrieve a cached LLM response.

    Args:
        query: The user's question
        tradition: Buddhist tradition
        redis_client: Redis client instance

    Returns:
        Cached response dict or None if not found
    """
    if redis_client is None:
        return None

    try:
        cache_key = get_cache_key(query, tradition)
        cached = await redis_client.get(cache_key)

        if cached:
            # Track cache hit
            await redis_client.incr("metrics:llm_cache:hits")
            logger.info(f"Cache HIT for key: {cache_key[:20]}...")
            return json.loads(cached)
        else:
            # Track cache miss
            await redis_client.incr("metrics:llm_cache:misses")
            logger.debug(f"Cache MISS for key: {cache_key[:20]}...")
            return None

    except Exception as e:
        logger.warning(f"Cache read error: {e}")
        return None


async def cache_response(
    query: str,
    tradition: str,
    response: dict,
    redis_client: Any,
    ttl_hours: int = CACHE_TTL_HOURS
) -> bool:
    """Cache an LLM response.

    Args:
        query: The user's question
        tradition: Buddhist tradition
        response: The LLM response to cache
        redis_client: Redis client instance
        ttl_hours: Hours until cache entry expires

    Returns:
        True if cached successfully, False otherwise
    """
    if redis_client is None:
        return False

    try:
        cache_key = get_cache_key(query, tradition)

        # Add metadata to cached response
        cache_entry = {
            **response,
            "_cached_at": datetime.utcnow().isoformat(),
            "_cache_key": cache_key
        }

        # Store with TTL
        ttl_seconds = ttl_hours * 3600
        await redis_client.setex(
            cache_key,
            ttl_seconds,
            json.dumps(cache_entry, ensure_ascii=False)
        )

        logger.info(f"Cached response for key: {cache_key[:20]}... (TTL: {ttl_hours}h)")
        return True

    except Exception as e:
        logger.warning(f"Cache write error: {e}")
        return False


async def get_cache_stats(redis_client: Any) -> dict:
    """Get cache hit/miss statistics.

    Args:
        redis_client: Redis client instance

    Returns:
        Dict with hits, misses, and hit_rate
    """
    if redis_client is None:
        return {"hits": 0, "misses": 0, "hit_rate": 0.0}

    try:
        hits = int(await redis_client.get("metrics:llm_cache:hits") or 0)
        misses = int(await redis_client.get("metrics:llm_cache:misses") or 0)
        total = hits + misses
        hit_rate = (hits / total * 100) if total > 0 else 0.0

        return {
            "hits": hits,
            "misses": misses,
            "total": total,
            "hit_rate": round(hit_rate, 2)
        }

    except Exception as e:
        logger.warning(f"Error getting cache stats: {e}")
        return {"hits": 0, "misses": 0, "hit_rate": 0.0, "error": str(e)}


async def clear_cache(redis_client: Any, pattern: str = "llm:*") -> int:
    """Clear cache entries matching pattern.

    Args:
        redis_client: Redis client instance
        pattern: Key pattern to match (default: all LLM cache entries)

    Returns:
        Number of keys deleted
    """
    if redis_client is None:
        return 0

    try:
        keys = []
        async for key in redis_client.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            deleted = await redis_client.delete(*keys)
            logger.info(f"Cleared {deleted} cache entries matching pattern: {pattern}")
            return deleted
        return 0

    except Exception as e:
        logger.warning(f"Error clearing cache: {e}")
        return 0
