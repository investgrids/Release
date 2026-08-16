"""
Phase 5A.4 — real, live proof of the full US ingestion semantics, same
rigor as the India source tests: official source -> parse -> normalize
-> identity_key -> upsert/version -> source_tier -> last_verified_at ->
real DB row -> idempotent rerun -> correct reschedule -> source-failure
isolation. Covers all three US sources: FOMC, BLS CPI, BLS jobs (NFP).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.db.models.economic_calendar import EconomicCalendarEvent
from app.services.economic_calendar.sync_engine import upsert_calendar_event, CalendarCandidate
from app.services.economic_calendar.fed_source import fetch_fomc_candidates
from app.services.economic_calendar.bls_source import fetch_us_cpi_candidates, fetch_us_jobs_candidates


async def _cleanup(prefix: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like(f"{prefix}%")))
        await db.commit()


def _aware(dt: datetime) -> datetime:
    """See test_economic_calendar_india_sources_live.py's identical
    helper — SQLite's DateTime(timezone=True) round-trips naive on a
    fresh read; the stored value itself is correct UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


SOURCES = [
    ("fomc:", fetch_fomc_candidates, "fed"),
    ("us_cpi:", fetch_us_cpi_candidates, "bls"),
    ("us_jobs:", fetch_us_jobs_candidates, "bls"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix,fetch_fn,expected_source", SOURCES)
async def test_real_ingestion_creates_events(prefix, fetch_fn, expected_source):
    await _cleanup(prefix)
    candidates = await fetch_fn()
    assert candidates, f"{prefix} source returned nothing — real site may be unreachable right now"

    async with AsyncSessionLocal() as db:
        results = [await upsert_calendar_event(db, c) for c in candidates]
    assert all(r["action"] == "created" for r in results)

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like(f"{prefix}%")))).scalars().all()
    assert len(rows) == len(candidates)
    assert all(r.source_tier == "tier_1" for r in rows)
    assert all(r.source == expected_source for r in rows)
    assert all(r.source_timezone == "America/New_York" for r in rows)
    assert len({r.identity_key for r in rows}) == len(rows)   # no collisions

    await _cleanup(prefix)


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix,fetch_fn,expected_source", SOURCES)
async def test_rerun_is_idempotent(prefix, fetch_fn, expected_source):
    await _cleanup(prefix)
    candidates = await fetch_fn()
    assert candidates

    async with AsyncSessionLocal() as db:
        for c in candidates:
            await upsert_calendar_event(db, c)

    async with AsyncSessionLocal() as db:
        second_results = [await upsert_calendar_event(db, c) for c in candidates]
    assert all(r["action"] == "unchanged" for r in second_results)

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like(f"{prefix}%")))).scalars().all()
    assert len(rows) == len(candidates)

    await _cleanup(prefix)


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix,fetch_fn,expected_source", SOURCES)
async def test_reschedule_updates_in_place(prefix, fetch_fn, expected_source):
    await _cleanup(prefix)
    candidates = await fetch_fn()
    assert candidates
    first = candidates[0]

    async with AsyncSessionLocal() as db:
        created = await upsert_calendar_event(db, first)

    postponed = CalendarCandidate(**{**first.__dict__, "scheduled_at": first.scheduled_at + timedelta(days=1)})
    async with AsyncSessionLocal() as db:
        updated = await upsert_calendar_event(db, postponed)
    assert updated["action"] == "updated"
    assert updated["id"] == created["id"]

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key == first.identity_key))).scalars().all()
    assert len(rows) == 1
    assert _aware(rows[0].scheduled_at) == postponed.scheduled_at

    await _cleanup(prefix)


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix,fetch_fn,expected_source", SOURCES)
async def test_source_failure_leaves_existing_rows_untouched(prefix, fetch_fn, expected_source):
    await _cleanup(prefix)
    candidates = await fetch_fn()
    assert candidates

    async with AsyncSessionLocal() as db:
        for c in candidates:
            await upsert_calendar_event(db, c)
    async with AsyncSessionLocal() as db:
        before = {r.identity_key: (_aware(r.scheduled_at), _aware(r.last_verified_at)) for r in (
            await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like(f"{prefix}%")))
        ).scalars().all()}

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=Exception("simulated network failure"))):
        failed_candidates = await fetch_fn()
    assert failed_candidates == []

    async with AsyncSessionLocal() as db:
        after = {r.identity_key: (_aware(r.scheduled_at), _aware(r.last_verified_at)) for r in (
            await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like(f"{prefix}%")))
        ).scalars().all()}
    assert before == after

    await _cleanup(prefix)


@pytest.mark.asyncio
async def test_fomc_decision_time_is_dst_correct_against_real_data():
    """Real-data confirmation (not just the synthetic proof in
    test_economic_calendar_dst.py) — the live FOMC schedule spans both
    EST and EDT meetings; their real UTC hours must differ by exactly
    one, matching each meeting's actual season."""
    candidates = await fetch_fomc_candidates()
    assert candidates
    winter_meetings = [c for c in candidates if c.scheduled_at.month in (1, 12)]
    summer_meetings = [c for c in candidates if c.scheduled_at.month in (6, 7)]
    assert winter_meetings and summer_meetings
    # 14:00 America/New_York -> 19:00 UTC in EST (winter), 18:00 UTC in EDT (summer)
    assert all(c.scheduled_at.hour == 19 for c in winter_meetings)
    assert all(c.scheduled_at.hour == 18 for c in summer_meetings)
