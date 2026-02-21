"""
Async Redis client setup.
Used for OTP storage, session caching, and real-time pub/sub.
"""

import redis.asyncio as aioredis

from app.core.config import settings

redis_client = aioredis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
)


async def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client. Used as a FastAPI dependency."""
    return redis_client
