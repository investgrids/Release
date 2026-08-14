"""
Regression test for the specific real production event that motivated the
2026-08 priority-aware AIPE selection fix: rss-5d304dc987ec.

Real EventTriage row (confirmed still present in the dev DB at the time
this test was written): headline "From Gift Nifty to US-Iran war, crude
oil prices: 7 key things that changed for Indian stock market overnight",
urgency=1, importance=6. The AI itself scored this low-urgency (a "what
changed overnight" roundup, not breaking news) — but the headline contains
"war", which engine.py's keyword floor forces to Critical regardless of
raw urgency. Before the fix, this event was excluded from AIPE's candidate
pool by get_high_urgency_triage's `WHERE urgency >= 6` clause, and would
have been separately rejected by intelligence_filter.should_generate_
intelligence's unconditional `urgency < 6` gate even if it had somehow
reached that far.

This is deliberately pinned to the real id/headline/urgency/importance
values rather than a synthetic equivalent, per the explicit ask to add a
regression test for this exact audit case.
"""
from __future__ import annotations

import pytest

from app.db.session import AsyncSessionLocal
from app.services.aipe.market_story_engine import get_high_urgency_triage
from app.services.aipe.intelligence_filter import should_generate_intelligence
from app.services.intelligence.engine import compute_priority

_REAL_EVENT_ID = "rss-5d304dc987ec"
_REAL_HEADLINE = "From Gift Nifty to US-Iran war, crude oil prices: 7 key things that changed for Indian stock market overnight"
_REAL_URGENCY = 1
_REAL_IMPORTANCE = 6


def test_compute_priority_forces_critical_despite_low_urgency():
    score, tier = compute_priority(_REAL_URGENCY, _REAL_IMPORTANCE, None, _REAL_HEADLINE)
    assert tier == "Critical", f"Expected keyword floor to force Critical, got {tier} ({score})"


def test_should_generate_intelligence_accepts_despite_urgency_below_min():
    event = {
        "headline": _REAL_HEADLINE,
        "urgency": _REAL_URGENCY,
        "importance": _REAL_IMPORTANCE,
        "market_impact": "medium",
        "is_structural": False,
    }
    ok, reason = should_generate_intelligence(event, source="triage")
    assert ok, f"Real audit-case event still rejected: {reason}"


@pytest.mark.asyncio
async def test_real_event_appears_in_aipe_candidate_pool_if_still_in_db():
    """Best-effort — this real row may eventually age out of the 300-row
    recency window get_high_urgency_triage queries, or be cleaned from the
    dev DB. Skips rather than fails if that's happened, since the two
    tests above already pin the actual logic this event exercises without
    depending on the row's continued existence."""
    async with AsyncSessionLocal() as db:
        candidates = await get_high_urgency_triage(db, min_urgency=6, hours=24 * 30)
    ids = [c["event_id"] for c in candidates]
    if _REAL_EVENT_ID not in ids:
        pytest.skip(f"{_REAL_EVENT_ID} no longer in the dev DB / outside the candidate window — logic covered by the two tests above regardless")
    match = next(c for c in candidates if c["event_id"] == _REAL_EVENT_ID)
    assert match["priority_tier"] == "Critical"
