"""
Phase 6B — Development -> Intelligence Graph linking
(app/services/development_memory/graph_link.py).

A new consumer of the existing IGNode/IGEdge graph, not a change to it.
Live tests against the real dev DB, following this codebase's established
convention for proving DB-backed behavior actually works. Every test
cleans up the development/evidence/graph rows it creates -- graph writes
(upsert_node/upsert_edge) manage their own sessions/commits internally,
so cleanup happens via direct deletes, not a rollback.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models.development import Development, DevelopmentEvidence
from app.db.models.event import GovernmentPolicy
from app.db.models.intelligence_graph import IGEdge, IGNode
from app.db.session import AsyncSessionLocal
from app.services.development_memory.graph_link import (
    HIGH_URGENCY_THRESHOLD,
    is_graph_worthy,
    link_development_to_graph,
)


async def _cleanup(db, *, development_ids: list[str] = (), node_ids: list[str] = (),
                    policy_ids: list[int] = ()) -> None:
    if development_ids:
        await db.execute(delete(DevelopmentEvidence).where(DevelopmentEvidence.development_id.in_(development_ids)))
        await db.execute(delete(Development).where(Development.id.in_(development_ids)))
    if node_ids:
        await db.execute(delete(IGEdge).where(
            IGEdge.source_id.in_(node_ids) | IGEdge.target_id.in_(node_ids)
        ))
        await db.execute(delete(IGNode).where(IGNode.id.in_(node_ids)))
    if policy_ids:
        await db.execute(delete(GovernmentPolicy).where(GovernmentPolicy.id.in_(policy_ids)))
    await db.commit()


def _make_dev(*, evidence_count: int = 1, formation_impact_tier: str | None = None,
              companies: list[str] | None = None, sectors: list[str] | None = None) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()),
        canonical_title="Test development for 6B graph linking",
        status="open",
        primary_company=(companies or [None])[0],
        companies=companies or [],
        sectors=sectors or [],
        themes=[],
        first_observed_at=now,
        last_observed_at=now,
        formation_impact_tier=formation_impact_tier,
        current_direction="positive",
        evidence_count=evidence_count,
        schema_version="test",
    )


@pytest.mark.asyncio
async def test_is_graph_worthy_true_for_corroborated_development():
    dev = _make_dev(evidence_count=2)
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            assert await is_graph_worthy(db, dev) is True
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=ids)


@pytest.mark.asyncio
async def test_is_graph_worthy_true_for_high_impact_single_evidence():
    """A single Critical-tier development must not need a second source
    to become graph-worthy -- corroboration and materiality are separate
    dimensions."""
    dev = _make_dev(evidence_count=1, formation_impact_tier="Critical")
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            assert await is_graph_worthy(db, dev) is True
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=ids)


@pytest.mark.asyncio
async def test_is_graph_worthy_false_for_routine_single_evidence():
    dev = _make_dev(evidence_count=1, formation_impact_tier=None)
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            assert await is_graph_worthy(db, dev) is False
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=ids)


@pytest.mark.asyncio
async def test_link_creates_development_node_and_company_edge():
    ticker = f"T6B{uuid.uuid4().hex[:6].upper()}"
    dev = _make_dev(evidence_count=2, companies=[ticker], sectors=["Test Sector 6B"])
    dev_node_id = f"development:{dev.id}"
    node_ids: list[str] = [dev_node_id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()

            result = await link_development_to_graph(db, dev)
            assert result == dev_node_id

            node = await db.get(IGNode, dev_node_id)
            assert node is not None
            assert node.node_type == "development"

            company_node = (await db.execute(
                select(IGNode).where(IGNode.node_type == "company", IGNode.ticker == ticker)
            )).scalar_one_or_none()
            assert company_node is not None
            node_ids.append(company_node.id)

            sector_node_id = "sector:test-sector-6b"
            node_ids.append(sector_node_id)
            edge = (await db.execute(
                select(IGEdge).where(IGEdge.source_id == dev_node_id, IGEdge.target_id == company_node.id)
            )).scalar_one_or_none()
            assert edge is not None
            assert edge.edge_type == "benefits"  # current_direction="positive"
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=[dev.id], node_ids=node_ids)


@pytest.mark.asyncio
async def test_link_is_idempotent_no_duplicate_edges_on_rerun():
    ticker = f"T6B{uuid.uuid4().hex[:6].upper()}"
    dev = _make_dev(evidence_count=2, companies=[ticker])
    dev_node_id = f"development:{dev.id}"
    node_ids: list[str] = [dev_node_id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            await link_development_to_graph(db, dev)
            await link_development_to_graph(db, dev)  # rerun

            company_node = (await db.execute(
                select(IGNode).where(IGNode.node_type == "company", IGNode.ticker == ticker)
            )).scalar_one_or_none()
            node_ids.append(company_node.id)

            edges = (await db.execute(
                select(IGEdge).where(IGEdge.source_id == dev_node_id, IGEdge.target_id == company_node.id)
            )).scalars().all()
            assert len(edges) == 1
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=[dev.id], node_ids=node_ids)


@pytest.mark.asyncio
async def test_non_worthy_development_is_not_linked():
    dev = _make_dev(evidence_count=1, formation_impact_tier=None)
    dev_node_id = f"development:{dev.id}"
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            result = await link_development_to_graph(db, dev)
            assert result is None
            node = await db.get(IGNode, dev_node_id)
            assert node is None
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=[dev.id])


@pytest.mark.asyncio
async def test_legacy_event_node_backfill_links_on_exact_membership():
    """The user's explicit rule: link ONLY on exact DevelopmentEvidence
    membership with a pre-existing event:{id} node -- never fuzzy-search."""
    event_id = f"evt-6b-{uuid.uuid4().hex[:8]}"
    legacy_node_id = f"event:{event_id}"
    dev = _make_dev(evidence_count=2)
    dev_node_id = f"development:{dev.id}"
    node_ids = [dev_node_id, legacy_node_id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            db.add(IGNode(id=legacy_node_id, node_type="event", label="Legacy test event",
                          created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            db.add(DevelopmentEvidence(
                id=str(uuid.uuid4()), development_id=dev.id, source_type="event", source_id=event_id,
                evidence_key=event_id, observed_at=datetime.now(timezone.utc), title="x", match_tier="seed",
            ))
            await db.commit()

            await link_development_to_graph(db, dev)

            edge = (await db.execute(
                select(IGEdge).where(IGEdge.source_id == legacy_node_id, IGEdge.target_id == dev_node_id)
            )).scalar_one_or_none()
            assert edge is not None
            assert edge.edge_type == "represented_by"
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=[dev.id], node_ids=node_ids)


@pytest.mark.asyncio
async def test_no_legacy_event_node_means_no_backfill_edge():
    """No exact membership match (the legacy node simply doesn't exist)
    -- must not create anything, must not error."""
    event_id = f"evt-6b-nomatch-{uuid.uuid4().hex[:8]}"
    dev = _make_dev(evidence_count=2)
    dev_node_id = f"development:{dev.id}"
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            db.add(DevelopmentEvidence(
                id=str(uuid.uuid4()), development_id=dev.id, source_type="event", source_id=event_id,
                evidence_key=event_id, observed_at=datetime.now(timezone.utc), title="x", match_tier="seed",
            ))
            await db.commit()

            await link_development_to_graph(db, dev)

            edges = (await db.execute(
                select(IGEdge).where(IGEdge.target_id == dev_node_id, IGEdge.edge_type == "represented_by")
            )).scalars().all()
            assert edges == []
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=[dev.id], node_ids=[dev_node_id])
