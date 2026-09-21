"""
Deterministic recommendation-language safety net for the V3 core response
itself — runs UNCONDITIONALLY, regardless of AI_SEARCH_AEV2_MODE.

Real defect this closes (found live, 2026-09-21): a raw LLM response for
a production "Should I invest in HDFC Bank?" query contained the literal
phrase "solid buy candidate" — caught only because that specific response
also happened to fail JSON parsing and fall through to the existing
degraded path. A response that parses successfully has no such safety
net today. Wiring this gate inside AEV2 (which defaults to `off`) would
not have protected anyone, since AEV2 correctly stays off until its own
build is complete — this module is deliberately independent of AEV2 and
protects every real serving route today, on the existing V3 contract.

    cached/fresh V3 core -> this gate -> honest degraded response
    on violation -> optional AEV2 assembly -> serialize

Never mutates its input `result` — reads it, and on a violation returns
an entirely new dict. Applies only to generated "conclusion"-shaped V3
text; never to evidence/news/event titles (immutable source text a real
outlet or filing actually published, not this platform's own words).
Logs only the offending field's name and a fixed violation code — never
the matched phrase or the surrounding generated text.
"""
from __future__ import annotations

import structlog

from app.services.ai_search.aev2.language_gate import scan
from app.services.ai_search.degraded_shape import build_degraded_shape

log = structlog.get_logger(__name__)

# (dict path, field label for logging) — the user-facing "conclusion"-
# shaped V3 fields most exposed to leaking generated advisory language.
# Deliberately does NOT include evidence[]/related_events/news/policies
# titles (immutable source text) or investment_verdict.rating (already a
# closed 8-value enum, not free text).
_SAFETY_FIELDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("answer", "bottom_line"), "bottom_line"),
    (("answer", "summary"), "summary"),
    (("ai_conclusion", "investor_action_note"), "investor_action_note"),
    (("decision_engine_v2", "why"), "decision_engine_v2_why"),
)


def _get_nested_str(d: dict, path: tuple[str, ...]) -> str:
    cur: object = d
    for key in path:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return cur if isinstance(cur, str) else ""


def find_v3_safety_violation(result: dict) -> str | None:
    """Returns the field label of the FIRST violating field found among
    _SAFETY_FIELDS, or None if the response is clean. Read-only."""
    for path, field_label in _SAFETY_FIELDS:
        text = _get_nested_str(result or {}, path)
        if text and scan(text):
            return field_label
    return None


def build_v3_safety_degraded_response(result: dict, field_label: str) -> dict:
    """Never mutates `result` — returns a brand new dict. Keeps the real,
    already-validated evidence (related_events/news/policies/companies —
    these already passed _verify_companies_exist and the narrative-
    consistency check upstream in validation.py, and are independent of
    which conclusion-shaped field failed this check) while nulling every
    analytical/verdict-shaped field. Shape matches pipeline.py's own
    fail-closed degraded response exactly, so the frontend's existing
    synthesis_incomplete gating (already shipped, commit 8414bf0) handles
    this identically to a genuine synthesis failure — a distinct response
    shape, not the real response with one field patched over.

    Logs only the field name and a fixed violation code here — never the
    matched phrase or any surrounding generated text — the single place
    this event is emitted, so every caller gets the same log shape."""
    log.warning(
        "ai_search_v3.recommendation_language_violation",
        field=field_label, violation_code="recommendation_language_pattern_match",
    )
    result = result or {}
    honest_summary = (
        "This answer could not be shown because the generated text did not pass "
        "the research-language check. The real evidence found is shown below, "
        "with no generated conclusion, confidence score, or outlook."
    )
    answer = result.get("answer") or {}
    return build_degraded_shape(
        query=result.get("query", ""),
        response_id=result.get("response_id"),
        schema_version=result.get("schema_version"),
        specialist_kind=result.get("specialist"),
        degraded_reason="recommendation_language_violation",
        summary=honest_summary,
        sources_count=answer.get("sources_count", 0),
        companies=result.get("companies", []),
        sectors=result.get("sectors", []),
        related_events=result.get("related_events", []),
        news=result.get("news", []),
        policies=result.get("policies", []),
        citations=result.get("citations", []),
        evidence_score=result.get("evidence_score", {}),
        source_attribution=result.get("source_attribution", []),
        validation=result.get("validation") or {"repairs": [], "omissions": [], "contradiction_flagged": False},
    )
