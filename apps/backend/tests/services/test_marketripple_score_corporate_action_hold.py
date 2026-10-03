"""HEG / HEGAM score hold (2026-10-03): demerger on 2026-09-07 leaves an
unadjusted -62.6% close in both tickers and pre-demerger annual financials,
so no score is shown until the hold is deliberately lifted."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete

from tests.services.data_quality_fixtures import FRESH_AS_OF, verified_inputs
from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.corporate_action_holds import SCORE_HOLDS, score_hold_for
from app.services.marketripple_score.public_projection import get_marketripple_score_projection, is_publicly_published


def test_both_symbols_are_held_and_lookup_is_case_and_suffix_tolerant():
    assert score_hold_for("HEGAM") is not None and score_hold_for("HEG") is not None
    assert score_hold_for("hegam.ns") is not None
    assert score_hold_for("TCS") is None and score_hold_for(None) is None
    assert "demerger" in SCORE_HOLDS["HEGAM"].message and "7 September 2026" in SCORE_HOLDS["HEGAM"].message


def _snap(symbol, **kw):
    base = dict(symbol=symbol, publishable=True, score=70.0, publication_block_reasons=[], market_behaviour_coverage_pct=100.0,
                financial_data_as_of=FRESH_AS_OF, market_behaviour_inputs=verified_inputs(symbol))
    base.update(kw)
    return SimpleNamespace(**base)


def test_a_fully_published_looking_snapshot_of_a_held_company_is_never_public():
    assert not is_publicly_published(_snap("HEGAM"))
    assert not is_publicly_published(_snap("HEG"))
    assert is_publicly_published(_snap("TCS"))


async def _seed(db, symbol, entity_id, with_snapshot):
    db.add(CompanyEntity(entity_id=entity_id, company_name=f"{symbol} Ltd", isin=f"INE{uuid.uuid4().hex[:9].upper()}", exchange="NSE",
                         symbol=symbol, series="EQ", listing_status="active", source="test"))
    await db.flush()
    db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))
    if with_snapshot:
        db.add(MarketRippleScoreSnapshot(
            entity_id=entity_id, symbol=symbol, score=70.0, rating="Positive", financial_strength=70.0, valuation=96.0,
            market_behaviour=40.0, coverage_pct=100.0, market_behaviour_coverage_pct=100.0, financial_metrics_used_count=6,
            financial_metrics_total_count=6, methodology_version="MARKETRIPPLE_SCORE_V1", peer_universe=[], peer_universe_count=1,
            calculated_at=datetime.now(timezone.utc), publishable=True, publication_policy_version="NONBANK_INDUSTRIAL_V2_P1",
            publication_block_reasons=[], pillar_coverage_status="complete", pillar_coverage_message="ok"))
    await db.commit()


async def _cleanup(symbol, entity_id):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketRippleScoreSnapshot).where(MarketRippleScoreSnapshot.symbol == symbol))
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity_id))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity_id))
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("with_snapshot", [False, True])
async def test_projection_of_a_held_company_says_why_and_shows_no_number(with_snapshot):
    """With no snapshot yet (HEGAM today) and with a full-looking one."""
    symbol, entity_id = "HEGAM", f"cmp_hold_{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        await _seed(db, symbol, entity_id, with_snapshot)
    try:
        async with AsyncSessionLocal() as db:
            result = await get_marketripple_score_projection(db, symbol)
        assert result["publishable"] is False and result["eligible"] is False
        assert result["score"] is None and result["rating"] is None
        assert result["block_headline"] == "Score on hold"
        assert "demerger" in result["block_message"]
        assert "CORPORATE_ACTION_HOLD" in result["block_reason_codes"]
    finally:
        await _cleanup(symbol, entity_id)


def test_kohinoor_is_held_pending_rescore_and_other_companies_are_not():
    hold = score_hold_for("KOHINOOR")
    assert hold is not None and hold.headline == "Score on hold" and "one-off" in hold.message
    assert score_hold_for("kohinoor.ns") is hold
    assert score_hold_for("KOHINOORX") is None
