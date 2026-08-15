"""
Deterministic material-change detector.

Design doc §7/§19/§20/§21 — this is the cheap gate a future scheduled
checkpoint (Phase 1B, not built here) would run before doing any
expensive historical-match/LLM-synthesis work: "is there enough new
evidence since the prior checkpoint to justify a new version." No LLM
call, no prediction, no synthesis — pure counting and structural
classification over already-normalized EvidenceItems.

Every threshold below is either reused from an existing, already-shipped
definition (event priority tiers via engine.py's compute_priority;
CompanyAnnouncement.is_high_impact; opportunity_intelligence's own
"Strong Conviction" confidence cutoff) or, where no existing threshold
applies, a single small, named, documented constant — never an implicit
magic number scattered through the logic.

Evidence-quality awareness (§21): "an LLM self-rated confidence of 95
must not automatically outrank a deterministic high-impact event." None
of the rules below compare raw `confidence` values across EvidenceItems
of different score_kind for exactly this reason — they key off
structural signals (priority tier, is_high_impact, a reused verdict
threshold) instead of treating every confidence number as equally
trustworthy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.weekend_intelligence.evidence import EvidenceItem
from app.services.weekend_intelligence.dedup import EvidenceCluster

# New-evidence-count threshold when no single item alone is material —
# e.g. a quiet weekend with a dozen routine announcements might still be
# worth a checkpoint even without any one Critical/High item. A single
# named constant, not a magic number inline in the logic below.
DEFAULT_EVIDENCE_COUNT_THRESHOLD = 5

# Proxy for opportunity_intelligence.compute_investment_verdict's own
# "Strong Conviction" cutoff (score>=85 & confidence>=75%, Phase 1
# architecture doc §9). Opportunity.confidence = min(0.95, score/110) is
# arithmetically tied to score, so confidence>=0.75 corresponds to
# roughly score>=82.5 — close enough to the real 85 cutoff to reuse as
# the single practical proxy without threading a second raw field through
# EvidenceItem. Reused, not a new threshold invented from scratch.
MEANINGFUL_OPPORTUNITY_CONFIDENCE = 0.75


@dataclass
class MaterialChangeResult:
    is_material: bool
    new_evidence_count: int
    critical_event_count: int = 0
    high_event_count: int = 0
    new_policy_count: int = 0
    new_high_impact_announcement_count: int = 0
    new_meaningful_opportunity_count: int = 0
    new_company_count: int = 0
    new_sector_count: int = 0
    reasons: list[str] = field(default_factory=list)


def detect_material_change(
    evidence: list[EvidenceItem],
    *,
    previously_seen_companies: set[str] | None = None,
    previously_seen_sectors: set[str] | None = None,
    evidence_count_threshold: int = DEFAULT_EVIDENCE_COUNT_THRESHOLD,
) -> MaterialChangeResult:
    """
    Pure function over an already-collected evidence window (see
    evidence_window.collect_evidence_since) — no DB/network access here,
    so this is cheap to run on every checkpoint tick regardless of
    whether the checkpoint ultimately proceeds to real synthesis.

    `previously_seen_companies`/`previously_seen_sectors` are optional —
    when supplied (from the prior WeekendIntelligenceSnapshot's
    top_company_refs/top_sector_refs, once Phase 1B exists), new_company/
    new_sector counts only count genuinely new entrants; when omitted,
    every company/sector mentioned in this window counts (a reasonable
    default for the very first checkpoint of a weekend, which by
    definition has no prior top-N to compare against).
    """
    previously_seen_companies = previously_seen_companies or set()
    previously_seen_sectors = previously_seen_sectors or set()

    # Dedup by (source_type, source_id) — the same underlying evidence row
    # must not be counted twice toward any threshold even if a caller
    # accidentally passes it in more than once (e.g. two overlapping
    # window queries). Order-preserving so `reasons`/counts stay stable.
    seen_keys: set[tuple[str, str]] = set()
    deduped: list[EvidenceItem] = []
    for item in evidence:
        key = (item.source_type, item.source_id)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(item)
    evidence = deduped

    critical = sum(1 for e in evidence if e.source_type == "event" and e.impact_strength == "Critical")
    high = sum(1 for e in evidence if e.source_type == "event" and e.impact_strength == "High")
    new_policy = sum(1 for e in evidence if e.source_type == "policy")
    high_impact_announcements = sum(
        1 for e in evidence if e.source_type == "announcement" and e.impact_strength == "high"
    )
    meaningful_opportunities = sum(
        1 for e in evidence
        if e.source_type == "opportunity" and (e.confidence or 0) >= MEANINGFUL_OPPORTUNITY_CONFIDENCE
    )

    seen_companies = {c for item in evidence for c in item.companies}
    seen_sectors = {s for item in evidence for s in item.sectors}
    new_companies = seen_companies - previously_seen_companies
    new_sectors = seen_sectors - previously_seen_sectors

    reasons: list[str] = []
    is_material = False

    if critical >= 1:
        is_material = True
        reasons.append(f"{critical} new Critical-priority event(s)")
    if high >= 1:
        is_material = True
        reasons.append(f"{high} new High-priority event(s)")
    if new_policy >= 1:
        is_material = True
        reasons.append(f"{new_policy} new policy item(s)")
    if high_impact_announcements >= 1:
        is_material = True
        reasons.append(f"{high_impact_announcements} new high-impact company announcement(s)")
    if meaningful_opportunities >= 1:
        is_material = True
        reasons.append(f"{meaningful_opportunities} new opportunity(ies) above the meaningful-confidence threshold")
    if len(evidence) >= evidence_count_threshold:
        is_material = True
        reasons.append(f"{len(evidence)} total new evidence items (>= threshold {evidence_count_threshold})")

    return MaterialChangeResult(
        is_material=is_material,
        new_evidence_count=len(evidence),
        critical_event_count=critical,
        high_event_count=high,
        new_policy_count=new_policy,
        new_high_impact_announcement_count=high_impact_announcements,
        new_meaningful_opportunity_count=meaningful_opportunities,
        new_company_count=len(new_companies),
        new_sector_count=len(new_sectors),
        reasons=reasons,
    )


def is_meaningful_development(cluster: EvidenceCluster) -> bool:
    """Cluster-level version of the same per-item criteria used above
    (Critical/High event, any policy item, high-impact announcement, a
    meaningful-confidence opportunity) — reused, not a second threshold
    set invented for this purpose. Evaluated per CLUSTER rather than per
    raw evidence row deliberately: "new since market close" should count
    real distinct developments, not how many separate sources happened
    to cover the same one (dedup.py's whole job) — 5 outlets reporting
    one RBI decision is 1 meaningful development, not 5."""
    for m in cluster.members:
        if m.source_type == "event" and m.impact_strength in ("Critical", "High"):
            return True
        if m.source_type == "policy":
            return True
        if m.source_type == "announcement" and m.impact_strength == "high":
            return True
        if m.source_type == "opportunity" and (m.confidence or 0) >= MEANINGFUL_OPPORTUNITY_CONFIDENCE:
            return True
    return False


def select_new_since_close(clusters: list[EvidenceCluster]) -> list[EvidenceCluster]:
    """"New since market close" (brief refinement, distinct from
    changes.py's "changed since prior CHECKPOINT VERSION" concept — see
    changes.py's module docstring): the subset of this checkpoint's
    evidence clusters that are independently meaningful on their own
    terms, regardless of whether any prior WeekendIntelligenceSnapshot
    version exists for this target_trading_date. On a first-ever
    checkpoint this is still a small, honest number (unlike
    changes_since_prior, which trivially reports "everything is new"
    when there is no prior version to diff against)."""
    return [c for c in clusters if is_meaningful_development(c)]
