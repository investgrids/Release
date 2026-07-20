"""AI Search API — POST /api/ai/search"""
from __future__ import annotations

import hashlib
import json
import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.ai_search_service import run_ai_search

router = APIRouter()
log = structlog.get_logger(__name__)

# ── Usage tracking (Ops Dashboard "AI Search" engine card) ────────────────────
# Deliberately separate from ai_service._AI_USAGE, which is the platform-wide
# LLM call counter shared by article generation, thesis/checklist AI, etc. —
# "Total Searches Today" means requests to *this* endpoint, not every AI call.
_SEARCH_STATS: dict = {
    "total": 0, "cache_hits": 0, "errors": 0, "timeouts": 0,
    "latency_ms_total": 0.0,
    "last_query_at": None, "last_success_at": None, "last_error_at": None, "last_error": None,
}


def get_search_stats() -> dict:
    from datetime import datetime, timezone
    resolved = _SEARCH_STATS["total"] - _SEARCH_STATS["cache_hits"]
    return {
        "total_today":     int(_SEARCH_STATS["total"]),
        "cache_hits":      int(_SEARCH_STATS["cache_hits"]),
        "errors":          int(_SEARCH_STATS["errors"]),
        "timeouts":        int(_SEARCH_STATS["timeouts"]),
        "avg_response_ms": round(_SEARCH_STATS["latency_ms_total"] / resolved, 0) if resolved > 0 else 0.0,
        "success_rate":    round((resolved - _SEARCH_STATS["errors"]) / resolved * 100, 1) if resolved > 0 else None,
        "last_query_at":   _SEARCH_STATS["last_query_at"],
        "last_success_at": _SEARCH_STATS["last_success_at"],
        "last_error_at":   _SEARCH_STATS["last_error_at"],
        "last_error":      _SEARCH_STATS["last_error"],
    }


# ── Rate limiting (in-process, per IP) ───────────────────────────────────────
_RL: dict[str, list[float]] = {}
_RL_WINDOW = 60   # seconds
_RL_LIMIT  = 10   # requests per window


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    hits = [t for t in _RL.get(ip, []) if now - t < _RL_WINDOW]
    if len(hits) >= _RL_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait before searching again.")
    hits.append(now)
    _RL[ip] = hits


# ── Redis cache helper ────────────────────────────────────────────────────────
async def _redis_get(key: str):
    try:
        from app.cache import get as cache_get
        return await cache_get(key)
    except Exception:
        return None


async def _redis_set(key: str, value: dict, ttl: int = 1800) -> None:
    try:
        from app.cache import set as cache_set
        await cache_set(key, value, ttl)
    except Exception:
        pass


# ── Request / Response schemas ────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query:    str  = Field(..., min_length=3, max_length=500)
    history:  list[str] = []
    provider: str  = "openrouter"


class SearchResponse(BaseModel):
    query:   str
    cached:  bool = False
    result:  dict


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.post("/search", response_model=SearchResponse)
async def ai_search(
    body: SearchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone

    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    _SEARCH_STATS["total"] += 1
    _SEARCH_STATS["last_query_at"] = datetime.now(timezone.utc).isoformat()

    cache_key = f"ai_search:{hashlib.md5(query.lower().encode()).hexdigest()}"

    # In-process cache (fast path — no Redis round-trip)
    from app.services.ai_search_service import _cget, _ck as _ip_ck
    ip_hit = _cget(_ip_ck(query))
    if ip_hit:
        log.info("ai_search.inprocess_hit", query=query[:50])
        _SEARCH_STATS["cache_hits"] += 1
        _SEARCH_STATS["last_success_at"] = _SEARCH_STATS["last_query_at"]
        return SearchResponse(query=query, cached=True, result=ip_hit)

    # Redis cache check (fallback for multi-instance deployments)
    redis_cached = await _redis_get(cache_key)
    if redis_cached:
        log.info("ai_search.redis_hit", query=query[:50])
        _SEARCH_STATS["cache_hits"] += 1
        _SEARCH_STATS["last_success_at"] = _SEARCH_STATS["last_query_at"]
        return SearchResponse(query=query, cached=True, result=redis_cached)

    # Run pipeline
    log.info("ai_search.request", query=query[:50], ip=ip)
    _t0 = time.monotonic()
    try:
        result = await run_ai_search(query, db)
    except Exception as exc:
        _SEARCH_STATS["errors"] += 1
        _SEARCH_STATS["last_error_at"] = datetime.now(timezone.utc).isoformat()
        _SEARCH_STATS["last_error"] = str(exc)[:200]
        if "timeout" in str(exc).lower() or isinstance(exc, TimeoutError):
            _SEARCH_STATS["timeouts"] += 1
        raise
    _SEARCH_STATS["latency_ms_total"] += (time.monotonic() - _t0) * 1000
    _SEARCH_STATS["last_success_at"] = datetime.now(timezone.utc).isoformat()

    # Store in Redis (30 min) — best-effort, non-blocking
    await _redis_set(cache_key, result, ttl=1800)

    return SearchResponse(query=query, cached=False, result=result)


@router.get("/suggestions")
async def get_suggestions():
    """Return trending search suggestions."""
    return {
        "trending": [
            "What railway stocks benefit from the latest budget?",
            "RBI rate cut impact on banks",
            "Solar energy policy impact on companies",
            "Upcoming IPOs in 2025",
            "Defence sector growth outlook",
            "AI impact on Indian IT companies",
        ],
        "categories": ["Infrastructure", "Banking", "Technology", "Defence", "Energy", "Pharma"],
    }
