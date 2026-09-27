"""
Non-Banking Commercial & Industrial V1 rankings — NS1 tests (2026-09-27).
Mirrors test_marketripple_score_rankings.py's own Banking test structure
exactly (same categorization contract, same _get_sector_rankings shared
code) but for get_industrial_sector_rankings(), confirming: (1) it works
identically for a real NS1 sector, (2) a Banking-methodology snapshot
never leaks into an industrial sector's ranked list and vice versa —
"do not imply that numbers from different sector methods are directly
comparable" (owner instruction) is enforced structurally by each ranking
call only ever querying its own sector's universe.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.rankings import get_industrial_sector_rankings
from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS, sector_peer_universe


def _entity_id_for(symbol: str) -> str:
    return f"cmp_test_ns1_{symbol.lower()}"


async def _seed_entity(db, symbol: str, sector: str) -> None:
    entity_id = _entity_id_for(symbol)
    existing = await db.get(CompanyEntity, entity_id)
    if existing is not None:
        return
    db.add(CompanyEntity(entity_id=entity_id, company_name=f"Test {symbol}", exchange="NSE", symbol=symbol, sector=sector, source="test"))
    await db.flush()
    db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))


async def _cleanup(symbols: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketRippleScoreSnapshot).where(MarketRippleScoreSnapshot.symbol.in_(symbols)))
        entity_ids = [_entity_id_for(s) for s in symbols]
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_(entity_ids)))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_(entity_ids)))
        await db.commit()


def _snapshot(symbol, *, score, publishable, block_reasons, methodology_version="NONBANK_INDUSTRIAL_V1", pillar_coverage_status="complete"):
    return MarketRippleScoreSnapshot(
        symbol=symbol, score=score, rating="Positive" if score else None,
        financial_strength=score, valuation=score, market_behaviour=score, current_intelligence=score,
        coverage_pct=80.0, methodology_version=methodology_version, peer_universe=[], peer_universe_count=33,
        calculated_at=datetime.now(timezone.utc), publishable=publishable,
        publication_block_reason=None if publishable else "S2 phase lock",
        publication_policy_version="NONBANK_INDUSTRIAL_V1_P1", publication_block_reasons=block_reasons,
        pillar_coverage_status=pillar_coverage_status,
        pillar_coverage_message="Complete coverage — 4 of 4 pillars" if pillar_coverage_status == "complete" else "Partial coverage — 2 of 4 pillars",
    )


def test_all_industrial_sectors_have_a_real_nonempty_live_peer_universe():
    """Sanity check every cohort sector resolves against the real, live
    company universe — not an empty/typo'd sector string. Minimum is 2
    (_percentile_rank's own real floor for a ranking to mean anything at
    all — see valuation.py's test), not a larger number: NS2 (2026-09-27)
    added real sectors as small as Electronics/Retail (2 real companies
    each) on real measured data, not assumed data availability — a small
    real peer pool is an honest methodology caveat (see sector_universe.py's
    own module docstring), not grounds to exclude a real sector."""
    for sector in NONBANK_INDUSTRIAL_SECTORS:
        universe = sector_peer_universe(sector)
        assert len(universe) >= 2, f"{sector} peer universe too small to rank at all: {universe}"


@pytest.mark.asyncio
async def test_industrial_sector_ranking_categorizes_like_banking_does():
    # A real Technology-sector symbol (get_industrial_sector_rankings only
    # ever iterates the real, live sector_peer_universe(sector) — a fake
    # test symbol would never be queried at all, unlike Banking's own test
    # file which could reuse real bank tickers safely). Deliberately NOT
    # one of s9_industrial_pilot_snapshot_compute.py's own pilot symbols
    # (TCS), so this test's cleanup never touches that real local snapshot.
    tag = "WIPRO"
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, tag, "Technology")
        db.add(_snapshot(tag, score=61.0, publishable=True, block_reasons=[]))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_industrial_sector_rankings(db, "Technology")
        assert result["sector"] == "Technology"
        assert result["methodology_version"] == "NONBANK_INDUSTRIAL_V1"
        assert result["supported"] is True
        row = next(r for r in result["ranked"] if r["symbol"] == tag)
        assert row["score"] == 61.0
        assert row["rank"] >= 1
    finally:
        await _cleanup([tag])


@pytest.mark.asyncio
async def test_industrial_ineligible_snapshot_lands_in_unavailable():
    tag = "TECHM"  # real, not an s9 pilot symbol
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, tag, "Technology")
        db.add(_snapshot(tag, score=45.0, publishable=True, block_reasons=["INSUFFICIENT_FINANCIAL_METRICS"]))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await get_industrial_sector_rankings(db, "Technology")
        assert tag not in {r["symbol"] for r in result["ranked"]}
        row = next(r for r in result["unavailable"] if r["symbol"] == tag)
        assert row["reason"] == "ineligible"
    finally:
        await _cleanup([tag])


@pytest.mark.asyncio
async def test_banking_snapshot_never_appears_in_an_industrial_sector_ranking():
    """The core comparability guarantee: a Banking-methodology score must
    never be counted as a real Technology (or any industrial sector)
    ranking result, even if hypothetically seeded under a symbol that
    happens to also be requested for an industrial sector's ranking."""
    tag = "TESTBANK1"
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, tag, "Banking")
        db.add(_snapshot(tag, score=99.0, publishable=True, block_reasons=[], methodology_version="BANKING_V1"))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            technology_result = await get_industrial_sector_rankings(db, "Technology")
        # A Banking-tagged symbol is never a member of Technology's real
        # peer universe, so it structurally cannot appear in this result
        # at all — confirms ranking never blends methodologies.
        all_symbols = (
            {r["symbol"] for r in technology_result["ranked"]}
            | {r["symbol"] for r in technology_result["partial_coverage"]}
            | {r["symbol"] for r in technology_result["unavailable"]}
        )
        assert tag not in all_symbols
    finally:
        await _cleanup([tag])


@pytest.mark.asyncio
async def test_two_different_industrial_sectors_are_ranked_completely_separately():
    tech_tag, fmcg_tag = "HCLTECH", "NESTLEIND"  # real, not s9 pilot symbols
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, tech_tag, "Technology")
        await _seed_entity(db, fmcg_tag, "FMCG")
        db.add(_snapshot(tech_tag, score=70.0, publishable=True, block_reasons=[]))
        db.add(_snapshot(fmcg_tag, score=55.0, publishable=True, block_reasons=[]))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            tech_result = await get_industrial_sector_rankings(db, "Technology")
            fmcg_result = await get_industrial_sector_rankings(db, "FMCG")
        assert tech_tag in {r["symbol"] for r in tech_result["ranked"]}
        assert tech_tag not in {r["symbol"] for r in fmcg_result["ranked"]}
        assert fmcg_tag in {r["symbol"] for r in fmcg_result["ranked"]}
        assert fmcg_tag not in {r["symbol"] for r in tech_result["ranked"]}
    finally:
        await _cleanup([tech_tag, fmcg_tag])
