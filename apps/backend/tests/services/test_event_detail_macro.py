"""
Regression suite — EventService.get_event_detail's macroRelease field
(Phase 9 slice, 2026-08 audit: wires the MacroRelease data built in Phase 7
into the already-existing, already-SEO-ready event detail pipeline rather
than leaving it with no public surface at all).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.event import Event
from app.db.models.macro_release import MacroRelease
from app.services.event_service import EventService


async def _cleanup(event_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MacroRelease).where(MacroRelease.id == event_id))
        await db.execute(delete(Event).where(Event.id == event_id))
        await db.commit()


@pytest.mark.asyncio
async def test_event_detail_includes_macro_release_when_linked():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-event-macro-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="CPI inflation eases to 4.2% in July 2026",
                source="PIB", event_type="policy", created_at=now, updated_at=now,
                enrichment_status="done",
            ))
            db.add(MacroRelease(
                id=event_id, event_id=event_id, metric="CPI",
                release_value=4.2, previous_value=4.8, expected_value=None,
                unit="%", period="July 2026", geography="India", importance="High",
                affected_sectors=["Banking", "NBFC", "Auto", "Real Estate"],
                affected_companies=[], source="PIB", source_url="https://pib.gov.in/test",
                headline="CPI inflation eases to 4.2% in July 2026",
            ))
            await db.commit()

            detail = await EventService(db).get_event_detail(event_id)
        assert detail is not None
        assert detail["macroRelease"] is not None
        macro = detail["macroRelease"]
        assert macro["metric"] == "CPI"
        assert macro["release_value"] == 4.2
        assert macro["previous_value"] == 4.8
        assert macro["expected_value"] is None
        assert macro["surprise"] is None  # can't compute without a real expected_value
        assert macro["unit"] == "%"
        assert "Banking" in macro["affected_sectors"]
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_event_detail_macro_release_is_none_when_not_linked():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-event-no-macro-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Finance Minister holds pre-budget consultations",
                source="PIB", event_type="policy", created_at=now, updated_at=now,
                enrichment_status="done",
            ))
            await db.commit()

            detail = await EventService(db).get_event_detail(event_id)
        assert detail is not None
        # Never fabricated — an event with no real extracted macro data
        # must report None, not an empty-but-present structure.
        assert detail["macroRelease"] is None
    finally:
        await _cleanup(event_id)


def test_macro_release_detail_schema_accepts_null_surprise_and_expected():
    from app.schemas.event_detail import MacroReleaseDetail
    m = MacroReleaseDetail(metric="CPI", release_value=4.2, unit="%")
    assert m.expected_value is None
    assert m.surprise is None
    assert m.affected_sectors == []
