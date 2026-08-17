"""AI Search API — POST /api/ai/search"""
from __future__ import annotations

import json
import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.db.session import get_db
from app.services.ai_search import instrumentation as ai_search_stats
from app.services.ai_search_service import run_ai_search

router = APIRouter()
log = structlog.get_logger(__name__)

# ── Usage tracking (Ops Dashboard "AI Search" engine card) ────────────────────
# 6G Cutover Gate: counters live in app.services.ai_search.instrumentation, a
# shared module V2 (below), /search/v3, and /search/stream all report into —
# NOT reset here, NOT reimplemented here. "Total Searches Today" means
# requests to any of these 3 routes, not every platform-wide AI call (that's
# ai_service._AI_USAGE, a separate counter). get_search_stats() is kept here,
# under its original import path, purely so app/api/publishing.py's existing
# `from app.api.ai_search import get_search_stats` needs no change.
def get_search_stats() -> dict:
    return ai_search_stats.get_stats()


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
    # Phase 1.7 — companies/sectors etc. already discussed this browser
    # session (client-held, sessionStorage-backed — never persisted server-
    # side). See session_context.resolve_context for exactly how this is
    # used; None/absent behaves identically to before this field existed.
    session_context: dict | None = None


class SearchResponse(BaseModel):
    query:   str
    cached:  bool = False
    result:  dict


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.post("/search", response_model=SearchResponse)
@limiter.limit("10/minute")
async def ai_search(
    request: Request,
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    ai_search_stats.record_query()

    # P2: entity/session-context-aware key (same resolution run_ai_search
    # does internally) — a query-text-only key here would let two sessions
    # asking identical literal text but resolving to different prior
    # companies collide on the same cached answer, bypassing run_ai_search's
    # own cache-key fix entirely since a hit here returns before
    # run_ai_search (and its entity resolution) ever runs.
    from app.services.ai_search_service import _cget, resolve_cache_key
    resolved_key = resolve_cache_key(query, body.session_context)
    cache_key = f"ai_search:{resolved_key}"

    # In-process cache (fast path — no Redis round-trip)
    ip_hit = _cget(resolved_key)
    if ip_hit:
        log.info("ai_search.inprocess_hit", query=query[:50])
        ai_search_stats.record_cache_hit()
        return SearchResponse(query=query, cached=True, result=ip_hit)

    # Redis cache check (fallback for multi-instance deployments)
    redis_cached = await _redis_get(cache_key)
    if redis_cached:
        log.info("ai_search.redis_hit", query=query[:50])
        ai_search_stats.record_cache_hit()
        return SearchResponse(query=query, cached=True, result=redis_cached)

    # Run pipeline
    log.info("ai_search.request", query=query[:50], ip=request.client.host if request.client else "unknown")
    _t0 = time.monotonic()
    try:
        result = await run_ai_search(query, db, session_context=body.session_context)
    except Exception as exc:
        ai_search_stats.record_error(exc)
        raise
    ai_search_stats.record_success((time.monotonic() - _t0) * 1000)

    # Store in Redis (30 min) — best-effort, non-blocking. Skip caching a
    # degraded (LLM-synthesis-failed) result so a retry shortly after can
    # get a real answer instead of the same fallback for 30 more minutes.
    if not result.get("synthesis_incomplete"):
        await _redis_set(cache_key, result, ttl=1800)

    return SearchResponse(query=query, cached=False, result=result)


class SearchResponseV3(BaseModel):
    query:  str
    cached: bool = False
    result: dict
    # Delivery-context fields for this specific serve — surfaced so the
    # frontend can attach them to feedback submissions without the backend
    # needing to re-derive "what happened this call" later (see
    # AISearchFeedback's docstring on why capturing this per-serve matters).
    response_id: str | None = None
    latency_ms: float | None = None
    provider: str | None = None


@router.post("/search/v3", response_model=SearchResponseV3)
@limiter.limit("10/minute")
async def ai_search_v3(
    request: Request,
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Non-streaming V3 pipeline endpoint — coexists with `/search` (V2).
    Frontend usage is gated by `NEXT_PUBLIC_AI_SEARCH_V3` (Vercel prod is
    currently unset, so `/search/stream` below, not this route, is what a
    flag flip would actually send browsers to); also used directly by the
    benchmark runner (`--pipeline v3`) and by background callers
    (comparison_publisher, page_intelligence_service) that call
    `run_ai_search_v3` in-process rather than through this HTTP route."""
    from app.services.ai_search.pipeline import run_ai_search_v3

    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    ai_search_stats.record_query()
    log.info("ai_search_v3.request", query=query[:50], ip=request.client.host if request.client else "unknown")
    _t0 = time.monotonic()
    try:
        result, was_cached = await run_ai_search_v3(query, db, body.session_context)
    except Exception as exc:
        log.warning("ai_search_v3.error", exc=str(exc)[:200])
        ai_search_stats.record_error(exc)
        raise
    latency_ms = round((time.monotonic() - _t0) * 1000, 1)
    log.info("ai_search_v3.done", latency_s=round(latency_ms / 1000, 1), query=query[:50], cached=was_cached)
    if was_cached:
        ai_search_stats.record_cache_hit()
    else:
        ai_search_stats.record_success(latency_ms)

    # last_provider is a shared, best-effort global (app.services.ai_service
    # ._AI_USAGE) — accurate for the common single-request-in-flight case,
    # can race under real concurrent load. Fine for this: it feeds internal
    # analytics, not billing. None on a cache hit — no live LLM call happened.
    from app.services.ai_service import _AI_USAGE
    provider = None if was_cached else _AI_USAGE.get("last_provider")

    return SearchResponseV3(
        query=query, cached=was_cached, result=result,
        response_id=(result or {}).get("response_id"), latency_ms=latency_ms, provider=provider,
    )


@router.get("/search/stream")
async def ai_search_stream(
    request: Request,
    q: str,
    session_context: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """SSE version of the v3 pipeline. GET + query param, not POST + body —
    `EventSource` (the browser API this is built for) can only issue GET
    requests; a 500-char query fits comfortably in a URL. Emits a `stage`
    event at each real pipeline checkpoint (see pipeline.STAGE_LABELS —
    genuine backend progress, never a fake timer) and one final `answer`
    event with the complete v3 response, then `done`.

    This is coarse (stage-progress) streaming, not token-level incremental
    rendering — the LLM call itself isn't streamed in Phase 1 (see the V3
    plan's own note on this tradeoff). `/api/ai/search/v3` (POST, non-
    streaming) still exists for the benchmark runner and any caller that
    doesn't need live progress."""
    import json as _json

    from app.services.ai_search.pipeline import _run_v3_steps

    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if len(query) > 500:
        raise HTTPException(status_code=400, detail="Query too long (max 500 characters).")

    # EventSource can only GET, so session_context travels as a JSON-encoded
    # query param (same pattern the frontend hook already uses for `history`).
    # Malformed/oversized input degrades to "no session context" rather than
    # failing the whole search — this is a UX enrichment, not a requirement.
    parsed_session_context: dict | None = None
    if session_context and len(session_context) <= 4000:
        try:
            parsed_session_context = _json.loads(session_context)
        except Exception:
            parsed_session_context = None

    async def _event_stream():
        ai_search_stats.record_query()
        _t0 = time.monotonic()
        stages_seen: set[str] = set()
        try:
            async for stage, label, payload in _run_v3_steps(query, db, parsed_session_context):
                stages_seen.add(stage)
                if payload is None:
                    yield f"event: stage\ndata: {_json.dumps({'stage': stage, 'label': label})}\n\n"
                else:
                    # Same "reasoning" stage absent == cache hit signal used
                    # by run_ai_search_v3 for the non-streaming route.
                    was_cached = "reasoning" not in stages_seen
                    latency_ms = round((time.monotonic() - _t0) * 1000, 1)
                    if was_cached:
                        ai_search_stats.record_cache_hit()
                    else:
                        ai_search_stats.record_success(latency_ms)
                    from app.services.ai_service import _AI_USAGE
                    provider = None if was_cached else _AI_USAGE.get("last_provider")
                    envelope = {
                        "result": payload,
                        "cached": was_cached,
                        "response_id": payload.get("response_id"),
                        "latency_ms": latency_ms,
                        "provider": provider,
                    }
                    yield f"event: answer\ndata: {_json.dumps(envelope)}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as exc:  # noqa: BLE001 — must reach the client as an SSE error event, not a bare 500
            log.warning("ai_search_v3.stream_error", exc=str(exc)[:200], query=query[:50])
            ai_search_stats.record_error(exc)
            yield f"event: error\ndata: {_json.dumps({'detail': str(exc)[:200]})}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


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
