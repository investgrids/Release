"""
read_service.py::_build_development_impacts -- the per-Development
sector/company attribution added to the V2 read contract (2026-09-20,
canary review fix). Pure-function unit tests (no DB) for the derivation
logic itself, plus one real DB-backed end-to-end test proving the new
field is wired into get_opportunity_v2_detail() without disturbing any
existing field (backward compatibility).
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
from app.services.opportunity_v2.read_service import (
    CompanyConnectedSchema,
    RippleEdgeSchema,
    RippleNodeSchema,
    RippleSchema,
    SupportingEvidenceSchema,
    _build_development_impacts,
    get_opportunity_v2_detail,
)


def _sev(dev_id: str, title: str = "Real development") -> SupportingEvidenceSchema:
    return SupportingEvidenceSchema(
        development_id=dev_id, canonical_title=title, evidence_count=2,
        current_confidence=0.8, current_impact_tier="High",
        first_observed_at="2026-09-19T00:00:00Z", source_types=["news"],
    )


# ── Pure derivation logic ─────────────────────────────────────────────────

def test_single_development_gets_its_own_real_sector_and_company():
    dev_id = "dev-a"
    ripple = RippleSchema(
        anchor=None,
        nodes=[
            RippleNodeSchema(id=f"development:{dev_id}", node_type="development", label="Real dev"),
            RippleNodeSchema(id="sector:Banking", node_type="sector", label="Banking"),
            RippleNodeSchema(id="company:HDFCBANK", node_type="company", label="HDFC Bank", ticker="HDFCBANK"),
        ],
        edges=[
            RippleEdgeSchema(id="e1", source=f"development:{dev_id}", target="sector:Banking", edge_type="benefits"),
            RippleEdgeSchema(id="e2", source=f"development:{dev_id}", target="company:HDFCBANK", edge_type="benefits"),
        ],
    )
    rows = _build_development_impacts(ripple, [_sev(dev_id)], [
        CompanyConnectedSchema(symbol="HDFCBANK", company_name="HDFC Bank", confirms_thesis=True),
    ])
    assert len(rows) == 1
    assert len(rows[0].sector_impacts) == 1
    assert rows[0].sector_impacts[0].sector == "Banking"
    assert rows[0].sector_impacts[0].direction == "benefits"
    assert rows[0].company_impacts[0].symbol == "HDFCBANK"
    assert rows[0].company_impacts[0].confirms_thesis is True


def test_multi_development_opportunity_each_row_shows_only_its_own_distinct_sectors():
    ripple = RippleSchema(
        anchor=None,
        nodes=[
            RippleNodeSchema(id="development:dev-a", node_type="development", label="Dev A"),
            RippleNodeSchema(id="development:dev-b", node_type="development", label="Dev B"),
            RippleNodeSchema(id="sector:Banking", node_type="sector", label="Banking"),
            RippleNodeSchema(id="sector:Pharma", node_type="sector", label="Pharma"),
        ],
        edges=[
            RippleEdgeSchema(id="e1", source="development:dev-a", target="sector:Banking", edge_type="benefits"),
            RippleEdgeSchema(id="e2", source="development:dev-b", target="sector:Pharma", edge_type="hurts"),
        ],
    )
    rows = _build_development_impacts(ripple, [_sev("dev-a", "Dev A"), _sev("dev-b", "Dev B")], [])
    assert len(rows) == 2
    by_id = {r.development_id: r for r in rows}
    assert [s.sector for s in by_id["dev-a"].sector_impacts] == ["Banking"]
    assert [s.sector for s in by_id["dev-b"].sector_impacts] == ["Pharma"]


def test_no_sector_leakage_between_developments():
    """The literal regression this fixes: a pooled union would have shown
    BOTH Banking and Pharma on both rows. Real edges never blend -- each
    row must show ONLY what its own Development has a real edge to."""
    ripple = RippleSchema(
        anchor=None,
        nodes=[
            RippleNodeSchema(id="development:dev-a", node_type="development", label="Dev A"),
            RippleNodeSchema(id="development:dev-b", node_type="development", label="Dev B"),
            RippleNodeSchema(id="sector:Banking", node_type="sector", label="Banking"),
            RippleNodeSchema(id="sector:Pharma", node_type="sector", label="Pharma"),
        ],
        edges=[
            RippleEdgeSchema(id="e1", source="development:dev-a", target="sector:Banking", edge_type="benefits"),
            RippleEdgeSchema(id="e2", source="development:dev-b", target="sector:Pharma", edge_type="hurts"),
        ],
    )
    rows = _build_development_impacts(ripple, [_sev("dev-a"), _sev("dev-b")], [])
    by_id = {r.development_id: r for r in rows}
    dev_a_sectors = {s.sector for s in by_id["dev-a"].sector_impacts}
    dev_b_sectors = {s.sector for s in by_id["dev-b"].sector_impacts}
    assert "Pharma" not in dev_a_sectors
    assert "Banking" not in dev_b_sectors


def test_development_with_no_real_graph_edges_produces_no_row_never_an_empty_placeholder():
    ripple = RippleSchema(
        anchor=None,
        nodes=[RippleNodeSchema(id="development:dev-a", node_type="development", label="Dev A")],
        edges=[],
    )
    rows = _build_development_impacts(ripple, [_sev("dev-a")], [])
    assert rows == []


def test_development_not_in_the_ripple_union_at_all_produces_no_row():
    """A Development with no ig_node_id (never graph-linked) -- its node
    simply won't be in `ripple.nodes` at all."""
    ripple = RippleSchema(anchor=None, nodes=[], edges=[])
    rows = _build_development_impacts(ripple, [_sev("dev-a")], [])
    assert rows == []


