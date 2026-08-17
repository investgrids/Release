"""
Development / DevelopmentEvidence — Phase 6A, Intelligence Memory.

Gives app/services/evidence_clustering/'s EvidenceCluster a persistent
identity. Today that clustering runs fresh per-request at 3 call sites
(Opportunity Radar, AI Search V2/V3, Weekend Intelligence) and is
discarded — the same real-world happening re-evidenced tomorrow is
invisible to yesterday's clustering. A Development is the durable record
of "Market Ripple has seen this specific real-world happening before",
with evidence accumulating onto it over time via
app/services/development_memory/identity.py's matching lifecycle.

formation_* fields are frozen at insert and never rewritten — "what we
believed when we first saw this". current_* fields are the live rollup,
updated as new evidence merges in. This mirrors
CompanyIntelligenceObservation's append/freeze philosophy
(sector_at_observation is that table's only precedent for "freeze,
don't re-derive").

impact is stored as a tier string, not a float: every evidence-clustering
normalizer's `impact_strength` field is sparse and inconsistent
(Critical/High/Medium/Low for events, "high"/None for announcements,
always None for policy/news/company_signal/opportunity) — there is no
reliable numeric impact anywhere in EvidenceItem. `confidence` (0.0-1.0,
also frequently None but the actually-consistent numeric axis) is what
carries the numeric weight here.

No Alembic migration — this repo's Alembic isn't wired into its deploy
path (see app/db/schema_patches.py's docstring); Base.metadata.create_all()
on boot is the real mechanism, same as every other table added since
Phase 2.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String,
    UniqueConstraint,
)

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Development(Base):
    """
    id format: uuid4 string.
    status: open (still accepting matching evidence) | closed (72h of no
    qualifying evidence — see identity.py's CLOSE_AFTER). A closed
    Development is never reopened; new matching evidence starts a fresh
    Development instead (6B links related Developments later).
    """
    __tablename__ = "developments"

    id                      = Column(String(36), primary_key=True)
    canonical_title         = Column(String(256), nullable=False)  # frozen — the seed evidence item's title
    status                  = Column(String(16), nullable=False, default="open", index=True)

    primary_company         = Column(String(32), nullable=True, index=True)
    companies                = Column(JSON, nullable=False, default=list)
    sectors                  = Column(JSON, nullable=False, default=list)
    themes                    = Column(JSON, nullable=False, default=list)  # Phase 6B — feeds development->theme graph edges
    category                  = Column(String(32), nullable=True)  # from seed item's category

    first_observed_at        = Column(DateTime(timezone=True), nullable=False, index=True)
    last_observed_at         = Column(DateTime(timezone=True), nullable=False, index=True)

    # Frozen at formation. Never rewritten after insert.
    formation_direction       = Column(String(16), nullable=True)   # positive | negative | neutral | mixed
    formation_impact_tier     = Column(String(16), nullable=True)   # verbatim seed item's impact_strength
    formation_confidence      = Column(Float, nullable=True)

    # Live rollup — updated as evidence merges in.
    current_direction         = Column(String(16), nullable=True)
    current_impact_tier       = Column(String(16), nullable=True)
    current_confidence        = Column(Float, nullable=True)

    evidence_count             = Column(Integer, nullable=False, default=0)  # denormalized, == count(DevelopmentEvidence)
    # Left for Phase 6B (graph linkage) — not populated by this slice.
    ig_node_id                  = Column(String(128), ForeignKey("ig_nodes.id", ondelete="SET NULL"), nullable=True, index=True)

    schema_version                = Column(String(32), nullable=False)
    created_at                     = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at                     = Column(DateTime(timezone=True), nullable=False, default=_now)  # bumped on every merge

    __table_args__ = (
        Index("ix_dev_company_observed", "primary_company", "last_observed_at"),
        Index("ix_dev_status_observed", "status", "last_observed_at"),
    )


class DevelopmentEvidence(Base):
    """
    evidence_key disambiguates source rows that share the same
    EvidenceItem.source_id but are NOT the same evidence — this only
    matters for source_type="company_signal": AICompanySignal.source_id
    encodes the originating article/opportunity, not the signal row
    itself, so 3 different companies extracted from one article share one
    source_id. evidence_key is source_id verbatim for every other source
    type (there it IS the real source row's own primary key, already
    unique) and f"{source_id}:{company}" for company_signal — see
    identity.py's compute_evidence_key().

    UniqueConstraint is GLOBAL (not scoped to development_id): a single
    piece of evidence belongs to exactly one Development, ever. This is
    stronger than just preventing duplicate re-attachment on job reruns
    (which it also does) — it's what makes "one piece of evidence, one
    home" an actual database-enforced invariant rather than a convention
    the matching logic has to get right on every call.
    """
    __tablename__ = "development_evidence"

    id                       = Column(String(36), primary_key=True)
    development_id           = Column(String(36), ForeignKey("developments.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type               = Column(String(24), nullable=False)   # event | policy | announcement | news | company_signal | opportunity
    source_id                 = Column(String(128), nullable=False)  # verbatim EvidenceItem.source_id
    evidence_key               = Column(String(160), nullable=False)
    observed_at                = Column(DateTime(timezone=True), nullable=False)
    title                      = Column(String(512), nullable=True)  # snapshot — avoids re-joining to source for display/audit
    direction                   = Column(String(16), nullable=True)  # snapshot of the source EvidenceItem's own direction — feeds current_direction's rollup and future evidence-reconciliation (6E)
    confidence                   = Column(Float, nullable=True)      # snapshot of the source EvidenceItem's own confidence
    match_tier                  = Column(String(16), nullable=False)  # seed | tier1 | tier2a | tier2b
    membership_confidence        = Column(Float, nullable=False, default=1.0)  # 1.0 for seed/tier1, heuristic strength for tier2
    added_at                     = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_devev_development", "development_id"),
        UniqueConstraint("source_type", "evidence_key", name="uq_devev_source"),
    )
