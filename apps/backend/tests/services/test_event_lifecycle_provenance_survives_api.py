"""
CD3-D (D2) — event_lifecycle.py's get_homepage_event_intelligence() used
to reduce every company dict from EventService.get_event_detail() (which
already carries real impact_provenance/impact_type per CD3-B) down to
just {symbol, name} before the homepage API response was built --
discarding exactly the information app.services.claim_authorization
needs. Same finding class for opportunity_sector/risk_sector (bare
strings, no provenance) and graph.edges[] (evidence_state dropped).

Per the owner's explicit instruction ("given the ecac930 lesson, test
the real API serialization path, not just the service object") this
suite goes through the REAL route (GET /api/homepage/intelligence) via
TestClient, not just a direct call to get_homepage_event_intelligence().
get_top_active_events() is mocked to point at a real, fully-fixtured
Event -- this isolates the provenance-serialization fix from the
unrelated active-event ranking logic, which is not what this bug is
about.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import AsyncSessionLocal
from app.db.models.event import Event, EventCompany, EventSector, EventGraphNode, EventGraphEdge
from app.db.models.intelligence_article import IntelligenceArticle
from app.schemas.event import EventSummary
from app.services.claim_provenance import ClaimProvenance, RippleEvidenceState

client = TestClient(app)


async def _cleanup(event_id: str, article_id: str) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import delete
        await db.execute(delete(EventGraphEdge).where(EventGraphEdge.event_id == event_id))
        await db.execute(delete(EventGraphNode).where(EventGraphNode.event_id == event_id))
        await db.execute(delete(EventSector).where(EventSector.event_id == event_id))
        await db.execute(delete(EventCompany).where(EventCompany.event_id == event_id))
        await db.execute(delete(Event).where(Event.id == event_id))
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id == article_id))
        await db.commit()


@pytest.mark.asyncio
async def test_real_homepage_api_response_preserves_company_and_sector_provenance():
    now = datetime.now(timezone.utc)
    event_id = f"pytest-lifecycle-provenance-{uuid.uuid4().hex[:8]}"
    article_id = str(uuid.uuid4())
    await _cleanup(event_id, article_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Test event for D2 provenance-survival check",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[],
            ))
            db.add(EventCompany(event_id=event_id, symbol="HDFCBANK", name="HDFC Bank",
                                 impact_type="beneficiary", impact_score=70.0, reason="test"))
            db.add(EventSector(event_id=event_id, sector="Banking", impact="positive", impact_score=62.0))
            db.add(EventGraphNode(event_id=event_id, node_id="n1", label="RBI", node_type="entity"))
            db.add(EventGraphNode(event_id=event_id, node_id="n2", label="Banking Sector", node_type="sector"))
            db.add(EventGraphEdge(event_id=event_id, source="n1", target="n2", edge_relationship="impacts"))
            # A real morning_intelligence article, required by the route
            # ahead of the event-engine call (see homepage_intelligence.py).
            db.add(IntelligenceArticle(
                id=article_id, slug=f"pytest-brief-{uuid.uuid4().hex[:8]}",
                article_type="morning_intelligence", angle="primary", is_evergreen=False,
                lifecycle_status="published", status="published",
                headline="Test Morning Brief", executive_summary="Test.",
                key_takeaway="Test.", companies_affected=[], sectors_affected=[],
                sources=["Test"], published_at=now, last_updated=now, update_count=0,
            ))
            await db.commit()

        fake_summary = EventSummary(
            id=event_id, slug="", title="Test event", summary="",
            impact_score=90.0, confidence=80.0, sectors=["Banking"], companies=[],
            date=now, lifecycle="Live", active_score=99.0,
        )
        with patch("app.services.event_lifecycle.get_top_active_events", new=AsyncMock(return_value=[fake_summary])):
            resp = client.get("/api/homepage/intelligence")

        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        # GET /api/homepage/intelligence nests the event-engine output
        # under "event" -> "primary" (app/api/homepage_intelligence.py).
        assert body["event"]["available"] is True
        primary = body["event"]["primary"]

        assert primary["companies"], "expected the real HDFCBANK company row"
        company = primary["companies"][0]
        assert company["symbol"] == "HDFCBANK"
        assert company["impact_provenance"] == ClaimProvenance.ANALYTICAL_HYPOTHESIS.value
        # HDFCBANK qualifies as a true beneficiary, so it reaches this
        # response via detail["beneficiaries"] (event_service.py's
        # pre-filtered list, which never carries impact_type -- the value
        # is redundant once a row is already known to be a beneficiary).
        # _preserve_provenance's impact_type passthrough is exercised by
        # the companion test below via the unfiltered `companies` path.
        assert "impact_type" not in company

        assert primary["opportunity_sector"] == "Banking"
        assert primary["opportunity_sector_provenance"] == ClaimProvenance.ANALYTICAL_HYPOTHESIS.value

        assert primary["ripple"], "expected the real graph edge"
        assert primary["ripple"][0]["evidence_state"] == RippleEvidenceState.HYPOTHESIZED.value
    finally:
        await _cleanup(event_id, article_id)


@pytest.mark.asyncio
async def test_real_api_response_preserves_impact_type_via_the_unfiltered_companies_path():
    """When no company qualifies as a true beneficiary, event_service.py
    falls back to the unfiltered `companies` list, which DOES carry
    impact_type -- confirms _preserve_provenance's optional passthrough
    actually fires on that path."""
    now = datetime.now(timezone.utc)
    event_id = f"pytest-lifecycle-losertype-{uuid.uuid4().hex[:8]}"
    article_id = str(uuid.uuid4())
    await _cleanup(event_id, article_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(
                id=event_id, title="Test event, loser-only company",
                source="Test", event_type="macro", created_at=now, updated_at=now,
                enrichment_status="done", sectors=[], companies=[],
            ))
            db.add(EventCompany(event_id=event_id, symbol="TATASTEEL", name="Tata Steel",
                                 impact_type="loser", impact_score=25.0, reason="test"))
            db.add(IntelligenceArticle(
                id=article_id, slug=f"pytest-brief-{uuid.uuid4().hex[:8]}",
                article_type="morning_intelligence", angle="primary", is_evergreen=False,
                lifecycle_status="published", status="published",
                headline="Test Morning Brief 2", executive_summary="Test.",
                key_takeaway="Test.", companies_affected=[], sectors_affected=[],
                sources=["Test"], published_at=now, last_updated=now, update_count=0,
            ))
            await db.commit()

        fake_summary = EventSummary(
            id=event_id, slug="", title="Test event", summary="",
            impact_score=90.0, confidence=80.0, sectors=[], companies=[],
            date=now, lifecycle="Live", active_score=99.0,
        )
        with patch("app.services.event_lifecycle.get_top_active_events", new=AsyncMock(return_value=[fake_summary])):
            resp = client.get("/api/homepage/intelligence")

        assert resp.status_code == 200
        body = resp.json()
        primary = body["event"]["primary"]
        assert primary["companies"], "expected the real TATASTEEL company row via the unfiltered fallback"
        company = primary["companies"][0]
        assert company["symbol"] == "TATASTEEL"
        assert company["impact_provenance"] == ClaimProvenance.ANALYTICAL_HYPOTHESIS.value
        assert company["impact_type"] == "loser"
    finally:
        await _cleanup(event_id, article_id)


@pytest.mark.asyncio
async def test_legacy_company_with_no_provenance_field_fails_closed_to_unknown():
    """A company dict that genuinely predates CD3-B tagging (no
    impact_provenance key at all) must resolve to UNKNOWN through the
    real API response -- never silently inferred as ANALYTICAL_HYPOTHESIS
    or any stronger claim just because a symbol/name is present."""
    from app.services.event_lifecycle import get_homepage_event_intelligence

    now = datetime.now(timezone.utc)
    event_id = f"pytest-lifecycle-legacy-{uuid.uuid4().hex[:8]}"

    class _FakeDB:
        pass

    fake_detail = {
        "event": {"slug": "test", "title": "Legacy test event"},
        "affectedSectors": [],
        "beneficiaries": [{"symbol": "RELIANCE", "name": "Reliance"}],  # no impact_provenance key at all
        "companies": [],
        "summary": {"why_it_matters": "Real reason."},
        "graph": {},
        "confidence": 50.0, "impactScore": 60.0,
    }
    fake_summary = EventSummary(
        id=event_id, slug="", title="Legacy test event", summary="",
        impact_score=60.0, confidence=50.0, sectors=[], companies=[],
        date=now, lifecycle="Live", active_score=50.0,
    )
    with patch("app.services.event_lifecycle.get_top_active_events", new=AsyncMock(return_value=[fake_summary])), \
         patch("app.services.event_service.EventService.get_event_detail", new=AsyncMock(return_value=fake_detail)):
        result = await get_homepage_event_intelligence(_FakeDB())

    assert result["available"] is True
    company = result["primary"]["companies"][0]
    assert company["symbol"] == "RELIANCE"
    assert company["impact_provenance"] == ClaimProvenance.UNKNOWN.value
