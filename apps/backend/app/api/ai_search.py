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
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    cache_key = f"ai_search:{hashlib.md5(query.lower().encode()).hexdigest()}"

    # In-process cache (fast path — no Redis round-trip)
    from app.services.ai_search_service import _cget, _ck as _ip_ck
    ip_hit = _cget(_ip_ck(query))
    if ip_hit:
        log.info("ai_search.inprocess_hit", query=query[:50])
        return SearchResponse(query=query, cached=True, result=ip_hit)

    # Redis cache check (fallback for multi-instance deployments)
    redis_cached = await _redis_get(cache_key)
    if redis_cached:
        log.info("ai_search.redis_hit", query=query[:50])
        return SearchResponse(query=query, cached=True, result=redis_cached)

    # Run pipeline
    log.info("ai_search.request", query=query[:50], ip=ip)
    result = await run_ai_search(query, db)

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
