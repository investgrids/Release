"""
S5-C — real DB-backed tests for the public read projection. Covers the
four real acceptance profiles the owner named (a complete/eligible case,
a partial-but-eligible case, and the two real block reasons), plus alias
resolution (an old/historical symbol must land on the exact same record
a current-symbol request would — never a second score identity) and the
two "not a real company" / "no snapshot yet" edge cases.
"""
from __future__ import annotations

import random
import string
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.public_projection import get_marketripple_score_projection


def _tag():
    return "".join(random.choices(string.ascii_uppercase, k=8))


def _entity_id():
    return f"cmp_{uuid.uuid4().hex[:12]}"


async def _cleanup(symbols: list[str], entity_ids: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketRippleScoreSnapshot).where(MarketRippleScoreSnapshot.symbol.in_(symbols)))
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id.in_(entity_ids)))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id.in_(entity_ids)))
        await db.commit()


async def _seed_entity(db, symbol: str, entity_id: str, old_symbol: str | None = None):
    db.add(CompanyEntity(
        entity_id=entity_id, company_name=f"Test Bank {symbol}", exchange="NSE",
        symbol=symbol, sector="Banking", source="test",
    ))
    await db.flush()  # CompanyAlias.entity_id FK needs the entity row to exist first
    db.add(CompanyAlias(
        entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE",
        valid_to=None, source="test",
    ))
    if old_symbol:
        db.add(CompanyAlias(
            entity_id=entity_id, alias_type="old_symbol", alias_value=old_symbol, exchange="NSE",
            valid_from=date(2020, 1, 1), valid_to=date(2024, 1, 1), source="test",
        ))


def _snapshot(symbol, entity_id, *, score, financial_strength, coverage_pct, fin_metrics_used,
              financial_data_as_of, block_reasons, publishable=False):
    now = datetime.now(timezone.utc)
    return MarketRippleScoreSnapshot(
        entity_id=entity_id, symbol=symbol, score=score, rating="Positive",
        financial_strength=financial_strength, valuation=30.8, market_behaviour=84.3, current_intelligence=56.4,
        coverage_pct=coverage_pct, financial_metrics_used_count=fin_metrics_used, financial_metrics_total_count=7,
        methodology_version="BANKING_V1", peer_universe=[], peer_universe_count=27,
        calculated_at=now, financial_data_as_of=financial_data_as_of,
        publishable=publishable, publication_block_reason=None if publishable else "S2 phase lock",
        publication_policy_version="BANKING_V1_P1", publication_block_reasons=block_reasons,
    )


@pytest.mark.asyncio
async def test_complete_eligible_bank_renders_real_score():
    # Real ICICIBANK-shaped profile: 7/7 metrics, eligible, AND the
    # whole-feature lock lifted (publishable=True) -- the only
    # combination that should ever render a real number.
    symbol, entity_id = f"T{_tag()}", _entity_id()
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, symbol, entity_id)
        db.add(_snapshot(symbol, entity_id, score=60.2, financial_strength=68.7, coverage_pct=83.3,
                          fin_metrics_used=7, financial_data_as_of="FY2025Q3", block_reasons=[],
                          publishable=True))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await get_marketripple_score_projection(db, symbol)
        assert result["resolved"] is True
        assert result["eligible"] is True
        assert result["score"] == 60.2
        assert result["block_headline"] is None
        assert result["block_message"] is None
        assert result["publishable"] is True
    finally:
        await _cleanup([symbol], [entity_id])


@pytest.mark.asyncio
async def test_partial_but_eligible_bank_renders_real_score():
    # Real KOTAKBANK-shaped profile: 6/7 metrics, still eligible under
    # BANKING_V1_P1, AND publishable.
    symbol, entity_id = f"T{_tag()}", _entity_id()
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, symbol, entity_id)
        db.add(_snapshot(symbol, entity_id, score=57.7, financial_strength=71.8, coverage_pct=80.0,
                          fin_metrics_used=6, financial_data_as_of="FY2025Q3", block_reasons=[],
                          publishable=True))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await get_marketripple_score_projection(db, symbol)
        assert result["eligible"] is True
        assert result["score"] == 57.7
    finally:
        await _cleanup([symbol], [entity_id])


