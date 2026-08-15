"""
Sector signal synthesis — brief §9.

Inputs actually available from Phase 1A's EvidenceCluster (not a new
proprietary formula): each cluster's own `.sectors` (unioned from
Event.sectors, Opportunity.sectors, and AICompanySignal.sector across the
cluster's members — see evidence.py's normalizers) and `.net_direction`
(brief §12: contradictory evidence inside a cluster already collapses to
"mixed" rather than silently picking a side). GovernmentPolicy evidence
carries no sector field in this codebase's schema (evidence.py's
normalize_policy leaves EvidenceItem.sectors empty for policy rows — an
honest reflection of what's actually stored, not a gap invented here) and
so does not contribute to sector aggregation; it can still show up in
`key_reasons` via a cluster that also touches a sector through its other
members.

The Friday/close-session's own sector_ranks (MarketSnapshot, Phase 1A) is
attached as `baseline_pct` context only — the prior session's real ETF
move, never blended into this weekend's direction/confidence numbers,
since it describes what already happened before the evidence window even
starts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.weekend_intelligence.dedup import EvidenceCluster

# Below this many contributing clusters, a sector's confidence is capped
# — a single cluster mentioning a sector is real evidence, but not
# enough on its own to claim more than modest confidence. Reused by
# confidence.py's per-sector rollup too (not duplicated there).
_SINGLE_CLUSTER_CONFIDENCE_CAP = 0.55


@dataclass
class SectorSignal:
    sector: str
    direction: str  # positive | negative | mixed | neutral
    strength: str   # low | medium | high — cluster-count bucket, not a fabricated precision score
    confidence: float
    evidence_count: int
    positive_evidence: int
    negative_evidence: int
    key_reasons: list[str] = field(default_factory=list)
    evidence_refs: list[dict] = field(default_factory=list)
    baseline_pct: float | None = None  # last-session close context, see module docstring


def _strength_bucket(evidence_count: int) -> str:
    if evidence_count >= 4:
        return "high"
    if evidence_count >= 2:
        return "medium"
    return "low"


def synthesize_sectors(
    clusters: list[EvidenceCluster], *, baseline_sector_ranks: list[dict] | None = None,
) -> list[SectorSignal]:
    baseline_by_key = {
        row["name"].strip().lower(): row.get("pct") for row in (baseline_sector_ranks or []) if row.get("name")
    }

    # Group by a case-insensitive key so e.g. "Finance" and "finance"
    # (both seen in real evidence during Phase 1B's local-DB verification
    # — different upstream sources capitalize sector names differently)
    # merge into one sector instead of appearing as two separate rows.
    # The FIRST-seen casing is kept as the display name — deliberately
    # not `.title()`-normalized, since that would corrupt real acronym
    # sector names like "IT" into "It".
    by_sector: dict[str, list[EvidenceCluster]] = {}
    display_name: dict[str, str] = {}
    for cluster in clusters:
        for sector in cluster.sectors:
            key = sector.strip().lower()
            display_name.setdefault(key, sector.strip())
            by_sector.setdefault(key, []).append(cluster)

    signals: list[SectorSignal] = []
    for key, sector_clusters in by_sector.items():
        sector = display_name[key]
        positive = sum(1 for c in sector_clusters if c.net_direction in ("positive", "bullish"))
        negative = sum(1 for c in sector_clusters if c.net_direction in ("negative", "bearish"))
        if positive and negative:
            direction = "mixed"
        elif positive:
            direction = "positive"
        elif negative:
            direction = "negative"
        else:
            direction = "neutral"

        evidence_count = len(sector_clusters)
        # Confidence here is a simple, transparent function of evidence
        # volume and agreement — NOT a copy of any single cluster's own
        # confidence number (those come from mixed score_kinds and aren't
        # comparable across clusters, per the architecture doc §8/§21).
        # confidence.py's production_confidence is the real, explainable
        # aggregate; this per-sector value is a lightweight, bounded
        # signal for ranking/display, deliberately capped low for
        # single-cluster sectors.
        base_confidence = min(0.9, 0.2 + 0.15 * evidence_count)
        if direction == "mixed":
            base_confidence *= 0.6  # contradiction — see brief §12
        if evidence_count <= 1:
            base_confidence = min(base_confidence, _SINGLE_CLUSTER_CONFIDENCE_CAP)

        key_reasons = [c.representative.title for c in sorted(
            sector_clusters, key=lambda c: len(c.members), reverse=True
        )[:3]]
        evidence_refs = [ref for c in sector_clusters for ref in c.evidence_refs()]

        signals.append(SectorSignal(
            sector=sector,
            direction=direction,
            strength=_strength_bucket(evidence_count),
            confidence=round(base_confidence, 3),
            evidence_count=evidence_count,
            positive_evidence=positive,
            negative_evidence=negative,
            key_reasons=key_reasons,
            evidence_refs=evidence_refs,
            baseline_pct=baseline_by_key.get(key),
        ))

    signals.sort(key=lambda s: (s.evidence_count, s.confidence), reverse=True)
    return signals
