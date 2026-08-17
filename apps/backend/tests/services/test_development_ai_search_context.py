"""
Phase 6F — Development Memory -> AI Search context
(app/services/development_memory/ai_search_context.py).

Live tests against the real dev DB. This is the shared builder both AI
Search V2 and V3 call -- these tests prove the builder itself, not the
pipeline wiring (that's verified separately, live, against the real
endpoints).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.development import Development, DevelopmentEvidence
from app.db.session import AsyncSessionLocal
from app.services.development_memory.ai_search_context import build_development_context


async def _cleanup(db, development_ids: list[str]) -> None:
    await db.execute(delete(DevelopmentEvidence).where(DevelopmentEvidence.development_id.in_(development_ids)))
    await db.execute(delete(Development).where(Development.id.in_(development_ids)))
    await db.commit()


def _make_dev(symbol: str, *, evidence_count: int = 2, current_direction: str | None = "positive",
              current_confidence: float | None = 0.8, category: str | None = None,
              sectors: list[str] | None = None) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()), canonical_title=f"Test development for {symbol}", status="open",
        primary_company=symbol, companies=[symbol], sectors=sectors or [], themes=[], category=category,
        first_observed_at=now, last_observed_at=now,
        current_direction=current_direction, current_confidence=current_confidence,
        evidence_count=evidence_count, schema_version="test",
    )


def _make_evidence(dev_id: str, direction: str | None, title: str, hours_ago: float) -> DevelopmentEvidence:
    observed_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return DevelopmentEvidence(
        id=str(uuid.uuid4()), development_id=dev_id, source_type="news",
        source_id=str(uuid.uuid4()), evidence_key=str(uuid.uuid4()),
        observed_at=observed_at, title=title, direction=direction, match_tier="seed",
    )


@pytest.mark.asyncio
async def test_returns_none_for_unknown_symbol():
    async with AsyncSessionLocal() as db:
        result = await build_development_context(db, f"NOSUCHSYMBOL{uuid.uuid4().hex[:8].upper()}")
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_for_non_graph_worthy_development():
    """Single low-value evidence, no impact tier -- must not surface."""
    symbol = f"T6F{uuid.uuid4().hex[:6].upper()}"
    dev = _make_dev(symbol, evidence_count=1)
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            result = await build_development_context(db, symbol)
            assert result is None
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_returns_compact_block_for_qualifying_development():
    symbol = f"T6F{uuid.uuid4().hex[:6].upper()}"
    dev = _make_dev(symbol, evidence_count=2, current_direction="positive", current_confidence=0.8,
                     category="Union Budget", sectors=["Infrastructure"])
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            db.add(_make_evidence(dev.id, "positive", "loan growth update", hours_ago=1))
            db.add(_make_evidence(dev.id, "positive", "RBI liquidity support", hours_ago=2))
            await db.commit()

            result = await build_development_context(db, symbol)
            assert result is not None
            assert "DEVELOPMENT MEMORY" in result
            assert dev.canonical_title[:20] in result
            assert "all_positive" in result
            assert "loan growth update" in result
            assert "RBI liquidity support" in result
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_block_stays_short_with_capped_evidence_and_analogues():
    """Real discipline check: even with many evidence rows, the block
    caps evidence at MAX_EVIDENCE_LINES and analogues at
    MAX_ANALOGUE_LINES separately -- a sentiment-only query can still
    legitimately clear find_similar_events' similarity threshold and add
    up to MAX_ANALOGUE_LINES real analogue bullets on top, so the total
    is checked as evidence-cap + analogue-cap, not a single flat number."""
    symbol = f"T6F{uuid.uuid4().hex[:6].upper()}"
    dev = _make_dev(symbol, evidence_count=6, current_direction="positive", current_confidence=0.8)
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            for i in range(6):
                db.add(_make_evidence(dev.id, "positive", f"positive item {i}", hours_ago=i))
            await db.commit()

            result = await build_development_context(db, symbol)
            assert result is not None
            bullet_count = result.count("• ")
            assert bullet_count <= 3 + 2  # MAX_EVIDENCE_LINES + MAX_ANALOGUE_LINES
            assert "positive item 5" not in result  # older items beyond the cap are dropped
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_no_signal_development_still_returns_a_thin_honest_block():
    """A graph-worthy Development (corroborated) with zero directional
    evidence still surfaces -- honestly showing no_signal, not hidden."""
    symbol = f"T6F{uuid.uuid4().hex[:6].upper()}"
    dev = _make_dev(symbol, evidence_count=2, current_direction=None, current_confidence=None)
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            db.add(_make_evidence(dev.id, None, "routine filing", hours_ago=1))
            db.add(_make_evidence(dev.id, None, "record date notice", hours_ago=2))
            await db.commit()

            result = await build_development_context(db, symbol)
            assert result is not None
            assert "no_signal" in result
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)
