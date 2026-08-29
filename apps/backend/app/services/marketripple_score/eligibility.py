"""
S5-B — publication eligibility analysis. A publication-quality decision,
deliberately separate from BANKING_V1 scoring itself: this module never
touches the score, the weights, the peer universe, or the pillar
formulas — it only asks whether a given, already-computed
MarketRippleScoreSnapshot carries enough real, current evidence to be
shown publicly.

Owner instruction (2026-08-29): this module does NOT choose a final
threshold. evaluate_eligibility() takes the policy as an explicit
parameter, so a real 27-bank audit can compare several candidate
policies side by side rather than one rule baked in reactively after
seeing any single bank's (e.g. YESBANK's) result. Wiring a chosen policy
into compute_and_persist_snapshot()'s actual publishable/
publication_block_reasons fields is a separate, later, explicit decision
— not part of this module.
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
REASON_STALE_FINANCIAL_DATA = "STALE_FINANCIAL_DATA"

# The real, currently-implemented Financial Strength metric set (S3-D) —
# 7 of the originally-proposed 12 (5 permanently SOURCE_UNAVAILABLE/
# insufficient-history, see financial_strength.py's own _KNOWN_UNAVAILABLE).
# financial_coverage_pct is stored scaled against 12 (the full original
# ambition, kept honest); this converts it back to "N of the 7 metrics
# that can currently ever be scored" — the count the owner asked to
# evaluate directly, not just a percentage that obscures it.
_PROPOSED_BANKING_METRICS = 12
_REAL_BANKING_METRICS = 7


def financial_metrics_used_from_coverage_pct(financial_coverage_pct: float | None) -> int:
    """Exact, not estimated: financial_coverage_pct is always
    len(sub_scores)/_PROPOSED_BANKING_METRICS*100, so this recovers the
    real integer count with no information loss — no live recomputation
    needed to know how many of the 7 real metrics actually contributed."""
    if financial_coverage_pct is None:
        return 0
    return round(financial_coverage_pct / 100 * _PROPOSED_BANKING_METRICS)


@dataclass
class EligibilityPolicy:
    """One candidate publication policy — parameterized so several can be
    compared side by side, never a single hardcoded rule."""
    name: str
    min_financial_metrics_used: int             # out of the real 7
    min_overall_coverage_pct: float
    require_financial_strength_pillar: bool = True
    max_financial_data_age_quarters: int | None = None  # not enforced numerically yet — see module docstring


@dataclass
class PublicationEligibility:
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    financial_metrics_used: int = 0
    financial_metrics_used_pct: float = 0.0   # out of the real 7, NOT the 12-denominator coverage_pct
    overall_coverage_pct: float = 0.0
    financial_data_as_of: str | None = None
    policy_name: str = ""


def evaluate_eligibility(
    *, financial_strength_score: float | None, financial_coverage_pct: float | None,
    overall_coverage_pct: float, financial_data_as_of: str | None, policy: EligibilityPolicy,
) -> PublicationEligibility:
    reasons: list[str] = []
    financial_metrics_used = financial_metrics_used_from_coverage_pct(financial_coverage_pct)

    if policy.require_financial_strength_pillar and financial_strength_score is None:
        reasons.append(REASON_MISSING_REQUIRED_PILLAR)

    if financial_data_as_of is None:
        reasons.append(REASON_NO_ELIGIBLE_FINANCIAL_PERIOD)

    if financial_metrics_used < policy.min_financial_metrics_used:
        reasons.append(REASON_INSUFFICIENT_FINANCIAL_METRICS)

    if overall_coverage_pct < policy.min_overall_coverage_pct:
        reasons.append(REASON_INSUFFICIENT_OVERALL_COVERAGE)

    # Freshness (owner-requested, audit-only for now): policy.max_financial_data_age_quarters
    # is intentionally never compared against a real value here — doing so
    # would need a real "current quarter" reference point, which the audit
    # script establishes analytically (relative to the observed population)
    # rather than this module guessing one.

    return PublicationEligibility(
        eligible=not reasons, reasons=reasons,
        financial_metrics_used=financial_metrics_used,
        financial_metrics_used_pct=round(financial_metrics_used / _REAL_BANKING_METRICS * 100, 1),
        overall_coverage_pct=overall_coverage_pct,
        financial_data_as_of=financial_data_as_of,
        policy_name=policy.name,
    )
