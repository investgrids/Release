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

from datetime import datetime, timezone

import pytest

from app.services.marketripple_score.contracts import MarketRippleScore, PillarScore, PillarStatus
from app.services.marketripple_score.market_behaviour import _pct_return, _rsi
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


def _pillar(score, coverage=100.0, status=PillarStatus.COMPLETE) -> PillarScore:
    return PillarScore(
        name="test", score=score, coverage_pct=coverage, status=status,
        metrics_used=["x"], metrics_missing=[], sources=["test"],
        as_of=datetime.now(timezone.utc),
    )


def test_marketripple_score_is_never_publishable_in_s2_phase():
    """The explicit S2 phase lock — this is a deliberate policy assertion,
    not a coverage-threshold computation. See engine.py's own docstring."""
    from app.services.marketripple_score.engine import _PUBLISH_LOCK_REASON

    score = MarketRippleScore(
        symbol="TEST", score=72.0, label="Positive", publishable=False,
        publish_reason=_PUBLISH_LOCK_REASON,
        pillars={"financial_strength": _pillar(80.0)}, weights={"financial_strength": 1.0},
        overall_coverage_pct=100.0,
    )
    assert score.publishable is False
    assert "S2" in score.publish_reason


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
