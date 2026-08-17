"""
MacroRelease persistence for macro-rate series — Phase 5C.

Rate sources here are event-driven or weekly (RBI repo rate, Fed funds,
India 10Y G-Sec) — re-fetching daily would mostly re-observe the same
value. upsert_rate_observation() writes a new MacroRelease row only
when the value genuinely differs from the latest stored row for that
metric, so the table naturally accumulates one row per real change
(a real, sparse history) instead of one row per sync run. US Treasury
2Y/10Y are deliberately NOT persisted here — a single live fetch
already returns the full year's daily series (see us_treasury_source.py),
so there is nothing this module would add beyond duplicate storage.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.macro_release import MacroRelease

log = structlog.get_logger(__name__)


async def upsert_rate_observation(
    db: AsyncSession,
    *,
    metric: str,
    value: float,
    observation_date: date,
    unit: str,
    source: str,
    source_url: str | None,
    geography: str,
    headline: str,
) -> dict:
    """Returns {"action": "created" | "unchanged", "id": str}. Never
    updates an existing row's value in place — a genuine new value
    always becomes a new row (this is a real, dated observation series,
    not a mutable "current state" cell), matching MacroRelease's own
    append-only shape used elsewhere in this codebase."""
    latest = (await db.execute(
        select(MacroRelease)
        .where(MacroRelease.metric == metric, MacroRelease.geography == geography)
        .order_by(MacroRelease.release_date.desc())
        .limit(1)
    )).scalar_one_or_none()

    if latest is not None and latest.release_value == value:
        return {"action": "unchanged", "id": latest.id}

    row = MacroRelease(
        id=str(uuid4()),
        metric=metric,
        release_value=value,
        previous_value=latest.release_value if latest is not None else None,
        expected_value=None,
        unit=unit,
        period=observation_date.isoformat(),
        geography=geography,
        importance="High",
        affected_sectors=[],
        affected_companies=[],
        source=source,
        source_url=source_url,
        headline=headline,
        raw_summary=None,
        release_date=datetime(observation_date.year, observation_date.month, observation_date.day, tzinfo=timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.commit()
    log.info("macro_rates.observation_created", metric=metric, value=value, observation_date=observation_date.isoformat())
    return {"action": "created", "id": row.id}


async def get_rate_history(db: AsyncSession, *, metric: str, geography: str, limit: int = 20) -> list[MacroRelease]:
    """Newest first."""
    rows = (await db.execute(
        select(MacroRelease)
        .where(MacroRelease.metric == metric, MacroRelease.geography == geography)
        .order_by(MacroRelease.release_date.desc())
        .limit(limit)
    )).scalars().all()
    return list(rows)
