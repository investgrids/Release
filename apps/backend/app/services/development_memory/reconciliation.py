"""
Development Evidence Reconciliation — Phase 6E.1.

Moves a Development's interpretation beyond the binary "mixed" flag
current_direction can carry (from identity.py's _net_direction majority
vote) into a genuine reconciliation state: HOW it conflicts, not just
whether it does, plus which specific evidence supports vs. conflicts —
not just counts.

Reuses app.services.intelligence_research.evidence._conflict_bucket()
completely unmodified rather than inventing a second reconciliation
vocabulary — it already classifies a (positive_count, negative_count)
pair into all_positive | all_negative | mostly_positive | mostly_negative
| balanced_conflict | no_signal, and is already proven in production for
CompanyIntelligenceObservation/the Phase 2E pilot. Development already
has everything this needs with zero schema change: DevelopmentEvidence.
direction (added in 6A) gives real per-evidence-row positive/negative/
neutral values, no re-derivation needed.

Deliberately does NOT include horizon-specific interpretation (short-
term vs. medium-term reconciliation) — that's Phase 6E.2, a genuinely
new heuristic (no existing codebase precedent to reuse, unlike this
module) requiring its own explicit design/validation pass. Every
returned evidence item DOES carry its real observed_at timestamp,
though, so 6E.2 has the raw temporal data it needs without this module
committing to any horizon assumption now.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.development import Development, DevelopmentEvidence
from app.services.intelligence_research.evidence import _conflict_bucket


@dataclass
class ReconciledEvidenceItem:
    source_type: str
    source_id: str
    title: str | None
    direction: str | None
    observed_at: str | None  # ISO — real timestamp, preserved for 6E.2's future use


@dataclass
class DevelopmentReconciliation:
    development_id: str
    positive_count: int
    negative_count: int
    neutral_count: int
    conflict_bucket: str  # all_positive | all_negative | mostly_positive | mostly_negative | balanced_conflict | no_signal
    positive_evidence: list[ReconciledEvidenceItem] = field(default_factory=list)
    negative_evidence: list[ReconciledEvidenceItem] = field(default_factory=list)
    # Only populated when the Development has a clear positive/negative
    # current_direction — there is no "side" to support/conflict with
    # when direction is neutral or mixed (see reconcile_development()).
    supporting_evidence: list[ReconciledEvidenceItem] | None = None
    conflicting_evidence: list[ReconciledEvidenceItem] | None = None


def _to_item(row: DevelopmentEvidence) -> ReconciledEvidenceItem:
    return ReconciledEvidenceItem(
        source_type=row.source_type,
        source_id=row.source_id,
        title=row.title,
        direction=row.direction,
        observed_at=row.observed_at.isoformat() if row.observed_at else None,
    )


async def reconcile_development(db: AsyncSession, dev: Development) -> DevelopmentReconciliation:
    rows = (await db.execute(
        select(DevelopmentEvidence).where(DevelopmentEvidence.development_id == dev.id)
    )).scalars().all()

    positive = [_to_item(r) for r in rows if r.direction == "positive"]
    negative = [_to_item(r) for r in rows if r.direction == "negative"]
    neutral_count = sum(1 for r in rows if r.direction not in ("positive", "negative"))

    bucket = _conflict_bucket(len(positive), len(negative))

    supporting: list[ReconciledEvidenceItem] | None = None
    conflicting: list[ReconciledEvidenceItem] | None = None
    if dev.current_direction == "positive":
        supporting, conflicting = positive, negative
    elif dev.current_direction == "negative":
        supporting, conflicting = negative, positive
    # neutral/mixed: no clear side — supporting/conflicting stay None,
    # callers use positive_evidence/negative_evidence directly instead.

    return DevelopmentReconciliation(
        development_id=dev.id,
        positive_count=len(positive),
        negative_count=len(negative),
        neutral_count=neutral_count,
        conflict_bucket=bucket,
        positive_evidence=positive,
        negative_evidence=negative,
        supporting_evidence=supporting,
        conflicting_evidence=conflicting,
    )
