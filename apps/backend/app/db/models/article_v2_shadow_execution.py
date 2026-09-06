"""
ArticleV2ShadowExecution — durable P6 telemetry (Article V2 Phase P5,
owner design, 2026-09-06). One row per real production candidate the
V2 pipeline was executed against in `shadow_v2`/`canary_v2`/`v2` mode,
capturing every stage's real outcome so P6 can analyze a whole cohort
without re-running anything or relying on manually-inspected logs.

Deliberately NOT an `IntelligenceArticle` row, even a draft one: this
table must never be queried by anything that serves public content, so
"is this a shadow row or a real article" is never a distinction any
consumer has to make. `would_publish`/`p4_validation_result` record
what WOULD have happened; nothing here is ever public.

Every column here corresponds directly to one item in the owner's own
P6 telemetry list -- no column exists that wasn't explicitly asked for,
and nothing on that list is missing.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, JSON, String, Text

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ArticleV2ShadowExecution(Base):
    __tablename__ = "article_v2_shadow_executions"

    id = Column(String(64), primary_key=True)

    # ── Candidate identity ──────────────────────────────────────────────
    triage_event_id = Column(String, nullable=True, index=True)  # EventTriage.event_id
    symbol = Column(String(32), nullable=True)
    canonical_entity_id = Column(String(32), nullable=True, index=True)  # CompanyEntity.entity_id, from C1

    # ── V1 side (for direct comparison) ─────────────────────────────────
    v1_publication_decision = Column(String(32), nullable=True)  # "created" | "updated" | "skipped" | "duplicate" | "unknown"

    # ── C1 ───────────────────────────────────────────────────────────────
    c1_outcome = Column(String(32), nullable=True)  # CANDIDATE | UPDATE_CANDIDATE | SKIP
    c1_reason_code = Column(String(64), nullable=True)

    # ── C2 ───────────────────────────────────────────────────────────────
    evidence_ids = Column(JSON, nullable=False, default=list)
    evidence_count = Column(Integer, nullable=True)

    # ── C3 ───────────────────────────────────────────────────────────────
    c3_context_status = Column(String(16), nullable=True)  # AVAILABLE | PARTIAL | NONE

    # ── C4 ───────────────────────────────────────────────────────────────
    c4_content_type = Column(String(32), nullable=True)  # FULL_ARTICLE | FACTUAL_UPDATE | SKIP
    c4_publication_action = Column(String(16), nullable=True)  # CREATE | UPDATE_EXISTING | NONE

    # ── C5 ───────────────────────────────────────────────────────────────
    c5_publication_action = Column(String(16), nullable=True)  # CREATE_NEW | UPDATE_EXISTING | NO_PUBLICATION
    identity_key = Column(String(256), nullable=True, index=True)

    # ── C8.1 tier ────────────────────────────────────────────────────────
    c8_tier = Column(String(16), nullable=True)  # ARTICLE | EVENT_ONLY | REJECT

    # ── Headline / identity ──────────────────────────────────────────────
    headline = Column(Text, nullable=True)

    # ── P1 ───────────────────────────────────────────────────────────────
    p1_translation_status = Column(String(24), nullable=True)  # ok | scan_violation | not_reached

    # ── P2 ───────────────────────────────────────────────────────────────
    p2_authorization_summary = Column(JSON, nullable=True)
    # {"authorized": n, "qualified": n, "unavailable": n, "sections_omitted": [...]}

    # ── P4 / Final Publication Validator ─────────────────────────────────
    p4_validation_result = Column(String(24), nullable=True)  # would_publish | refused | not_reached
    would_publish = Column(Boolean, nullable=False, default=False)
    rejection_reason = Column(Text, nullable=True)
    stage_reached = Column(String(24), nullable=True)  # C1|C2|C3|C4|C5|C8_TIER|HEADLINE|COMPOSE|P1|P2|P4

    # ── Execution metadata ───────────────────────────────────────────────
    execution_time_ms = Column(Float, nullable=True)
    pipeline_mode = Column(String(16), nullable=False)  # shadow_v2 | canary_v2 | v2 -- never "v1" (V2 doesn't execute then)
    pipeline_version = Column(String(32), nullable=False, default="C1-C8.5+P1P2P4")

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    __table_args__ = (
        Index("ix_article_v2_shadow_executions_would_publish", "would_publish", "created_at"),
    )
