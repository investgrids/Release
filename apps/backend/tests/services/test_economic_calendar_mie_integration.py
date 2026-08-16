"""
Phase 5A.10 — MIE integration: read_upcoming_calendar() (which feeds
MIE's tomorrow_watch field, compute_intelligence_state()) is migrated
onto real EconomicCalendarEvent data as of Phase 5A.9 — this proves the
integration end-to-end with a real, seeded future row, closing the
loop the original audit flagged ("tomorrow_watch is computed but never
finds real data").
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.economic_calendar import EconomicCalendarEvent
from app.services.intelligence.engine import read_upcoming_calendar


async def _cleanup(prefix: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like(f"{prefix}%")))
        await db.commit()


@pytest.mark.asyncio
async def test_tomorrow_watch_surfaces_a_real_future_calendar_row():
    prefix = f"mie_test_{uuid.uuid4().hex[:6]}"
    key = f"{prefix}:future"
    future = datetime.now(timezone.utc) + timedelta(days=10)
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(
            id=str(uuid.uuid4()), identity_key=key, reference_period="2026-01",
            title="MIE Integration Test Event", category="test_cat", country="XX",
            scheduled_at=future, source_timezone="UTC", importance="critical",
            status="scheduled", source="rbi", source_tier="tier_1",
            last_verified_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    upcoming = await read_upcoming_calendar(limit=50)
    titles = [e["title"] for e in upcoming]
    assert "MIE Integration Test Event" in titles

    await _cleanup(prefix)


@pytest.mark.asyncio
async def test_tomorrow_watch_excludes_past_events():
    prefix = f"mie_test_past_{uuid.uuid4().hex[:6]}"
    key = f"{prefix}:past"
    past = datetime.now(timezone.utc) - timedelta(days=10)
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(
            id=str(uuid.uuid4()), identity_key=key, reference_period="2026-01",
            title="Past Event Should Not Appear", category="test_cat", country="XX",
            scheduled_at=past, source_timezone="UTC", importance="critical",
            status="scheduled", source="rbi", source_tier="tier_1",
            last_verified_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    upcoming = await read_upcoming_calendar(limit=50)
    titles = [e["title"] for e in upcoming]
    assert "Past Event Should Not Appear" not in titles

    await _cleanup(prefix)
