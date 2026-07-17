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
    return json.dumps({
        "id":               event.raw.id,
        "headline":         event.raw.headline,
        "urgency":          event.urgency,
        "importance":       event.importance,
        "sentiment":        event.sentiment,
        "direction":        event.direction,
        "one_liner":        event.one_liner,
        "themes":           event.themes,
        "sectors":          event.sectors,
        "tickers":          event.tickers,
        "broadcast":        event.broadcast,
        "refresh_homepage": event.refresh_homepage,
        "source":           event.raw.source,
        "ts":               event.raw.timestamp.isoformat(),
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


async def _generate(queue: asyncio.Queue):  # type: ignore[type-arg]
    yield "event: connected\ndata: {\"status\":\"connected\"}\n\n"
    while True:
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
