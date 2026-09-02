"""
Deep Research (Layer 2, 2026-08 event page redesign) — no-fabrication and
consolidation guards for app/services/event_deep_research_service.py.

Covers the guarantees called out explicitly in its module docstring:
  - Timeline is real EventTimeline rows only, never the synthetic
    "Event Announced"/"Market Outlook" fallback EventService.get_event_detail
    uses for its own (unrelated) Overview-tab display.
  - Scenario Analysis's one AI call only fires when the event is both
    materially high-impact and genuinely uncertain; degraded/fabricated
    provider output is never surfaced as scenario_status="shown".
  - Second-order effects only come from a real ai_generated ripple graph,
    never a fallback_template placeholder.
  - Unknown event ids return None (404 at the API layer), not a crash.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.event import Event, EventTimeline
from app.db.models.ripple import RippleGraph
from app.services import event_deep_research_service as svc
from app.services.event_deep_research_service import _scenario_worthy, get_deep_research


async def _cleanup(event_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(RippleGraph).where(RippleGraph.event_id == event_id))
        await db.execute(delete(EventTimeline).where(EventTimeline.event_id == event_id))
        await db.execute(delete(Event).where(Event.id == event_id))
        await db.commit()


def _mk_event(event_id: str, *, impact_score=None, confidence=None) -> Event:
    now = datetime.now(timezone.utc)
    return Event(
        id=event_id, title="Test event for deep research", source="Test",
        event_type="policy", created_at=now, updated_at=now,
        enrichment_status="done", impact_score=impact_score, confidence=confidence,
    )


class TestScenarioWorthyGate:
    """Pure function — no DB, no network. The heuristic itself: reuses the
    event's own real impact_score/confidence rather than inventing a new
    'uncertainty' signal."""

    def test_low_impact_never_worthy_regardless_of_confidence(self):
        assert _scenario_worthy(30.0, 10.0) is False
        assert _scenario_worthy(64.9, None) is False

    def test_high_impact_high_confidence_not_worthy(self):
        # Well-understood direction (e.g. "RBI keeps rate unchanged" with
        # 93% AI confidence) — no genuine Bull/Base/Bear split to show.
        assert _scenario_worthy(87.0, 93.0) is False

    def test_high_impact_low_confidence_is_worthy(self):
        # Genuinely uncertain high-impact event — multiple real paths.
        assert _scenario_worthy(70.0, 40.0) is True

    def test_high_impact_unscored_confidence_is_worthy(self):
        assert _scenario_worthy(80.0, None) is True

    def test_none_impact_never_worthy(self):
        assert _scenario_worthy(None, 10.0) is False


class TestDeepResearchService:
    async def test_unknown_event_returns_none(self):
        async with AsyncSessionLocal() as db:
            result = await get_deep_research(db, f"pytest-nonexistent-{uuid.uuid4().hex[:8]}")
        assert result is None

    async def test_timeline_is_never_the_synthetic_fallback(self, monkeypatch):
        """EventService.get_event_detail() synthesizes a placeholder
        timeline (generic 'Event Announced' / 'Market Outlook: Monitor for
        developments over the coming weeks.' steps) when no real
        EventTimeline rows exist — real UI/backend behavior confirmed live
        against the dev DB. Deep Research must never surface that."""
        event_id = f"pytest-dr-timeline-{uuid.uuid4().hex[:8]}"
        await _cleanup(event_id)
        try:
            async with AsyncSessionLocal() as db:
                db.add(_mk_event(event_id, impact_score=20.0, confidence=50.0))
                await db.commit()
                result = await get_deep_research(db, event_id)
            assert result is not None
            assert result.timeline == []
            assert "Market Outlook" not in [t.title for t in result.timeline]
        finally:
            await _cleanup(event_id)

    async def test_timeline_includes_real_stored_steps(self):
        event_id = f"pytest-dr-realtl-{uuid.uuid4().hex[:8]}"
        await _cleanup(event_id)
        try:
            async with AsyncSessionLocal() as db:
                db.add(_mk_event(event_id, impact_score=20.0, confidence=50.0))
                db.add(EventTimeline(event_id=event_id, date="2026-06-18", title="RBI statement released", description="Real dated step.", order=0))
                await db.commit()
                result = await get_deep_research(db, event_id)
            assert result is not None
            assert len(result.timeline) == 1
            assert result.timeline[0].title == "RBI statement released"
            assert result.timeline[0].date == "2026-06-18"
        finally:
            await _cleanup(event_id)

    async def test_scenario_not_applicable_below_materiality_threshold(self, monkeypatch):
        calls = []
        async def _fake_scenario(**kwargs):
            calls.append(kwargs)
            return {"bull": {"outcome": "x", "key_drivers": [], "confidence": 60}}
        monkeypatch.setattr(svc, "_get_scenarios", svc._get_scenarios)  # sanity: attribute exists
        import app.services.ai_service as ai_service
        monkeypatch.setattr(ai_service, "generate_scenario_analysis", _fake_scenario)

        event_id = f"pytest-dr-lowimpact-{uuid.uuid4().hex[:8]}"
        await _cleanup(event_id)
        try:
            async with AsyncSessionLocal() as db:
                db.add(_mk_event(event_id, impact_score=20.0, confidence=10.0))
                await db.commit()
                result = await get_deep_research(db, event_id)
            assert result is not None
            assert result.scenario_status == "not_applicable"
            assert result.scenarios == []
            # The AI call must never fire for a low-materiality event —
            # this is the "reduce AI calls" guarantee, not just a labeling
            # difference.
            assert calls == []
        finally:
            await _cleanup(event_id)

    async def test_scenario_shown_when_worthy_and_ai_succeeds(self, monkeypatch):
        async def _fake_scenario(**kwargs):
            return {
                "bull": {"outcome": "Strong upside on policy clarity.", "key_drivers": ["d1"], "confidence": 70},
                "base": {"outcome": "In line with consensus.", "key_drivers": ["d2"], "confidence": 60},
                "bear": {"outcome": "Downside on global risk-off.", "key_drivers": ["d3"], "confidence": 50},
            }
        import app.services.ai_service as ai_service
        monkeypatch.setattr(ai_service, "generate_scenario_analysis", _fake_scenario)

        event_id = f"pytest-dr-worthy-{uuid.uuid4().hex[:8]}"
        await _cleanup(event_id)
        try:
            async with AsyncSessionLocal() as db:
                db.add(_mk_event(event_id, impact_score=80.0, confidence=40.0))
                await db.commit()
                result = await get_deep_research(db, event_id)
            assert result is not None
            assert result.scenario_status == "shown"
            assert len(result.scenarios) == 3
            assert result.scenarios[0].confidence in ("High", "Medium", "Low")
        finally:
            await _cleanup(event_id)

    async def test_scenario_unavailable_when_ai_degrades(self, monkeypatch):
        """The AI call fires (event qualifies) but returns the provider's
        own 'degraded' generic-template fallback — must never be surfaced
        as real scenario content."""
        async def _fake_degraded(**kwargs):
            return {"degraded": True, "bull": {"outcome": "Strong performance for X driven by favourable macro conditions..."}}
        import app.services.ai_service as ai_service
        monkeypatch.setattr(ai_service, "generate_scenario_analysis", _fake_degraded)

        event_id = f"pytest-dr-degraded-{uuid.uuid4().hex[:8]}"
        await _cleanup(event_id)
        try:
            async with AsyncSessionLocal() as db:
                db.add(_mk_event(event_id, impact_score=80.0, confidence=40.0))
                await db.commit()
                result = await get_deep_research(db, event_id)
            assert result is not None
            assert result.scenario_status == "unavailable"
            assert result.scenarios == []
        finally:
            await _cleanup(event_id)

    async def test_second_order_effects_excludes_fallback_template(self):
        """A ripple_graphs row with source='fallback_template' is
        ripple_service.py's own hand-written placeholder, not real
        analysis of this event — must never appear as an 'observed' or
        'likely' second-order effect."""
        event_id = f"pytest-dr-ripplefallback-{uuid.uuid4().hex[:8]}"
        await _cleanup(event_id)
        try:
            async with AsyncSessionLocal() as db:
                db.add(_mk_event(event_id, impact_score=20.0, confidence=50.0))
                db.add(RippleGraph(
                    event_id=event_id, scenario_type="event", source="fallback_template",
                    graph_data={"nodes": [{"id": "n1"}], "edges": []},
                    insights={"summary": "Templated placeholder text."},
                ))
                await db.commit()
                result = await get_deep_research(db, event_id)
            assert result is not None
            assert result.second_order_effects == []
        finally:
            await _cleanup(event_id)

    async def test_second_order_effects_includes_ai_generated(self):
        event_id = f"pytest-dr-ripplereal-{uuid.uuid4().hex[:8]}"
        await _cleanup(event_id)
        try:
            async with AsyncSessionLocal() as db:
                db.add(_mk_event(event_id, impact_score=20.0, confidence=50.0))
                db.add(RippleGraph(
                    event_id=event_id, scenario_type="event", source="ai_generated",
                    graph_data={"nodes": [{"id": "n1"}], "edges": []},
                    insights={"summary": "Real AI-generated ripple summary.", "impacted_sectors": [{"name": "Banking"}]},
                ))
                await db.commit()
                result = await get_deep_research(db, event_id)
            assert result is not None
            levels = [e.level for e in result.second_order_effects]
            assert "immediate" in levels
            assert "sector" in levels
        finally:
            await _cleanup(event_id)

    async def test_second_order_effects_never_labeled_observed(self):
        """CD3-B fix: this endpoint's second-order effects come entirely
        from RippleGraph.insights, an AI-generated summary with no
        per-event evidence-validation path (CD3-A finding) — the
        'immediate' summary effect used to be hardcoded status="observed"
        even though it's the same unverified content as the sector/company
        effects below it, which were already "likely". All three must now
        read "hypothesized", never "observed" -- that state is reserved for
        a future evidence-validated producer this endpoint doesn't have."""
        event_id = f"pytest-dr-ripplestatus-{uuid.uuid4().hex[:8]}"
        await _cleanup(event_id)
        try:
            async with AsyncSessionLocal() as db:
                db.add(_mk_event(event_id, impact_score=20.0, confidence=50.0))
                db.add(RippleGraph(
                    event_id=event_id, scenario_type="event", source="ai_generated",
                    graph_data={"nodes": [{"id": "n1"}], "edges": []},
                    insights={
                        "summary": "Real AI-generated ripple summary.",
                        "impacted_sectors": [{"name": "Banking"}],
                        "beneficiaries": [{"name": "HDFC Bank"}],
                    },
                ))
                await db.commit()
                result = await get_deep_research(db, event_id)
            assert result is not None
            assert len(result.second_order_effects) == 3
            statuses = {e.status for e in result.second_order_effects}
            assert statuses == {"hypothesized"}
            assert "observed" not in statuses
        finally:
            await _cleanup(event_id)
