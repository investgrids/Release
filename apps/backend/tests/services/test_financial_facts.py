"""
Financial Facts — S3-B pure-logic tests. The live NSE fetch/parse path was
validated manually against real data (see artifacts/marketripple_score_
s3a_reliability_and_casa_check.md and the real ICICIBANK ingest run it's
based on) — these tests cover the deterministic logic that doesn't need
network access: fiscal-year parsing, the anomaly-detection threshold and
its near-zero-baseline guard (a real bug found live while validating this
module — see quality.py's own comment).
"""
from __future__ import annotations

from app.services.financial_facts.ingest import _fiscal_year_from_financial_year
from app.services.financial_facts.metrics import METRICS_BY_CODE, QUARTERLY_METRICS, ANNUAL_METRICS
from app.services.financial_facts import quality


def test_fiscal_year_parses_real_nse_format():
    # Real format confirmed live: "01-Apr-2024 To 31-Mar-2025" -> FY25
    assert _fiscal_year_from_financial_year("01-Apr-2024 To 31-Mar-2025") == 2025
    assert _fiscal_year_from_financial_year("01-Apr-0012 To 31-Mar-0013") == 13  # real old-format filing, low but parseable
    assert _fiscal_year_from_financial_year(None) is None
    assert _fiscal_year_from_financial_year("") is None


def test_car_and_casa_are_registered_but_have_no_tag():
    """The two real, confirmed-absent metrics must stay registered (so a
    SOURCE_UNAVAILABLE row gets written) but must never carry a tag that
    would make ingest.py try to extract them, and CAR specifically must
    never be derivable as CET1 + AdditionalTier1 (would omit Tier 2)."""
    assert METRICS_BY_CODE["car_total"].tag is None
    assert METRICS_BY_CODE["casa_ratio"].tag is None
    assert METRICS_BY_CODE["cet1_ratio"].tag == "CET1Ratio"
    assert METRICS_BY_CODE["additional_tier1_ratio"].tag == "AdditionalTier1Ratio"


def test_quarterly_and_annual_metrics_are_disjoint_period_types():
    assert all(m.period_type == "Quarterly" for m in QUARTERLY_METRICS)
    assert all(m.period_type == "Annual" for m in ANNUAL_METRICS)


def test_quality_ok_with_insufficient_trailing_history():
    status, reason = quality.assess(0.02, [])
    assert status == "OK"
    assert reason is None
    status, reason = quality.assess(0.02, [0.019])  # only 1 real prior point
    assert status == "OK"


def test_quality_flags_real_confirmed_anomaly():
    # The real, live-confirmed ICICIBANK Q1 FY25 case: Gross NPA reads
    # 0.02% against a ~2% trailing trend.
    status, reason = quality.assess(0.0002, [0.0196, 0.0197, 0.0216, 0.0142])
    assert status == "ANOMALY"
    assert "deviates" in reason


def test_quality_does_not_flag_near_zero_baseline_noise():
    """Real bug found live: a metric that's genuinely near-zero every real
    quarter (AdditionalTier1Ratio) must not trigger on ordinary 0.0009 <->
    0.0 noise — the trailing median itself is too close to zero for a
    ratio comparison to carry real signal."""
    status, reason = quality.assess(0.0, [0.0009, 0.001, 0.0011])
    assert status == "OK"
    assert reason is None


def test_quality_does_not_flag_normal_quarter_to_quarter_drift():
    # Real reference-bank data moves at most ~15% quarter to quarter.
    status, reason = quality.assess(0.145, [0.140, 0.138, 0.135])
    assert status == "OK"
