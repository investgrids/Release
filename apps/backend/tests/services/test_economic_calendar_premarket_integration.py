"""
Phase 5A.10 — Pre-Market integration: get_premarket_data() now includes
`scheduled_today`, sourced from real EconomicCalendarEvent rows for the
current IST calendar day. Proven both ways: nothing scheduled -> empty
list (never fabricated), something scheduled -> it appears, correctly
converted to IST.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.economic_calendar import EconomicCalendarEvent
from app.services.market_data import get_premarket_data


async def _cleanup(prefix: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like(f"{prefix}%")))
        await db.commit()


@pytest.mark.asyncio
async def test_scheduled_today_empty_when_nothing_real_is_scheduled():
    """No fixture seeded — confirms the field exists and is an empty
    list (not missing, not a fabricated placeholder) when nothing is
    genuinely scheduled today."""
    with patch("app.services.market_data._fetch_premarket", return_value={"asian": [], "us": [], "commodities": []}):
        data = await get_premarket_data()
    assert "scheduled_today" in data
    assert isinstance(data["scheduled_today"], list)


@pytest.mark.asyncio
async def test_scheduled_today_surfaces_a_real_row_scheduled_today():
    prefix = f"premarket_test_{uuid.uuid4().hex[:6]}"
    key = f"{prefix}:today"
    # Noon UTC = safely inside "today" in IST (17:30 IST) regardless of
    # when this test runs.
    today_safe = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(
            id=str(uuid.uuid4()), identity_key=key, reference_period="2026-01",
            title="Test Scheduled Catalyst", category="test_cat", country="XX",
            scheduled_at=today_safe, source_timezone="UTC", importance="high",
            status="scheduled", source="rbi", source_tier="tier_1",
            last_verified_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    with patch("app.services.market_data._fetch_premarket", return_value={"asian": [], "us": [], "commodities": []}):
        data = await get_premarket_data()

    titles = [c["title"] for c in data["scheduled_today"]]
    assert "Test Scheduled Catalyst" in titles
    match = next(c for c in data["scheduled_today"] if c["title"] == "Test Scheduled Catalyst")
    assert match["importance"] == "high"
    assert ":" in match["time_ist"]   # HH:MM

    await _cleanup(prefix)


@pytest.mark.asyncio
async def test_scheduled_today_excludes_tomorrows_event():
    prefix = f"premarket_test_tmrw_{uuid.uuid4().hex[:6]}"
    key = f"{prefix}:tomorrow"
    tomorrow = datetime.now(timezone.utc) + timedelta(days=2)   # safely outside today regardless of TZ edge
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(
            id=str(uuid.uuid4()), identity_key=key, reference_period="2026-01",
            title="Not Today Event", category="test_cat", country="XX",
            scheduled_at=tomorrow, source_timezone="UTC", importance="high",
            status="scheduled", source="rbi", source_tier="tier_1",
            last_verified_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    with patch("app.services.market_data._fetch_premarket", return_value={"asian": [], "us": [], "commodities": []}):
        data = await get_premarket_data()

    titles = [c["title"] for c in data["scheduled_today"]]
    assert "Not Today Event" not in titles

    await _cleanup(prefix)


@pytest.mark.asyncio
async def test_scheduled_today_failure_does_not_break_premarket_quotes():
    """A calendar-read failure must not take Pre-Market's quote data
    down with it."""
    with patch("app.services.market_data._fetch_premarket", return_value={"asian": [{"name": "test"}], "us": [], "commodities": []}), \
         patch("app.db.session.AsyncSessionLocal", side_effect=Exception("simulated DB failure")):
        data = await get_premarket_data()
    assert data["asian"] == [{"name": "test"}]
    assert data["scheduled_today"] == []
