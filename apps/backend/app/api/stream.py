"""
SSE broadcast endpoint — /api/stream/events

Clients connect with EventSource and receive:
  connected     — initial handshake
  alert         — urgency >= 7 triaged event
  update        — urgency 4-6 triaged event
  score_update  — Intelligence Orchestrator recomputed a score (event/
                   company/sector ripple-touched by a new event or trigger)
  heartbeat     — every 30 s keepalive
"""
from __future__ import annotations

import asyncio
import json
import structlog
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.intelligence.event_bus import get_broadcaster, TriagedEvent, ScoreUpdate

log = structlog.get_logger(__name__)
router = APIRouter()


def _serialize_triaged(event: TriagedEvent) -> str:
    # REST (/mie/feed) already returns confidence/market_impact/priority_tier —
    # the live SSE push was missing them, so a freshly-arrived alert would
    # render blank/stale until the next 60s refresh backfilled it. Compute the
    # same priority_score/tier here so live pushes match the REST shape exactly.
    from app.services.intelligence.engine import _compute_priority
    priority_score, priority_tier = _compute_priority(event.urgency, event.importance, None, event.raw.headline)
    return json.dumps({
        "id":               event.raw.id,
        "headline":         event.raw.headline,
        "urgency":          event.urgency,
        "importance":       event.importance,
        "confidence":       event.confidence,
        "sentiment":        event.sentiment,
        "horizon":          event.horizon,
        "market_impact":    event.market_impact,
        "is_structural":    event.is_structural,
        "direction":        event.direction,
        "one_liner":        event.one_liner,
        "themes":           event.themes,
        "sectors":          event.sectors,
        "tickers":          event.tickers,
        "broadcast":        event.broadcast,
        "refresh_homepage": event.refresh_homepage,
        "source":           event.raw.source,
        "ts":               event.raw.timestamp.isoformat(),
        "priority_score":   priority_score,
        "priority_tier":    priority_tier,
    })


def _serialize_score_update(update: ScoreUpdate) -> str:
    return json.dumps({
        "entity_type":      update.entity_type,
        "entity_id":        update.entity_id,
        "model":            update.model,
        "score":            update.score,
        "previous_score":   update.previous_score,
        "confidence":       update.confidence,
        "status":           update.status,
        "data_status":      update.data_status,
        "version":          update.version,
        "top_contributors": update.top_contributors,
        "reasoning":        update.reasoning,
        "trigger":          update.trigger,
        "ts":               update.timestamp.isoformat(),
    })


# One connection must not stay open forever: a 900-second stream was seen holding a worker, and every idle heartbeat is billed egress. EventSource reconnects by itself (the `retry:` hint below),
# so closing after this lifetime costs a client nothing it can notice.
SSE_MAX_SECONDS = 300.0
SSE_RETRY_MS = 5000


async def _generate(queue: asyncio.Queue, max_seconds: float | None = None):  # type: ignore[type-arg]
    import time
    limit = SSE_MAX_SECONDS if max_seconds is None else max_seconds
    started = time.monotonic()
    yield f"retry: {SSE_RETRY_MS}\nevent: connected\ndata: {{\"status\":\"connected\"}}\n\n"
    while True:
        if time.monotonic() - started >= limit:
            yield "event: reconnect\ndata: {\"reason\":\"max_lifetime\"}\n\n"
            break
        try:
            item = await asyncio.wait_for(queue.get(), timeout=30.0)
            if isinstance(item, ScoreUpdate):
                yield f"event: score_update\ndata: {_serialize_score_update(item)}\n\n"
            else:
                etype = "alert" if item.urgency >= 7 else "update"
                yield f"event: {etype}\ndata: {_serialize_triaged(item)}\n\n"
            queue.task_done()
        except asyncio.TimeoutError:
            ts = datetime.now(timezone.utc).isoformat()
            yield f"event: heartbeat\ndata: {{\"ts\":\"{ts}\"}}\n\n"
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.error("sse.error", error=str(exc))
            break


@router.get("/events")
async def stream_events():
    """Connect with EventSource('/api/stream/events') from the frontend."""
    broadcaster = get_broadcaster()
    queue = broadcaster.subscribe()
    log.debug("sse.client_connected", subscribers=broadcaster.subscriber_count)

    async def _cleanup():
        try:
            async for chunk in _generate(queue):
                yield chunk
        finally:
            broadcaster.unsubscribe(queue)
            log.debug("sse.client_disconnected", subscribers=broadcaster.subscriber_count)

    return StreamingResponse(
        _cleanup(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )
