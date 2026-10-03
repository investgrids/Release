"""Public data-quality gate (2026-10-03 audit of the 421 public scores)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete

from app.db.models.company_entity import CompanyAlias, CompanyEntity
from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.data_quality import (
    financial_data_is_stale, financial_period_end, market_inputs_unverified_reason, snapshot_data_quality_reasons,
)
from app.services.marketripple_score.public_projection import get_marketripple_score_projection, is_publicly_published
from tests.services.data_quality_fixtures import FRESH_AS_OF, verified_inputs

TODAY = date(2026, 10, 3)


def test_bank_fy_labels_map_to_their_quarter_end_and_dec_2024_is_stale():
    assert financial_period_end("FY2025Q3") == date(2024, 12, 31)   # what all 26 public banks had
    assert financial_period_end("FY2026Q4") == date(2026, 3, 31)
    assert financial_data_is_stale("FY2025Q3", TODAY) is True
    assert financial_data_is_stale("FY2026Q2", TODAY) is False  # Sep 2025, 368 days


def test_industrial_statement_dates_and_september_year_ends_are_not_stale():
    assert financial_data_is_stale("2026-03-31T00:00:00+00:00", TODAY) is False
    assert financial_data_is_stale("2025-09-30T00:00:00+00:00", TODAY) is False  # Sep FY-end: latest annual statement
    assert financial_data_is_stale("2024-03-31T00:00:00+00:00", TODAY) is True
    assert financial_data_is_stale(None, TODAY) is False and financial_data_is_stale("garbage", TODAY) is False


def test_market_inputs_verification_cases():
    ok = verified_inputs("TCS")
    assert market_inputs_unverified_reason(ok, "TCS") is None
    assert "no recorded" in market_inputs_unverified_reason(None, "TCS")
    behind = verified_inputs("TCS")
    behind["series"]["TCS.NS"]["observation_end"] = (date.today() - timedelta(days=9)).isoformat()
    assert "before the market" in market_inputs_unverified_reason(behind, "TCS")
    past = verified_inputs("TCS")
    past["series"]["^NSEI"]["observation_end"] = (date.today() + timedelta(days=1)).isoformat()
    assert "past the completed-session cutoff" in market_inputs_unverified_reason(past, "TCS")


def _snap(symbol="TCS", **kw):
    base = dict(symbol=symbol, publishable=True, score=60.0, publication_block_reasons=[], market_behaviour_coverage_pct=100.0,
                financial_data_as_of=FRESH_AS_OF, market_behaviour_inputs=verified_inputs(symbol))
    base.update(kw)
    return SimpleNamespace(**base)


def test_fresh_verified_snapshot_is_public_stale_bank_and_legacy_are_not():
    assert is_publicly_published(_snap())
    assert not is_publicly_published(_snap("SBIN", financial_data_as_of="FY2025Q3"))
    assert not is_publicly_published(_snap(market_behaviour_inputs=None))  # legacy: computed intraday
    assert snapshot_data_quality_reasons(_snap("SBIN", financial_data_as_of="FY2025Q3", market_behaviour_inputs=None)) == [
        "STALE_FINANCIAL_DATA", "MARKET_INPUTS_UNVERIFIED"]


async def _seed(db, symbol, entity_id, **snap_kw):
    db.add(CompanyEntity(entity_id=entity_id, company_name=f"{symbol} Ltd", isin=f"INE{uuid.uuid4().hex[:9].upper()}", exchange="NSE",
                         symbol=symbol, series="EQ", listing_status="active", source="test"))
    await db.flush()
    db.add(CompanyAlias(entity_id=entity_id, alias_type="symbol", alias_value=symbol, exchange="NSE", valid_to=None, source="test"))
    base = dict(entity_id=entity_id, symbol=symbol, score=52.9, rating="Neutral", financial_strength=60.0, valuation=50.0,
                market_behaviour=40.0, coverage_pct=100.0, market_behaviour_coverage_pct=100.0, financial_metrics_used_count=7,
                financial_metrics_total_count=7, methodology_version="MARKETRIPPLE_SCORE_V1", peer_universe=[], peer_universe_count=1,
                calculated_at=datetime.now(timezone.utc), publishable=True, publication_policy_version="BANKING_V1_P1",
                publication_block_reasons=[], pillar_coverage_status="complete", pillar_coverage_message="ok",
                financial_data_as_of=FRESH_AS_OF, market_behaviour_inputs=verified_inputs(symbol))
    base.update(snap_kw)
    db.add(MarketRippleScoreSnapshot(**base))
    await db.commit()


async def _cleanup(symbol, entity_id):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketRippleScoreSnapshot).where(MarketRippleScoreSnapshot.symbol == symbol))
        await db.execute(delete(CompanyAlias).where(CompanyAlias.entity_id == entity_id))
        await db.execute(delete(CompanyEntity).where(CompanyEntity.entity_id == entity_id))
        await db.commit()


@pytest.mark.asyncio
async def test_stale_bank_projection_says_financial_data_awaiting_update():
    symbol, entity_id = "ZBANK1", f"cmp_dq_{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        await _seed(db, symbol, entity_id, financial_data_as_of="FY2025Q3")
    try:
        async with AsyncSessionLocal() as db:
            r = await get_marketripple_score_projection(db, symbol)
        assert r["publishable"] is False and r["score"] is None and r["rating"] is None
        assert r["block_headline"] == "Financial data awaiting update"
        assert "STALE_FINANCIAL_DATA" in r["block_reason_codes"]
    finally:
        await _cleanup(symbol, entity_id)


@pytest.mark.asyncio
async def test_legacy_snapshot_without_recorded_inputs_is_withheld_as_being_refreshed():
    symbol, entity_id = "ZCO1", f"cmp_dq_{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        await _seed(db, symbol, entity_id, market_behaviour_inputs=None, publication_policy_version="NONBANK_INDUSTRIAL_V2_P1")
    try:
        async with AsyncSessionLocal() as db:
            r = await get_marketripple_score_projection(db, symbol)
        assert r["publishable"] is False and r["score"] is None
        assert r["block_headline"] == "Score being refreshed"
    finally:
        await _cleanup(symbol, entity_id)


@pytest.mark.asyncio
async def test_recomputing_a_bank_with_stale_facts_does_not_make_it_public_again(monkeypatch):
    """The refresh builds a verified, fully-covered snapshot, but the bank has
    newest financial fact still Dec-2024: it must stay unpublishable."""
    import app.services.aipe.company_score_engine as cse
    import app.services.company_identity.qualification as qual
    import app.services.marketripple_score.eligibility as elig
    from app.services.marketripple_score import snapshot as snap_mod
    from app.services.marketripple_score.contracts import MarketRippleScore, PillarScore, PillarStatus

    symbol = "ZBANK2"

    def pillar(score, used):
        return PillarScore(name="t", score=score, coverage_pct=100.0, status=PillarStatus.COMPLETE, metrics_used=used,
                           metrics_missing=[], sources=["t"], as_of=datetime.now(timezone.utc))
    mkt = pillar(50.0, ["relative_return_vs_nifty50"])
    mkt.detail = {"input_provenance": verified_inputs(symbol)}
    result = MarketRippleScore(symbol=symbol, score=55.0, label="Neutral", publishable=True, publish_reason=None,
                               pillars={"financial_strength": pillar(60.0, list("abcdefg")), "valuation": pillar(50.0, ["x"]),
                                        "market_behaviour": mkt, "current_intelligence": pillar(40.0, ["y"])},
                               weights={}, overall_coverage_pct=100.0)

    async def _compute(*a, **k): return result
    async def _entity(*a, **k): return None
    async def _fin_as_of(*a, **k): return "FY2025Q3"

    class _Verdict:
        reasons: list = []

    monkeypatch.setattr(snap_mod, "compute_marketripple_score", _compute)
    monkeypatch.setattr(snap_mod, "_real_financial_data_as_of", _fin_as_of)
    monkeypatch.setattr(qual, "resolve_entity_by_any_symbol", _entity)
    monkeypatch.setattr(cse, "_sector_for", lambda s: "Banking")
    monkeypatch.setattr(elig, "evaluate_eligibility", lambda **k: _Verdict())
    try:
        async with AsyncSessionLocal() as db:
            snap = await snap_mod.compute_and_persist_snapshot(db, symbol)
        assert snap.publishable is False
        assert "STALE_FINANCIAL_DATA" in (snap.publication_block_reasons or [])
        assert "MARKET_INPUTS_UNVERIFIED" not in (snap.publication_block_reasons or [])
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(MarketRippleScoreSnapshot).where(MarketRippleScoreSnapshot.symbol == symbol))
            await db.commit()
