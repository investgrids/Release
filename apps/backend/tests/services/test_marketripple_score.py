"""
Unified MarketRipple Score — S2 tests. Covers the pure, network-free logic
(percentile ranking, RSI/return math, engine composition/weighting) with
real assertions rather than mocking yfinance end to end — the live-data
paths were validated manually against real ICICIBANK/HDFCBANK/AXISBANK/
KOTAKBANK/SBIN data (see scripts/marketripple_score_five_bank_comparison.py
and its real output, not reproduced here since it depends on live market
data that changes daily).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.services.marketripple_score.contracts import MarketRippleScore, PillarScore, PillarStatus
from app.services.marketripple_score import market_behaviour
from app.services.marketripple_score.market_behaviour import (
    _pct_return, _rsi, completed_session_cutoff_date, market_behaviour_coverage_meets_minimum,
)
from app.services.marketripple_score.valuation import _percentile_rank


def test_percentile_rank_cheaper_is_better():
    values = {"A": 10.0, "B": 20.0, "C": 30.0, "D": 40.0, "E": 50.0}
    assert _percentile_rank(values, "A", cheaper_is_better=True) == 100.0  # cheapest -> best
    assert _percentile_rank(values, "E", cheaper_is_better=True) == 0.0    # priciest -> worst
    assert _percentile_rank(values, "C", cheaper_is_better=True) == 50.0  # middle


def test_percentile_rank_higher_is_better():
    values = {"A": 10.0, "B": 20.0, "C": 30.0}
    assert _percentile_rank(values, "C", cheaper_is_better=False) == 100.0
    assert _percentile_rank(values, "A", cheaper_is_better=False) == 0.0


def test_percentile_rank_excludes_missing_and_requires_at_least_two():
    # A real peer with no real value for this metric must never be treated
    # as a data point (e.g. KOTAKBANK's real, confirmed-live null ROE).
    assert _percentile_rank({"A": 10.0}, "A") is None       # only 1 real value -- can't rank
    assert _percentile_rank({}, "A") is None                # symbol itself missing
    assert _percentile_rank({"B": 10.0}, "A") is None        # symbol itself missing from the set


def test_pct_return_real_math():
    closes = [100.0] * 60 + [110.0]  # 61 points, lookback 60 -> +10%
    assert _pct_return(closes, 60) == 10.0
    assert _pct_return(closes, 100) is None  # not enough history -- must not fabricate


def test_rsi_all_gains_is_100_all_losses_is_0():
    rising = [100.0 + i for i in range(20)]
    assert _rsi(rising) == 100.0
    falling = [100.0 - i for i in range(20)]
    assert _rsi(falling) == 0.0
    assert _rsi([100.0, 101.0]) is None  # fewer than period+1 points -- must not fabricate


def test_completed_session_cutoff_excludes_the_session_until_vendor_finalization():
    local_before_finalization = datetime(2026, 9, 30, 15, 59, tzinfo=ZoneInfo("Asia/Kolkata"))
    local_after_finalization = datetime(2026, 9, 30, 16, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

    assert completed_session_cutoff_date(local_before_finalization) == date(2026, 9, 29)
    assert completed_session_cutoff_date(local_after_finalization) == date(2026, 9, 30)


def test_candidate_market_behaviour_minimum_is_two_of_four_components():
    assert market_behaviour_coverage_meets_minimum(25.0, 52, ["rsi_14"]) is False
    assert market_behaviour_coverage_meets_minimum(
        50.0, 64, ["rsi_14", "relative_return_vs_nifty50"],
    ) is True
    assert market_behaviour_coverage_meets_minimum(
        50.0, 200, ["200_dma_position", "rsi_14"],
    ) is False
    assert market_behaviour_coverage_meets_minimum(
        50.0, 63, ["rsi_14", "relative_return_vs_nifty50"],
    ) is False
    assert market_behaviour_coverage_meets_minimum(
        50.0, 64, ["rsi_14", "relative_return_vs_sector_etf (HEALTHY)"]
    ) is True
    assert market_behaviour_coverage_meets_minimum(None, 64, []) is False


@pytest.mark.asyncio
async def test_market_behaviour_uses_only_completed_dated_observations(monkeypatch):
    first_day = date(2025, 1, 1)
    own = [((first_day + timedelta(days=index)).isoformat(), 100.0 + index) for index in range(220)]
    nifty = [((first_day + timedelta(days=index)).isoformat(), 200.0 + index * 0.25) for index in range(220)]
    cutoff_date = date.fromisoformat(own[-2][0])
    monkeypatch.setattr(market_behaviour, "_fetch_daily_close_observations_sync", lambda _ticker: own)

    result = await market_behaviour.score_market_behaviour(
        "TEST", None, prefetched_benchmarks={"^NSEI": nifty}, cutoff_date=cutoff_date.isoformat(),
    )

    provenance = result.detail["input_provenance"]
    assert result.score is not None
    assert provenance["cutoff_date"] == cutoff_date.isoformat()
    assert provenance["series"]["TEST.NS"]["observation_end"] == cutoff_date.isoformat()
    assert provenance["series"]["^NSEI"]["observation_end"] == cutoff_date.isoformat()
    assert len(provenance["series"]["TEST.NS"]["observations"]) == 200
    assert len(provenance["series"]["^NSEI"]["observations"]) == 64
    dma_input = provenance["inputs"]["price_vs_200dma_pct"]
    assert dma_input["value"] == result.detail["price_vs_200dma_pct"]
    assert dma_input["source"] == "Yahoo Finance via yfinance"
    assert dma_input["observation_windows"]["TEST.NS"]["requested_observations"] == 200


@pytest.mark.asyncio
async def test_rsi_only_pillar_is_measured_but_candidate_minimum_is_not_enforced(monkeypatch):
    first_day = date(2026, 7, 1)
    own = [((first_day + timedelta(days=index)).isoformat(), 100.0 + index) for index in range(52)]
    monkeypatch.setattr(market_behaviour, "_fetch_daily_close_observations_sync", lambda _ticker: own)

    result = await market_behaviour.score_market_behaviour("HEG", None, cutoff_date=own[-1][0])

    assert result.score is not None
    assert result.coverage_pct == 25.0
    assert result.metrics_used == ["rsi_14"]
    assert market_behaviour_coverage_meets_minimum(
        result.coverage_pct, len(own), result.metrics_used,
    ) is False


def _pillar(score, coverage=100.0, status=PillarStatus.COMPLETE) -> PillarScore:
    return PillarScore(
        name="test", score=score, coverage_pct=coverage, status=status,
        metrics_used=["x"], metrics_missing=[], sources=["test"],
        as_of=datetime.now(timezone.utc),
    )


def _stub_engine(monkeypatch, *, sector, fs=80.0, val=60.0, mkt=50.0):
    """Stub the network-dependent pillar scorers so compute_marketripple_score
    runs its real headline + publication logic offline."""
    from app.services.marketripple_score import engine
    import app.services.aipe.company_score_engine as cse

    async def _fs(*a, **k): return _pillar(fs) if fs is not None else None
    async def _ci(*a, **k): return _pillar(40.0)
    async def _val(*a, **k): return _pillar(val) if val is not None else None
    async def _mkt(*a, **k): return _pillar(mkt) if mkt is not None else None
    monkeypatch.setattr(engine, "score_financial_strength", _fs)
    monkeypatch.setattr(engine, "score_current_intelligence", _ci)
    monkeypatch.setattr(engine, "score_valuation", _val)
    monkeypatch.setattr(engine, "score_market_behaviour", _mkt)
    monkeypatch.setattr(engine, "sector_peer_universe", lambda s: ["AAA", "BBB"])
    monkeypatch.setattr(cse, "_sector_for", lambda sym: sector)


@pytest.mark.asyncio
async def test_real_headline_score_is_publishable(monkeypatch):
    """Owner decision 2026-09-28 lifted the S2 phase lock: a real headline
    number is publishable (snapshot.py still applies eligibility on top)."""
    from app.services.marketripple_score.engine import compute_marketripple_score
    from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS

    _stub_engine(monkeypatch, sector=NONBANK_INDUSTRIAL_SECTORS[0])
    result = await compute_marketripple_score(None, "TEST")
    assert result.score is not None
    assert result.publishable is True
    assert result.publish_reason is None


@pytest.mark.asyncio
async def test_missing_required_pillar_is_never_publishable(monkeypatch):
    from app.services.marketripple_score.engine import compute_marketripple_score
    from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS

    _stub_engine(monkeypatch, sector=NONBANK_INDUSTRIAL_SECTORS[0], val=None)
    result = await compute_marketripple_score(None, "TEST")
    assert result.score is None
    assert result.publishable is False
    assert result.publish_reason


@pytest.mark.asyncio
async def test_unsupported_sector_is_never_publishable(monkeypatch):
    from app.services.marketripple_score.engine import compute_marketripple_score

    _stub_engine(monkeypatch, sector="Insurance")
    result = await compute_marketripple_score(None, "TEST")
    assert result.score is None
    assert result.publishable is False


def test_label_thresholds():
    from app.services.marketripple_score.engine import _label_for

    assert _label_for(None) is None
    assert _label_for(80) == "Strong"
    assert _label_for(65) == "Positive"
    assert _label_for(50) == "Neutral"
    assert _label_for(30) == "Cautious"
    # boundary values
    assert _label_for(75) == "Strong"
    assert _label_for(60) == "Positive"
    assert _label_for(45) == "Neutral"
    assert _label_for(44.9) == "Cautious"