@pytest.mark.asyncio
async def test_eligible_but_not_publishable_hides_real_score():
    """Company Page release audit fix, 2026-08-31 -- the exact real leak
    this closes: an eligible bank (real BANKING_V1_P1 pass) whose
    whole-feature lock is still on (publishable=False, the real,
    current, standing state for every bank today) must NEVER expose its
    real score/rating/pillars/coverage/financial_data_as_of through this
    public, unauthenticated endpoint -- eligibility alone is not enough,
    `publishable` is the real trust boundary. `eligible` itself stays
    correctly reported (calculation is untouched) so a caller can still
    distinguish "genuinely ineligible" from "eligible but not yet
    published" if it ever needs to."""
    symbol, entity_id = f"T{_tag()}", _entity_id()
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, symbol, entity_id)
        db.add(_snapshot(symbol, entity_id, score=59.7, financial_strength=68.7, coverage_pct=83.3,
                          fin_metrics_used=7, financial_data_as_of="FY2025Q3", block_reasons=[],
                          publishable=False))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await get_marketripple_score_projection(db, symbol)
        assert result["resolved"] is True
        assert result["publishable"] is False
        assert result["eligible"] is True  # real per-bank verdict, still honestly reported
        assert result["score"] is None
        assert result["rating"] is None
        assert result["pillars"] == {
            "financial_strength": None, "valuation": None,
            "market_behaviour": None, "current_intelligence": None,
        }
        assert result["evidence_coverage_pct"] is None
        assert result["financial_data_as_of"] is None
    finally:
        await _cleanup([symbol], [entity_id])


@pytest.mark.asyncio
async def test_data_quality_block_shows_insufficient_data_message():
    # Real YESBANK-shaped profile: 3 independent reasons.
    symbol, entity_id = f"T{_tag()}", _entity_id()
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, symbol, entity_id)
        db.add(_snapshot(
            symbol, entity_id, score=52.8, financial_strength=52.8, coverage_pct=57.5,
            fin_metrics_used=3, financial_data_as_of=None,
            block_reasons=["NO_ELIGIBLE_FINANCIAL_PERIOD", "INSUFFICIENT_FINANCIAL_METRICS", "INSUFFICIENT_OVERALL_COVERAGE"],
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await get_marketripple_score_projection(db, symbol)
        assert result["eligible"] is False
        # NO_ELIGIBLE_FINANCIAL_PERIOD outranks INSUFFICIENT_OVERALL_COVERAGE in priority.
        assert result["block_headline"] == "Insufficient verified financial data"
        assert "financial evidence could not be verified" in result["block_message"]
        assert result["score"] is None  # ineligible AND not publishable -- never exposed either way
    finally:
        await _cleanup([symbol], [entity_id])


@pytest.mark.asyncio
async def test_evidence_thinness_block_shows_building_message():
    # Real INDUSINDBK-shaped profile: exactly one reason.
    symbol, entity_id = f"T{_tag()}", _entity_id()
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, symbol, entity_id)
        db.add(_snapshot(symbol, entity_id, score=50.8, financial_strength=64.0, coverage_pct=57.5,
                          fin_metrics_used=6, financial_data_as_of="FY2025Q3",
                          block_reasons=["INSUFFICIENT_OVERALL_COVERAGE"]))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await get_marketripple_score_projection(db, symbol)
        assert result["eligible"] is False
        assert result["block_headline"] == "Evidence still building"
        assert "enough current evidence" in result["block_message"]
        assert result["score"] is None
    finally:
        await _cleanup([symbol], [entity_id])


@pytest.mark.asyncio
async def test_alias_resolves_to_the_same_canonical_snapshot():
    # A historical/alias symbol request must land on the exact same real
    # record the current symbol would -- never a second score identity.
    old_symbol, current_symbol, entity_id = f"T{_tag()}OLD", f"T{_tag()}NEW", _entity_id()
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, current_symbol, entity_id, old_symbol=old_symbol)
        db.add(_snapshot(current_symbol, entity_id, score=61.0, financial_strength=61.0, coverage_pct=77.8,
                          fin_metrics_used=7, financial_data_as_of="FY2025Q3", block_reasons=[],
                          publishable=True))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            via_old = await get_marketripple_score_projection(db, old_symbol)
            via_current = await get_marketripple_score_projection(db, current_symbol)
        assert via_old["resolved"] is True
        assert via_old["symbol"] == current_symbol  # canonical, not the raw alias
        assert via_old["score"] == via_current["score"] == 61.0
    finally:
        await _cleanup([current_symbol], [entity_id])


@pytest.mark.asyncio
async def test_unresolved_symbol_returns_resolved_false():
    async with AsyncSessionLocal() as db:
        result = await get_marketripple_score_projection(db, f"NOTAREALCOMPANY{_tag()}")
    assert result["resolved"] is False


@pytest.mark.asyncio
async def test_real_company_with_no_snapshot_yet():
    symbol, entity_id = f"T{_tag()}", _entity_id()
    async with AsyncSessionLocal() as db:
        await _seed_entity(db, symbol, entity_id)
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await get_marketripple_score_projection(db, symbol)
        assert result["resolved"] is True
        assert result["snapshot"] is False
    finally:
        await _cleanup([symbol], [entity_id])
