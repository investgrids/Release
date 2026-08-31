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
from app.services.financial_facts.nse_xbrl_client import extract_tag_value


def test_extract_tag_value_prefers_four_d_context():
    """Real bug found live during S3-D: ReturnOnAssets can genuinely
    diverge between the OneD (single period) and FourD (trailing four
    periods / annualized) contexts — confirmed live, HDFCBANK OneD=0.47%
    vs FourD=1.43%, a real 3x gap. FourD must always win when present."""
    xml = (
        '<in-bse-fin:ReturnOnAssets contextRef="OneD" decimals="4">0.0047</in-bse-fin:ReturnOnAssets>'
        '<in-bse-fin:ReturnOnAssets contextRef="FourD" decimals="4">0.0143</in-bse-fin:ReturnOnAssets>'
    )
    assert extract_tag_value(xml, "ReturnOnAssets") == 0.0143


def test_extract_tag_value_identical_contexts_unaffected():
    """Point-in-time ratios (NPA%, CET1) have identical OneD/FourD values
    on every real filing checked — the fix must not change their result."""
    xml = (
        '<in-bse-fin:CET1Ratio contextRef="OneD" decimals="4">0.1997</in-bse-fin:CET1Ratio>'
        '<in-bse-fin:CET1Ratio contextRef="FourD" decimals="4">0.1997</in-bse-fin:CET1Ratio>'
    )
    assert extract_tag_value(xml, "CET1Ratio") == 0.1997


def test_extract_tag_value_falls_back_without_context():
    xml = '<in-bse-fin:GrossNonPerformingAssets decimals="2">123.45</in-bse-fin:GrossNonPerformingAssets>'
    assert extract_tag_value(xml, "GrossNonPerformingAssets") == 123.45


def test_extract_tag_value_none_when_absent():
    assert extract_tag_value("<xml></xml>", "CET1Ratio") is None


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


def test_plausibility_flags_real_confirmed_yesbank_cet1():
    # The real, live-confirmed YESBANK case (S4): CET1 reads 0.13% across
    # all 8 real quarters checked — internally consistent (assess() alone
    # finds nothing wrong) but ~100x below any plausible real value.
    status, reason = quality.assess_plausibility("cet1_ratio", 0.0013)
    assert status == "IMPLAUSIBLE_SCALE"
    assert "0.0013" in reason


def test_plausibility_does_not_flag_real_observed_cet1_range():
    # Real observed range across the S4 27-bank universe: 11.97%-21.71%.
    for real_value in (0.1197, 0.1360, 0.1591, 0.1991, 0.2171):
        status, reason = quality.assess_plausibility("cet1_ratio", real_value)
        assert status == "OK", f"{real_value} incorrectly flagged: {reason}"


def test_plausibility_ok_for_metric_with_no_registered_range():
    # Additive layer only — a metric not yet scoped for plausibility must
    # never be blocked by this check.
    status, reason = quality.assess_plausibility("deposit_growth", 999.0)
    assert status == "OK"
    assert reason is None
