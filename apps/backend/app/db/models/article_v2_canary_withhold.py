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

"shadow_qualified" means V2's shadow re-evaluation this cycle again
reached would_publish=True -- proof the mechanism worked, not proof
anything was actually published. "published_v2" (P7 Real-Write,
2026-09-14) means canary_publisher.py's own fresh rerun ALSO reached
NO_COLLISION/P4 and a real IntelligenceArticle was committed --
`published_article_id` then points at it. Both
article_v2_canary_ownership_enabled and the separate
article_v2_canary_public_write_enabled default False; "published_v2"
can only ever be written once both are True, a separate, later,
explicitly-authorized activation checkpoint, not a side effect of this
patch shipping.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, JSON, String, text

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
    # published_v2
    outcome = Column(String(24), nullable=True)

    # P7 Real-Write (2026-09-14): the durable pointer from this audit row
    # to the exact IntelligenceArticle it authorized, set only once
    # outcome == "published_v2". Never set for any other outcome value.
    # Reconciliation after a post-commit crash (see canary_publisher.py)
    # backfills this from the real, already-committed article rather
    # than inferring it from shadow-execution lineage.
    published_article_id = Column(String, nullable=True)

    __table_args__ = (
        # The real invariant: at most one withhold, ever, per event.
        Index("ux_article_v2_canary_withholds_triage_event_id", "triage_event_id", unique=True),
        # P7 Real-Write (2026-09-14): the real lifetime-budget invariant
        # -- "prefer DB-level protection if practical, don't overengineer
        # distributed locking" (same precedent as
        # weekend_intelligence.py's ux_weekend_snapshot_current_per_target).
        # A partial unique index on a single fixed value means AT MOST ONE
        # row can ever hold outcome="published_v2", enforced atomically by
        # the DB at commit time -- closes the theoretical two-worker
        # check-then-write race a plain "does a published_v2 row already
        # exist?" query cannot close on its own, without a new table or a
        # bespoke locking mechanism.
        Index(
            "ux_article_v2_canary_withholds_one_published_v2",
            "outcome",
            unique=True,
            sqlite_where=text("outcome = 'published_v2'"),
            postgresql_where=text("outcome = 'published_v2'"),
        ),
    )
