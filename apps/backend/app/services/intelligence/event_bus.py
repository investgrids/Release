"""
EventIngestionBus — all event sources push RawEvent here; TriageWorker consumes.
EventBroadcaster — fan-out to SSE connections; TriageWorker pushes TriagedEvent here.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class RawEvent:
    """Normalized event before AI triage."""
    id: str
    headline: str
    summary: str
    source: str                              # news | policy | price | synthetic
    source_url: str = ""
    sectors: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)
    raw_impact: float = 5.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoreUpdate:
    """
    Broadcast whenever the Intelligence Orchestrator (re)computes a score
    for an entity — powers live score changes on the frontend (Homepage,
    Companies, Themes, Events, ...) without a page refresh. Distinct from
    TriagedEvent (a new raw news/event item); this is "a score changed",
    which can fire with no new news at all (e.g. a ripple recompute).
    """
    entity_type: str                    # "event" | "company" | "sector" | "theme" | "opportunity" | "risk"
    entity_id: str
    model: str                          # "event_impact" | "company_impact" | "ripple_strength" | ...
    score: Optional[float]
    previous_score: Optional[float]
    confidence: Optional[float]
    status: str                         # "ok" | "insufficient_data" | "ripple_signal"
    version: str
    top_contributors: list = field(default_factory=list)
    reasoning: list = field(default_factory=list)
    trigger: str = "unknown"            # "new_event" | "new_news" | "earnings" | "market_close" | "policy_change" | "ripple_propagation"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TriagedEvent:
    """Event after AI triage — ready for broadcast or storage."""
    raw: RawEvent
    urgency: int
    importance: int
    confidence: int
    sentiment: str
    horizon: str
    market_impact: str
    is_structural: bool
    direction: str
    one_liner: str
    themes: list[str]
    sectors: list[str]
    tickers: list[str]
    broadcast: bool          # urgency >= 7
    refresh_homepage: bool   # urgency >= 8


class EventIngestionBus:
    """Single asyncio.Queue — all sources push here, TriageWorker consumes."""

    def __init__(self, maxsize: int = 500):
        self._queue: asyncio.Queue[RawEvent] = asyncio.Queue(maxsize=maxsize)

    async def push(self, event: RawEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            await self._queue.put(event)

    async def consume(self) -> RawEvent:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    @property
    def size(self) -> int:
        return self._queue.qsize()


class EventBroadcaster:
    """Fan-out to all active SSE connections."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def broadcast(self, event: "TriagedEvent | ScoreUpdate") -> None:
        dead: set[asyncio.Queue] = set()
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.add(q)
        for q in dead:
            self._subscribers.discard(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# ── Singletons ────────────────────────────────────────────────────────────────

_bus: Optional[EventIngestionBus] = None
_broadcaster: Optional[EventBroadcaster] = None


def get_event_bus() -> EventIngestionBus:
    global _bus
    if _bus is None:
        _bus = EventIngestionBus()
    return _bus


def get_broadcaster() -> EventBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster()
    return _broadcaster
