"""
ArticleV2CanaryWithhold — P7 Candidate Ownership Arbitration audit trail
(owner design, 2026-09-13).

Records the one moment V1 deliberately stood aside for a High-tier
candidate so V2 could attempt ownership, based on strong post-collision-
gate shadow evidence from the immediately preceding AIPE cycle. A
withhold row's mere EXISTENCE for a given triage_event_id permanently
disqualifies any future withhold for that same event -- "at most once,
ever" is a real database invariant, not an application-level "check
then insert" convention, hence the unique index. If a duplicate insert
is ever attempted (should never happen in the current single-process
synchronous execution model, but the invariant is worth enforcing at
the DB level regardless), the caller fails closed: V1 retains
ownership rather than creating a second arbitration record for the
same event.

`outcome` is deliberately never "converted"/"published_v2" in this
patch -- V2 has no real public-write path yet (see
app/services/article_v2/shadow_orchestrator.py's own structural
persistence boundary; app/services/article_v2/publisher.py's
publish_v2_article() is the only real write path, and nothing in this
patch calls it). "shadow_qualified" means V2's shadow re-evaluation
this cycle again reached would_publish=True -- proof the mechanism
worked, not proof anything was actually published. A later, separate,
explicitly-authorized real-write patch owns "published_v2"/"converted".
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, JSON, String

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ArticleV2CanaryWithhold(Base):
    __tablename__ = "article_v2_canary_withholds"

    id = Column(String(64), primary_key=True)

    triage_event_id = Column(String, nullable=False)
    prior_shadow_execution_id = Column(String, nullable=False)

    # Exactly which predicate values were checked and passed -- e.g.
    # {"evidence_count": 5, "c8_tier": "ARTICLE", "c5_publication_action":
    # "CREATE_NEW", "collision_gate_outcome": "no_collision",
    # "prior_shadow_age_seconds": 312.4} -- an auditor should never need
    # to re-derive what qualified this withhold from other tables.
    reason_predicates = Column(JSON, nullable=False, default=dict)

    withheld_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    # not_evaluated (default, never actually stored -- see below) |
    # shadow_qualified | shadow_not_qualified | shadow_failed |
    # published_v2 (reserved for the later real-write patch, never set here)
    outcome = Column(String(24), nullable=True)

    __table_args__ = (
        # The real invariant: at most one withhold, ever, per event.
        Index("ux_article_v2_canary_withholds_triage_event_id", "triage_event_id", unique=True),
    )
