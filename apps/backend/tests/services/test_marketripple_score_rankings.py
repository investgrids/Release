"""
Company Rankings — real DB-backed tests (2026-09-26 migration). Confirms
get_banking_rankings() categorizes real snapshot states correctly, reads
every field from get_marketripple_score_projection() (never a second
computation), and never substitutes the older AI Company Score. Also
confirms non-Banking sectors get an honest "not supported" response.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.banking_universe import ALL_ELIGIBLE_NSE_BANKS
from app.services.marketripple_score.rankings import get_banking_rankings, get_unsupported_sector_response


def _entity_id_for(symbol: str) -> str:
    return f"cmp_test_{symbol.lower()}"


async def _seed_entity(db, symbol: str) -> None:
    """get_marketripple_score_projection() resolves through
    resolve_entity_by_any_symbol() BEFORE it ever looks at a snapshot — a
    real CompanyEntity/CompanyAlias row must exist or every snapshot below
    is unreachable regardless of its own real data (same real fixture
    shape as test_marketripple_score_public_projection.py's _seed_entity)."""
    entity_id = _entity_id_for(symbol)
    existing = await db.get(CompanyEntity, entity_id)
    if existing is not None:
        return
    db.add(CompanyEntity(
        entity_id=entity_id, company_name=f"Test {symbol}", exchange="NSE",
        symbol=symbol, sector="Banking", source="test",
    ))
    await db.flush()
    db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))


async def _cleanup(symbols: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketRippleScoreSnapshot).where(MarketRippleScoreSnapshot.symbol.in_(symbols)))
        entity_ids = [_entity_id_for(s) for s in symbols]
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_(entity_ids)))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_(entity_ids)))
        await db.commit()


def _snapshot(symbol, *, score, publishable, block_reasons, pillar_coverage_status="complete", calculated_at=None):
    now = calculated_at or datetime.now(timezone.utc)
    return MarketRippleScoreSnapshot(
        symbol=symbol, score=score, rating="Positive" if score else None,
        financial_strength=score, valuation=score, market_behaviour=score, current_intelligence=score,
        coverage_pct=80.0, methodology_version="BANKING_V1", peer_universe=[], peer_universe_count=27,
        calculated_at=now, publishable=publishable,
        publication_block_reason=None if publishable else "S2 phase lock",
        publication_policy_version="BANKING_V1_P1", publication_block_reasons=block_reasons,
        pillar_coverage_status=pillar_coverage_status,
        pillar_coverage_message="Complete coverage — 4 of 4 pillars" if pillar_coverage_status == "complete" else "Partial coverage — 2 of 4 pillars",
    )


@pytest.mark.asyncio
async def test_no_snapshot_at_all_lands_in_unavailable_with_honest_reason():
    """Today's real, universal state: zero snapshots exist anywhere. Every
    one of the 27 real banks must appear in `unavailable`, never silently
    dropped, never substituted with the old AI Company Score."""
    async with AsyncSessionLocal() as db:
        result = await get_banking_rankings(db)
    assert result["sector"] == "Banking"
    assert result["supported"] is True
    assert result["ranked"] == []
    assert result["total_universe"] == len(ALL_ELIGIBLE_NSE_BANKS)
    unavailable_symbols = {r["symbol"] for r in result["unavailable"]}
    assert unavailable_symbols == set(ALL_ELIGIBLE_NSE_BANKS), "every real bank must appear somewhere — none silently dropped"
    for row in result["unavailable"]:
        assert row["reason"] == "no_snapshot_computed_yet"


@pytest.mark.asyncio
async def test_publishable_eligible_fresh_snapshot_is_ranked_with_real_rank_assigned():
    tag = "ICICIBANK"  # a real symbol in ALL_ELIGIBLE_NSE_BANKS
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, tag)
        db.add(_snapshot(tag, score=60.2, publishable=True, block_reasons=[]))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_banking_rankings(db)
        ranked_symbols = {r["symbol"]: r for r in result["ranked"]}
        assert tag in ranked_symbols
        assert ranked_symbols[tag]["score"] == 60.2
        assert ranked_symbols[tag]["rank"] >= 1
        assert tag not in {r["symbol"] for r in result["unavailable"]}
    finally:
        await _cleanup([tag])


@pytest.mark.asyncio
async def test_publishable_but_ineligible_lands_in_unavailable():
    tag = "HDFCBANK"
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, tag)
        db.add(_snapshot(tag, score=52.8, publishable=True, block_reasons=["INSUFFICIENT_OVERALL_COVERAGE"]))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_banking_rankings(db)
        assert tag not in {r["symbol"] for r in result["ranked"]}
        row = next(r for r in result["unavailable"] if r["symbol"] == tag)
        assert row["reason"] == "ineligible"
    finally:
        await _cleanup([tag])


@pytest.mark.asyncio
async def test_not_publishable_lands_in_unavailable_even_if_eligible():
    """The real, current, universal state for every bank today: eligible
    per BANKING_V1_P1 doesn't matter while the whole-feature lock is on."""
    tag = "AXISBANK"
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, tag)
        db.add(_snapshot(tag, score=55.0, publishable=False, block_reasons=[]))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_banking_rankings(db)
        assert tag not in {r["symbol"] for r in result["ranked"]}
        row = next(r for r in result["unavailable"] if r["symbol"] == tag)
        assert row["reason"] == "publication_locked"
    finally:
        await _cleanup([tag])


@pytest.mark.asyncio
async def test_partial_coverage_snapshot_lands_in_its_own_section_not_ranked():
    tag = "KOTAKBANK"
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, tag)
        db.add(_snapshot(tag, score=None, publishable=True, block_reasons=[], pillar_coverage_status="partial"))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_banking_rankings(db)
        assert tag not in {r["symbol"] for r in result["ranked"]}
        assert tag not in {r["symbol"] for r in result["unavailable"]}
        row = next(r for r in result["partial_coverage"] if r["symbol"] == tag)
        assert "Partial coverage" in row["message"]
    finally:
        await _cleanup([tag])


@pytest.mark.asyncio
async def test_stale_snapshot_excluded_from_ranking_with_explanation():
    tag = "SBIN"
    old = datetime.now(timezone.utc) - timedelta(days=45)
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, tag)
        db.add(_snapshot(tag, score=58.0, publishable=True, block_reasons=[], calculated_at=old))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_banking_rankings(db)
        assert tag not in {r["symbol"] for r in result["ranked"]}
        row = next(r for r in result["unavailable"] if r["symbol"] == tag)
        assert row["reason"] == "stale"
    finally:
        await _cleanup([tag])


@pytest.mark.asyncio
async def test_ranked_rows_are_sorted_descending_with_sequential_rank():
    tags_scores = [("PNB", 40.0), ("CANBK", 70.0), ("BANKBARODA", 55.0)]
    async with AsyncSessionLocal() as db:
        for tag, score in tags_scores:
            await _seed_entity(db, tag)
            db.add(_snapshot(tag, score=score, publishable=True, block_reasons=[]))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_banking_rankings(db)
        ranked = [r for r in result["ranked"] if r["symbol"] in {t for t, _ in tags_scores}]
        assert [r["symbol"] for r in ranked] == ["CANBK", "BANKBARODA", "PNB"]
        assert [r["score"] for r in ranked] == [70.0, 55.0, 40.0]
    finally:
        await _cleanup([t for t, _ in tags_scores])


def test_unsupported_sector_returns_honest_empty_state_never_the_old_score():
    result = get_unsupported_sector_response("Technology")
    assert result["sector"] == "Technology"
    assert result["supported"] is False
    assert result["ranked"] == []
    assert "not yet available" in result["message"]
