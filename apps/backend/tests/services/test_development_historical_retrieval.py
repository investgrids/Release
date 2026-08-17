"""
Phase 6D V1 — Development -> Historical Analogue Retrieval
(app/services/development_memory/historical_retrieval.py).

Pure retrieval, no persistence -- these tests don't need cleanup for
Development rows since none of them are committed to the DB (the
function only reads dev's in-memory fields, never queries by id). Live
against the real seeded HistoricalMarketEvent table.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.db.models.development import Development
from app.services.development_memory.historical_retrieval import (
    MAX_ANALOGUES,
    build_historical_query,
    find_similar_developments_context,
)


def _make_dev(*, category: str | None = None, sectors: list[str] | None = None,
              current_direction: str | None = "positive", evidence_count: int = 1,
              formation_impact_tier: str | None = None) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()),
        canonical_title="Test development for 6D historical retrieval",
        status="open",
        companies=[],
        sectors=sectors or [],
        themes=[],
        category=category,
        first_observed_at=now,
        last_observed_at=now,
        formation_impact_tier=formation_impact_tier,
        current_direction=current_direction,
        evidence_count=evidence_count,
        schema_version="test",
    )


@pytest.mark.asyncio
async def test_returns_real_analogues_for_a_realistic_query():
    """Union Budget / Infrastructure / bullish matches a real seeded row
    closely -- this must return at least one real analogue with real
    verified outcome data, not an empty/fabricated result."""
    dev = _make_dev(category="Union Budget", sectors=["Infrastructure"], current_direction="positive")
    ctx = await find_similar_developments_context(dev)

    assert ctx.development_id == dev.id
    assert ctx.source_direction == "positive"
    assert ctx.query_used["sentiment"] == "bullish"
    assert ctx.query_used["category"] == "Union Budget"
    assert len(ctx.analogues) >= 1
    top = ctx.analogues[0]
    assert top["similarity"] > 0
    assert top["nifty_1m"] is not None  # verified real outcome, not a placeholder


@pytest.mark.asyncio
async def test_no_significance_gate_low_evidence_single_source_still_retrieves():
    """A single-evidence, no-impact-tier Development (would fail
    is_graph_worthy()) must still be eligible for retrieval -- there is
    deliberately no gate here."""
    dev = _make_dev(category="Union Budget", sectors=["Infrastructure"], current_direction="positive",
                     evidence_count=1, formation_impact_tier=None)
    ctx = await find_similar_developments_context(dev)
    assert len(ctx.analogues) >= 1  # same result as the corroborated case -- no gate suppressed it


@pytest.mark.asyncio
async def test_mixed_direction_maps_to_neutral_but_preserves_source_direction():
    dev = _make_dev(category="Union Budget", sectors=["Infrastructure"], current_direction="mixed")
    ctx = await find_similar_developments_context(dev)

    assert ctx.query_used["sentiment"] == "neutral"
    assert ctx.source_direction == "mixed"  # NOT erased by the neutral mapping


@pytest.mark.asyncio
async def test_market_regime_and_crude_trend_never_fabricated():
    dev = _make_dev(category="Union Budget", sectors=["Infrastructure"])
    query = await build_historical_query(dev, known_sectors={"Infrastructure"})
    assert "market_regime" not in query
    assert "crude_trend" not in query


@pytest.mark.asyncio
async def test_no_category_or_sectors_still_produces_a_valid_sentiment_only_query():
    dev = _make_dev(category=None, sectors=[], current_direction="negative")
    query = await build_historical_query(dev, known_sectors=set())
    assert query["sentiment"] == "bearish"
    assert "category" not in query
    assert "sectors" not in query


@pytest.mark.asyncio
async def test_result_capped_at_max_analogues():
    dev = _make_dev(category=None, sectors=[], current_direction="neutral")
    ctx = await find_similar_developments_context(dev)
    assert len(ctx.analogues) <= MAX_ANALOGUES
