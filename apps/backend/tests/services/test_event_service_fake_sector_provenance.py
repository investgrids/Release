"""
CD3-B — _FakeSector fail-closed fix + sector/company/graph-edge claim
provenance tagging in EventService.get_event_detail.

CD3-A found event_service.py's _FakeSector fallback (used when an event has
no real EventSector rows AND no Event.sectors JSON) hardcoded
impact="positive" from zero evidence -- a fabricated directional claim,
indistinguishable from a real one at the API surface. Fixed to
impact="unavailable", which itself must never authorize a directional
claim (not even "neutral" -- the owner's explicit correction). This suite
proves: (1) the fallback path now reports "unavailable", (2) a real
EventSector row is correctly tagged ANALYTICAL_HYPOTHESIS instead, (3)
companies/beneficiaries/losers/graph edges all carry their own correct
provenance/evidence_state tags.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.event import Event, EventCompany, EventSector, EventGraphEdge, EventGraphNode
from app.services.claim_provenance import ClaimProvenance, RippleEvidenceState
from app.services.event_service import EventService


async def _cleanup(event_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventGraphEdge).where(EventGraphEdge.event_id == event_id))
        await db.execute(delete(EventGraphNode).where(EventGraphNode.event_id == event_id))
        await db.execute(delete(EventSector).where(EventSector.event_id == event_id))
        await db.execute(delete(EventCompany).where(EventCompany.event_id == event_id))
        await db.execute(delete(Event).where(Event.id == event_id))
        await db.commit()


@pytest.mark.asyncio
async def test_fake_sector_fallback_reports_unavailable_not_positive():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-event-fakesector-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            # No category, no Event.sectors, no real EventSector rows --
            # forces the _FakeSector zero-evidence fallback.
            db.add(Event(
                id=event_id, title="Test event with no sector data at all",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[], category=None,
            ))
            await db.commit()

            detail = await EventService(db).get_event_detail(event_id)
        assert detail is not None
        assert detail["affectedSectors"], "expected the category-default fallback sectors"
        for s in detail["affectedSectors"]:
            assert s["impact"] == "unavailable", "fabricated 'positive' must not survive"
            assert s["impact_provenance"] == ClaimProvenance.UNAVAILABLE.value
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_real_event_sector_row_tagged_as_analytical_hypothesis():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-event-realsector-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Test event with a real EventSector row",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[],
            ))
            db.add(EventSector(event_id=event_id, sector="Banking", impact="positive", impact_score=62.0))
            await db.commit()

            detail = await EventService(db).get_event_detail(event_id)
        assert detail is not None
        assert len(detail["affectedSectors"]) == 1
        s = detail["affectedSectors"][0]
        assert s["impact"] == "positive"  # real value untouched
        assert s["impact_provenance"] == ClaimProvenance.ANALYTICAL_HYPOTHESIS.value
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_companies_beneficiaries_losers_tagged_as_analytical_hypothesis():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-event-companies-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Test event with real EventCompany rows",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[],
            ))
            db.add(EventCompany(event_id=event_id, symbol="HDFCBANK", name="HDFC Bank",
                                 impact_type="beneficiary", impact_score=70.0, reason="test"))
            db.add(EventCompany(event_id=event_id, symbol="ICICIBANK", name="ICICI Bank",
                                 impact_type="loser", impact_score=30.0, reason="test"))
            await db.commit()

            detail = await EventService(db).get_event_detail(event_id)
        assert detail is not None
        assert len(detail["companies"]) == 2
        for c in detail["companies"]:
            assert c["impact_provenance"] == ClaimProvenance.ANALYTICAL_HYPOTHESIS.value
        assert len(detail["beneficiaries"]) == 1
        assert detail["beneficiaries"][0]["impact_provenance"] == ClaimProvenance.ANALYTICAL_HYPOTHESIS.value
        assert len(detail["losers"]) == 1
        assert detail["losers"][0]["impact_provenance"] == ClaimProvenance.ANALYTICAL_HYPOTHESIS.value
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_graph_edges_tagged_as_hypothesized():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-event-graph-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Test event with a real graph edge",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[],
            ))
            db.add(EventGraphNode(event_id=event_id, node_id="n1", label="RBI", node_type="entity"))
            db.add(EventGraphNode(event_id=event_id, node_id="n2", label="Banking Sector", node_type="sector"))
            db.add(EventGraphEdge(event_id=event_id, source="n1", target="n2", edge_relationship="impacts"))
            await db.commit()

            detail = await EventService(db).get_event_detail(event_id)
        assert detail is not None
        assert len(detail["graph"]["edges"]) == 1
        edge = detail["graph"]["edges"][0]
        assert edge["relationship"] == "impacts"  # real value untouched
        assert edge["evidence_state"] == RippleEvidenceState.HYPOTHESIZED.value
    finally:
        await _cleanup(event_id)
