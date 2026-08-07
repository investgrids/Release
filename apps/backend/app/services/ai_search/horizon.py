"""
Deterministic investment-horizon bucketing — P5 Stage 3, item 4.

Replaces the hardcoded "6-12 months" fallback both pipelines used whenever
the LLM's own response didn't state a horizon. No LLM call, no new signals —
reuses VIX (already fetched for confidence scoring), the historical-
similarity comparisons (already fetched via find_similar_events), and the
evidence's own immediate/medium/long-term impact fields (already part of
both pipelines' schema) — the same "don't add a call if deterministic data
already answers it" stance as investment_verdict_engine.py and
opportunity_intelligence.py.

Only used as a fallback: a real LLM-stated horizon is always kept as-is by
the caller, never overridden by this.
"""
from __future__ import annotations

# Matches investment_verdict_engine.py's own elevated-volatility threshold —
# one definition of "high VIX" across the app, not a second one invented here.
_HIGH_VIX = 22.0

# The horizon-window vocabulary already used elsewhere across this codebase
# (ai_search_service.py's timeline entries, decision panels, etc.) — this
# function picks among them, it doesn't invent a new label set.
_SHORT = "1-3 months"
_MEDIUM = "3-6 months"
_LONG = "6-12 months"
_EXTENDED = "12-18 months"


def compute_horizon(
    vix_level: float | None,
    historical: list[dict] | None,
    medium_term: str | None,
    long_term: str | None,
) -> str:
    """VIX regime + historical-similarity duration + driver timing -> one of
    the four window strings above.

    - Elevated VIX compresses the horizon outright: a longer-horizon call is
      less reliable when the market itself is this unsettled, regardless of
      what the other two signals say.
    - Historical-similarity duration: for each matched precedent with both a
      1-week and 1-month outcome, does the move keep extending past the
      first week (nifty_1m materially larger in magnitude than nifty_1w), or
      does it resolve and hold? Averaged across all matched precedents.
    - Driver timing: which of the evidence's own medium/long-term impact
      fields actually has real content — the furthest-out bucket with
      substantive text is a proxy for how far the already-computed evidence
      itself is pointing.
    """
    vix = float(vix_level or 0)
    if vix > _HIGH_VIX:
        return _SHORT

    extends_long = False
    if historical:
        gaps = [
            abs(h["nifty_1m"]) - abs(h["nifty_1w"])
            for h in historical
            if h.get("nifty_1m") is not None and h.get("nifty_1w") is not None
        ]
        if gaps:
            extends_long = (sum(gaps) / len(gaps)) > 3.0

    has_long_driver = bool((long_term or "").strip())
    has_medium_driver = bool((medium_term or "").strip())

    if has_long_driver and extends_long:
        return _EXTENDED
    if has_long_driver or extends_long:
        return _LONG
    if has_medium_driver:
        return _MEDIUM
    return _SHORT
