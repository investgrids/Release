"""
Phase 5A.12 — real E2E finding: get_legacy_shaped_calendar() (feeding
crud.get_calendar -> /api/calendar, /api/market/calendar, MIE's
tomorrow_watch, Pre-Market's Event Layer) must only return future (or
very-recently-past) events. Caught live: a screenshot of /calendar
before this fix showed 2021 FOMC decisions at the top of "Upcoming
Calendar", because EconomicCalendarEvent deliberately retains full
multi-year history (Phase 5A §23 research value) unlike the old dead
table, which only ever had forward-dated seed rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.economic_calendar import EconomicCalendarEvent
from app.services.economic_calendar.legacy_adapter import get_legacy_shaped_calendar


async def _cleanup(prefix: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like(f"{prefix}%")))
        await db.commit()


@pytest.mark.asyncio
async def test_legacy_adapter_excludes_old_history():
    prefix = f"legacy_test_old_{uuid.uuid4().hex[:6]}"
    key = f"{prefix}:2021"
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(
            id=str(uuid.uuid4()), identity_key=key, reference_period="2021-01",
            title="Old FOMC From 2021", category="test_cat", country="XX",
            scheduled_at=datetime(2021, 1, 28, tzinfo=timezone.utc),
            source_timezone="UTC", importance="critical", status="scheduled",
            source="fed", source_tier="tier_1", last_verified_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    async with AsyncSessionLocal() as db:
        rows = await get_legacy_shaped_calendar(db)
    titles = [r.title for r in rows]
    assert "Old FOMC From 2021" not in titles

    await _cleanup(prefix)


@pytest.mark.asyncio
async def test_legacy_adapter_includes_future_events():
    prefix = f"legacy_test_future_{uuid.uuid4().hex[:6]}"
    key = f"{prefix}:future"
    future = datetime.now(timezone.utc) + timedelta(days=20)
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(
            id=str(uuid.uuid4()), identity_key=key, reference_period="2026-09",
            title="Future Test Event", category="test_cat", country="XX",
            scheduled_at=future, source_timezone="UTC", importance="critical",
            status="scheduled", source="rbi", source_tier="tier_1",
            last_verified_at=datetime.now(timezone.utc),
        ))
        await db.commit()
        rows = await get_legacy_shaped_calendar(db)

    titles = [r.title for r in rows]
    assert "Future Test Event" in titles

    await _cleanup(prefix)


@pytest.mark.asyncio
async def test_legacy_adapter_includes_events_within_last_day():
    """A small back-window (1 day) — an event that JUST happened
    shouldn't vanish mid-day for a caller reading it slightly later."""
    prefix = f"legacy_test_recent_{uuid.uuid4().hex[:6]}"
    key = f"{prefix}:recent"
    recent = datetime.now(timezone.utc) - timedelta(hours=6)
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(
            id=str(uuid.uuid4()), identity_key=key, reference_period="2026-08",
            title="Just Happened Event", category="test_cat", country="XX",
            scheduled_at=recent, source_timezone="UTC", importance="critical",
            status="scheduled", source="rbi", source_tier="tier_1",
            last_verified_at=datetime.now(timezone.utc),
        ))
        await db.commit()
        rows = await get_legacy_shaped_calendar(db)

    titles = [r.title for r in rows]
    assert "Just Happened Event" in titles

    await _cleanup(prefix)
