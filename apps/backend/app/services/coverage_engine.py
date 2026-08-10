"""
Critical Event Coverage Engine.

The audit found two independent event-scoring systems (Event.impact_score,
starved by the paused job_enrich_events; EventTriage, live and unaffected)
but no layer that tracked whether an important EventTriage row actually
ended up covered by a published article — important events could be
silently dropped by the per-cycle cap (max 3), the daily article cap, or
duplicate-detection, with no record that it ever happened.

This module doesn't re-score events — it reuses the existing Intelligence
Priority Queue (app.services.intelligence.engine.compute_priority, already
used by the homepage's live pulse) to classify, then persists an
EventCoverage row and updates it as the event moves through AIPE.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.event_coverage import EventCoverage
from app.services.intelligence.engine import compute_priority

log = structlog.get_logger(__name__)

# Critical/High must never be silently dropped by cycle/daily caps —
# Medium/Low go through the normal pipeline unchanged.
_MUST_COVER_TIERS = ("Critical", "High")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def classify(urgency: int | None, importance: int | None, headline: str | None) -> tuple[int, str]:
    """Thin pass-through to the existing Intelligence Priority Queue —
    kept as its own function here only so coverage_engine has one obvious
    place documenting which tiers are must-cover, not to re-score."""
    return compute_priority(urgency, importance, None, headline)


def is_must_cover(priority_tier: str) -> bool:
    return priority_tier in _MUST_COVER_TIERS


async def register_event(
    db: AsyncSession, *, event_id: str, source: str | None, headline: str,
    urgency: int, importance: int, sectors: list | None, companies: list | None,
) -> EventCoverage | None:
    """Upsert a coverage row right after EventTriage is stored — every
    triaged event gets one, not just the important ones, so 'what did we
    see today' stays a complete, honest answer rather than only tracking
    the events that turned out to matter."""
    try:
        existing = (await db.execute(
            select(EventCoverage).where(EventCoverage.event_id == event_id)
        )).scalar_one_or_none()
        if existing:
            existing.last_checked_at = _now()
            await db.commit()
            return existing

        score, tier = classify(urgency, importance, headline)
        row = EventCoverage(
            id=str(uuid.uuid4()),
            event_id=event_id,
            priority=tier,
            priority_score=score,
            detected_at=_now(),
            source=source,
            event_title=(headline or "")[:512],
            sectors=sectors or [],
            companies=companies or [],
            article_required=is_must_cover(tier),
            coverage_status="DETECTED",
            last_checked_at=_now(),
        )
        db.add(row)
        await db.commit()
        return row
    except Exception as exc:
        log.error("coverage.register_failed", error=str(exc), event_id=event_id)
        return None


async def mark_published(db: AsyncSession, *, event_id: str | None, article_id: str) -> None:
    if not event_id:
        return
    try:
        row = (await db.execute(
            select(EventCoverage).where(EventCoverage.event_id == event_id)
        )).scalar_one_or_none()
        if row:
            row.article_generated = True
            row.article_id = article_id
            row.daily_brief_covered = True
            row.coverage_status = "PUBLISHED"
            row.last_checked_at = _now()
            await db.commit()
    except Exception as exc:
        log.error("coverage.mark_published_failed", error=str(exc), event_id=event_id)


async def mark_covered_by_existing(db: AsyncSession, *, event_id: str | None, article_id: str) -> None:
    if not event_id:
        return
    try:
        row = (await db.execute(
            select(EventCoverage).where(EventCoverage.event_id == event_id)
        )).scalar_one_or_none()
        if row:
            row.article_generated = True
            row.article_id = article_id
            row.daily_brief_covered = True
            row.coverage_status = "COVERED_BY_EXISTING_ARTICLE"
            row.last_checked_at = _now()
            await db.commit()
    except Exception as exc:
        log.error("coverage.mark_covered_failed", error=str(exc), event_id=event_id)


async def find_uncovered_critical(db: AsyncSession, hours: int = 24) -> list[EventCoverage]:
    """Read-only observability check — Critical/High rows detected within
    the window that never got an article. Does not trigger generation
    itself (that's explicitly a later phase, per the implementation
    order)."""
    cutoff = _now() - timedelta(hours=hours)
    rows = (await db.execute(
        select(EventCoverage)
        .where(EventCoverage.priority.in_(list(_MUST_COVER_TIERS)))
        .order_by(EventCoverage.detected_at.desc())
        .limit(500)
    )).scalars().all()
    # SQLite reads DateTime(timezone=True) back tz-naive — same footgun
    # documented elsewhere in this codebase (tools.py, insights.py).
    return [
        r for r in rows
        if r.detected_at and r.detected_at.replace(tzinfo=timezone.utc) >= cutoff
        and r.coverage_status not in ("PUBLISHED", "COVERED_BY_EXISTING_ARTICLE")
    ]


async def funnel_counts(db: AsyncSession, hours: int = 24) -> dict[str, Any]:
    """Publishing funnel observability (Part 25/8) — real counts derived
    from EventCoverage rows detected in the window, not a fabricated or
    estimated figure at any stage."""
    cutoff = _now() - timedelta(hours=hours)
    rows = (await db.execute(
        select(EventCoverage)
        .where(EventCoverage.detected_at >= cutoff - timedelta(days=1))  # generous bound, filtered below
        .limit(2000)
    )).scalars().all()
    recent = [r for r in rows if r.detected_at and r.detected_at.replace(tzinfo=timezone.utc) >= cutoff]

    detected = len(recent)
    by_tier = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    published = 0
    covered_existing = 0
    uncovered_critical = 0
    for r in recent:
        by_tier[r.priority] = by_tier.get(r.priority, 0) + 1
        if r.coverage_status == "PUBLISHED":
            published += 1
        elif r.coverage_status == "COVERED_BY_EXISTING_ARTICLE":
            covered_existing += 1
        if is_must_cover(r.priority) and r.coverage_status not in ("PUBLISHED", "COVERED_BY_EXISTING_ARTICLE"):
            uncovered_critical += 1

    return {
        "window_hours": hours,
        "detected": detected,
        "by_priority": by_tier,
        "critical": by_tier["Critical"],
        "high": by_tier["High"],
        "published": published,
        "covered_by_existing_article": covered_existing,
        "uncovered_critical_or_high": uncovered_critical,
        "generated_at": _now().isoformat(),
    }
