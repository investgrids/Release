"""
Redis client — optional. Falls back silently when Redis is not available.
All cache helpers return None on miss, so callers decide what to do.
"""
import json
import logging
import time
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[aioredis.Redis] = None
_unavailable_until: float = 0.0  # backoff: skip retries until this timestamp


async def get_redis() -> Optional[aioredis.Redis]:
    global _client, _unavailable_until
    if _client is not None:
        return _client
    # Avoid 2-second TCP timeout on every call when Redis is known unavailable
    if time.time() < _unavailable_until:
        return None
    try:
        _client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
        )
        await _client.ping()
    except Exception:
        logger.warning("Redis unavailable — caching disabled")
        _client = None
        _unavailable_until = time.time() + 300  # retry in 5 minutes
    return _client


async def cache_get(key: str) -> Optional[Any]:
    r = await get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def cache_set(key: str, value: Any, ttl: int = settings.redis_ttl_default) -> None:
    r = await get_redis()
    if r is None:
        return
    try:
        await r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        pass


async def cache_delete(key: str) -> None:
    r = await get_redis()
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception:
        pass


async def close_redis() -> None:
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:
            pass
        _client = None
