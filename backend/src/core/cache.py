"""
Redis cache management for session state and query caching.
"""
import json
from typing import Optional, Any
from redis import asyncio as aioredis
from datetime import timedelta

from .config import settings

# Global Redis client
redis_client: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    """Initialize Redis connection."""
    global redis_client

    redis_client = await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
        socket_keepalive=True,
        socket_connect_timeout=5,
        retry_on_timeout=True,
    )

    print(f"✓ Redis initialized: {settings.redis_host}:{settings.redis_port}")


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


async def get_redis() -> aioredis.Redis:
    """Get Redis client."""
    if redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return redis_client


# Session Management
async def set_session(session_id: str, data: dict, ttl_hours: Optional[int] = None) -> None:
    """Store session data in Redis."""
    ttl = ttl_hours or settings.session_ttl_hours
    redis = await get_redis()

    await redis.setex(
        f"session:{session_id}",
        timedelta(hours=ttl),
        json.dumps(data)
    )


async def get_session(session_id: str) -> Optional[dict]:
    """Retrieve session data from Redis."""
    redis = await get_redis()
    data = await redis.get(f"session:{session_id}")

    if data:
        return json.loads(data)
    return None


async def delete_session(session_id: str) -> None:
    """Delete session from Redis."""
    redis = await get_redis()
    await redis.delete(f"session:{session_id}")


async def extend_session(session_id: str, ttl_hours: Optional[int] = None) -> bool:
    """Extend session TTL."""
    ttl = ttl_hours or settings.session_ttl_hours
    redis = await get_redis()

    return await redis.expire(f"session:{session_id}", timedelta(hours=ttl))


# Query Cache Management
async def set_query_cache(query_hash: str, result: Any, ttl_minutes: Optional[int] = None) -> None:
    """Cache query result."""
    if not settings.enable_query_cache:
        return

    ttl = ttl_minutes or settings.query_cache_ttl_minutes
    redis = await get_redis()

    await redis.setex(
        f"query:{query_hash}",
        timedelta(minutes=ttl),
        json.dumps(result)
    )


async def get_query_cache(query_hash: str) -> Optional[Any]:
    """Retrieve cached query result."""
    if not settings.enable_query_cache:
        return None

    redis = await get_redis()
    data = await redis.get(f"query:{query_hash}")

    if data:
        return json.loads(data)
    return None


async def invalidate_query_cache(query_hash: str) -> None:
    """Invalidate specific query cache."""
    redis = await get_redis()
    await redis.delete(f"query:{query_hash}")


async def invalidate_all_query_cache() -> None:
    """Invalidate all query cache."""
    redis = await get_redis()
    keys = await redis.keys("query:*")

    if keys:
        await redis.delete(*keys)


# Rate Limiting
async def check_rate_limit(user_id: str, limit_per_minute: Optional[int] = None) -> bool:
    """Check if user is within rate limit."""
    limit = limit_per_minute or settings.rate_limit_requests_per_minute
    redis = await get_redis()

    key = f"ratelimit:{user_id}:minute"
    current = await redis.incr(key)

    if current == 1:
        await redis.expire(key, 60)

    return current <= limit


async def increment_token_usage(user_id: str, tokens: int) -> int:
    """Increment user's daily token usage."""
    redis = await get_redis()
    key = f"tokens:{user_id}:daily"

    current = await redis.incrby(key, tokens)

    if current == tokens:  # First increment
        await redis.expire(key, timedelta(days=1))

    return current


async def get_token_usage(user_id: str) -> int:
    """Get user's daily token usage."""
    redis = await get_redis()
    usage = await redis.get(f"tokens:{user_id}:daily")

    return int(usage) if usage else 0


async def check_token_limit(user_id: str) -> bool:
    """Check if user is within daily token limit."""
    usage = await get_token_usage(user_id)
    return usage < settings.rate_limit_tokens_per_day


# Working Memory (short-term context)
async def set_working_memory(user_id: str, context: dict, ttl_hours: int = 1) -> None:
    """Store working memory for user."""
    redis = await get_redis()

    await redis.setex(
        f"working_memory:{user_id}",
        timedelta(hours=ttl_hours),
        json.dumps(context)
    )


async def get_working_memory(user_id: str) -> Optional[dict]:
    """Retrieve working memory for user."""
    redis = await get_redis()
    data = await redis.get(f"working_memory:{user_id}")

    if data:
        return json.loads(data)
    return None


async def append_to_working_memory(user_id: str, message: dict) -> None:
    """Append message to working memory."""
    memory = await get_working_memory(user_id) or {"messages": []}
    memory["messages"].append(message)

    # Keep only last N messages
    max_messages = 20
    if len(memory["messages"]) > max_messages:
        memory["messages"] = memory["messages"][-max_messages:]

    await set_working_memory(user_id, memory)
