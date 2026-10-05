"""
Post-specialist processing: evidence score + the 6-part confidence
breakdown. Both computed server-side from real signals — never trusted from
raw LLM output (same principle as V2's existing evidence-based confidence).

Reuses V2's `confidence_service.calculate_confidence()` unchanged as the
proven, already-calibrated scoring engine — the user-facing 6-part
breakdown is a *view* over that engine's own internal breakdown dict
(mapped from raw point-scales to 0-100 percentages of each component's own
max), plus one genuinely new signal (data_freshness) confidence_service
doesn't compute today.

Enrichment/graph-build/ripple-chain assembly (_enrich_sync, _build_graph,
_classify_ripple_position, _fetch_chart_sync) are intentionally NOT
duplicated here — pipeline.py imports and calls V2's originals directly,
since that mechanism is untouched and doesn't need a typed wrapper.
"""
from __future__ import annotations

import re

from datetime import datetime, timezone


def compute_evidence_score(evidence) -> dict:
    """1-5 star rating + a checklist of what actually backs the answer —
    both derived from the real EvidenceBundle, never LLM-guessed.

    Phase 5E.5: the breadth bonus is computed from development_count
    (independent developments, via the shared evidence-clustering
    primitive — 5E.3), not raw evidence.source_count. Before this fix,
    5 outlets reporting the identical NSE filing inflated this bonus
    exactly as if 5 independent stories existed — the same class of bug
    already fixed for Opportunity Radar (5E.4). source_count is still
    returned in the response dict below, unchanged, as real
    corroboration/diversity information — just no longer what decides
    the star rating."""
    checklist = evidence.evidence_checklist()
    backed = sum(1 for v in checklist.values() if v)
    total_categories = len(checklist)
    source_bonus = min(evidence.development_count, 10) / 10  # 0-1
    coverage = backed / total_categories if total_categories else 0
    combined = (coverage * 0.7) + (source_bonus * 0.3)
    stars = max(1, min(5, round(combined * 5)))
    return {
        "stars": stars, "checklist": checklist,
        "source_count": evidence.source_count,
        "development_count": evidence.development_count,
        "corroborating_source_count": evidence.corroborating_source_count,
    }


def _freshness_score(evidence) -> float:
    """0-100: how recent is the underlying evidence. Mirrors the benchmark
    runner's own score_freshness() logic (relative "Nm ago" strings or ISO
    timestamps), kept independent since this runs server-side per-request,
    not as a post-hoc benchmark scoring pass."""
    import re
    now = datetime.now(timezone.utc)
    ages_min: list[float] = []
    for item in (evidence.news or []) + (evidence.events or []):
        ts = item.get("published_at") or item.get("date")
        if not ts or not isinstance(ts, str):
            continue
        rel = re.match(r"(\d+)\s*([mhd])\s*ago", ts.strip().lower())
        if rel:
            n, unit = int(rel.group(1)), rel.group(2)
            ages_min.append(n * (1 if unit == "m" else 60 if unit == "h" else 1440))
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ages_min.append(max(0.0, (now - dt).total_seconds() / 60))
        except ValueError:
            continue
    if not ages_min:
        return 50.0  # no timestamped evidence at all — neutral, not zero (absence isn't staleness)
    newest = min(ages_min)
    # Full marks under 1 hour old, decaying to a floor of 20 by 7 days.
    if newest <= 60:
        return 100.0
    if newest >= 10080:  # 7 days
        return 20.0
    return round(100 - (newest - 60) / (10080 - 60) * 80, 1)


async def compute_confidence_breakdown(evidence, parsed: dict, mie_state: dict | None = None) -> dict:
    """The public answer-confidence breakdown. Step 5 decision: **there is no public answer confidence**, so this is always the unscored shape.

    The number it used to return (for example 42.5 / "Medium") was not a measured property of the answer. Its inputs were: a model self-rating that is no longer requested and silently defaulted to 5 of 10
    (the "reasoning_confidence 50"); a market-confirmation and a historical-similarity score that are 0 both when nothing confirms and when nothing was retrieved; a calibration line quoting the accuracy of
    PAST stored predictions, which says nothing about this answer; and a source term built from a development count. Filling the gaps with constants and blending the result into one figure is what the
    contract forbids, and no replacement formula is invented here.

    What genuinely describes the evidence stays separate and is named for what it is: `evidence_score` (stars and checklist, how much of the expected evidence was retrieved) and
    `answer_availability.evidence_count`. Evidence strength is not answer confidence, a prediction probability, or recommendation conviction, and none of those exists in this response.
    Signature unchanged for its callers; the arguments are intentionally unused."""
    return {
        "evidence_quality": None, "market_confirmation": None, "historical_similarity": None, "data_freshness": None, "reasoning_confidence": None,
        "final_confidence": None, "level": "unscored", "reasons": [],
    }


# ── AEV2 confidence contract — the ONE place the approved formula's
# arithmetic lives (review, 2026-09-21: a first frontend build recomputed
# this same weighted sum in React, creating a second scoring path that
# could drift from aev2/confidence.py's own copy; correction moved the
# canonical formula here instead, a module with no aev2/ dependency, so
# both aev2/confidence.py's compute_aev2_confidence AND every V3 response
# — regardless of AEV2 mode — can share it without violating aev2/'s own
# import-isolation rule, which forbids the reverse direction (aev2
# modules importing pipeline/provider machinery), not this one).
#
# Fixed weights, exactly the closed specification aev2/confidence.py's
# own docstring documents in full: 0.35 evidence_quality + 0.25
# market_confirmation + 0.25 historical_similarity + 0.15 data_freshness.
# A missing component contributes zero and weights are never
# renormalized; all 4 missing -> unscored. See that module's docstring
# for the full missing-component rationale — this is the same rule,
# just factored out so it has exactly one implementation.
_CONFIDENCE_CONTRACT_WEIGHTS: dict[str, float] = {
    "evidence_quality": 0.35,
    "market_confirmation": 0.25,
    "historical_similarity": 0.25,
    "data_freshness": 0.15,
}


def build_confidence_contract(breakdown: dict | None) -> dict:
    """The frontend-facing confidence contract: `{status, score,
    components}`. The frontend only formats this — it never recomputes
    weighting, decides what "unscored" means, or rounds a score itself.

    `breakdown` is the same dict `compute_confidence_breakdown` above (or
    CoreAnswer.confidence_breakdown) already produces; this function does
    no evidence counting of its own, so there is nowhere for a duplicate
    source/company count to be double-scored."""
    breakdown = breakdown or {}
    components = {
        name: (float(breakdown[name]) if breakdown.get(name) is not None else None)
        for name in _CONFIDENCE_CONTRACT_WEIGHTS
    }
    available = {name: value for name, value in components.items() if value is not None}
    score = (
        round(sum(value * _CONFIDENCE_CONTRACT_WEIGHTS[name] for name, value in available.items()), 1)
        if available else None
    )
    return {
        "status": "unscored" if score is None else "scored",
        "score": score,
        "components": components,
    }
