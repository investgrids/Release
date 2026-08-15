"""
Production confidence — brief §15-§17. The most important part of Phase
1B, so this module states its formula in full, not just in a docstring:
every number that goes into `production_confidence` is also returned in
`confidence_components` at both its raw (0-1) and weighted-contribution
value, so the final score is always reconcilable by summing the listed
contributions — never a black box.

Critically: NO component here reads any EvidenceItem's own `.confidence`
value. Per Phase 1A's evidence.py classification, roughly half of this
codebase's "confidence" numbers are LLM self-ratings or heuristics
passed straight through — an LLM saying 95 must never become
production_confidence=95 (brief §16's explicit example). Every input
below is instead a structural COUNT or STRUCTURAL AGREEMENT signal
(how many independent clusters, how many distinct source types, how
much internal contradiction, whether a real close baseline exists) —
things that are true regardless of whether any individual evidence
item's self-reported confidence can be trusted.

    production_confidence = 100 * (
        0.30 * evidence_strength
      + 0.20 * source_diversity
      + 0.25 * agreement
      + 0.10 * historical_support
      + 0.15 * baseline_quality
    )

Weights sum to exactly 1.0, so the score is bounded [0, 100] by
construction and each component's weighted contribution is directly
additive — "why is this 78" is answered by reading the five
contributions off confidence_components and summing them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.weekend_intelligence.dedup import EvidenceCluster
from app.services.weekend_intelligence.evidence import DETERMINISTIC

_ALL_SOURCE_TYPES = {"event", "policy", "announcement", "news", "company_signal", "opportunity"}

_WEIGHT_EVIDENCE_STRENGTH = 0.30
_WEIGHT_SOURCE_DIVERSITY = 0.20
_WEIGHT_AGREEMENT = 0.25
_WEIGHT_HISTORICAL_SUPPORT = 0.10
_WEIGHT_BASELINE_QUALITY = 0.15

# A cluster count at/above this is treated as "as strong as it gets" for
# the evidence_strength component — an explicit, named saturation point
# rather than an unbounded linear scale (brief §17: "do not create
# meaningless precision").
_CLUSTER_SATURATION_COUNT = 8

# Confidence contribution assigned to "no historical analogue found" —
# neutral-low rather than zero: absence of a match isn't itself negative
# evidence, it just isn't a positive signal either (brief §13:
# "historical analogues are supporting evidence, they must not dominate
# current evidence" — this also means their ABSENCE must not dominate).
_NO_HISTORICAL_ANALOGUE_SCORE = 0.2


@dataclass
class ConfidenceBreakdown:
    evidence_strength: float
    source_diversity: float
    agreement: float
    historical_support: float
    baseline_quality: float

    def weighted_contributions(self) -> dict[str, float]:
        return {
            "evidence_strength": round(self.evidence_strength * _WEIGHT_EVIDENCE_STRENGTH, 4),
            "source_diversity": round(self.source_diversity * _WEIGHT_SOURCE_DIVERSITY, 4),
            "agreement": round(self.agreement * _WEIGHT_AGREEMENT, 4),
            "historical_support": round(self.historical_support * _WEIGHT_HISTORICAL_SUPPORT, 4),
            "baseline_quality": round(self.baseline_quality * _WEIGHT_BASELINE_QUALITY, 4),
        }

    def as_dict(self) -> dict:
        return {
            "raw": {
                "evidence_strength": round(self.evidence_strength, 4),
                "source_diversity": round(self.source_diversity, 4),
                "agreement": round(self.agreement, 4),
                "historical_support": round(self.historical_support, 4),
                "baseline_quality": round(self.baseline_quality, 4),
            },
            "weights": {
                "evidence_strength": _WEIGHT_EVIDENCE_STRENGTH,
                "source_diversity": _WEIGHT_SOURCE_DIVERSITY,
                "agreement": _WEIGHT_AGREEMENT,
                "historical_support": _WEIGHT_HISTORICAL_SUPPORT,
                "baseline_quality": _WEIGHT_BASELINE_QUALITY,
            },
            "weighted_contributions": self.weighted_contributions(),
        }

    def total(self) -> float:
        return round(sum(self.weighted_contributions().values()) * 100, 2)


@dataclass
class EvidenceDiversity:
    unique_development_count: int
    unique_source_type_count: int
    unique_company_count: int
    unique_sector_count: int
    high_quality_evidence_count: int  # clusters containing >=1 DETERMINISTIC-scored member


def compute_diversity(clusters: list[EvidenceCluster]) -> EvidenceDiversity:
    source_types: set[str] = set()
    companies: set[str] = set()
    sectors: set[str] = set()
    high_quality = 0
    for c in clusters:
        source_types |= c.source_types
        companies |= c.companies
        sectors |= c.sectors
        if any(m.score_kind == DETERMINISTIC for m in c.members):
            high_quality += 1
    return EvidenceDiversity(
        unique_development_count=len(clusters),
        unique_source_type_count=len(source_types),
        unique_company_count=len(companies),
        unique_sector_count=len(sectors),
        high_quality_evidence_count=high_quality,
    )


def _agreement_score(clusters: list[EvidenceCluster]) -> float:
    """
    Two distinct kinds of disagreement, both penalized:
      - WITHIN a cluster (dedup.py already collapsed contradictory items
        into net_direction == "mixed")
      - ACROSS clusters (e.g. 2 independently-clustered developments say
        positive, 2 say negative — each individually clean, but the
        overall evidence set still disagrees with itself)
    `dominance` measures how lopsided the positive/negative split is
    (1.0 = unanimous, 0.5 = perfectly split), rescaled to a 0-1 agreement
    score; any individually-mixed clusters subtract further.
    """
    directional = [c for c in clusters if c.net_direction != "neutral"]
    if not directional:
        return 0.5  # no directional claims at all — neither agreement nor contradiction
    total = len(directional)
    positive = sum(1 for c in directional if c.net_direction in ("positive", "bullish"))
    negative = sum(1 for c in directional if c.net_direction in ("negative", "bearish"))
    mixed = sum(1 for c in directional if c.net_direction == "mixed")

    dominance = max(positive, negative) / total  # 0.5 (even split) .. 1.0 (unanimous)
    agreement = (dominance - 0.5) / 0.5           # rescaled to 0..1
    agreement -= 0.5 * (mixed / total)
    return round(max(0.0, min(1.0, agreement)), 4)


def compute_production_confidence(
    clusters: list[EvidenceCluster],
    *,
    baseline_available: bool,
    historical_analogues: list[dict],
) -> tuple[float, ConfidenceBreakdown]:
    diversity = compute_diversity(clusters)

    evidence_density = min(1.0, diversity.unique_development_count / _CLUSTER_SATURATION_COUNT)
    # Deliberately a saturating COUNT (same scale/shape as evidence_density),
    # not a ratio of high-quality-to-total clusters. A ratio would reward
    # FEWER total clusters whenever the deterministic ones are held fixed
    # (e.g. 1 deterministic cluster alone scores "100% deterministic" and
    # beats 1 deterministic + 2 more independent non-deterministic
    # clusters, which is backwards — more independent evidence, even
    # heuristic/LLM-sourced, should never REDUCE the score). A saturating
    # count fixes this: adding more clusters never lowers evidence_strength.
    deterministic_density = min(1.0, diversity.high_quality_evidence_count / _CLUSTER_SATURATION_COUNT)
    evidence_strength = round(0.5 * evidence_density + 0.5 * deterministic_density, 4)

    source_diversity = round(diversity.unique_source_type_count / len(_ALL_SOURCE_TYPES), 4)

    agreement = _agreement_score(clusters)

    if historical_analogues:
        avg_similarity = sum(a.get("similarity", 0.0) for a in historical_analogues) / len(historical_analogues)
        count_factor = min(1.0, len(historical_analogues) / 3)
        historical_support = round((avg_similarity / 100.0) * count_factor, 4)
    else:
        historical_support = _NO_HISTORICAL_ANALOGUE_SCORE

    baseline_quality = 1.0 if baseline_available else 0.0

    breakdown = ConfidenceBreakdown(
        evidence_strength=evidence_strength,
        source_diversity=source_diversity,
        agreement=agreement,
        historical_support=historical_support,
        baseline_quality=baseline_quality,
    )
    return breakdown.total(), breakdown
