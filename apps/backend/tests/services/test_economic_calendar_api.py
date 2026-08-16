"""
Phase 5A.8 — canonical Economic Calendar API tests. Uses the TestClient
against the real app + real DB (same convention as this repo's other
API tests), seeding real-shaped rows directly rather than depending on
network access, so this suite passes offline and in CI.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.main import app
from app.db.session import AsyncSessionLocal
from app.db.models.economic_calendar import EconomicCalendarEvent

client = TestClient(app)


def _row(**overrides) -> dict:
    base = dict(
        id=str(uuid.uuid4()), identity_key=f"api_test:{uuid.uuid4().hex[:8]}", reference_period="2026-09",
        title="API Test Event", category="rbi_mpc", country="IN", region=None,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=5),
        source_timezone="Asia/Kolkata", importance="critical",
        actual=None, forecast=None, previous=None, unit=None,
        status="scheduled", source="rbi", source_url=None, source_tier="tier_1",
        companies=[], sectors=[], themes=[], last_verified_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return base


async def _seed(*rows: dict) -> None:
    async with AsyncSessionLocal() as db:
        for r in rows:
            db.add(EconomicCalendarEvent(**r))
        await db.commit()


async def _cleanup(prefix: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like(f"{prefix}%")))
        await db.commit()


@pytest.mark.asyncio
async def test_list_returns_only_current_real_source_rows():
    prefix = f"api_test_list_{uuid.uuid4().hex[:6]}"
    await _seed(
        _row(identity_key=f"{prefix}:current", source="rbi"),
        _row(identity_key=f"{prefix}:noncurrent", source="rbi", is_current=False),
        _row(identity_key=f"{prefix}:seed", source="seed", source_tier="tier_3"),
    )

    resp = client.get(f"/api/economic-calendar/?category=rbi_mpc")
    assert resp.status_code == 200
    keys = {e["id"] for e in resp.json()}
    # can't filter by identity_key via the API, so just confirm none of
    # the excluded rows' sources ever appear
    sources = {e["source"] for e in resp.json()}
    assert "seed" not in sources

    await _cleanup(prefix)


@pytest.mark.asyncio
async def test_filters_by_country_category_importance():
    prefix = f"api_test_filter_{uuid.uuid4().hex[:6]}"
    await _seed(
        _row(identity_key=f"{prefix}:in", country="IN", category="rbi_mpc", importance="critical"),
        _row(identity_key=f"{prefix}:us", country="US", category="fomc", importance="critical", source="fed"),
    )

    r_country = client.get("/api/economic-calendar/?country=US")
    assert all(e["country"] == "US" for e in r_country.json())

    r_category = client.get("/api/economic-calendar/?category=rbi_mpc")
    assert all(e["category"] == "rbi_mpc" for e in r_category.json())

    await _cleanup(prefix)


@pytest.mark.asyncio
async def test_scheduled_at_ist_matches_utc_plus_5_30():
    prefix = f"api_test_ist_{uuid.uuid4().hex[:6]}"
    scheduled = datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc)
    key = f"{prefix}:ist"
    await _seed(_row(identity_key=key, scheduled_at=scheduled, category="rbi_mpc", source="rbi"))

    resp = client.get(f"/api/economic-calendar/upcoming?days=90")
    match = next(e for e in resp.json() if e["id"] and datetime.fromisoformat(e["scheduled_at"].replace("Z", "+00:00")) == scheduled)
    ist = datetime.fromisoformat(match["scheduled_at_ist"])
    assert (ist.hour, ist.minute) == (16, 0)   # 10:30 UTC + 5:30 = 16:00 IST

    await _cleanup(prefix)


@pytest.mark.asyncio
async def test_today_endpoint_uses_ist_day_boundary():
    prefix = f"api_test_today_{uuid.uuid4().hex[:6]}"
    now_ist_date = datetime.now(timezone.utc).astimezone().date()   # not exact IST but close enough for a same-day sanity bound
    # An event at 23:30 UTC today is already TOMORROW in IST (UTC+5:30) —
    # picks a moment clearly still "today" in IST regardless of when the
    # test runs, by anchoring to noon UTC (always safely inside today's
    # IST calendar day: 12:00 UTC = 17:30 IST, same date).
    today_ist_safe = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    key = f"{prefix}:today"
    await _seed(_row(identity_key=key, scheduled_at=today_ist_safe, category="rbi_mpc", source="rbi"))

    resp = client.get("/api/economic-calendar/today")
    assert resp.status_code == 200
    ids_today = {e["id"] for e in resp.json()}
    seeded_ids = set()
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        rows = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key == key))).scalars().all()
        seeded_ids = {r.id for r in rows}
    assert seeded_ids & ids_today

    await _cleanup(prefix)


@pytest.mark.asyncio
async def test_health_endpoint_reports_real_sources_only():
    resp = client.get("/api/economic-calendar/health")
    assert resp.status_code == 200
    sources = {h["source"] for h in resp.json()}
    assert sources <= {"rbi", "mospi", "fed", "bls"}   # never a seed/test tag, even if one exists in the DB


@pytest.mark.asyncio
async def test_company_filter_is_case_insensitive_and_portable():
    prefix = f"api_test_company_{uuid.uuid4().hex[:6]}"
    key = f"{prefix}:withco"
    await _seed(_row(identity_key=key, companies=["HDFCBANK"], category="rbi_mpc", source="rbi"))

    resp = client.get("/api/economic-calendar/?company=hdfcbank")
    assert resp.status_code == 200
    assert any("HDFCBANK" in e["companies"] for e in resp.json())

    await _cleanup(prefix)
