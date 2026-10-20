"""
Provenance contract, Stage A (2026-10-19) — engine.py::read_top_events()
is the single shared aggregator underneath the AI Search evidence feed,
the Fact registry, and the homepage top_events, so this is the one real
chokepoint for propagating triage_source. Runs against the real
configured DB (this test file's own convention, matching
test_event_bridge.py) -- unique ids, cleaned up in a finally block.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence import EventTriage
from app.services.intelligence.engine import read_top_events

_IDS = ["rte-prov-ai-1", "rte-prov-fallback-1", "rte-prov-unknown-1"]


async def _cleanup():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventTriage).where(EventTriage.event_id.in_(_IDS)))
        await db.commit()


@pytest.mark.asyncio
async def test_read_top_events_propagates_triage_source_for_all_three_states():
    await _cleanup()
    try:
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            db.add(EventTriage(
                id="t-prov-ai-1", event_id="rte-prov-ai-1", source="news",
                headline="AI-triaged headline", urgency=9, importance=8, confidence=8,
                one_liner="AI-triaged one-liner", triage_source="ai", triaged_at=now,
            ))
            db.add(EventTriage(
                id="t-prov-fallback-1", event_id="rte-prov-fallback-1", source="news",
                headline="Fallback headline", urgency=9, importance=8, confidence=4,
                one_liner="Fallback headline", triage_source="rule_based_fallback", triaged_at=now,
            ))
            # No triage_source passed -- exercises the real ORM/column default,
            # the same path a genuine pre-migration row takes.
            db.add(EventTriage(
                id="t-prov-unknown-1", event_id="rte-prov-unknown-1", source="news",
                headline="Pre-migration headline", urgency=9, importance=8, confidence=4,
                one_liner="Pre-migration headline", triaged_at=now,
            ))
            await db.commit()

        events = await read_top_events(limit=50, min_urgency=0, hours=1)
        by_id = {e["id"]: e for e in events if e["id"] in _IDS}
        assert set(by_id) == set(_IDS), "all three seeded rows must be returned"
        assert by_id["rte-prov-ai-1"]["triage_source"] == "ai"
        assert by_id["rte-prov-fallback-1"]["triage_source"] == "rule_based_fallback"
        assert by_id["rte-prov-unknown-1"]["triage_source"] == "unknown"
    finally:
        await _cleanup()
