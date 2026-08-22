"""
Opportunity Engine V2 — OpportunityV2 / OpportunityV2Development.

Deliberately a SEPARATE table/file from app/db/models/opportunity.py's V1
Opportunity — V1 is not modified, not stopped, and keeps serving its 121+
existing rows at their existing URLs unchanged. V2 runs in shadow
(source="opportunity_v2_shadow" until it's reviewed and promoted; see the
Opportunity Engine V2 plan) until it demonstrably outperforms V1 on real
production data.

frozen (formation_*) / live (current_*) split mirrors Development's own
exact convention (app/db/models/development.py) — "what we believed when
we first formed this thesis" vs. "the live rollup as more evidence
attaches."

thesis_anchor/thesis_direction (never the AI title) are the real merge
key — see app/services/opportunity_v2/identity.py. No DB-level unique
constraint on (thesis_anchor, thesis_direction) yet: V2 is shadow-only
today, so identity.py's own application-level match-before-insert check
is the real enforcement; a hard constraint can be added once V2 is
promoted out of shadow and needs to defend against genuinely concurrent
writers.

No Alembic migration — this repo's Alembic isn't wired into its deploy
path (see app/db/schema_patches.py); Base.metadata.create_all() on boot
is the real mechanism, same as every table added since Phase 2.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text,
    UniqueConstraint,
)

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OpportunityV2(Base):
    """
    id format: uuid4 string (matches Development's own convention).
    status: open (still accepting matching Developments) | closed (mirrors
    Development.sweep_close_stale()'s pattern one level up — see
    opportunity_v2/lifecycle.py).
    source: "opportunity_v2_shadow" while in shadow mode (never publicly
    served); a later "opportunity_v2" value marks a promoted, publicly-
    served row — the two are never the same value so a query can't
    accidentally leak shadow rows into a public read path.
    """
    __tablename__ = "opportunities_v2"

    id                       = Column(String(36), primary_key=True)

    # The real merge key — see opportunity_v2/identity.py. NEVER the
    # AI-generated title (owner correction, 2026-08-22: a single
    # Development, e.g. an RBI rate cut, can legitimately support several
    # distinct theses -- Banking margin AND Real Estate demand -- so
    # "already linked to an Opportunity" cannot be the merge signal).
    thesis_anchor             = Column(String(160), nullable=False, index=True)
    thesis_direction          = Column(String(16), nullable=False)  # positive | negative | neutral | mixed

    status                    = Column(String(16), nullable=False, default="open", index=True)
    source                    = Column(String(32), nullable=False, default="opportunity_v2_shadow")

    # Three independent status axes (owner instruction, 2026-08-22) —
    # deliberately separate from `status` (open/closed lifecycle) above.
    # The whole point: AI capacity failures must never block the
    # deterministic candidate from being observable. A candidate can be
    # candidate_status="formed" (the deterministic pipeline — gate,
    # coherence, identity, scoring — completed) with
    # narrative_status="failed_capacity" (every provider failed) at the
    # exact same time this app's real, currently-degraded free-tier AI
    # capacity is a known, tracked problem (see ai_service.py's
    # 2026-08-22 fixes) — this triad is what makes that distinction
    # queryable/reportable instead of invisible.
    candidate_status           = Column(String(16), nullable=False, default="formed")  # formed (only real value today — see identity.py: nothing is persisted before the deterministic pipeline completes)
    narrative_status            = Column(String(16), nullable=False, default="pending")  # pending | generated | failed_capacity
    public_status                 = Column(String(16), nullable=False, default="shadow")  # shadow | public — promotion out of shadow is a separate, later decision

    # Frozen at formation. Never rewritten after insert.
    formation_title            = Column(String(256), nullable=True)  # null if AI generation failed closed — see generation.py
    formation_score            = Column(Float, nullable=True)
    formation_at                = Column(DateTime(timezone=True), nullable=False, default=_now)

    # Live rollup — updated as new coherent Developments merge in.
    current_title               = Column(String(256), nullable=True)
    current_summary              = Column(Text, nullable=True)
    current_score                 = Column(Float, nullable=True)

    # sha256 of the exact evidence/thesis payload the current narrative was
    # generated from (opportunity_v2/orchestration.py::_narrative_input_hash)
    # — owner instruction, 2026-08-22: a worker running repeatedly in
    # production must not re-spend a paid LLM call on an opportunity whose
    # evidence hasn't materially changed since it was last narrated. Set
    # only on a SUCCESSFUL generation (never on failed_capacity — a failed
    # attempt must keep retrying next pass even with unchanged evidence,
    # since capacity may have recovered).
    narrative_input_hash          = Column(String(64), nullable=True)
    # Real union of every linked Development's own graph-confirmed
    # sectors/companies (opportunity_v2/scoring.py) — never a blind union
    # of each member's own self-reported tags (that was V1's bug).
    sectors                        = Column(JSON, nullable=False, default=list)
    companies                       = Column(JSON, nullable=False, default=list)

    created_at                       = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at                        = Column(DateTime(timezone=True), nullable=False, default=_now)  # bumped on every merge

    __table_args__ = (
        Index("ix_ov2_thesis", "thesis_anchor", "thesis_direction"),
        Index("ix_ov2_status_updated", "status", "updated_at"),
    )


class OpportunityV2Development(Base):
    """
    Many-to-many by design (owner correction, 2026-08-22): one Development
    can support multiple distinct Opportunities (an RBI rate cut supports
    a Banking-margin thesis AND a Real-Estate-demand thesis, genuinely
    different theses, not a duplicate). Mirrors DevelopmentEvidence's own
    join-table shape exactly, one level up.
    """
    __tablename__ = "opportunity_v2_developments"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id     = Column(String(36), ForeignKey("opportunities_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    development_id       = Column(String(36), ForeignKey("developments.id", ondelete="CASCADE"), nullable=False, index=True)
    added_at               = Column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        Index("ix_ov2dev_opportunity", "opportunity_id"),
        Index("ix_ov2dev_development", "development_id"),
        UniqueConstraint("opportunity_id", "development_id", name="uq_ov2dev_pair"),
    )
