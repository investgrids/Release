"""
AEV2's own four-component confidence score — deterministic arithmetic
over signals V3 already computed, never a recomputation of evidence
retrieval and never a provider call.

Components (each 0-100, each independently omittable when its own input
is empty — see `components_available`):
  - evidence_quality:    reused verbatim from postprocess.compute_
                          confidence_breakdown's own evidence_quality
                          (CoreAnswer.confidence_breakdown — already
                          computed upstream, not recomputed here).
  - data_freshness:      same passthrough, data_freshness component.
  - source_diversity:    how many of the 3 evidence types (event/news/
                          policy) contributed at least one real citation
                          — a presentation-layer signal AEV2 computes
                          itself from CoreAnswer's own already-retrieved
                          lists (zero new retrieval; just counting what's
                          already there).
  - company_attribution: fraction of resolved companies AEV2 could
                          actually attribute a live price movement to
                          (build_price_movement_groups' own output) —
                          the deterministic company-attribution signal,
                          reused rather than recomputed a second time.

final score = the unweighted mean of whichever components have real
input; `components_available` records exactly which ones, so a response
missing all 4 (e.g. a degraded shell before this ever runs) honestly
reports unscored rather than a fabricated number.
"""
from __future__ import annotations

from app.services.ai_search.core_answer import CoreAnswer
from app.services.confidence_service import _THRESHOLDS


def _score_to_level(score: float) -> str:
    return next(label for threshold, label in _THRESHOLDS if score >= threshold)


def compute_aev2_confidence(core: CoreAnswer, price_movement: dict) -> dict:
    components: dict[str, float] = {}
    breakdown = core.confidence_breakdown or {}

    evidence_quality = breakdown.get("evidence_quality")
    if evidence_quality is not None:
        components["evidence_quality"] = float(evidence_quality)

    data_freshness = breakdown.get("data_freshness")
    if data_freshness is not None:
        components["data_freshness"] = float(data_freshness)

    evidence_groups = (core.related_events, core.news, core.policies)
    total_sources = sum(len(g) for g in evidence_groups)
    if total_sources > 0:
        distinct_types_present = sum(1 for g in evidence_groups if g)
        components["source_diversity"] = round((distinct_types_present / len(evidence_groups)) * 100, 1)

    attributed = len(price_movement.get("currently_higher", [])) + len(price_movement.get("currently_lower", []))
    omitted = len(price_movement.get("omitted_unattributed", []))
    total_companies = attributed + omitted
    if total_companies > 0:
        components["company_attribution"] = round((attributed / total_companies) * 100, 1)

    if not components:
        return {"score": None, "level": "unscored", "components_available": []}

    score = round(sum(components.values()) / len(components), 1)
    return {
        "score": score,
        "level": _score_to_level(score),
        "components_available": sorted(components.keys()),
    }
