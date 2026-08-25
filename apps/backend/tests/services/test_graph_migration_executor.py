"""
Graph migration executor — real DB-backed tests on a small SYNTHETIC
graph (not the full real ~1000-node Graph; that's exercised once, for
real, directly against a copied dev DB — see
artifacts/company_identity_c3_graph_migration.md). Synthetic nodes/edges
use a uuid-prefixed id namespace so they can never collide with real
Graph data and are always cleaned up in a finally block.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

from app.db.models.intelligence_graph import IGNode, IGEdge
from app.db.session import AsyncSessionLocal
from app.services.company_identity.importer import run_full_import
from app.services.company_identity.graph_migration_plan import build_graph_migration_plan, MigrationPlan, MigrationPlanRow
from app.services.company_identity.graph_migration_executor import execute_graph_migration
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
async def test_duplicate_nodes_merge_and_edges_deduplicate(company_master_seeded):
    tag = _tag()
    n_canonical = f"company:reliance-{tag}"
    n_dup1 = f"company:reliance-ns-{tag}"
    n_dup2 = f"company:nse-reliance-{tag}"
    n_target = f"sector:energy-{tag}"

    async with AsyncSessionLocal() as db:
        db.add_all([
            IGNode(id=n_canonical, node_type="company", label="Reliance", ticker="RELIANCE", auto_added=False),
            IGNode(id=n_dup1, node_type="company", label="Reliance", ticker="RELIANCE.NS", auto_added=True),
            IGNode(id=n_dup2, node_type="company", label="Reliance", ticker="NSE:RELIANCE", auto_added=True),
            IGNode(id=n_target, node_type="sector", label="Energy"),
        ])
        await db.flush()  # nodes must exist before the FK-constrained edge inserts
        # Same real relationship, anchored to 3 different duplicate node ids
        # -- exactly the C1 finding. All 3 should collapse to 1 after merge.
        db.add_all([
            IGEdge(id=f"e1-{tag}", source_id=n_canonical, target_id=n_target, edge_type="benefits", weight=0.8, confidence=0.9, auto_added=True),
            IGEdge(id=f"e2-{tag}", source_id=n_dup1, target_id=n_target, edge_type="benefits", weight=0.7, confidence=0.8, auto_added=True),
            IGEdge(id=f"e3-{tag}", source_id=n_dup2, target_id=n_target, edge_type="benefits", weight=0.6, confidence=0.7, auto_added=True),
        ])
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            plan = await build_graph_migration_plan(db)
        our_rows = [r for r in plan.rows if r.node_id in (n_canonical, n_dup1, n_dup2)]
        assert len(our_rows) == 3
        assert all(r.action == "MERGE" for r in our_rows)
        entity_id = our_rows[0].entity_id
        assert all(r.entity_id == entity_id for r in our_rows)

        scoped_plan = MigrationPlan(rows=our_rows)

        async with AsyncSessionLocal() as db:
            dry = await execute_graph_migration(db, scoped_plan, dry_run=True)
        assert dry.nodes_merged_away == 2
        # 3 edges carrying the SAME real relationship -> 1 kept, 2 deduplicated.
        # (distinct_relationships_* fields are whole-graph counts by design --
        # a real migration needs a global before/after proof -- so they're not
        # asserted here; the per-cluster fields below are what's scoped to
        # this test's own data, and the DB check further down confirms the
        # concrete outcome directly.)
        assert sum(c.edges_deduplicated for c in dry.merge_clusters) + \
               sum(c.edges_repointed for c in dry.merge_clusters) == 2  # 2 non-canonical edges processed
        assert dry.merge_clusters[0].edges_deduplicated == 2

        async with AsyncSessionLocal() as db:
            real = await execute_graph_migration(db, scoped_plan, dry_run=False)
            await db.commit()

        assert real.relationships_preserved is True
        assert real.merge_clusters[0].edges_deduplicated == 2

        async with AsyncSessionLocal() as db:
            remaining_nodes = (await db.execute(
                select(IGNode).where(IGNode.id.in_([n_canonical, n_dup1, n_dup2]))
            )).scalars().all()
            remaining_edges = (await db.execute(
                select(IGEdge).where(IGEdge.target_id == n_target)
            )).scalars().all()
        assert len(remaining_nodes) == 1
        assert remaining_nodes[0].id == n_canonical  # manually-curated node preferred as canonical
        assert len(remaining_edges) == 1
        assert remaining_edges[0].source_id == n_canonical
    finally:
        await _cleanup_nodes([n_canonical, n_dup1, n_dup2, n_target])


@pytest.mark.asyncio
async def test_edge_directly_between_two_duplicates_becomes_a_removed_self_loop(company_master_seeded):
    """A real, if rare, case: two duplicate nodes of the SAME company
    somehow ended up with an edge between each other. After merge that's
    a self-loop on the canonical node -- meaningless, must be removed, not
    silently kept as a fake self-referencing relationship."""
    tag = _tag()
    n_canonical = f"company:tcs-{tag}"
    n_dup = f"company:tcs-ns-{tag}"

    async with AsyncSessionLocal() as db:
        db.add_all([
            IGNode(id=n_canonical, node_type="company", label="TCS", ticker="TCS", auto_added=False),
            IGNode(id=n_dup, node_type="company", label="TCS", ticker="TCS.NS", auto_added=True),
        ])
        await db.flush()
        db.add(IGEdge(id=f"eloop-{tag}", source_id=n_canonical, target_id=n_dup, edge_type="competes_with", weight=0.1, confidence=0.5, auto_added=True))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            plan = await build_graph_migration_plan(db)
        our_rows = [r for r in plan.rows if r.node_id in (n_canonical, n_dup)]
        assert len(our_rows) == 2 and all(r.action == "MERGE" for r in our_rows)
        scoped_plan = MigrationPlan(rows=our_rows)

        async with AsyncSessionLocal() as db:
            real = await execute_graph_migration(db, scoped_plan, dry_run=False)
            await db.commit()

        assert real.self_loops_removed_total == 1
        assert real.relationships_preserved is True  # the self-loop was never a real relationship

        async with AsyncSessionLocal() as db:
            remaining_edges = (await db.execute(
                select(IGEdge).where((IGEdge.source_id == n_canonical) | (IGEdge.target_id == n_canonical))
            )).scalars().all()
        assert len(remaining_edges) == 0
    finally:
        await _cleanup_nodes([n_canonical, n_dup])


@pytest.mark.asyncio
async def test_reclassify_changes_node_type_and_leaves_edges_alone(company_master_seeded):
    tag = _tag()
    n_index = f"company:nsei-{tag}"
    n_other = f"sector:x-{tag}"

    async with AsyncSessionLocal() as db:
        db.add_all([
            IGNode(id=n_index, node_type="company", label="Nifty 50", ticker="^NSEI"),
            IGNode(id=n_other, node_type="sector", label="X"),
        ])
        await db.flush()
        db.add(IGEdge(id=f"ercl-{tag}", source_id=n_index, target_id=n_other, edge_type="influences", weight=0.5, confidence=0.5))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            plan = await build_graph_migration_plan(db)
        row = next(r for r in plan.rows if r.node_id == n_index)
        assert row.action == "RECLASSIFY"
        assert row.identifier_type == "index"
        scoped_plan = MigrationPlan(rows=[row])

        async with AsyncSessionLocal() as db:
            real = await execute_graph_migration(db, scoped_plan, dry_run=False)
            await db.commit()

        assert real.nodes_reclassified == 1
        assert real.reclassify_by_type == {"index": 1}

        async with AsyncSessionLocal() as db:
            node = await db.get(IGNode, n_index)
            edges = (await db.execute(select(IGEdge).where(IGEdge.source_id == n_index))).scalars().all()
        assert node.node_type == "index"
        assert len(edges) == 1  # untouched -- reclassify never touches edges
    finally:
        await _cleanup_nodes([n_index, n_other])


@pytest.mark.asyncio
async def test_unresolved_and_ok_rows_are_never_written():
    tag = _tag()
    n_unresolved = f"company:madeup-{tag}"

    async with AsyncSessionLocal() as db:
        db.add(IGNode(id=n_unresolved, node_type="company", label="Made Up Co", ticker=f"MADEUP{tag[:4].upper()}"))
        await db.commit()

    try:
        row = MigrationPlanRow(node_id=n_unresolved, label="Made Up Co", ticker=f"MADEUP{tag[:4].upper()}", action="UNRESOLVED", identifier_type="company")
        plan = MigrationPlan(rows=[row])

        async with AsyncSessionLocal() as db:
            real = await execute_graph_migration(db, plan, dry_run=False)
            await db.commit()

        assert real.unresolved_retained == 1
        assert real.nodes_reclassified == 0
        assert real.nodes_merged_away == 0

        async with AsyncSessionLocal() as db:
            node = await db.get(IGNode, n_unresolved)
        assert node is not None
        assert node.node_type == "company"  # untouched
    finally:
        await _cleanup_nodes([n_unresolved])
