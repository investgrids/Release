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
