"""
AI usage instrumentation tables (2026-10-11).

Why: the production audit of 2026-10-11 found that nothing recorded AI Search request volume, per-provider token usage or per-feature call counts, so cost and reliability could only be
estimated. These tables record what actually happened, and only what actually happened:

  ai_usage_attempt       one row per LLM HTTP attempt (success or failure), tagged with the feature (operation) and the call it belonged to. Skipped-because-cooling-down attempts are
                         NOT HTTP attempts; they are aggregated into one counted row per (operation, provider, model) per flush with outcome "skipped_cooldown".
  ai_search_request_log  one row per AI Search request (not per LLM call): outcome, cache hit, latency, how many LLM calls and tokens it used.
  ai_usage_daily         permanent daily rollup of the attempt table (raw rows are pruned after ATTEMPT_RETENTION_DAYS), so long-range cost history survives the pruning.

Honesty rules baked into the schema:
  - input_tokens / output_tokens are NULL (unknown), never 0, when the provider did not report usage. usage_source says which: "provider" or "unknown".
  - No prompts, no user questions, no response bodies, no API keys are stored. A search request stores only the length of the query.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String

from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class AIUsageAttempt(Base):
    __tablename__ = "ai_usage_attempt"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), default=_now, nullable=False)
    operation = Column(String(48), nullable=False)          # ai_search | article_generation | scheduled_market_article | article_update | event_enrichment | triage | other:<module>
    call_id = Column(String(16), nullable=True)             # groups the attempts of one fallback-chain call
    request_id = Column(String(24), nullable=True)          # the AI Search request this belongs to, when there is one
    attempt_no = Column(Integer, nullable=True)             # 1 = first provider tried within the call; >1 = a fallback/retry within the same call
    provider = Column(String(32), nullable=False)
    model = Column(String(96), nullable=False)
    outcome = Column(String(24), nullable=False)            # success | rate_limited | billing | auth_error | not_found | server_error | timeout | api_error | empty | other | skipped_cooldown
    http_status = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)           # NULL = unknown (provider reported no usage)
    output_tokens = Column(Integer, nullable=True)
    usage_source = Column(String(12), nullable=False, default="unknown")   # provider | unknown
    n = Column(Integer, nullable=False, default=1)          # 1 for a real attempt; the count for an aggregated skipped_cooldown row

    __table_args__ = (
        Index("ix_ai_usage_attempt_ts", "ts"),
        Index("ix_ai_usage_attempt_op_ts", "operation", "ts"),
    )


class AISearchRequestLog(Base):
    __tablename__ = "ai_search_request_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), default=_now, nullable=False)
    request_id = Column(String(24), nullable=False, unique=True)
    origin = Column(String(12), nullable=False)             # api (a user request through an AI Search route) | internal (another service calling the pipeline, e.g. a publisher)
    outcome = Column(String(12), nullable=False)            # answered | degraded | error
    degraded_reason = Column(String(48), nullable=True)
    specialist = Column(String(24), nullable=True)
    cache_hit = Column(Boolean, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    query_len = Column(Integer, nullable=True)              # length only; the question itself is never stored
    llm_calls = Column(Integer, nullable=False, default=0)  # fallback-chain calls made for this request
    llm_attempts = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=True)           # sum over attempts that reported usage; NULL when none did
    output_tokens = Column(Integer, nullable=True)
    tokens_unknown_attempts = Column(Integer, nullable=False, default=0)

    __table_args__ = (Index("ix_ai_search_request_log_ts", "ts"),)


class AIUsageDaily(Base):
    __tablename__ = "ai_usage_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    day = Column(String(10), nullable=False)                # UTC date YYYY-MM-DD
    operation = Column(String(48), nullable=False)
    provider = Column(String(32), nullable=False)
    model = Column(String(96), nullable=False)
    outcome = Column(String(24), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)       # sum over rows that reported usage
    output_tokens = Column(Integer, nullable=False, default=0)
    attempts_with_usage = Column(Integer, nullable=False, default=0)
    latency_ms_sum = Column(Float, nullable=False, default=0.0)

    __table_args__ = (Index("ux_ai_usage_daily_key", "day", "operation", "provider", "model", "outcome", unique=True),)
