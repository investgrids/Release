"""
Sanitized AEV2 telemetry (errata §10, item 8 + item 10, 2026-09-21;
hashing hardened after review, 2026-09-21).

Never stores or logs the raw query text, the LLM's generated prose, or
any other prompt content — only an opaque, keyed hash of the query,
pass/fail flags per check, failure_reason codes, stage timings, and
confidence component values. Emitted via structlog, matching this
codebase's existing `ai_search_v3.*`/`ai.*` structured-log convention —
no new storage mechanism introduced here.

Review finding: a PLAIN SHA-256 of the query text is not private — common
queries ("Should I invest in HDFC Bank?") are trivially recovered by
dictionary/rainbow-table lookup, since the input space of real user
queries is small and guessable. hash_query() below is HMAC-SHA256 keyed
by settings.aev2_telemetry_key — a dedicated secret, deliberately never
admin_api_key (a compromised telemetry key must never also compromise the
admin-write surface, and vice versa). If that key is unset, hash_query()
returns a fixed placeholder rather than silently falling back to plain
SHA-256 — fail closed, never quietly reintroduce the exact gap this
change exists to close.

RETENTION: 30 days is the intended window (ordinary log-retention
discipline, not a special exception built for this feature) but nothing
in this module enforces it — no dedicated telemetry store/schema was
asked for as part of this foundation slice, so retention/purge is
whatever the underlying log sink (Railway's own log retention, or any
downstream aggregator) is actually configured to. Before AI_SEARCH_AEV2_
MODE is ever set to "shadow" (or beyond) in a real environment, someone
must confirm that sink's real retention setting matches this window —
that is an operational verification step, not something this module can
prove from application code alone.

Review finding (2026-09-21, second pass): a missing telemetry key must
not let shadow/canary/public LOOK operational while actually being
unusable. Emitting `ai_search.aev2_assembly` events with a fixed shared
placeholder in place of query_hash would do exactly that — an operator
watching for those log lines would see them arriving on schedule and
reasonably conclude telemetry is working, when every row is in fact
uncorrelatable with every other row. Every emit_* function below now
checks readiness FIRST and emits nothing at all (beyond the one-time
warning) when the key is unset — an absent stream of
ai_search.aev2_assembly events is the honest signal that shadow mode
isn't actually collecting usable telemetry yet, not a stream of
misleadingly uniform ones.
"""
from __future__ import annotations

import hashlib
import hmac

import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)

RETENTION_DAYS = 30

_warned_unconfigured = False


def _telemetry_ready() -> bool:
    """False when no dedicated telemetry key is configured — the one
    gate every emit_* function below runs through first. Warns once
    (not once per call) so an operator sees it, without spamming a log
    line per search."""
    global _warned_unconfigured
    if settings.aev2_telemetry_key:
        return True
    if not _warned_unconfigured:
        log.warning("ai_search.aev2_telemetry_key_unconfigured")
        _warned_unconfigured = True
    return False


def hash_query(query: str) -> str:
    """Opaque identifier for correlating telemetry rows about the same
    query without ever storing the query text itself. HMAC-SHA256 keyed
    by a dedicated secret — never a bare hash, which dictionary/rainbow-
    table attacks defeat for a small, guessable query space. Callers must
    check _telemetry_ready() before calling this — it has no unconfigured
    fallback of its own (an empty key would make hmac.new itself the
    guard, but every real emit_* call site below never reaches this
    function at all when the key is unset, which is the actual contract)."""
    key = settings.aev2_telemetry_key
    return hmac.new(key.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def emit_assembly_success(
    *,
    query: str,
    mode: str,
    response_id: str | None,
    had_language_violation: bool,
    is_fallback: bool,
    stage_ms: dict,
) -> None:
    if not _telemetry_ready():
        return
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
    if not _telemetry_ready():
        return
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
    if not _telemetry_ready():
        return
    log.info(
        "ai_search.aev2_confidence_computed",
        query_hash=hash_query(query),
        aev2_score=aev2_score,
        components_available=components_available,
        llm_self_rating=llm_self_rating,
    )
