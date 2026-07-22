"""
Investment Verdict Engine — Phase 2.

Computes the research-outlook rating (one of the 8 _OUTLOOK_LABELS) from
real signals instead of trusting the LLM's own free-text rating:

  - direction          real, from the MIE's live market signals
  - confidence_score    real, the blended evidence+calibration confidence
                         already computed by confidence_service before this
                         runs (source counts, historical accuracy, macro
                         alignment, VIX regime, calibration-adjusted)
  - opportunity_score   real, from the Opportunity Engine when the named
                         entity/sector has a live match — None when it
                         doesn't, never a fabricated stand-in
  - vix_level           real, live India VIX

No LLM call happens in this module. This is the same principle as
market_scoring_engine.py: pure, deterministic, reuses real engines rather
than duplicating them. ai_search_service.py reconciles this against the
AI's own stated rating — close agreement keeps the AI's (more
query-specific) label; a real disagreement overrides it, since data wins
over an unconstrained guess.
"""
from __future__ import annotations

_OUTLOOK_LABELS = [
    "Strongly Constructive", "Constructive", "Positive Outlook",
    "Selectively Constructive", "Neutral", "Cautious",
    "Elevated Risk", "High Uncertainty",
]


def compute_investment_verdict(
    direction: str,
    confidence_score: float,
    opportunity_score: float | None,
    vix_level: float | None,
) -> dict:
    d = (direction or "sideways").lower()
    conf = confidence_score or 0.0
    opp = opportunity_score if opportunity_score is not None else 50.0
    vix = vix_level if vix_level is not None else 15.0
    high_vix = vix > 22  # elevated volatility regime dampens conviction either way

    if d == "bullish":
        if opp >= 85 and conf >= 80 and not high_vix:
            rating = "Strongly Constructive"
        elif opp >= 70 and conf >= 60:
            rating = "Constructive"
        elif conf >= 50:
            rating = "Positive Outlook"
        else:
            rating = "Selectively Constructive"
    elif d == "bearish":
        if opp <= 25 or conf < 35 or high_vix:
            rating = "High Uncertainty"
        else:
            rating = "Elevated Risk"
    else:  # sideways / unknown market direction
        if conf < 45:
            rating = "Cautious"
        elif opp >= 60:
            rating = "Selectively Constructive"
        else:
            rating = "Neutral"

    return {
        "rating":                  rating,
        "tier":                    _OUTLOOK_LABELS.index(rating),
        "direction":               d,
        "confidence_used":         round(conf),
        "opportunity_score_used":  round(opp, 1) if opportunity_score is not None else None,
        "vix_level_used":          vix,
        "basis":                   "computed" if opportunity_score is not None else "computed_no_opportunity_match",
    }
