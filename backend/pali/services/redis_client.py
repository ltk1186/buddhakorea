"""
Redis client for session management and caching.
"""
import json
from typing import Optional, Any
from datetime import timedelta
import redis.asyncio as redis

from ..config import settings


class RedisClient:
    """Async Redis client wrapper."""

    def __init__(self):
        """Initialize the Redis client."""
        self._redis: Optional[redis.Redis] = None

    async def connect(self):
        """Establish connection to Redis."""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis

    async def close(self):
        """Close the Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def get_client(self) -> redis.Redis:
        """Get the Redis client, connecting if needed."""
        if self._redis is None:
            await self.connect()
        return self._redis

    # Session management
    async def set_session(
        self,
        session_id: str,
        data: dict,
        expire_seconds: int = 86400  # 24 hours
    ):
        """Store session data."""
        client = await self.get_client()
        await client.setex(
            f"session:{session_id}",
            expire_seconds,
            json.dumps(data)
        )

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve session data."""
        client = await self.get_client()
        data = await client.get(f"session:{session_id}")
        if data:
            return json.loads(data)
        return None

    async def delete_session(self, session_id: str):
        """Delete a session."""
        client = await self.get_client()
        await client.delete(f"session:{session_id}")

    # Caching
    async def cache_get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        client = await self.get_client()
        data = await client.get(f"cache:{key}")
        if data:
            return json.loads(data)
        return None

    async def cache_set(
        self,
        key: str,
        value: Any,
        expire_seconds: int = 3600  # 1 hour
    ):
        """Set cached value."""
        client = await self.get_client()
        await client.setex(
            f"cache:{key}",
            expire_seconds,
            json.dumps(value)
        )

    async def cache_delete(self, key: str):
        """Delete cached value."""
        client = await self.get_client()
        await client.delete(f"cache:{key}")

    async def cache_clear_pattern(self, pattern: str):
        """Clear all cache keys matching pattern."""
        client = await self.get_client()
        keys = await client.keys(f"cache:{pattern}")
        if keys:
            await client.delete(*keys)

    # Chat history
    async def append_chat_message(
        self,
        session_id: str,
        message: dict,
        max_messages: int = 50
    ):
        """Append a message to chat history."""
        client = await self.get_client()
        key = f"chat:{session_id}"

        await client.rpush(key, json.dumps(message))
        await client.ltrim(key, -max_messages, -1)  # Keep last N messages
        await client.expire(key, 86400)  # Expire after 24 hours

    async def get_chat_history(
        self,
        session_id: str,
        limit: int = 20
    ) -> list:
        """Get chat history for a session."""
        client = await self.get_client()
        messages = await client.lrange(f"chat:{session_id}", -limit, -1)
        return [json.loads(m) for m in messages]

    async def clear_chat_history(self, session_id: str):
        """Clear chat history for a session."""
        client = await self.get_client()
        await client.delete(f"chat:{session_id}")

    # Health check
    async def ping(self) -> bool:
        """Check if Redis is reachable."""
        try:
            client = await self.get_client()
            await client.ping()
            return True
        except Exception:
            return False


# Global instance
redis_client = RedisClient()
