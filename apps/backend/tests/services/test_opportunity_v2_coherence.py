"""
opportunity_v2/coherence.py — real DB-backed tests, same convention as
test_development_graph_link.py (real IGNode/IGEdge rows via the existing
link_development_to_graph(), not mocked). Builds real graph linkage for
fixture Developments, then asserts find_coherent_clusters()'s real
STRONG/WEAK behavior.

test_shared_sector_only_does_not_merge is the literal regression test for
the reported bug: "Aditya Birla Capital enters gold loans" and "Goldman
rates Indian banks" both tag Banking and nothing else — must not cluster.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.development import Development, DevelopmentEvidence
from app.db.models.intelligence_graph import IGEdge, IGNode
from app.db.session import AsyncSessionLocal
from app.services.development_memory.graph_link import link_development_to_graph
from app.services.opportunity_v2.coherence import find_coherent_clusters


async def _cleanup(development_ids: list[str], node_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        if development_ids:
            await db.execute(delete(DevelopmentEvidence).where(DevelopmentEvidence.development_id.in_(development_ids)))
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
        formation_impact_tier="High",  # graph-worthy on its own (materiality), no second-source needed
        current_direction="positive", evidence_count=1, schema_version="test",
    )


async def _link(dev: Development) -> str:
    async with AsyncSessionLocal() as db:
        db.add(dev)
        await db.commit()
        node_id = await link_development_to_graph(db, dev)
        assert node_id, "fixture must be graph-worthy for this test to be meaningful"
        dev.ig_node_id = node_id
        db.add(dev)
        await db.commit()
    return node_id


@pytest.mark.asyncio
async def test_shared_sector_only_does_not_merge():
    """The literal Aditya Birla regression: two real Developments sharing
    ONLY a broad sector must never cluster into one opportunity."""
    dev_a = _make_dev("Aditya Birla Capital enters gold loan market", sectors=["Banking"])
    dev_b = _make_dev("Goldman rates Indian banks", sectors=["Banking"])
    node_ids: list[str] = []
    try:
        node_ids.append(await _link(dev_a))
        node_ids.append(await _link(dev_b))
        sector_node_id = "sector:banking"
        node_ids.append(sector_node_id)

        clusters = await find_coherent_clusters([dev_a, dev_b])

        assert len(clusters) == 2, "shared sector alone must not merge two otherwise-unrelated developments"
        merged_titles = {frozenset(d.canonical_title for d in c.developments) for c in clusters}
        assert frozenset([dev_a.canonical_title]) in merged_titles
        assert frozenset([dev_b.canonical_title]) in merged_titles
    finally:
        await _cleanup([dev_a.id, dev_b.id], node_ids)


@pytest.mark.asyncio
async def test_shared_company_does_merge():
    """A real shared company (STRONG tier) must merge, even though both
    also (incidentally) share a sector -- the STRONG signal is what
    actually decides it, not the presence of a WEAK one alongside it."""
    ticker = f"TCOH{uuid.uuid4().hex[:6].upper()}"
    dev_a = _make_dev("Company announces gold loan expansion", companies=[ticker], sectors=["Banking"])
    dev_b = _make_dev("Analyst raises rating on the same company", companies=[ticker], sectors=["Banking"])
    node_ids: list[str] = []
    try:
        node_ids.append(await _link(dev_a))
        node_ids.append(await _link(dev_b))

        clusters = await find_coherent_clusters([dev_a, dev_b])

        assert len(clusters) == 1
        assert {d.canonical_title for d in clusters[0].developments} == {dev_a.canonical_title, dev_b.canonical_title}
    finally:
        await _cleanup([dev_a.id, dev_b.id], node_ids)


@pytest.mark.asyncio
async def test_unrelated_developments_with_no_shared_node_stay_singletons():
    ticker_a = f"TA{uuid.uuid4().hex[:6].upper()}"
    ticker_b = f"TB{uuid.uuid4().hex[:6].upper()}"
    dev_a = _make_dev("Completely unrelated pharma story", companies=[ticker_a], sectors=["Pharma"])
    dev_b = _make_dev("Completely unrelated auto story", companies=[ticker_b], sectors=["Automotive"])
    node_ids: list[str] = []
    try:
        node_ids.append(await _link(dev_a))
        node_ids.append(await _link(dev_b))

        clusters = await find_coherent_clusters([dev_a, dev_b])

        assert len(clusters) == 2
    finally:
        await _cleanup([dev_a.id, dev_b.id], node_ids)


@pytest.mark.asyncio
async def test_development_with_no_graph_node_is_kept_as_a_singleton_not_dropped():
    """A candidate with no ig_node_id (not yet graph-linked) can't
    participate in graph coherence, but must still surface as its own
    candidate cluster -- never silently discarded."""
    now = datetime.now(timezone.utc)
    dev = Development(
        id=str(uuid.uuid4()), canonical_title="Not yet graph-linked", status="open",
        primary_company=None, companies=[], sectors=["Energy"], themes=[],
        first_observed_at=now, last_observed_at=now, ig_node_id=None,
        current_direction="positive", evidence_count=1, schema_version="test",
    )
    clusters = await find_coherent_clusters([dev])
    assert len(clusters) == 1
    assert clusters[0].developments == [dev]
    assert clusters[0].strong_node_ids == set()


@pytest.mark.asyncio
async def test_empty_input_returns_no_clusters():
    assert await find_coherent_clusters([]) == []
