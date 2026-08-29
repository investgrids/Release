"""
S5-B — pure-logic tests for the publication eligibility contract. No
threshold is "the" implemented policy here — evaluate_eligibility() takes
a policy as an explicit parameter, matching the owner's instruction not
to bake in a single rule reactively.
"""
from __future__ import annotations

from app.services.marketripple_score.eligibility import (
    EligibilityPolicy, evaluate_eligibility, financial_metrics_used_from_coverage_pct,
    REASON_INSUFFICIENT_FINANCIAL_METRICS, REASON_INSUFFICIENT_OVERALL_COVERAGE,
    REASON_MISSING_REQUIRED_PILLAR, REASON_NO_ELIGIBLE_FINANCIAL_PERIOD,
)


def test_financial_metrics_used_matches_real_observed_yesbank_values():
    # Real, live-confirmed values from S4.5-A (6/7 metrics -> 50.0%) and
    # S4.5-B (3/7 metrics -> 25.0%) — exact round-trip, not an estimate.
    assert financial_metrics_used_from_coverage_pct(50.0) == 6
    assert financial_metrics_used_from_coverage_pct(25.0) == 3
    assert financial_metrics_used_from_coverage_pct(None) == 0
    assert financial_metrics_used_from_coverage_pct(0.0) == 0


def test_financial_metrics_used_exact_for_full_seven():
    # 7/12*100 = 58.333...% -- must round-trip to exactly 7, not 6 or 8.
    assert financial_metrics_used_from_coverage_pct(round(7 / 12 * 100, 1)) == 7


def test_eligible_when_policy_fully_satisfied():
    policy = EligibilityPolicy(name="A", min_financial_metrics_used=5, min_overall_coverage_pct=70.0)
    result = evaluate_eligibility(
        financial_strength_score=68.7, financial_coverage_pct=round(7 / 12 * 100, 1),
        overall_coverage_pct=83.3, financial_data_as_of="FY2025Q3", policy=policy,
    )
    assert result.eligible is True
    assert result.reasons == []
    assert result.financial_metrics_used == 7


def test_real_yesbank_case_fails_a_reasonable_policy():
    # Real, post-S4.5-B YESBANK values.
    policy = EligibilityPolicy(name="B", min_financial_metrics_used=5, min_overall_coverage_pct=60.0)
    result = evaluate_eligibility(
        financial_strength_score=56.4, financial_coverage_pct=25.0,
        overall_coverage_pct=57.5, financial_data_as_of=None, policy=policy,
    )
    assert result.eligible is False
    assert REASON_INSUFFICIENT_FINANCIAL_METRICS in result.reasons
    assert REASON_NO_ELIGIBLE_FINANCIAL_PERIOD in result.reasons
    assert result.financial_metrics_used == 3


def test_missing_financial_strength_pillar_always_blocks_when_required():
    policy = EligibilityPolicy(name="C", min_financial_metrics_used=0, min_overall_coverage_pct=0.0)
    result = evaluate_eligibility(
        financial_strength_score=None, financial_coverage_pct=None,
        overall_coverage_pct=90.0, financial_data_as_of=None, policy=policy,
    )
    assert result.eligible is False
    assert REASON_MISSING_REQUIRED_PILLAR in result.reasons


def test_overall_coverage_gate_independent_of_financial_metrics():
    policy = EligibilityPolicy(name="D", min_financial_metrics_used=0, min_overall_coverage_pct=90.0)
    result = evaluate_eligibility(
        financial_strength_score=70.0, financial_coverage_pct=round(7 / 12 * 100, 1),
        overall_coverage_pct=83.3, financial_data_as_of="FY2025Q3", policy=policy,
    )
    assert result.eligible is False
    assert result.reasons == [REASON_INSUFFICIENT_OVERALL_COVERAGE]
