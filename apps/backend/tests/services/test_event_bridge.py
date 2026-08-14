"""
Regression suite — triage_worker's Critical/High RSS-to-Event bridge.

Runs against the real configured DB (this codebase's existing convention
for DB-touching tests — no isolated test-DB fixture exists here today; see
the _live test files in this same directory). Each test uses a unique,
clearly-marked id and cleans up its own rows in a finally block, so this is
safe to run against the dev DB repeatedly without leaving residue —
confirmed by hand during the 2026-08-13 audit before being written up as a
permanent test, then re-verified here.

Covers the exact three scenarios from that manual verification:
  1. A Critical-tier RSS-triaged event with no existing Event row gets one
     created, linked by the same id EventTriage/EventCoverage already use.
  2. A Medium-tier event does NOT get bridged — this isn't "every RSS item
     becomes an Event," only Critical/High.
  3. An id that already has a real Event row (e.g. NSE-sourced) is never
     overwritten or duplicated, even if a Critical-tier triage comes in
     under the same id.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.event import Event
from app.db.models.intelligence import EventTriage
from app.db.models.event_coverage import EventCoverage
from app.services.intelligence.event_bus import RawEvent, TriagedEvent
from app.services.intelligence.triage_worker import _store_triage


async def _cleanup(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        for model, col in ((Event, Event.id), (EventTriage, EventTriage.event_id), (EventCoverage, EventCoverage.event_id)):
            await db.execute(delete(model).where(col.in_(ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_critical_rss_event_creates_event_row():
    test_id = "rss-pytest-bridge-critical-001"
    await _cleanup(test_id)
    try:
        raw = RawEvent(
            id=test_id,
            headline="US-Iran war escalation sends crude oil surging, RBI may face pressure",
            summary="Test summary for bridge verification",
            source="news", origin="Livemint",
            sectors=["Energy"], companies=[],
        )
        triage = TriagedEvent(
            raw=raw, urgency=1, importance=6, confidence=50,
            sentiment="negative", horizon="short", market_impact="high",
            is_structural=False, direction="down", one_liner="test",
            themes=[], sectors=["Energy"], tickers=[],
            broadcast=False, refresh_homepage=False,
        )
        await _store_triage(triage)

        async with AsyncSessionLocal() as db:
            ev = await db.get(Event, test_id)
            assert ev is not None, "Critical-tier RSS event should have created a real Event row"
            assert ev.enrichment_status == "pending"
            assert ev.impact_score is None, "impact_score must be None, not a fabricated placeholder"

            from sqlalchemy import select
            t = (await db.execute(select(EventTriage).where(EventTriage.event_id == test_id))).scalar_one_or_none()
            c = (await db.execute(select(EventCoverage).where(EventCoverage.event_id == test_id))).scalar_one_or_none()
            assert t is not None and t.event_id == test_id
            assert c is not None and c.event_id == test_id and c.priority == "Critical"
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_medium_tier_event_does_not_bridge():
    test_id = "rss-pytest-bridge-medium-002"
    await _cleanup(test_id)
    try:
        raw = RawEvent(
            id=test_id,
            headline="Company X announces routine board meeting update",
            summary="Test summary", source="news", origin="Moneycontrol",
        )
        triage = TriagedEvent(
            raw=raw, urgency=3, importance=3, confidence=40,
            sentiment="neutral", horizon="short", market_impact="low",
            is_structural=False, direction="flat", one_liner="test",
            themes=[], sectors=[], tickers=[],
            broadcast=False, refresh_homepage=False,
        )
        await _store_triage(triage)

        async with AsyncSessionLocal() as db:
            ev = await db.get(Event, test_id)
            assert ev is None, "Medium-tier event must NOT be bridged to a real Event row"
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_existing_event_row_never_overwritten():
    test_id = "nse-pytest-bridge-existing-003"
    await _cleanup(test_id)
    try:
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=test_id, title="Original NSE event", summary="x", source="NSE",
                event_type="corporate", impact_score=7.0, confidence=0.8,
                published_at=now, created_at=now, updated_at=now,
                enrichment_status="done",
            ))
            await db.commit()

        raw = RawEvent(id=test_id, headline="RBI repo rate decision war crisis", summary="x", source="news", origin="NSE")
        triage = TriagedEvent(
            raw=raw, urgency=9, importance=9, confidence=90,
            sentiment="negative", horizon="short", market_impact="high",
            is_structural=True, direction="down", one_liner="t",
            themes=[], sectors=[], tickers=[], broadcast=True, refresh_homepage=True,
        )
        await _store_triage(triage)

        async with AsyncSessionLocal() as db:
            ev = await db.get(Event, test_id)
            assert ev is not None
            assert ev.title == "Original NSE event", "Existing Event row must never be overwritten by the bridge"
            assert ev.enrichment_status == "done"
            assert ev.impact_score == 7.0
    finally:
        await _cleanup(test_id)
