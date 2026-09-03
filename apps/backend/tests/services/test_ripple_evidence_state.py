"""
CD3-D (D4) — the Ripple Engine's public graph used to render literal
"X causes Y" arrows for every edge regardless of where the edge came
from: a single-shot AI-generated narrative with no evidence-validation
path (CD3-A's own finding) and a hardcoded, keyword-selected fallback
template with zero connection to the specific event were both rendered
with the same unqualified "causes" language as a real observed
relationship. Worse, an edge with no relationship field at all
defaulted to "causes" client-side.

app.services.ripple_service._annotate_evidence_state tags every edge
with app.services.claim_provenance.RippleEvidenceState based on the
graph's source: "ai_generated" -> HYPOTHESIZED, "fallback_template" ->
UNAVAILABLE (matching the precedent event_deep_research_service.py's
_get_second_order_effects already set for excluding fallback_template
rows from being presented as real).

Per the owner's explicit instruction ("given the ecac930 lesson, test
the real API serialization path, not just the service object") these
tests go through the real routes (GET /api/ripple/event/{id}, POST
/api/ripple/scenario) via TestClient, not just a direct call to the
service functions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import AsyncSessionLocal
from app.db.models.event import Event
from app.db.models.ripple import RippleGraph
from app.services.claim_provenance import RippleEvidenceState

client = TestClient(app)

_FAKE_AI_RESULT = {
    "nodes": [
        {"id": "event_center", "label": "Test Event", "type": "event", "impact": "mixed",
         "impact_strength": 0.7, "depth": 0, "icon": "⚡", "change_direction": "neutral"},
        {"id": "target_co", "label": "Target Co", "type": "company", "impact": "positive",
         "impact_strength": 0.6, "depth": 1, "icon": "🏢", "change_direction": "up"},
    ],
    "edges": [
        {"source": "event_center", "target": "target_co", "relationship": "causes",
         "impact_strength": 0.6, "confidence": 0.7, "explanation": "test", "time_horizon": "short_term"},
    ],
    "insights": {"summary": "test"},
}


async def _cleanup(event_id: str) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import delete
        await db.execute(delete(RippleGraph).where(RippleGraph.event_id == event_id))
        await db.execute(delete(Event).where(Event.id == event_id))
        await db.commit()


@pytest.mark.asyncio
async def test_real_api_response_tags_ai_generated_edges_hypothesized():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-ripple-ai-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Test event for D4 evidence-state check",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[], impact_score=70.0,
            ))
            await db.commit()

        with patch("app.services.ai_service.generate_ripple_graph", new=AsyncMock(return_value=_FAKE_AI_RESULT)):
            resp = client.get(f"/api/ripple/event/{event_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "ai_generated"
        edges = body["graph_data"]["edges"]
        assert edges, "expected the fake AI edge to survive"
        assert all(e["evidence_state"] == RippleEvidenceState.HYPOTHESIZED.value for e in edges)
        # The old unqualified literal must never appear un-annotated.
        assert edges[0]["relationship"] == "causes"
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_real_api_response_tags_fallback_template_edges_unavailable():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-ripple-fallback-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="RBI cuts repo rate by 25 bps",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[], impact_score=80.0,
            ))
            await db.commit()

        # AI generation raising forces the fallback-template path.
        with patch("app.services.ai_service.generate_ripple_graph", new=AsyncMock(side_effect=RuntimeError("no provider"))):
            resp = client.get(f"/api/ripple/event/{event_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "fallback_template"
        edges = body["graph_data"]["edges"]
        assert edges, "expected the monetary template's real edges"
        assert all(e["evidence_state"] == RippleEvidenceState.UNAVAILABLE.value for e in edges)
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_legacy_db_row_with_no_evidence_state_is_annotated_on_read():
    """A RippleGraph row persisted before D4 shipped has edges with no
    evidence_state key at all -- the DB-cache read path must annotate it
    on the way out, not just newly generated graphs."""
    now = datetime.now(timezone.utc)
    event_id = f"pytest-ripple-legacy-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Legacy cached ripple event",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[], impact_score=60.0,
            ))
            legacy_edges = [
                {"source": "event_center", "target": "co1", "relationship": "causes"},
            ]
            db.add(RippleGraph(
                event_id=event_id, scenario_type="event",
                event_title="Legacy cached ripple event", event_summary="",
                graph_data={"nodes": [{"id": "event_center"}, {"id": "co1"}], "edges": legacy_edges},
                insights={}, source="ai_generated", generated_at=now,
            ))
            await db.commit()

        resp = client.get(f"/api/ripple/event/{event_id}")

        assert resp.status_code == 200
        body = resp.json()
        edges = body["graph_data"]["edges"]
        assert edges[0]["evidence_state"] == RippleEvidenceState.HYPOTHESIZED.value
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_scenario_route_also_tags_evidence_state():
    with patch("app.services.ai_service.generate_ripple_graph", new=AsyncMock(return_value=_FAKE_AI_RESULT)):
        resp = client.post("/api/ripple/scenario", json={"scenario": "What if RBI cuts rates by 50 bps"})

    assert resp.status_code == 200
    body = resp.json()
    edges = body["graph_data"]["edges"]
    assert edges
    assert all(e["evidence_state"] == RippleEvidenceState.HYPOTHESIZED.value for e in edges)
