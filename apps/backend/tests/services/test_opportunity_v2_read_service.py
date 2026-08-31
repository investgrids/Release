"""
opportunity_v2/read_service.py — real DB-backed tests for the V2-A
contract: get_opportunity_v2_detail() and the fields the frontend's
V2OpportunityDetail component actually renders
(OpportunityPageClient.tsx). Not mocked — real OpportunityV2/Development
rows, real graph links via link_development_to_graph, same precedent as
test_opportunity_v2_orchestration.py.

Don't run this file while the local uvicorn dev server (or any other
process writing to the same sqlite dev DB) is running — same real
`database is locked` risk documented in
test_opportunity_v2_orchestration.py's own module docstring.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.development import Development
from app.db.models.intelligence_graph import IGEdge, IGNode
from app.db.models.opportunity_v2 import OpportunityV2, OpportunityV2Development
from app.db.session import AsyncSessionLocal
from app.services.development_memory.graph_link import link_development_to_graph
from app.services.opportunity_v2.read_service import get_opportunity_v2_detail


async def _cleanup(development_ids: list[str], node_ids: list[str], opportunity_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        if opportunity_ids:
            await db.execute(delete(OpportunityV2Development).where(OpportunityV2Development.opportunity_id.in_(opportunity_ids)))
            await db.execute(delete(OpportunityV2).where(OpportunityV2.id.in_(opportunity_ids)))
        if development_ids:
            await db.execute(delete(Development).where(Development.id.in_(development_ids)))
        if node_ids:
            await db.execute(delete(IGEdge).where(IGEdge.source_id.in_(node_ids) | IGEdge.target_id.in_(node_ids)))
            await db.execute(delete(IGNode).where(IGNode.id.in_(node_ids)))
        await db.commit()


def _make_dev(title: str, *, companies: list[str] | None = None, sectors: list[str] | None = None) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()), canonical_title=title, status="open",
        primary_company=(companies or [None])[0], companies=companies or [], sectors=sectors or [],
        themes=[], first_observed_at=now, last_observed_at=now,
        formation_impact_tier="High", current_direction="positive", current_confidence=0.9,
        evidence_count=1, schema_version="test",
    )


def _make_opp(*, thesis_anchor: str, public_status: str, current_title: str | None,
              formation_title: str | None = None, companies: list[str] | None = None,
              score_breakdown: dict | None = None, contradictions: list[str] | None = None) -> OpportunityV2:
    now = datetime.now(timezone.utc)
    return OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor=thesis_anchor, thesis_direction="positive",
        status="open", source="test",
        candidate_status="formed", narrative_status="generated", public_status=public_status,
        formation_title=formation_title, formation_score=50.0, formation_at=now,
        current_title=current_title, current_summary="Real test summary.", current_score=55.0,
        sectors=["Banking"], companies=companies or [],
        slug=f"test-opp-{uuid.uuid4().hex[:8]}",
        score_breakdown=score_breakdown, contradictions=contradictions or [],
        created_at=now, updated_at=now,
    )


@pytest.mark.asyncio
async def test_shadow_opportunity_returns_none_public_status_gate_holds():
    """Re-confirms the public_status gate this file's sibling module
    (radar.py) depends on for the dual V1/V2 lookup route — a real
    regression here would silently expose every shadow opportunity."""
    opp = _make_opp(thesis_anchor="company:testbank", public_status="shadow", current_title="Shadow Test Opportunity")
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            detail = await get_opportunity_v2_detail(db, opp.slug)
        assert detail is None
    finally:
        await _cleanup([], [], [opp.id])


@pytest.mark.asyncio
async def test_unknown_slug_returns_none():
    async with AsyncSessionLocal() as db:
        detail = await get_opportunity_v2_detail(db, "this-slug-does-not-exist-at-all-zzz")
    assert detail is None


@pytest.mark.asyncio
async def test_public_opportunity_renders_real_companies_evidence_and_ripple():
    """The V2-A target completion condition, at the service layer: a real
    public opportunity with a real graph-linked Development returns real
    companies_connected (from the persisted score_breakdown, never a live
    recompute), real supporting_evidence, and a real non-empty Ripple
    subgraph rooted on the real thesis anchor."""
    dev = _make_dev("Test Bank posts strong quarterly results", companies=["TESTBANK"], sectors=["Banking"])
    node_ids: list[str] = []
    opp_ids: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            node_id = await link_development_to_graph(db, dev)
            assert node_id
            dev.ig_node_id = node_id
            db.add(dev)
            await db.commit()
        node_ids.append(node_id)

        score_breakdown = {
            "evidence_quality": 80.0, "development_count": 1.0,
            "company_confirmation": 60.0, "sector_confirmation": 40.0,
            "freshness": 90.0, "contradiction_penalty": 0.0,
            "company_signals": [
                {"symbol": "TESTBANK", "score": 71.5, "real_direction": "positive", "confirms_thesis": True, "contradicts_thesis": False},
            ],
        }
        opp = _make_opp(
            thesis_anchor=node_id, public_status="public", current_title="Test Bank Strong Results Opportunity",
            companies=["TESTBANK"], score_breakdown=score_breakdown, contradictions=["TESTBANK: one real disagreeing signal"],
        )
        async with AsyncSessionLocal() as db:
            db.add(opp)
            await db.commit()
        opp_ids.append(opp.id)

        async with AsyncSessionLocal() as db:
            db.add(OpportunityV2Development(opportunity_id=opp.id, development_id=dev.id))
            await db.commit()

        async with AsyncSessionLocal() as db:
            detail = await get_opportunity_v2_detail(db, opp.slug)

        assert detail is not None
        assert detail.title == "Test Bank Strong Results Opportunity"
        assert detail.public_status == "public"

        # Companies Connected — real, from the persisted score_breakdown
        assert len(detail.companies_connected) == 1
        c = detail.companies_connected[0]
        assert c.symbol == "TESTBANK"
        assert c.real_score == 71.5
        assert c.real_direction == "positive"
        assert c.confirms_thesis is True

        # Supporting Evidence — real linked Development
        assert len(detail.supporting_evidence) == 1
        assert detail.supporting_evidence[0].development_id == dev.id
        assert detail.supporting_evidence[0].canonical_title == "Test Bank posts strong quarterly results"

        # Ripple — real, non-empty, rooted on the real thesis anchor
        assert detail.ripple.anchor == node_id
        assert len(detail.ripple.nodes) >= 1
        assert any(n.id == node_id for n in detail.ripple.nodes)

        # Contradictions — real, never invented
        assert detail.contradictions_risks == ["TESTBANK: one real disagreeing signal"]
    finally:
        await _cleanup([dev.id], node_ids, opp_ids)


@pytest.mark.asyncio
async def test_ripple_is_empty_not_a_manufactured_star_when_no_graph_linked_developments():
    """A raw_company:/raw_dev:-anchored opportunity with zero graph-linked
    Developments must return an EMPTY Ripple, not a synthetic single-anchor
    star — the exact fabrication pattern Phase 0 removed elsewhere in the
    app. Development exists but is deliberately never linked to the graph
    (ig_node_id stays null)."""
    dev = _make_dev("Unlinked development with no real graph node", companies=["RAWCO"])
    opp_ids: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()

        opp = _make_opp(thesis_anchor="raw_company:RAWCO", public_status="public", current_title="Raw Company Opportunity")
        async with AsyncSessionLocal() as db:
            db.add(opp)
            await db.commit()
        opp_ids.append(opp.id)

        async with AsyncSessionLocal() as db:
            db.add(OpportunityV2Development(opportunity_id=opp.id, development_id=dev.id))
            await db.commit()

        async with AsyncSessionLocal() as db:
            detail = await get_opportunity_v2_detail(db, opp.slug)

        assert detail is not None
        assert detail.ripple.anchor is None
        assert detail.ripple.nodes == []
        assert detail.ripple.edges == []
    finally:
        await _cleanup([dev.id], [], opp_ids)


@pytest.mark.asyncio
async def test_title_falls_back_to_formation_title_then_thesis_anchor():
    """The real fallback chain (current_title or formation_title or
    thesis_anchor) the frontend depends on to always have something to
    put in <h1>/metadata, even for an opportunity narrative generation
    hasn't produced a title for yet."""
    opp_ids: list[str] = []
    try:
        # current_title present -> used
        opp1 = _make_opp(thesis_anchor="company:a", public_status="public", current_title="Current Wins", formation_title="Formation Loses")
        # current_title absent, formation_title present -> falls back
        opp2 = _make_opp(thesis_anchor="company:b", public_status="public", current_title=None, formation_title="Formation Wins")
        # both absent -> falls back to the real thesis_anchor
        opp3 = _make_opp(thesis_anchor="company:c", public_status="public", current_title=None, formation_title=None)

        async with AsyncSessionLocal() as db:
            db.add_all([opp1, opp2, opp3])
            await db.commit()
        opp_ids = [opp1.id, opp2.id, opp3.id]

        async with AsyncSessionLocal() as db:
            d1 = await get_opportunity_v2_detail(db, opp1.slug)
            d2 = await get_opportunity_v2_detail(db, opp2.slug)
            d3 = await get_opportunity_v2_detail(db, opp3.slug)

        assert d1.title == "Current Wins"
        assert d2.title == "Formation Wins"
        assert d3.title == "company:c"
    finally:
        await _cleanup([], [], opp_ids)
