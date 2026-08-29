"""
S5-B — pure-logic tests for the publication eligibility contract.
BANKING_V1_P1 is the real, decided policy (owner, 2026-08-29); tests also
cover evaluate_eligibility() generically since a caller can still pass a
different EligibilityPolicy (e.g. for the retired candidate-comparison
audit, or a future sector).
"""
from __future__ import annotations

from app.services.marketripple_score.eligibility import (
    BANKING_V1_P1, EligibilityPolicy, evaluate_eligibility,
    REASON_INSUFFICIENT_FINANCIAL_METRICS, REASON_INSUFFICIENT_OVERALL_COVERAGE,
    REASON_MISSING_REQUIRED_PILLAR, REASON_NO_ELIGIBLE_FINANCIAL_PERIOD,
)


def test_banking_v1_p1_matches_the_decided_policy():
    assert BANKING_V1_P1.min_financial_metrics_used == 5
    assert BANKING_V1_P1.min_overall_coverage_pct == 65.0
    assert BANKING_V1_P1.require_financial_strength_pillar is True


def test_eligible_when_policy_fully_satisfied():
    result = evaluate_eligibility(
        financial_strength_score=68.7, financial_metrics_used=7, financial_metrics_total=7,
        overall_coverage_pct=83.3, financial_data_as_of="FY2025Q3", policy=BANKING_V1_P1,
    )
    assert result.eligible is True
    assert result.reasons == []


def test_real_yesbank_case_fails_banking_v1_p1_on_three_grounds():
    # Real, post-S4.5-B YESBANK values (3/7 real metrics, no eligible period).
    result = evaluate_eligibility(
        financial_strength_score=56.4, financial_metrics_used=3, financial_metrics_total=7,
        overall_coverage_pct=57.5, financial_data_as_of=None, policy=BANKING_V1_P1,
    )
    assert result.eligible is False
    assert set(result.reasons) == {
        REASON_NO_ELIGIBLE_FINANCIAL_PERIOD,
        REASON_INSUFFICIENT_FINANCIAL_METRICS,
        REASON_INSUFFICIENT_OVERALL_COVERAGE,
    }


def test_real_indusindbk_case_fails_banking_v1_p1_on_coverage_alone():
    # Real values: 6/7 financial metrics (clears the 5/7 floor), but only
    # 57.5% overall coverage (Current Intelligence evidence is thin) --
    # a categorically different failure from YESBANK's.
    result = evaluate_eligibility(
        financial_strength_score=64.0, financial_metrics_used=6, financial_metrics_total=7,
        overall_coverage_pct=57.5, financial_data_as_of="FY2025Q3", policy=BANKING_V1_P1,
    )
    assert result.eligible is False
    assert result.reasons == [REASON_INSUFFICIENT_OVERALL_COVERAGE]


def test_four_of_seven_is_insufficient_under_banking_v1_p1():
    # The real reason B (>=5/7) was chosen over the more permissive A
    # (>=4/7): almost half the core Banking model absent is not
    # defensible for a public score, even where today's real population
    # happens not to have a bank sitting at exactly 4/7.
    result = evaluate_eligibility(
        financial_strength_score=50.0, financial_metrics_used=4, financial_metrics_total=7,
        overall_coverage_pct=80.0, financial_data_as_of="FY2025Q3", policy=BANKING_V1_P1,
    )
    assert result.eligible is False
    assert result.reasons == [REASON_INSUFFICIENT_FINANCIAL_METRICS]


def test_missing_financial_strength_pillar_always_blocks_when_required():
    policy = EligibilityPolicy(name="generic", min_financial_metrics_used=0, min_overall_coverage_pct=0.0)
    result = evaluate_eligibility(
        financial_strength_score=None, financial_metrics_used=0, financial_metrics_total=7,
        overall_coverage_pct=90.0, financial_data_as_of=None, policy=policy,
    )
    assert result.eligible is False
    assert REASON_MISSING_REQUIRED_PILLAR in result.reasons


def test_generic_policy_can_relax_the_required_pillar_check():
    policy = EligibilityPolicy(
        name="generic-no-required-pillar", min_financial_metrics_used=0,
        min_overall_coverage_pct=0.0, require_financial_strength_pillar=False,
    )
    result = evaluate_eligibility(
        financial_strength_score=None, financial_metrics_used=0, financial_metrics_total=7,
        overall_coverage_pct=90.0, financial_data_as_of="FY2025Q3", policy=policy,
    )
    assert result.eligible is True
