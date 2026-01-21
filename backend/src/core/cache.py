"""
Redis cache management for session state and query caching.

Note: Redis is OPTIONAL for the simple supervisor pattern.
The supervisor can run without Redis - it's only needed for
session caching and rate limiting features.
"""
import json
from typing import Optional, Any
from redis import asyncio as aioredis
from datetime import timedelta

from .config import settings

# Global Redis client
redis_client: Optional[aioredis.Redis] = None

# Track if Redis is available
redis_available: bool = False


async def init_redis() -> None:
    """Initialize Redis connection.

    This is OPTIONAL - the supervisor can run without Redis.
    If connection fails, we log a warning but continue.
    """
    global redis_client, redis_available

    try:
        redis_client = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )

        # Test connection
        await redis_client.ping()

        redis_available = True
        print(f"✓ Redis initialized: {settings.redis_host}:{settings.redis_port}")

    except Exception as e:
        redis_available = False
        redis_client = None
        print(f"⚠ Redis not available (optional): {e}")
        print("  The supervisor will run without caching features (session caching, rate limiting).")


async def close_redis() -> None:
    """Close Redis connection."""
    global redis_client

    if redis_client:
        await redis_client.close()
        print("✓ Redis connection closed")


async def check_redis_health() -> bool:
    """Check Redis connectivity."""
    try:
        if redis_client is None:
            return False

        await redis_client.ping()
        return True
    except Exception as e:
        print(f"✗ Redis health check failed: {e}")
        return False


async def get_redis() -> Optional[aioredis.Redis]:
    """Get Redis client. Returns None if Redis is not available."""
    if not redis_available or redis_client is None:
        return None
    return redis_client


# Session Management
async def set_session(session_id: str, data: dict, ttl_hours: Optional[int] = None) -> None:
    """Store session data in Redis. No-op if Redis unavailable."""
    redis = await get_redis()
    if redis is None:
        return

    ttl = ttl_hours or settings.session_ttl_hours
    await redis.setex(
        f"session:{session_id}",
        timedelta(hours=ttl),
        json.dumps(data)
    )


async def get_session(session_id: str) -> Optional[dict]:
    """Retrieve session data from Redis. Returns None if Redis unavailable."""
    redis = await get_redis()
    if redis is None:
        return None

    data = await redis.get(f"session:{session_id}")
    if data:
        return json.loads(data)
    return None


async def delete_session(session_id: str) -> None:
    """Delete session from Redis. No-op if Redis unavailable."""
    redis = await get_redis()
    if redis is None:
        return

    await redis.delete(f"session:{session_id}")


async def extend_session(session_id: str, ttl_hours: Optional[int] = None) -> bool:
    """Extend session TTL. Returns False if Redis unavailable."""
    redis = await get_redis()
    if redis is None:
        return False

    ttl = ttl_hours or settings.session_ttl_hours
    return await redis.expire(f"session:{session_id}", timedelta(hours=ttl))


# Query Cache Management
async def set_query_cache(query_hash: str, result: Any, ttl_minutes: Optional[int] = None) -> None:
    """Cache query result. No-op if Redis unavailable."""
    if not settings.enable_query_cache:
        return

    redis = await get_redis()
    if redis is None:
        return

    ttl = ttl_minutes or settings.query_cache_ttl_minutes
    await redis.setex(
        f"query:{query_hash}",
        timedelta(minutes=ttl),
        json.dumps(result)
    )


async def get_query_cache(query_hash: str) -> Optional[Any]:
    """Retrieve cached query result. Returns None if Redis unavailable."""
    if not settings.enable_query_cache:
        return None

    redis = await get_redis()
    if redis is None:
        return None

    data = await redis.get(f"query:{query_hash}")
    if data:
        return json.loads(data)
    return None


async def invalidate_query_cache(query_hash: str) -> None:
    """Invalidate specific query cache. No-op if Redis unavailable."""
    redis = await get_redis()
    if redis is None:
        return

    await redis.delete(f"query:{query_hash}")


async def invalidate_all_query_cache() -> None:
    """Invalidate all query cache. No-op if Redis unavailable."""
    redis = await get_redis()
    if redis is None:
        return

    keys = await redis.keys("query:*")
    if keys:
        await redis.delete(*keys)


# Rate Limiting
async def check_rate_limit(user_id: str, limit_per_minute: Optional[int] = None) -> bool:
    """Check if user is within rate limit. Returns True (allowed) if Redis unavailable."""
    redis = await get_redis()
    if redis is None:
        return True  # Allow if no rate limiting available

    limit = limit_per_minute or settings.rate_limit_requests_per_minute
    key = f"ratelimit:{user_id}:minute"
    current = await redis.incr(key)

    if current == 1:
        await redis.expire(key, 60)

    return current <= limit


async def increment_token_usage(user_id: str, tokens: int) -> int:
    """Increment user's daily token usage. Returns 0 if Redis unavailable."""
    redis = await get_redis()
    if redis is None:
        return 0

    key = f"tokens:{user_id}:daily"
    current = await redis.incrby(key, tokens)

    if current == tokens:  # First increment
        await redis.expire(key, timedelta(days=1))

    return current


async def get_token_usage(user_id: str) -> int:
    """Get user's daily token usage. Returns 0 if Redis unavailable."""
    redis = await get_redis()
    if redis is None:
        return 0

    usage = await redis.get(f"tokens:{user_id}:daily")
    return int(usage) if usage else 0


async def check_token_limit(user_id: str) -> bool:
    """Check if user is within daily token limit. Returns True if Redis unavailable."""
    if not redis_available:
        return True

    usage = await get_token_usage(user_id)
    return usage < settings.rate_limit_tokens_per_day


# Working Memory (short-term context)
async def set_working_memory(user_id: str, context: dict, ttl_hours: int = 1) -> None:
    """Store working memory for user. No-op if Redis unavailable."""
    redis = await get_redis()
    if redis is None:
        return

    await redis.setex(
        f"working_memory:{user_id}",
        timedelta(hours=ttl_hours),
        json.dumps(context)
    )


async def get_working_memory(user_id: str) -> Optional[dict]:
    """Retrieve working memory for user. Returns None if Redis unavailable."""
    redis = await get_redis()
    if redis is None:
        return None

    data = await redis.get(f"working_memory:{user_id}")
    if data:
        return json.loads(data)
    return None


async def append_to_working_memory(user_id: str, message: dict) -> None:
    """Append message to working memory. No-op if Redis unavailable."""
    if not redis_available:
        return

    memory = await get_working_memory(user_id) or {"messages": []}
    memory["messages"].append(message)

    # Keep only last N messages
    max_messages = 20
    if len(memory["messages"]) > max_messages:
        memory["messages"] = memory["messages"][-max_messages:]

    await set_working_memory(user_id, memory)
