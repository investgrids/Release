import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, JSON
from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class EventCoverage(Base):
    """Critical Event Coverage registry — one row per triaged event,
    written the moment EventTriage is (see triage_worker._store_triage),
    updated when AIPE either publishes a new article or matches an
    existing one for it (see publisher.run_aipe_cycle). Answers two
    questions the pipeline previously couldn't: "what important events did
    we detect today" and "which important ones did we fail to cover" —
    see coverage_engine.find_uncovered_critical.

    priority reuses app.services.intelligence.engine.compute_priority's
    existing Critical/High/Medium/Low tiers (that function's own docstring
    says other modules should import it rather than re-implement the
    cutoffs) — this table doesn't invent its own scoring."""
    __tablename__ = "event_coverage"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, nullable=False, index=True, unique=True)
    priority = Column(String(16), nullable=False, index=True)  # Critical|High|Medium|Low
    priority_score = Column(Integer, nullable=True)            # 0-100, from compute_priority
    detected_at = Column(DateTime(timezone=True), default=_now, index=True)
    source = Column(String(64), nullable=True)
    event_title = Column(Text, nullable=True)
    sectors = Column(JSON, nullable=False, default=list)
    companies = Column(JSON, nullable=False, default=list)
    article_required = Column(Boolean, nullable=False, default=False)
    article_generated = Column(Boolean, nullable=False, default=False)
    article_id = Column(String, nullable=True)
    daily_brief_covered = Column(Boolean, nullable=False, default=False)
    coverage_status = Column(String(32), nullable=False, default="DETECTED", index=True)
    # DETECTED | PUBLISHED | COVERED_BY_EXISTING_ARTICLE | FAILED
    # Audit finding (2026-08-12): FAILED was declared here from the start
    # but no code path ever wrote it — article_generator returning None and
    # quality_validator rejecting an article both left the row at DETECTED
    # forever, indistinguishable from "never attempted." failure_reason is
    # new alongside actually writing FAILED (coverage_engine.mark_failed),
    # so a failed row says *why* instead of just that it failed.
    failure_reason = Column(String(256), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)
