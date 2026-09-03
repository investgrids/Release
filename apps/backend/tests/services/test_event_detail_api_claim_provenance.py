"""
CD3-B follow-up (2026-09-02, found during production deploy verification):
GET /api/events/{id} declares response_model=EventDetailResponse. Pydantic's
default behavior for a response_model is to serialize ONLY the fields the
model declares -- any extra key in the dict EventService.get_event_detail()
returns is silently dropped. The CD3-B claim-provenance tags
(impact_provenance/evidence_state) were added to that dict but NOT to
EventDetailResponse's nested schemas (app/schemas/event_detail.py), so they
were computed correctly but never reached a real API response -- confirmed
live against production right after deploying commit 5321066, before this
fix. The service-level tests added for CD3-B (test_event_service_fake_
sector_provenance.py) called EventService.get_event_detail() directly and
never caught this, because they bypass the route's response_model
serialization entirely.

This suite exercises the REAL route through TestClient -- the actual
response_model boundary -- specifically to catch this class of bug, not
just the service function's own return value.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.main import app
from app.db.session import AsyncSessionLocal
from app.db.models.event import Event, EventCompany, EventSector, EventGraphEdge, EventGraphNode
from app.services.claim_provenance import ClaimProvenance, RippleEvidenceState

client = TestClient(app)


async def _cleanup(event_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventGraphEdge).where(EventGraphEdge.event_id == event_id))
        await db.execute(delete(EventGraphNode).where(EventGraphNode.event_id == event_id))
        await db.execute(delete(EventSector).where(EventSector.event_id == event_id))
        await db.execute(delete(EventCompany).where(EventCompany.event_id == event_id))
        await db.execute(delete(Event).where(Event.id == event_id))
        await db.commit()


@pytest.mark.asyncio
async def test_real_api_response_includes_claim_provenance_on_companies_sectors_edges():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-api-provenance-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Test event for real API provenance check",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[],
            ))
            db.add(EventCompany(event_id=event_id, symbol="HDFCBANK", name="HDFC Bank",
                                 impact_type="beneficiary", impact_score=70.0, reason="test"))
            db.add(EventSector(event_id=event_id, sector="Banking", impact="positive", impact_score=62.0))
            db.add(EventGraphNode(event_id=event_id, node_id="n1", label="RBI", node_type="entity"))
            db.add(EventGraphNode(event_id=event_id, node_id="n2", label="Banking Sector", node_type="sector"))
            db.add(EventGraphEdge(event_id=event_id, source="n1", target="n2", edge_relationship="impacts"))
            await db.commit()

        resp = client.get(f"/api/events/{event_id}")
        assert resp.status_code == 200
        body = resp.json()

        assert body["companies"][0]["impact_provenance"] == ClaimProvenance.ANALYTICAL_HYPOTHESIS.value
        assert body["affectedSectors"][0]["impact_provenance"] == ClaimProvenance.ANALYTICAL_HYPOTHESIS.value
        assert body["graph"]["edges"][0]["evidence_state"] == RippleEvidenceState.HYPOTHESIZED.value
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_real_api_response_fake_sector_reports_unavailable_through_response_model():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-api-fakesector-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Test event with no sector data, via real API",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[], category=None,
            ))
            await db.commit()

        resp = client.get(f"/api/events/{event_id}")
        assert resp.status_code == 200
        body = resp.json()

        assert body["affectedSectors"], "expected the category-default fallback sectors"
        for s in body["affectedSectors"]:
            assert s["impact"] == "unavailable"
            assert s["impact_provenance"] == ClaimProvenance.UNAVAILABLE.value
    finally:
        await _cleanup(event_id)
