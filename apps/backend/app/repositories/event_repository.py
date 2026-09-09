"""
EventRepository — single responsibility: all database I/O for event detail data.
No business logic, no AI calls, no transformations beyond raw ORM queries.
"""
from __future__ import annotations

import structlog
from typing import Optional

from sqlalchemy import select, update, or_, String, cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event import (
    Event,
    EventCompany,
    EventGraphEdge,
    EventGraphNode,
    EventNews,
    EventPolicy,
    EventSector,
    EventSimilar,
    EventTimeline,
)

logger = structlog.get_logger(__name__)


class EventRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Core reads ────────────────────────────────────────────────────────────

    async def get_by_id(self, event_id: str) -> Optional[Event]:
        result = await self._db.execute(
            select(Event).where(Event.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Event]:
        # scalar_one_or_none() would raise on a collision — confirmed live,
        # 7 of 1142 slugs are shared by 2-4 different events (generic
        # compliance-filing boilerplate headlines like "To consider and
        # approve the financial results...", where even the id-suffix the
        # slug generator appends wasn't enough to disambiguate). Rather than
        # 500 on those, deterministically take the most recently created
        # match — the slug generator itself is unchanged/out of scope here.
        result = await self._db.execute(
            select(Event).where(Event.slug == slug).order_by(Event.created_at.desc()).limit(1)
        )
        return result.scalars().first()

    # R2 (2026-09-09 freshness/backlog audit): strict oldest-eligible-first
    # FIFO across the whole queue guarantees no retry-eligible row starves
    # forever, but under a large backlog it has the opposite failure mode —
    # backlog rows always have an earlier created_at than any fresh arrival,
    # so 100% of a day's fresh events queued behind the entire backlog with
    # zero same-day coverage (measured live: 5,062 pending, every day's
    # arrivals from 2026-08-30 onward still ~100% pending 9+ days later).
    # A 14-day real-arrival replay (events.created_at, prod, read-only)
    # showed arrivals are bursty batch-injection, not steady (79.8% of
    # 5-min windows empty, spikes up to 25/window, never sustained past
    # 10min) — ruling out a naive fixed per-cycle ratio (wastes capacity on
    # empty windows) in favor of a fresh-first, work-conserving policy with
    # a bounded backlog floor as insurance against sustained overload (a
    # stress-replay at demand > total capacity showed a floor of exactly
    # zero without a guarantee — the same starvation bug this file's
    # existing ordering was built to prevent, just backlog-side instead of
    # fresh-side). Three guarantee frequencies were replayed against the
    # real 14-day trace (every 2/3/4 cycles); N=4 measured strictly best
    # fresh latency (p50=80min vs 110min at N=2) with zero backlog-drain
    # difference in the real regime (all three fully drain the real 5,062
    # backlog in 14 days — fallthrough alone does that work, since real
    # average demand sits well under total capacity; the reservation is
    # inert today and only becomes load-bearing under future sustained
    # overload). None of the three came near a "95% within 1h" aspirational
    # target (best case 44.7%) — that ceiling comes from burst size vs.
    # only _BATCH=3 slots/cycle, not from this reservation, and fixing it
    # would require changing _BATCH or cadence, explicitly out of scope
    # here. _FRESH_WINDOW_HOURS is a proxy for "not yet attempted," not a
    # claim that 23h enrichment is acceptable — last_attempt_at isn't
    # reliably recorded on success, so it can't be used as the queue-state
    # discriminator without a schema change (not done here).
    _FRESH_WINDOW_HOURS = 24
    _BACKLOG_GUARANTEE_EVERY_N_BUCKETS = 4

    async def get_pending_enrichment(self, limit: int = 10, *, now: "datetime | None" = None) -> list[Event]:
        """Free-tier data track, Stage 2 (2026-08-06): now also picks up
        'failed' events and 'processing' events stuck past a stale timeout —
        previously only 'pending' was selected, so a worker crash (or any
        exception escaping run_event_pipeline's own except-block, see its
        docstring) left an event's status at 'processing' forever, and
        get_failed_enrichment existed with zero call sites, meaning a failed
        enrichment was never retried either. Confirmed live: one event
        (nse-d3f8b9d2fc) has been stuck in 'processing' since 2026-07-23 —
        14+ days — before this fix. `updated_at` refreshes on every
        mark_status() call (Column-level onupdate, fires for Core UPDATE
        statements too), so it's a reliable 'when did this last actually
        change' signal for the stale-processing check.

        Retry/backoff (Phase 2, 2026-08-13 audit): two further gaps fixed
        here. First, this used to return every 'failed' row regardless of
        how many times it had already failed or when it last failed —
        no backoff, so a genuinely down AI provider would just get hammered
        again next tick. Now a 'failed' row is only eligible once its
        next_retry_at has passed (see event_pipeline.run_event_pipeline for
        where that's computed), and once retry_count reaches
        _MAX_ENRICHMENT_RETRIES the row graduates to 'failed_permanent' —
        a distinct terminal status, excluded here, but still fully visible
        via get_permanently_failed_enrichment() rather than silently
        vanishing. Second, ordering was `created_at DESC` (newest first)
        across every eligible row — with ingestion running continuously,
        an older retry-eligible failure could be starved indefinitely
        behind a steady stream of newer pending events. Ordering by
        COALESCE(next_retry_at, created_at) ASC instead treats "when this
        row became eligible to run" as one fair FIFO queue, whether that's
        a pending row's creation time or a failed row's backoff expiry.

        R2 two-lane split (2026-09-09): lane membership is determined
        purely by Event.created_at (age) — a retry never promotes an old
        event into the fresh lane, and never demotes a fresh event into
        backlog early; within each lane, the exact same
        COALESCE(next_retry_at, created_at) ASC eligibility/ordering above
        still applies unchanged. Once every _BACKLOG_GUARANTEE_EVERY_N_BUCKETS
        wall-clock buckets (derived from `now`, not a persisted counter —
        restart-safe, but means a genuinely missed bucket has no catch-up:
        this guarantees one qualifying 5-min bucket every ~20min of
        wall-clock time, not literally every 4th executed cycle), exactly
        one eligible backlog row is reserved before fresh is served; every
        other slot is fresh-first. Always work-conserving in both
        directions: an unsatisfiable guarantee (no eligible backlog row)
        falls through to fresh, and any fresh shortfall falls through to
        backlog — so a quiet fresh day still drains backlog at full
        capacity, and a sustained fresh flood still can't fully starve
        backlog. `limit < 1` intentionally bypasses all of this and
        reproduces the exact single-query pre-R2 behavior (including
        whatever SQLAlchemy does with a non-positive LIMIT), since no
        caller relies on lane semantics at a degenerate limit."""
        from datetime import datetime, timedelta, timezone
        from app.pipeline.event_pipeline import _MAX_ENRICHMENT_RETRIES
        from app.core.config import settings
        from sqlalchemy import func

        now = now or datetime.now(timezone.utc)
        stale_before = now - timedelta(minutes=45)
        eligible_at = func.coalesce(Event.next_retry_at, Event.created_at)
        eligibility = or_(
            Event.enrichment_status == "pending",
            (Event.enrichment_status == "failed")
            & (Event.retry_count < _MAX_ENRICHMENT_RETRIES)
            & or_(Event.next_retry_at.is_(None), Event.next_retry_at <= now),
            (Event.enrichment_status == "processing") & (Event.updated_at < stale_before),
        )

        if limit < 1:
            result = await self._db.execute(
                select(Event).where(eligibility).order_by(eligible_at.asc()).limit(limit)
            )
            return list(result.scalars().all())

        cutoff = now - timedelta(hours=self._FRESH_WINDOW_HOURS)
        interval_sec = settings.event_enrichment_interval_sec
        bucket = int(now.timestamp() // interval_sec)
        force_backlog = (bucket % self._BACKLOG_GUARANTEE_EVERY_N_BUCKETS) == 0

        fresh_result = await self._db.execute(
            select(Event)
            .where(eligibility, Event.created_at >= cutoff)
            .order_by(eligible_at.asc())
            .limit(limit)
        )
        fresh_rows = list(fresh_result.scalars().all())

        backlog_result = await self._db.execute(
            select(Event)
            .where(eligibility, Event.created_at < cutoff)
            .order_by(eligible_at.asc())
            .limit(limit)
        )
        backlog_rows = list(backlog_result.scalars().all())

        selected: list[Event] = []
        remaining = limit
        backlog_offset = 0

        if force_backlog and backlog_rows:
            selected.append(backlog_rows[0])
            backlog_offset = 1
            remaining -= 1

        take_fresh = min(remaining, len(fresh_rows))
        selected.extend(fresh_rows[:take_fresh])
        remaining -= take_fresh

        take_backlog = min(remaining, len(backlog_rows) - backlog_offset)
        selected.extend(backlog_rows[backlog_offset:backlog_offset + take_backlog])

        return selected

    async def get_failed_enrichment(self, limit: int = 5) -> list[Event]:
        result = await self._db.execute(
            select(Event)
            .where(Event.enrichment_status == "failed")
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_permanently_failed_enrichment(self, limit: int = 50) -> list[Event]:
        """Terminal enrichment failures — retry_count exhausted, no longer
        retried, but must stay visible in operational monitoring rather
        than disappearing (this is the whole point of a distinct terminal
        status instead of just leaving them at 'failed' forever)."""
        result = await self._db.execute(
            select(Event)
            .where(Event.enrichment_status == "failed_permanent")
            .order_by(Event.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_enrichment_failed(
        self, event_id: str, *, retry_count: int, reason: str, next_retry_at,
    ) -> None:
        """Records a failed enrichment attempt with its retry state.
        next_retry_at=None + status='failed_permanent' signals retries are
        exhausted; otherwise status stays 'failed' and next_retry_at is the
        computed backoff time."""
        status = "failed_permanent" if next_retry_at is None else "failed"
        from datetime import datetime, timezone
        await self._db.execute(
            update(Event).where(Event.id == event_id).values(
                enrichment_status=status,
                retry_count=retry_count,
                last_attempt_at=datetime.now(timezone.utc),
                next_retry_at=next_retry_at,
                last_failure_reason=reason[:64],
            )
        )
        await self._db.commit()

    async def get_similar_by_sectors(
        self, sectors: list[str], exclude_id: str, limit: int = 10
    ) -> list[Event]:
        """Keyword-based candidate lookup; AI will rank afterward."""
        if not sectors:
            return []
        conditions = [cast(Event.sectors, String).ilike(f"%{s}%") for s in sectors]
        result = await self._db.execute(
            select(Event)
            .where(Event.id != exclude_id)
            .where(Event.enrichment_status == "done")
            .where(or_(*conditions))
            .order_by(Event.impact_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ── Related data reads ────────────────────────────────────────────────────

    async def get_companies(self, event_id: str) -> list[EventCompany]:
        result = await self._db.execute(
            select(EventCompany)
            .where(EventCompany.event_id == event_id)
            .order_by(EventCompany.impact_score.desc())
        )
        return list(result.scalars().all())

    async def get_sectors(self, event_id: str) -> list[EventSector]:
        result = await self._db.execute(
            select(EventSector).where(EventSector.event_id == event_id)
        )
        return list(result.scalars().all())

    async def get_timeline(self, event_id: str) -> list[EventTimeline]:
        result = await self._db.execute(
            select(EventTimeline)
            .where(EventTimeline.event_id == event_id)
            .order_by(EventTimeline.order)
        )
        return list(result.scalars().all())

    async def get_news_links(self, event_id: str, limit: int = 10) -> list[EventNews]:
        result = await self._db.execute(
            select(EventNews)
            .where(EventNews.event_id == event_id)
            .order_by(EventNews.relevance_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_graph(
        self, event_id: str
    ) -> tuple[list[EventGraphNode], list[EventGraphEdge]]:
        nodes = await self._db.execute(
            select(EventGraphNode).where(EventGraphNode.event_id == event_id)
        )
        edges = await self._db.execute(
            select(EventGraphEdge).where(EventGraphEdge.event_id == event_id)
        )
        return list(nodes.scalars().all()), list(edges.scalars().all())

    async def get_similar_events(self, event_id: str) -> list[EventSimilar]:
        result = await self._db.execute(
            select(EventSimilar)
            .where(EventSimilar.event_id == event_id)
            .order_by(EventSimilar.similarity_score.desc())
        )
        return list(result.scalars().all())

    async def get_policy_links(self, event_id: str) -> list[EventPolicy]:
        result = await self._db.execute(
            select(EventPolicy).where(EventPolicy.event_id == event_id)
        )
        return list(result.scalars().all())

    async def get_events_by_ids(self, ids: list[str]) -> list[Event]:
        if not ids:
            return []
        result = await self._db.execute(
            select(Event).where(Event.id.in_(ids))
        )
        return list(result.scalars().all())

    # ── Status updates ────────────────────────────────────────────────────────

    async def mark_status(self, event_id: str, status: str) -> None:
        await self._db.execute(
            update(Event).where(Event.id == event_id).values(enrichment_status=status)
        )
        await self._db.commit()

    async def update_core_fields(self, event_id: str, data: dict) -> None:
        await self._db.execute(
            update(Event).where(Event.id == event_id).values(**data)
        )

    async def update_company_score(self, event_id: str, symbol: str, impact_score: Optional[float]) -> None:
        """
        Patch a single event-company row's impact_score in place — unlike
        replace_companies(), this doesn't touch the other companies on the
        same event, so the enrichment worker can update just the top-impact
        symbols it actually fetched live data for.
        """
        await self._db.execute(
            update(EventCompany)
            .where(EventCompany.event_id == event_id, EventCompany.symbol == symbol)
            .values(impact_score=impact_score)
        )

    # ── Writes (pipeline) ────────────────────────────────────────────────────

    async def replace_companies(self, event_id: str, items: list[dict]) -> None:
        await self._db.execute(
            EventCompany.__table__.delete().where(EventCompany.event_id == event_id)
        )
        for item in items:
            self._db.add(EventCompany(event_id=event_id, **item))

    async def replace_sectors(self, event_id: str, items: list[dict]) -> None:
        await self._db.execute(
            EventSector.__table__.delete().where(EventSector.event_id == event_id)
        )
        for item in items:
            self._db.add(EventSector(event_id=event_id, **item))

    async def replace_timeline(self, event_id: str, steps: list[dict]) -> None:
        await self._db.execute(
            EventTimeline.__table__.delete().where(EventTimeline.event_id == event_id)
        )
        for step in steps:
            self._db.add(EventTimeline(event_id=event_id, **step))

    async def replace_graph(
        self, event_id: str, nodes: list[dict], edges: list[dict]
    ) -> None:
        await self._db.execute(
            EventGraphNode.__table__.delete().where(EventGraphNode.event_id == event_id)
        )
        await self._db.execute(
            EventGraphEdge.__table__.delete().where(EventGraphEdge.event_id == event_id)
        )
        for n in nodes:
            self._db.add(EventGraphNode(event_id=event_id, **n))
        for e in edges:
            self._db.add(EventGraphEdge(event_id=event_id, **e))

    async def add_news_links(self, event_id: str, items: list[dict]) -> None:
        for item in items:
            existing = await self._db.execute(
                select(EventNews.id).where(
                    EventNews.event_id == event_id,
                    EventNews.news_id == item["news_id"],
                )
            )
            if existing.scalar_one_or_none() is None:
                self._db.add(EventNews(event_id=event_id, **item))

    async def replace_similar(self, event_id: str, items: list[dict]) -> None:
        await self._db.execute(
            EventSimilar.__table__.delete().where(EventSimilar.event_id == event_id)
        )
        for item in items:
            self._db.add(EventSimilar(event_id=event_id, **item))

    async def replace_policies(
        self, event_id: str, policy_ids: list[int], relevances: list[str]
    ) -> None:
        await self._db.execute(
            EventPolicy.__table__.delete().where(EventPolicy.event_id == event_id)
        )
        for pid, rel in zip(policy_ids, relevances):
            self._db.add(EventPolicy(event_id=event_id, policy_id=pid, relevance=rel))