def test_reversed_policy_to_development_edge_is_never_read_as_an_outgoing_impact():
    ripple = RippleSchema(
        anchor=None,
        nodes=[
            RippleNodeSchema(id="development:dev-a", node_type="development", label="Dev A"),
            RippleNodeSchema(id="policy:some-policy", node_type="policy", label="Some Policy"),
        ],
        edges=[
            RippleEdgeSchema(id="e1", source="policy:some-policy", target="development:dev-a", edge_type="influences"),
        ],
    )
    rows = _build_development_impacts(ripple, [_sev("dev-a")], [])
    assert rows == []  # the only edge present points INTO dev-a, never out of it


def test_company_attribution_reuses_the_real_confirms_and_contradicts_signal():
    ripple = RippleSchema(
        anchor=None,
        nodes=[
            RippleNodeSchema(id="development:dev-a", node_type="development", label="Dev A"),
            RippleNodeSchema(id="company:ICICIBANK", node_type="company", label="ICICI Bank", ticker="ICICIBANK"),
        ],
        edges=[
            RippleEdgeSchema(id="e1", source="development:dev-a", target="company:ICICIBANK", edge_type="hurts"),
        ],
    )
    rows = _build_development_impacts(ripple, [_sev("dev-a")], [
        CompanyConnectedSchema(symbol="ICICIBANK", company_name="ICICI Bank", contradicts_thesis=True),
    ])
    assert rows[0].company_impacts[0].contradicts_thesis is True
    assert rows[0].company_impacts[0].confirms_thesis is False


def test_company_with_no_real_signal_still_attributed_honestly_never_fabricated():
    ripple = RippleSchema(
        anchor=None,
        nodes=[
            RippleNodeSchema(id="development:dev-a", node_type="development", label="Dev A"),
            RippleNodeSchema(id="company:UNKNOWNCO", node_type="company", label="Unknown Co", ticker="UNKNOWNCO"),
        ],
        edges=[
            RippleEdgeSchema(id="e1", source="development:dev-a", target="company:UNKNOWNCO", edge_type="influences"),
        ],
    )
    rows = _build_development_impacts(ripple, [_sev("dev-a")], [])  # no real signal for UNKNOWNCO at all
    assert rows[0].company_impacts[0].confirms_thesis is False
    assert rows[0].company_impacts[0].contradicts_thesis is False
    assert rows[0].company_impacts[0].company_name == "Unknown Co"  # falls back to the real node label


def test_empty_sectors_column_is_honestly_empty_not_padded():
    ripple = RippleSchema(
        anchor=None,
        nodes=[
            RippleNodeSchema(id="development:dev-a", node_type="development", label="Dev A"),
            RippleNodeSchema(id="company:HDFCBANK", node_type="company", label="HDFC Bank", ticker="HDFCBANK"),
        ],
        edges=[
            RippleEdgeSchema(id="e1", source="development:dev-a", target="company:HDFCBANK", edge_type="benefits"),
        ],
    )
    rows = _build_development_impacts(ripple, [_sev("dev-a")], [])
    assert rows[0].sector_impacts == []
    assert len(rows[0].company_impacts) == 1


# ── Real DB-backed: backward compatibility ────────────────────────────────

def _make_dev(title: str, *, companies=None, sectors=None) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()), canonical_title=title, status="open",
        primary_company=(companies or [None])[0], companies=companies or [], sectors=sectors or [],
        themes=[], first_observed_at=now, last_observed_at=now,
        formation_impact_tier="High", current_direction="positive", current_confidence=0.9,
        evidence_count=1, schema_version="test",
    )


async def _link(dev: Development) -> str:
    async with AsyncSessionLocal() as db:
        db.add(dev)
        await db.commit()
        node_id = await link_development_to_graph(db, dev)
        dev.ig_node_id = node_id
        db.add(dev)
        await db.commit()
    return node_id


async def _cleanup(development_ids, node_ids, opportunity_ids) -> None:
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


@pytest.mark.asyncio
async def test_existing_fields_remain_unchanged_new_field_is_purely_additive():
    ticker = f"TDEVIMP{uuid.uuid4().hex[:4].upper()}"
    dev = _make_dev("Real development for backward-compat check", companies=[ticker], sectors=["Banking"])
    now = datetime.now(timezone.utc)
    opp = OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor=f"company:{ticker.lower()}", thesis_direction="positive",
        status="open", source="test",
        candidate_status="formed", narrative_status="generated", public_status="public",
        formation_title="Real Backward Compat Test", formation_score=50.0, formation_at=now,
        current_title="Real Backward Compat Test", current_summary="Real summary.", current_score=50.0,
        sectors=["Banking"], companies=[ticker], contradictions=[],
        slug=f"real-backward-compat-{uuid.uuid4().hex[:8]}",
        created_at=now, updated_at=now,
    )
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev))
        async with AsyncSessionLocal() as db:
            db.add(opp)
            await db.commit()
            db.add(OpportunityV2Development(opportunity_id=opp.id, development_id=dev.id, added_at=now))
            await db.commit()
        opp_ids = [opp.id]

        async with AsyncSessionLocal() as db:
            detail = await get_opportunity_v2_detail(db, opp.slug)

        assert detail is not None
        # Every pre-existing field is still present and correct.
        assert detail.slug == opp.slug
        assert detail.sectors_themes == ["Banking"]
        assert len(detail.supporting_evidence) == 1
        assert len(detail.ripple.nodes) >= 1
        # New field is additive and real.
        assert len(detail.development_impacts) == 1
        assert detail.development_impacts[0].development_id == dev.id
    finally:
        await _cleanup([dev.id], node_ids, opp_ids)
