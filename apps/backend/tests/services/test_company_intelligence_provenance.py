"""
Provenance contract, Stage D remaining consumers (2026-10-19) --
company_intelligence.py::get_active_events() must not show a
rule_based_fallback/unknown event as one of a company's "active events"
today. Sorting/scoring (active_score/lifecycle) for the remaining real
items is otherwise untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence import EventTriage
from app.services.company_intelligence import get_active_events

_IDS = ["ci-prov-ev-1", "ci-prov-ev-2"]


async def _cleanup():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventTriage).where(EventTriage.event_id.in_(_IDS)))
        await db.commit()


async def _seed(event_id: str, triage_source: str):
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        db.add(EventTriage(
            id=f"t-{event_id}", event_id=event_id, source="news",
            headline=f"{event_id} headline", urgency=8, importance=6, confidence=5,
            one_liner=f"{event_id} raw or AI one-liner", triage_source=triage_source,
            sectors=[], tickers=["RELIANCE"], triaged_at=now,
        ))
        await db.commit()


@pytest.mark.asyncio
async def test_fallback_sourced_event_is_excluded_from_active_events():
    await _cleanup()
    try:
        await _seed(_IDS[0], "rule_based_fallback")
        async with AsyncSessionLocal() as db:
            items = await get_active_events(db, symbol="RELIANCE", sector=None)
        assert items == []
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_unknown_provenance_event_is_excluded():
    await _cleanup()
    try:
        await _seed(_IDS[0], "unknown")
        async with AsyncSessionLocal() as db:
            items = await get_active_events(db, symbol="RELIANCE", sector=None)
        assert items == []
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_ai_sourced_event_is_unaffected():
    await _cleanup()
    try:
        await _seed(_IDS[0], "ai")
        async with AsyncSessionLocal() as db:
            items = await get_active_events(db, symbol="RELIANCE", sector=None)
        assert len(items) == 1
        assert items[0]["headline"] == f"{_IDS[0]} raw or AI one-liner"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_eligible_event_still_returned_alongside_a_skipped_one():
    await _cleanup()
    try:
        await _seed(_IDS[0], "rule_based_fallback")
        await _seed(_IDS[1], "ai")
        async with AsyncSessionLocal() as db:
            items = await get_active_events(db, symbol="RELIANCE", sector=None)
        assert len(items) == 1
        assert items[0]["id"] == _IDS[1]
    finally:
        await _cleanup()
