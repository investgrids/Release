"""
AEV2 confidence score — restored to the CLOSED SPECIFICATION exactly
(review correction, 2026-09-21: Build 1's first draft substituted
source_diversity/company_attribution for two of the approved
components — a product-contract change made without approval, reverted
here in full):

    0.35 * evidence_quality
  + 0.25 * market_confirmation
  + 0.25 * historical_similarity
  + 0.15 * data_freshness

All 4 components are read VERBATIM from postprocess.compute_confidence_
breakdown's own already-computed 0-100 values (CoreAnswer.
confidence_breakdown — computed once, upstream, from real evidence;
never recomputed, never re-derived from raw counts here). AEV2 performs
no counting of its own, which is what makes "the score cannot increase
merely because duplicate sources or companies were counted" true by
construction, not by a separate guard: postprocess.py's own evidence_
quality already uses development_count (deduplicated independent
developments — see its Phase 5E.5 fix) rather than raw source rows, and
AEV2 never touches source/company counts at all, so there is no place
left in this module where a duplicate could be counted twice.

Component meanings (for a future UI to render honestly, not spin):
  - evidence_quality:      how well the real evidence (source count,
                            company sensitivity, sector confirmation)
                            supports the analysis.
  - market_confirmation:   whether other sectors/indices are already
                            moving in the direction this analysis
                            expects.
  - historical_similarity: how closely genuinely similar past events
                            match, and how accurate those past
                            predictions turned out to be.
  - data_freshness:        how recent the underlying news/events are.

Missing-component behavior: compute_confidence_breakdown normally
produces all 4 together in one call, so partial availability is not a
realistic runtime state today — but this module still handles it
explicitly (defensive, not assumed): a component is included only when
its value is not None; the weights of whichever components ARE present
are renormalized to sum to 1.0 (so a 2-of-4 case is still a proper
weighted average, not silently divided by the full 1.0). Zero
components present -> unscored, never a fabricated number.

The 4 components are each already bounded to [0, 100] by postprocess.py
before this module ever sees them; a weighted average (weights summing
to 1.0) of bounded values is itself bounded within
[min(components), max(components)] subset of [0, 100] — the final score
can never exceed the best individual component, let alone 100, and
never drops below the worst one. See
test_aev2_confidence_matches_approved_formula.py for the fixture-based
proof of this and the distribution comparison against V3's own blended
final_confidence.
"""
from __future__ import annotations

from app.services.ai_search.core_answer import CoreAnswer
from app.services.confidence_service import _THRESHOLDS

_WEIGHTS = {
    "evidence_quality": 0.35,
    "market_confirmation": 0.25,
    "historical_similarity": 0.25,
    "data_freshness": 0.15,
}


def _score_to_level(score: float) -> str:
    return next(label for threshold, label in _THRESHOLDS if score >= threshold)


def compute_aev2_confidence(core: CoreAnswer) -> dict:
    """Reads only core.confidence_breakdown — no price-movement or
    company-attribution input (Build 1's first draft took a
    `price_movement` argument for exactly the two unapproved components
    this restores away from; there is nothing left for this function to
    read from that source, so the parameter is gone, not just unused)."""
    breakdown = core.confidence_breakdown or {}
    available = {
        name: float(breakdown[name])
        for name in _WEIGHTS
        if breakdown.get(name) is not None
    }
    if not available:
        return {"score": None, "level": "unscored", "components_available": []}

    weight_sum = sum(_WEIGHTS[name] for name in available)
    score = round(sum(value * _WEIGHTS[name] for name, value in available.items()) / weight_sum, 1)
    return {
        "score": score,
        "level": _score_to_level(score),
        "components_available": sorted(available.keys()),
    }
