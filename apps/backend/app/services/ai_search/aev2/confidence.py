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

Missing-component behavior (corrected in review, 2026-09-21 third pass:
the FIRST correction — renormalizing weights across whatever components
were present — was itself wrong and is reverted here). The closed
errata is explicit: a missing component contributes ZERO, weights are
NEVER renormalized. Renormalizing lets sparse evidence masquerade as a
fully-confident score — e.g. evidence_quality=100 with the other 3
components missing must score 0.35 * 100 = 35.0, not 100.0 (which
renormalizing across "the one component we have" would have produced).
A component is included in `components_available` when its value is
not None, but its WEIGHT is applied against the fixed 0.35/0.25/0.25/
0.15 table regardless of what else is present — a missing component is
arithmetically a zero contribution, not an absent term in a rescaled
sum. All 4 missing -> unscored (None), never a numeric zero that could
be misread as "very low confidence" rather than "not computed at all".
Rounded once, server-side, to one decimal — never re-rounded by a
caller.

The 4 components are each already bounded to [0, 100] by postprocess.py
before this module ever sees them, and the fixed weights sum to 1.0 —
so a response with EVERY component present is bounded within
[min(components), max(components)] subset of [0, 100]. A response
missing one or more components is NOT bound by that same range by
design (that is the whole point of this correction): its score is
capped by the sum of the weights of whatever IS present times 100, and
must read low precisely because coverage is incomplete, not because the
formula is broken. See test_aev2_build1_restructuring.py's sparse-input
tests for the fixture-based proof.
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

    # Fixed weights, NEVER renormalized — a missing component contributes
    # exactly zero, not "redistributed" among the components that are
    # present. See module docstring for why renormalizing was wrong.
    score = round(sum(value * _WEIGHTS[name] for name, value in available.items()), 1)
    return {
        "score": score,
        "level": _score_to_level(score),
        "components_available": sorted(available.keys()),
    }
