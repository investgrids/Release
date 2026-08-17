"""AI Search API — POST /api/ai/search"""
from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.db.session import get_db
from app.services.ai_search import instrumentation as ai_search_stats

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
# 6G Cutover Gate — compatibility adapter. V2's own generation logic
# (app.services.ai_search_service.run_ai_search) is no longer called here:
# every real V2-only capability was ported to V3 (Slice 1), both known
# non-route callers were migrated (Slices 2-3), and the final V2-dependency
# audit found nothing else depending on V2's own implementation specifically
# — only this route's external CONTRACT ({query, cached, result}) needs to
# keep working unchanged for whatever still calls this exact path. Delegates
# to the canonical run_ai_search_v3 core and reshapes only the envelope,
# not the result body: `result` is typed as a plain dict here (not a strict
# sub-model), so V3's richer response shape (schema_version, response_id,
# decision_intelligence.entity_analyses, etc.) passes through unchanged —
# the same frontend rendering path already needs to handle both shapes
# today (used identically whether NEXT_PUBLIC_AI_SEARCH_V3 is on or off).
# V2's own external pre-checks (in-process + Redis cache, keyed via
# resolve_cache_key) are retired too: run_ai_search_v3 already does its own
# Layer 1 (exact) + Layer 2 (semantic) caching internally and returns
# was_cached — keeping V2's pre-checks alongside would just be a second,
# redundant cache layer with its own separate key scheme.
@router.post("/search", response_model=SearchResponse)
@limiter.limit("10/minute")
async def ai_search(
    request: Request,
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.services.ai_search.pipeline import run_ai_search_v3

    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    ai_search_stats.record_query()
    log.info("ai_search.request", query=query[:50], ip=request.client.host if request.client else "unknown")
    _t0 = time.monotonic()
    try:
        result, was_cached = await run_ai_search_v3(query, db, body.session_context)
    except Exception as exc:
        ai_search_stats.record_error(exc)
        raise
    latency_ms = (time.monotonic() - _t0) * 1000
    if was_cached:
        ai_search_stats.record_cache_hit()
    else:
        ai_search_stats.record_success(latency_ms)

    return SearchResponse(query=query, cached=was_cached, result=result)


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
    """Non-streaming V3 pipeline endpoint — canonical JSON adapter. `/search`
    above is now a thin compatibility wrapper over this same core (6G
    Cutover Gate), not a separate V2 implementation. Frontend usage is
    gated by `NEXT_PUBLIC_AI_SEARCH_V3` (Vercel prod is currently unset, so
    `/search/stream` below, not this route, is what a flag flip would
    actually send browsers to); also used directly by the benchmark runner
    (`--pipeline v3`) and by background callers (comparison_publisher,
    page_intelligence_service) that call `run_ai_search_v3` in-process
    rather than through this HTTP route."""
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
