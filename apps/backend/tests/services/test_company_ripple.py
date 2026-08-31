"""
Company Ripple resolver (redesign Batch 4) — real DB-backed tests on a
small SYNTHETIC graph layered on top of the real Company Master fixture
import (same pattern as test_graph_migration_executor.py). Covers the
four states graph_ripple.py must distinguish, the richest-node tie-break,
and that a historical-alias symbol still resolves to the correct real
graph node -- never a generated or templated fallback (there is none in
this module by construction).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.db.models.intelligence_graph import IGNode, IGEdge
from app.db.session import AsyncSessionLocal
from app.services.company_identity.importer import run_full_import
from app.services.company_identity.graph_ripple import get_company_ripple
from tests.services.test_company_identity import EQ_CSV, SYMBOLCHANGE_CSV, _clean_fixture_rows


def _tag():
    return uuid.uuid4().hex[:8]


@pytest.fixture
async def company_master_seeded():
    async with AsyncSessionLocal() as db:
        await _clean_fixture_rows(db)
        await run_full_import(db, EQ_CSV, SYMBOLCHANGE_CSV)
        await db.commit()
    yield
    async with AsyncSessionLocal() as db:
        await _clean_fixture_rows(db)


async def _cleanup_nodes(node_ids: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IGEdge).where(
            (IGEdge.source_id.in_(node_ids)) | (IGEdge.target_id.in_(node_ids))
        ))
        await db.execute(delete(IGNode).where(IGNode.id.in_(node_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_no_entity_for_a_symbol_that_does_not_resolve(company_master_seeded):
    async with AsyncSessionLocal() as db:
        result = await get_company_ripple(db, "ZZZZNOTREALCOMPANY")
    assert result.status == "no_entity"
    assert result.nodes == [] and result.edges == []


@pytest.mark.asyncio
async def test_no_node_for_a_real_entity_with_no_graph_presence(company_master_seeded):
    # AUROPHARMA is a real fixture entity but no IGNode is ever created for
    # it in this test — a real, common state (Tier B: real company, no
    # graph coverage yet).
    async with AsyncSessionLocal() as db:
        result = await get_company_ripple(db, "AUROPHARMA")
    assert result.status == "no_node"
    assert result.canonical_symbol == "AUROPHARMA"
    assert result.node_id is None


@pytest.mark.asyncio
async def test_no_edges_when_a_real_node_exists_but_has_zero_relationships(company_master_seeded):
    tag = _tag()
    node_id = f"company:ceat-{tag}"
    async with AsyncSessionLocal() as db:
        db.add(IGNode(id=node_id, node_type="company", label="CEAT", ticker="CEATLTD", auto_added=True))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_company_ripple(db, "CEATLTD")
        assert result.status == "no_edges"
        assert result.node_id == node_id
        assert result.edges == []
    finally:
        await _cleanup_nodes([node_id])


@pytest.mark.asyncio
async def test_has_edges_returns_real_evidence_fields(company_master_seeded):
    tag = _tag()
    n_company = f"company:reliance-{tag}"
    n_sector = f"sector:energy-{tag}"
    edge_id = f"e-{tag}"
    async with AsyncSessionLocal() as db:
        db.add_all([
            IGNode(id=n_company, node_type="company", label="Reliance", ticker="RELIANCE", auto_added=True),
            IGNode(id=n_sector, node_type="sector", label="Energy", auto_added=True),
        ])
        await db.flush()
        db.add(IGEdge(
            id=edge_id, source_id=n_company, target_id=n_sector, edge_type="benefits",
            weight=0.75, confidence=0.85, lag_days=3, description="Real evidence description",
            source_event="rss-real-test-event", auto_added=True,
        ))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_company_ripple(db, "RELIANCE")
        assert result.status == "has_edges"
        assert result.node_id == n_company
        assert len(result.edges) == 1
        e = result.edges[0]
        # Every field on the real edge must pass through unchanged -- no
        # invented labels, no recomputed "strength"/"importance".
        assert e["edge_type"] == "benefits"
        assert e["weight"] == 0.75
        assert e["confidence"] == 0.85
        assert e["lag_days"] == 3
        assert e["description"] == "Real evidence description"
        assert e["source_event"] == "rss-real-test-event"
    finally:
        await _cleanup_nodes([n_company, n_sector])


@pytest.mark.asyncio
async def test_richest_node_wins_when_multiple_nodes_resolve_to_the_same_entity(company_master_seeded):
    """Real pre-C3-merge-style duplicate: two IGNodes both resolve to the
    same TCS entity via different ticker spellings. The resolver must pick
    the one with real edges, not an arbitrary first match — the same
    tie-break graph_migration_executor.py's _choose_canonical() uses."""
    tag = _tag()
    n_rich = f"company:tcs-rich-{tag}"
    n_poor = f"company:tcs-poor-{tag}"
    n_target = f"sector:it-{tag}"
    async with AsyncSessionLocal() as db:
        db.add_all([
            IGNode(id=n_rich, node_type="company", label="TCS", ticker="TCS", auto_added=True),
            IGNode(id=n_poor, node_type="company", label="TCS", ticker="TCS.NS", auto_added=True),
            IGNode(id=n_target, node_type="sector", label="IT", auto_added=True),
        ])
        await db.flush()
        db.add(IGEdge(id=f"e-{tag}", source_id=n_rich, target_id=n_target, edge_type="benefits", weight=0.6, confidence=0.7, auto_added=True))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_company_ripple(db, "TCS")
        assert result.status == "has_edges"
        assert result.node_id == n_rich
    finally:
        await _cleanup_nodes([n_rich, n_poor, n_target])


@pytest.mark.asyncio
async def test_historical_alias_symbol_resolves_to_the_current_entitys_real_graph_node(company_master_seeded):
    """TELCO -> TATAMOTORS -> TMPV is the real rename chain (see
    nse_symbolchange_sample.csv). A request under the oldest historical
    symbol must still reach the real graph node for the current entity —
    mirrors the real live TELCO->TMPV Ripple behavior verified manually
    against the actual dev DB."""
    tag = _tag()
    node_id = f"company:tatamotors-{tag}"
    async with AsyncSessionLocal() as db:
        db.add(IGNode(id=node_id, node_type="company", label="TATAMOTORS", ticker="TATAMOTORS", auto_added=True))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_company_ripple(db, "TELCO")
        assert result.status in ("no_edges", "has_edges")
        assert result.canonical_symbol == "TMPV"
        assert result.node_id == node_id
    finally:
        await _cleanup_nodes([node_id])
