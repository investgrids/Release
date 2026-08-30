"""
CandidateRun — durable lifecycle record for scheduled/synthetic article
candidates (morning_intelligence, market_wrap, educational_intelligence/
evergreen, historical_intelligence): content that is never triaged, so has
no real EventTriage/EventCoverage row to fall back on for observability
the way triage-driven candidates already do (see EventCoverage's own
docstring and coverage_engine.mark_failed).

Real incident this closes (2026-08-30, artifacts/ai_provider_reliability_
audit.md): a candidate on one of these paths that failed generation left
ZERO database trace -- no coverage row (none exists for non-triaged
content by construction), no IntelligenceArticle row (only ever created
by a SUCCESSFUL generate_intelligence_article call inside
_publish_new_article, even for a later validation failure -- a pure
generation failure returns None before any row is ever built). Measured
22 real occurrences of exactly this in a single 3h11m production log
window. Deliberately NOT solved by fabricating an EventTriage row for a
synthetic event -- scheduled/evergreen/historical content is a genuinely
different real thing from a triaged market event, not disguised triage.

Owner's explicit design (2026-08-30): every scheduled article candidate
that enters generation gets a durable terminal outcome, even when no
article is produced.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, JSON, String, Text

from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


TERMINAL_PUBLISHED = "PUBLISHED"
TERMINAL_SKIPPED = "SKIPPED"
TERMINAL_PROVIDER_FAILED = "PROVIDER_FAILED"
TERMINAL_VALIDATION_FAILED = "VALIDATION_FAILED"
TERMINAL_INTERNAL_ERROR = "INTERNAL_ERROR"

TERMINAL_STATUSES = (
    TERMINAL_PUBLISHED, TERMINAL_SKIPPED, TERMINAL_PROVIDER_FAILED,
    TERMINAL_VALIDATION_FAILED, TERMINAL_INTERNAL_ERROR,
)


class CandidateRun(Base):
    __tablename__ = "candidate_run"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Real story_id/topic slug this run is for, e.g. "morning-2026-08-30",
    # "evergreen-what-is-repo-rate", "historical-how-the-last-rbi-..." --
    # NOT unique across time (the same scheduled slot recurs daily), so
    # indexed but not a unique constraint.
    candidate_id = Column(String, nullable=False, index=True)
    candidate_type = Column(String(32), nullable=False, index=True)
    # How this candidate was produced -- all 3 real callers today are
    # scheduler-driven, kept as its own field (not folded into
    # candidate_type) since a future non-cron trigger (e.g. a manual
    # backfill run) is a real, distinct provenance question.
    trigger_type = Column(String(32), nullable=False, default="scheduled_cron")
    created_at = Column(DateTime(timezone=True), default=_now, index=True)
    generation_started_at = Column(DateTime(timezone=True), nullable=True)
    # [{model, provider, reason}, ...] -- the real failure_log threaded
    # through generate_intelligence_article/_call_with_fallback, not a
    # synthetic summary. Empty list, never null, when nothing was attempted
    # (e.g. a SKIPPED run that never reached generation).
    provider_attempts = Column(JSON, nullable=False, default=list)
    terminal_status = Column(String(24), nullable=True, index=True)
    failure_reason = Column(Text, nullable=True)
    article_id = Column(String, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
