"""
Quality assessment — separate from extraction status (see FinancialFact's
module docstring, rule 2). A real, populated value can still be untrustworthy;
this module never rejects or "corrects" it, only flags it for review.

Threshold below is a candidate, informed by the one real case found live
(ICICIBANK Q1 FY25 Gross NPA reading 0.02% against a ~2% trailing trend
across every adjacent real quarter) — not validated against a broad real
sample yet. Flagged explicitly as such, same discipline as every other
candidate threshold in this initiative.
"""
from __future__ import annotations

import statistics

# A new value is ANOMALY when it differs from the trailing median by more
# than this multiple — catches the real ICICIBANK case (0.02 vs ~2.0, a
# ~100x deviation) without flagging normal quarter-to-quarter drift (the
# real reference-bank data moves at most ~15% quarter to quarter).
_ANOMALY_RATIO_THRESHOLD = 3.0
_MIN_TRAILING_OBSERVATIONS = 2  # below this, there's no real trend to compare against

# Real bug found live while validating this module: a pure ratio-based
# comparison is meaningless near a genuinely-tiny baseline — real
# ICICIBANK AdditionalTier1Ratio values (0.0, 0.0009, ...) are legitimately
# near-zero every quarter (many Indian banks carry little/no AT1 capital
# at a given point), and a swing from 0.0009 to 0.0 is a "0.0x deviation"
# by ratio while being economically insignificant. Skip anomaly evaluation
# entirely when the trailing median's own absolute value sits below this
# floor — below it, ratio comparison has no real signal. Candidate value,
# not validated beyond this one real case.
_MIN_MEANINGFUL_BASELINE = 0.005  # 0.5% for pct-unit metrics


def assess(new_value: float, trailing_values: list[float]) -> tuple[str, str | None]:
    """Returns (quality_status, quality_reason). trailing_values should be
    the symbol's own real prior POPULATED values for this exact metric_code
    + consolidation_scope, most-recent-first, already excluding the new one."""
    from app.db.models.financial_fact import QUALITY_ANOMALY, QUALITY_OK

    if len(trailing_values) < _MIN_TRAILING_OBSERVATIONS:
        return QUALITY_OK, None

    trailing = trailing_values[:4]  # last 4 real quarters/years — recent trend, not full history
    median = statistics.median(trailing)
    if abs(median) < _MIN_MEANINGFUL_BASELINE:
        return QUALITY_OK, None  # baseline too close to zero for a ratio comparison to mean anything

    ratio = max(abs(new_value), 1e-9) / abs(median)
    deviates = ratio >= _ANOMALY_RATIO_THRESHOLD or ratio <= 1 / _ANOMALY_RATIO_THRESHOLD
    if deviates:
        return QUALITY_ANOMALY, (
            f"{new_value} deviates {ratio:.1f}x from the trailing {len(trailing)}-period "
            f"median of {median:.4g} (candidate threshold {_ANOMALY_RATIO_THRESHOLD}x, unvalidated)"
        )
    return QUALITY_OK, None


# S4.5 — cross-sectional/metric plausibility validation (owner decision,
# 2026-08-29). Real gap this closes: the within-entity check above is
# structurally blind to a filer whose own values are consistently wrong
# across its own full history (real, confirmed-live case: YESBANK's real
# CET1 sits at ~0.13% across all 8 real quarters checked — internally
# consistent, so `assess()` correctly finds no deviation — but ~100x below
# any plausible real value; see artifacts/marketripple_score_s4_wide_banking_validation.md
# §7). This check is deliberately metric/unit-grounded, not fit to that one
# case: bounds come from the metric's own real-world regulatory/structural
# meaning, never from "what YESBANK's real value should have been."
#
# cet1_ratio has a genuine hard floor: Basel III's absolute minimum CET1 is
# 4.5%, and RBI's real effective minimum (including capital conservation
# buffer) is ~8% for Indian scheduled commercial banks — nothing below 2%
# is plausible for any real, operating bank, regulatory floor or not.
# gross_npa_pct/net_npa_pct/roa get much looser structural sanity bounds
# (never observed anywhere near real-world for any Indian bank) — these
# exist to catch a genuine scale error (e.g. a misplaced decimal reading as
# 200%), not to reverse-engineer this one filer's specific numbers. A real,
# tighter low-end NPA bound is a legitimate future enhancement, not added
# here since — unlike CET1 — NPA has no comparably hard regulatory floor.
_PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    "cet1_ratio": (0.02, 0.60),      # 2%-60%
    "gross_npa_pct": (0.0, 0.60),    # 0%-60%
    "net_npa_pct": (0.0, 0.60),      # 0%-60%
    "roa": (-0.10, 0.10),            # -10%-10%
}


def assess_plausibility(metric_code: str, value: float) -> tuple[str, str | None]:
    """Returns (quality_status, quality_reason) — independent of any
    trailing history, purely a metric/unit-level real-world plausibility
    check. Never touches `value` itself; only ever produces a status/reason
    to attach alongside the real, unmodified, as-filed value. A metric with
    no registered plausible range (not yet scoped) always passes as OK —
    this is an additive layer, not a blocker for unscoped metrics."""
    from app.db.models.financial_fact import QUALITY_IMPLAUSIBLE_SCALE, QUALITY_OK

    bounds = _PLAUSIBLE_RANGES.get(metric_code)
    if bounds is None:
        return QUALITY_OK, None
    lo, hi = bounds
    if value < lo or value > hi:
        return QUALITY_IMPLAUSIBLE_SCALE, (
            f"{value} is outside the plausible real-world range for {metric_code} "
            f"({lo}-{hi}) — likely a source scale/unit error, not a genuine value; "
            f"preserved as-filed, excluded from scoring"
        )
    return QUALITY_OK, None
