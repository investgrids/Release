"""
Decision Engine — Phase 2.

For genuine two-entity decisions (switch/compare/hold, where the user
named both a holding and a target), computes which side the real data
favors instead of letting the LLM assert a preference unconstrained.

Reuses investment_verdict_engine.compute_investment_verdict independently
for each entity — same market-wide signals (direction, blended confidence,
VIX) apply to both sides, so the real differentiator is each entity's own
Opportunity Engine score (when one matches) and, when available, a real
P/E comparison from the same valuation fetch the general pipeline already
does. No LLM call happens here.
"""
from __future__ import annotations

from app.services.investment_verdict_engine import compute_investment_verdict


def compute_decision(
    entity_a_symbol: str,
    entity_b_symbol: str,
    direction: str,
    confidence_score: float,
    vix_level: float | None,
    opportunity_score_a: float | None,
    opportunity_score_b: float | None,
    valuation_a: dict | None = None,
    valuation_b: dict | None = None,
) -> dict:
    verdict_a = compute_investment_verdict(direction, confidence_score, opportunity_score_a, vix_level)
    verdict_b = compute_investment_verdict(direction, confidence_score, opportunity_score_b, vix_level)
    tier_gap = verdict_b["tier"] - verdict_a["tier"]  # positive => A has the better (lower) tier

    if tier_gap >= 2:
        favored, margin = entity_a_symbol, "clear"
    elif tier_gap == 1:
        favored, margin = entity_a_symbol, "slight"
    elif tier_gap == 0:
        favored, margin = None, "no_clear_edge"
    elif tier_gap == -1:
        favored, margin = entity_b_symbol, "slight"
    else:
        favored, margin = entity_b_symbol, "clear"

    valuation_note = None
    pe_a = (valuation_a or {}).get("pe")
    pe_b = (valuation_b or {}).get("pe")
    if pe_a and pe_b:
        cheaper, hi, lo = (
            (entity_a_symbol, pe_b, pe_a) if pe_a < pe_b else (entity_b_symbol, pe_a, pe_b)
        )
        valuation_note = f"{cheaper} trades at a lower P/E ({lo} vs {hi})"

    return {
        "favored_entity": favored,
        "margin":         margin,
        "entity_a":       {"symbol": entity_a_symbol, **verdict_a},
        "entity_b":       {"symbol": entity_b_symbol, **verdict_b},
        "valuation_note": valuation_note,
        "basis":          "computed",
    }
