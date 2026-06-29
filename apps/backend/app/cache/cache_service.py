"""
CacheService — typed Redis wrapper with TTL management, structured logging,
and graceful degradation when Redis is unavailable.

All methods accept/return plain Python dicts or lists (JSON-serialisable).
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

import structlog

from app.core.redis import get_redis

log = structlog.get_logger(__name__)

# ── Cache key namespaces ───────────────────────────────────────────────────────
DASHBOARD_KEY        = "dashboard:v1"
DASHBOARD_MARKET_KEY = "dashboard:market:v1"
DASHBOARD_EVENTS_KEY = "dashboard:events:v1"
DASHBOARD_RADAR_KEY  = "dashboard:radar:v1"
DASHBOARD_STORIES_KEY = "dashboard:stories:v1"
DASHBOARD_AI_KEY     = "dashboard:ai_summary:v1"

# ── TTLs (seconds) ─────────────────────────────────────────────────────────────
TTL_DASHBOARD = 900    # 15 min — precomputed at 7 AM
TTL_MARKET    = 60     # 1 min  — live index quotes
TTL_NEWS      = 600    # 10 min
TTL_EVENT     = 900    # 15 min
TTL_RADAR     = 900    # 15 min
TTL_AI        = 900    # 15 min
TTL_DEFAULT   = 300    # 5 min


async def get(key: str) -> Optional[Any]:
    """Return cached value or None on miss / Redis unavailable."""
    r = await get_redis()
    if r is None:
        return None
    try:
        t0 = time.perf_counter()
        raw = await r.get(key)
        elapsed = (time.perf_counter() - t0) * 1000
        if raw:
            log.debug("cache.hit", key=key, latency_ms=round(elapsed, 2))
            return json.loads(raw)
        log.debug("cache.miss", key=key)
        return None
    except Exception as exc:
        log.warning("cache.get_error", key=key, error=str(exc))
        return None


async def set(key: str, value: Any, ttl: int = TTL_DEFAULT) -> bool:
    """Store value with TTL. Returns True on success."""
    r = await get_redis()
    if r is None:
        return False
    try:
        t0 = time.perf_counter()
        await r.set(key, json.dumps(value, default=str), ex=ttl)
        elapsed = (time.perf_counter() - t0) * 1000
        log.info("cache.set", key=key, ttl=ttl, latency_ms=round(elapsed, 2))
        return True
    except Exception as exc:
        log.warning("cache.set_error", key=key, error=str(exc))
        return False


async def delete(key: str) -> None:
    r = await get_redis()
    if r is None:
        return
    try:
        await r.delete(key)
        log.debug("cache.delete", key=key)
    except Exception as exc:
        log.warning("cache.delete_error", key=key, error=str(exc))


async def delete_pattern(pattern: str) -> int:
    """Delete all keys matching a glob pattern. Returns count deleted."""
    r = await get_redis()
    if r is None:
        return 0
    try:
        keys = await r.keys(pattern)
        if keys:
            await r.delete(*keys)
        log.info("cache.delete_pattern", pattern=pattern, count=len(keys))
        return len(keys)
    except Exception as exc:
        log.warning("cache.delete_pattern_error", pattern=pattern, error=str(exc))
        return 0


async def get_or_compute(key: str, compute, ttl: int = TTL_DEFAULT) -> Any:
    """
    Cache-aside pattern: return cached value or call compute() and cache result.
    compute must be a coroutine factory (async callable).
    """
    cached = await get(key)
    if cached is not None:
        return cached
    value = await compute()
    if value is not None:
        await set(key, value, ttl)
    return value
