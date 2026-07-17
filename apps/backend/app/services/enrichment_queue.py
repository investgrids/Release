"""
Enrichment Queue — the hand-off point between the (synchronous) event
pipeline and the (asynchronous) live market-data enrichment worker.

The pipeline must never block on an external market-data request, so it
only ever calls `.push()` here — a non-blocking, bounded put — and moves
on. app/services/enrichment_worker.py is the sole consumer.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class CompanyCandidate:
    symbol: str
    name: str = ""
    ai_impact_score: float = 0.0   # AI's own 0-10ish estimate, used only to RANK which companies are worth a live fetch


@dataclass
class EnrichmentJob:
    """
    One event's bounded enrichment batch. Carries the already-computed
    preliminary EventFeatures object directly (safe — this is an in-process
    asyncio.Queue, not a serialized message broker) so the worker can patch
    in real market_cap_affected/institutional_mentions and rescore without
    re-deriving anything the pipeline already worked out.
    """
    event_id: str
    event_title: str
    sector_names: list
    companies: list                     # list[CompanyCandidate], already bounded/ranked by the orchestrator
    event_features: Any                 # feature_extraction.EventFeatures — mutated in place by the worker
    preliminary_score: Optional[float] = None   # the event's score right before enrichment, for a true before/after delta
    similar_historical_events: list = field(default_factory=list)  # for per-company historical_sensitivity
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EnrichmentQueue:
    """Bounded asyncio.Queue — drops the oldest pending job under sustained overload rather than blocking the producer."""

    def __init__(self, maxsize: int = 200):
        self._queue: asyncio.Queue[EnrichmentJob] = asyncio.Queue(maxsize=maxsize)

    def push(self, job: EnrichmentJob) -> None:
        """Non-blocking by design — the event pipeline calls this and must never await it."""
        try:
            self._queue.put_nowait(job)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(job)
            except asyncio.QueueFull:
                pass

    async def consume(self) -> EnrichmentJob:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    @property
    def size(self) -> int:
        return self._queue.qsize()


_queue: Optional[EnrichmentQueue] = None


def get_enrichment_queue() -> EnrichmentQueue:
    global _queue
    if _queue is None:
        _queue = EnrichmentQueue()
    return _queue
