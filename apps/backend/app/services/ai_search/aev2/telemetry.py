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
"""
from __future__ import annotations

import hashlib
import hmac

import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)

RETENTION_DAYS = 30

_UNCONFIGURED_PLACEHOLDER = "telemetry-key-unconfigured"
_warned_unconfigured = False


def hash_query(query: str) -> str:
    """Opaque identifier for correlating telemetry rows about the same
    query without ever storing the query text itself. HMAC-SHA256 keyed
    by a dedicated secret — never a bare hash, which dictionary/rainbow-
    table attacks defeat for a small, guessable query space. Returns a
    fixed, non-identifying placeholder (logged once) if no key is
    configured, rather than falling back to an insecure bare hash."""
    global _warned_unconfigured
    key = settings.aev2_telemetry_key
    if not key:
        if not _warned_unconfigured:
            log.warning("ai_search.aev2_telemetry_key_unconfigured")
            _warned_unconfigured = True
        return _UNCONFIGURED_PLACEHOLDER
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
