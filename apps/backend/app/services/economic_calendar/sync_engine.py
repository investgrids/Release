"""
The one shared upsert path into EconomicCalendarEvent — Phase 5A.3.

Every source module (rbi_source.py, mospi_source.py, ...) produces a
list of CalendarCandidate values and hands them here; none writes to
the table directly. This is what makes the source-tier precedence rule
(§7 of the Phase 5A audit: "a lower tier may fill a field a higher
tier hasn't already set, never overwrite one a higher tier did")
an enforced invariant instead of a convention every source would
otherwise have to reimplement correctly on its own.

Idempotency and reschedule handling both fall out of one rule: find
the CURRENT row for this identity_key (the partial unique index on
economic_calendar.py guarantees there's at most one). If none exists,
insert. If one exists, only touch it when the incoming source is at
least as authoritative (source_tier) as whatever set the row's current
values — a reschedule from the SAME tier-1 source is a real update; a
tier-3 source disagreeing with an existing tier-1 schedule is silently
ignored for scheduling purposes (recorded in the returned action so a
caller can log it, never applied).

This module intentionally does NOT implement the actual/previous
"revision" path (a new versioned row after release) — Phase 5A.3 is
schedule-only (India MPC/CPI/IIP scheduling), not release-outcome
ingestion. That path is exercised in economic_calendar.py's own model
tests (test_revision_preserves_prior_row_and_links_back) and will be
wired to a real source once release-value ingestion exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.economic_calendar import EconomicCalendarEvent

log = structlog.get_logger(__name__)

# Lower number = more authoritative. A candidate may only update a field
# an existing row already has when its own tier rank is <= the row's
# current tier rank (same or more authoritative source).
_TIER_RANK = {"tier_1": 1, "tier_2": 2, "tier_3": 3}


@dataclass
class CalendarCandidate:
    identity_key: str
    reference_period: str
    title: str
    category: str
    country: str
    scheduled_at: datetime          # UTC-aware
    source_timezone: str
    importance: str
    source: str
    source_tier: str                # "tier_1" | "tier_2" | "tier_3"
    source_url: str | None = None
    region: str | None = None
    unit: str | None = None
    companies: list = field(default_factory=list)
    sectors: list = field(default_factory=list)
    themes: list = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    """SQLite's DateTime(timezone=True) columns round-trip as naive on a
    fresh SELECT (confirmed directly against the raw column: stored as
    text with no offset suffix) — the value itself is correct UTC, only
    the read-back Python object is missing tzinfo. Without this, `!=`
    between a naive existing.scheduled_at and an aware candidate.
    scheduled_at is True on every comparison regardless of the actual
    values (naive/aware datetimes never compare equal), which made every
    idempotent rerun misfire as a "reschedule" — caught by
    test_rbi_rerun_is_idempotent / test_mospi_rerun_is_idempotent
    against real data before this could reach production."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def upsert_calendar_event(db: AsyncSession, candidate: CalendarCandidate) -> dict:
    """Returns {"action": "created" | "updated" | "unchanged" | "skipped_lower_tier", "id": str}."""
    existing = (await db.execute(
        select(EconomicCalendarEvent).where(
            EconomicCalendarEvent.identity_key == candidate.identity_key,
            EconomicCalendarEvent.is_current.is_(True),
        )
    )).scalar_one_or_none()

    if existing is None:
        row = EconomicCalendarEvent(
            id=str(uuid4()), identity_key=candidate.identity_key, reference_period=candidate.reference_period,
            title=candidate.title, category=candidate.category, country=candidate.country, region=candidate.region,
            scheduled_at=candidate.scheduled_at, source_timezone=candidate.source_timezone,
            importance=candidate.importance, unit=candidate.unit, status="scheduled",
            source=candidate.source, source_url=candidate.source_url, source_tier=candidate.source_tier,
            companies=candidate.companies, sectors=candidate.sectors, themes=candidate.themes,
            last_verified_at=_now(),
        )
        db.add(row)
        await db.commit()
        log.info("economic_calendar.created", identity_key=candidate.identity_key, source=candidate.source)
        return {"action": "created", "id": row.id}

    incoming_rank = _TIER_RANK.get(candidate.source_tier, 99)
    existing_rank = _TIER_RANK.get(existing.source_tier, 99)
    if incoming_rank > existing_rank:
        # A less authoritative source disagreeing with an already-set
        # higher-tier schedule — never overwrite. Still worth knowing
        # this happened, hence a distinct action rather than silence.
        log.info("economic_calendar.skipped_lower_tier", identity_key=candidate.identity_key,
                  existing_source=existing.source, incoming_source=candidate.source)
        return {"action": "skipped_lower_tier", "id": existing.id}

    changed = (
        _aware(existing.scheduled_at) != candidate.scheduled_at
        or existing.title != candidate.title
        or existing.importance != candidate.importance
    )
    existing.last_verified_at = _now()
    if changed:
        existing.scheduled_at = candidate.scheduled_at
        existing.source_timezone = candidate.source_timezone
        existing.title = candidate.title
        existing.importance = candidate.importance
        existing.source = candidate.source
        existing.source_url = candidate.source_url
        existing.source_tier = candidate.source_tier
    await db.commit()

    action = "updated" if changed else "unchanged"
    log.info(f"economic_calendar.{action}", identity_key=candidate.identity_key, source=candidate.source)
    return {"action": action, "id": existing.id}
