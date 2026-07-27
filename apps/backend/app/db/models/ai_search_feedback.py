import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, String, Text

from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


# Kept here (not enforced as a DB-level CHECK constraint — SQLite's ALTER
# support is limited and this app never runs formal migrations, see
# schema_patches.py) but validated at the API boundary in api/ai_search.py.
RATINGS = ("helpful", "not_helpful")
REASONS = (
    "wrong_company", "too_generic", "too_slow", "missing_news",
    "incorrect_conclusion", "didnt_answer", "hallucination", "other",
)


class AISearchFeedback(Base):
    """👍/👎 feedback on an AI Search V3 answer — the raw dataset behind the
    Phase 1.5 continuous-improvement loop. Each row pairs a user's judgment
    with the real delivery context (provider, cache hit, latency) for that
    specific serve, so weaknesses can be prioritized from actual usage
    instead of guesswork (e.g. "which reason correlates with cache misses
    vs. hits", "which specialist gets the most hallucination reports").

    response_id identifies the generated ANSWER CONTENT (stable across
    repeat cache-hit serves of the same analysis — see pipeline.py's
    _assemble_response), not the individual HTTP request. Two users who
    both landed on the same cached HAL analysis and both said "too generic"
    are the same signal about the same content, and should count as such."""
    __tablename__ = "ai_search_feedback"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    response_id = Column(String(64), nullable=False, index=True)
    query = Column(Text, nullable=False)
    rating = Column(String(16), nullable=False, index=True)  # helpful | not_helpful
    reason = Column(String(32), nullable=True)   # one of REASONS, only when rating == not_helpful
    reason_text = Column(Text, nullable=True)    # optional free text ("Other" or elaboration)

    # Delivery context, captured at feedback time — client-reported (the
    # frontend already received all of this in the search response
    # envelope), an acceptable trust boundary since this is an internal
    # improvement dataset, not a security- or billing-relevant record.
    specialist = Column(String(16), nullable=True)      # company | sector | comparison
    provider = Column(String(32), nullable=True)         # None when served from cache — no live LLM call that serve
    cache_hit = Column(Boolean, nullable=True)
    latency_ms = Column(Float, nullable=True)
    schema_version = Column(String(8), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, index=True)
