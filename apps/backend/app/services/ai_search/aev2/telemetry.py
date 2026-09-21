"""
Sanitized AEV2 telemetry (errata §10, item 8 + item 10, 2026-09-21).

Never stores or logs the raw query text, the LLM's generated prose, or
any other prompt content — only an opaque hash of the query, pass/fail
flags per check, failure_reason codes, stage timings, and confidence
component values. Emitted via structlog, matching this codebase's
existing `ai_search_v3.*`/`ai.*` structured-log convention — no new
storage mechanism introduced here. Retention is inherited from whatever
already governs this process's logs (Railway's own log retention) —
ordinary log-retention discipline, not a special exception built for this
feature; RETENTION_DAYS below documents the intended window rather than
enforcing it in code, since no dedicated telemetry store/schema was asked
for as part of this foundation slice.
"""
from __future__ import annotations

import hashlib

import structlog

log = structlog.get_logger(__name__)

RETENTION_DAYS = 30


def hash_query(query: str) -> str:
    """Opaque, non-reversible identifier for correlating telemetry rows
    about the same query without ever storing the query text itself."""
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def emit_assembly_success(
    *,
    query: str,
    mode: str,
    response_id: str | None,
    had_language_violation: bool,
    is_fallback: bool,
    stage_ms: dict,
) -> None:
    log.info(
        "ai_search.aev2_assembly",
        query_hash=hash_query(query),
        mode=mode,
        response_id=response_id,
        had_language_violation=had_language_violation,
        is_fallback=is_fallback,
        stage_ms=stage_ms,
    )


def emit_assembly_failed(
    *,
    query: str,
    mode: str,
    failure_reason: str,
    stage_ms: dict,
) -> None:
    """failure_reason is a specific code (e.g. "insufficient_evidence",
    "citation_resolution_exception", "attribution_exception") — never a
    raw exception message, which could incidentally quote generated text."""
    log.warning(
        "ai_search.aev2_assembly_failed",
        query_hash=hash_query(query),
        mode=mode,
        failure_reason=failure_reason,
        stage_ms=stage_ms,
    )


def emit_confidence_computed(
    *,
    query: str,
    aev2_score: float | None,
    components_available: list[str],
    llm_self_rating: int | None,
) -> None:
    """llm_self_rating is recorded here ONLY for offline calibration
    research — never included in the AEV2 confidence formula itself (see
    the confidence-renormalization design) and never returned to any HTTP
    caller in any form."""
    log.info(
        "ai_search.aev2_confidence_computed",
        query_hash=hash_query(query),
        aev2_score=aev2_score,
        components_available=components_available,
        llm_self_rating=llm_self_rating,
    )
