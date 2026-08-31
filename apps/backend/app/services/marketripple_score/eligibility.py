"""
S5-B — publication eligibility. A publication-quality decision,
deliberately separate from BANKING_V1 scoring itself: this module never
touches the score, the weights, the peer universe, or the pillar
formulas — it only asks whether a given, already-computed
MarketRippleScoreSnapshot carries enough real, current evidence to be
shown publicly.

BANKING_V1_P1 is the owner's real, decided policy (2026-08-29): >=5 of
the 7 real Financial Strength metrics, >=65% overall evidence coverage,
Financial Strength required, an eligible financial period required.
Chosen over a >=4/7 floor (too permissive — almost half the core
Banking model absent is not defensible for a public score, even though
today's real population happens to produce an identical result at 4 or
5) and over a >=70% overall floor (Policy C in the S5-B audit — would
have additionally excluded BANKBARODA/PNB, both with PERFECT financial
data, primarily for thin Current Intelligence, a pillar this design
explicitly does NOT require).

Historical quarantine does NOT independently block publication — a
company's CURRENT snapshot inputs (their real coverage/freshness/metric
count) are what's evaluated, not whether some past period was ever
quarantined; current valid evidence supersedes stale flags on unrelated
periods (see quarantine.py's own real document-identity scoping for why
that's already true at the fact level).

Freshness (STALE_FINANCIAL_DATA) is reserved but NOT enforced yet — the
real S5-B audit found no genuinely lagging bank to calibrate a rule
against (every real bank shares the same newest eligible period);
activating a threshold before a real case exists would be inventing a
number, not measuring one.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Stable, machine-readable reason codes — never free-form/LLM prose, so a
# future frontend can render fixed copy per code without recreating
# eligibility logic itself.
REASON_MISSING_REQUIRED_PILLAR = "MISSING_REQUIRED_PILLAR"
REASON_NO_ELIGIBLE_FINANCIAL_PERIOD = "NO_ELIGIBLE_FINANCIAL_PERIOD"
REASON_INSUFFICIENT_FINANCIAL_METRICS = "INSUFFICIENT_FINANCIAL_METRICS"
REASON_INSUFFICIENT_OVERALL_COVERAGE = "INSUFFICIENT_OVERALL_COVERAGE"
REASON_STALE_FINANCIAL_DATA = "STALE_FINANCIAL_DATA"  # reserved, not enforced — see module docstring


@dataclass
class EligibilityPolicy:
    """One publication policy — parameterized, not hardcoded, so
    candidates could always be compared side by side (see the S5-B audit,
    artifacts/marketripple_score_s5b_eligibility_audit.md)."""
    name: str
    min_financial_metrics_used: int             # out of REAL_BANKING_METRICS_TOTAL (7)
    min_overall_coverage_pct: float
    require_financial_strength_pillar: bool = True
    max_financial_data_age_quarters: int | None = None  # not enforced yet — see module docstring


# The real, decided Banking V1 publication policy (owner decision,
# 2026-08-29, following the S5-B audit).
BANKING_V1_P1 = EligibilityPolicy(
    name="BANKING_V1_P1",
    min_financial_metrics_used=5,
    min_overall_coverage_pct=65.0,
    require_financial_strength_pillar=True,
)


@dataclass
class PublicationEligibility:
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    financial_metrics_used: int = 0
    financial_metrics_total: int = 0
    overall_coverage_pct: float = 0.0
    financial_data_as_of: str | None = None
    policy_name: str = ""


def evaluate_eligibility(
    *, financial_strength_score: float | None, financial_metrics_used: int, financial_metrics_total: int,
    overall_coverage_pct: float, financial_data_as_of: str | None, policy: EligibilityPolicy,
) -> PublicationEligibility:
    """Takes the real, directly-persisted metric count (never a value
    reverse-derived from a coverage percentage) — see
    MarketRippleScoreSnapshot.financial_metrics_used_count."""
    reasons: list[str] = []

    if policy.require_financial_strength_pillar and financial_strength_score is None:
        reasons.append(REASON_MISSING_REQUIRED_PILLAR)

    if financial_data_as_of is None:
        reasons.append(REASON_NO_ELIGIBLE_FINANCIAL_PERIOD)

    if financial_metrics_used < policy.min_financial_metrics_used:
        reasons.append(REASON_INSUFFICIENT_FINANCIAL_METRICS)

    if overall_coverage_pct < policy.min_overall_coverage_pct:
        reasons.append(REASON_INSUFFICIENT_OVERALL_COVERAGE)

    return PublicationEligibility(
        eligible=not reasons, reasons=reasons,
        financial_metrics_used=financial_metrics_used, financial_metrics_total=financial_metrics_total,
        overall_coverage_pct=overall_coverage_pct, financial_data_as_of=financial_data_as_of,
        policy_name=policy.name,
    )
