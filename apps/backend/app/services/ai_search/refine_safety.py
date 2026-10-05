"""
Exhaustive recommendation-language safety net for /api/ai/search/refine
(Phase 1 fix, 2026-09-21 — hardened in review's next pass: the first
version of this fix only checked 2 of the 9 real free-text locations
Refine's own output can carry, exactly the "bypass the two known paths"
risk that review named).

Refine's LLM call only ever fills INVESTMENT_GROUP + DECISION_GROUP
(schema.py) — never evidence/timeline/risks/extras — so every free-text
field this endpoint can possibly return traces to one of those two
templates. flatten_nested() (schema.py) splits them across THREE
top-level response keys (investment_verdict/decision_engine_v2/
ai_conclusion), several of them duplicated across keys (the same
`decision.what_changes_the_view` value backs both decision_engine_v2.
what_changes_the_view AND investment_verdict.catalysts) — this module
enumerates every one of those (key, field) locations explicitly, not
just the two most obviously "conclusion-shaped" ones, so a new field
appearing in one of the two templates can't silently reach a client
unscanned the way review found live.

Deliberately excludes: rating/direction/verdict_scale/horizon/confidence
(schema-constrained enums and numbers, not free text — validation.py's
own checks are the right layer for those, not a language scanner) and
top_picks/risks/opportunity_score (always empty for Refine — no extras/
risks group is ever requested in refine.py's own prompt).

Uses advisory_language.py's shared, context-aware scan() — no dependency
on the aev2/ package (this module, like advisory_language.py itself,
must be deployable independent of AEV2 — see safety_gate.py's own
docstring for the review finding this design avoids repeating).
"""
from __future__ import annotations

import structlog

from app.services.ai_search.advisory_language import scan
from app.services.ai_search.degraded_shape import empty_investment_verdict

log = structlog.get_logger(__name__)

# (top-level key, field name) — scalar free-text fields.
_SCALAR_FIELDS: tuple[tuple[str, str], ...] = (
    ("decision_engine_v2", "why"),
    ("ai_conclusion", "current_view"),
    ("ai_conclusion", "reason"),
    ("ai_conclusion", "biggest_opportunity"),
    ("ai_conclusion", "biggest_risk"),
    ("ai_conclusion", "investor_action_note"),
)

# (top-level key, field name) — list-of-free-text fields.
_LIST_FIELDS: tuple[tuple[str, str], ...] = (
    ("decision_engine_v2", "what_changes_the_view"),
    ("decision_engine_v2", "what_invalidates_the_thesis"),
    ("investment_verdict", "catalysts"),
)

# (top-level key, nested-dict field, sub-field) — comparison-mode only
# (DECISION_GROUP_EXPLAIN_WHY_NOT), absent entirely for a single-entity
# refine.
_NESTED_SCALAR_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("decision_engine_v2", "explain_why_not", "reason_rejected"),
)


def find_refine_violation(parsed: dict) -> str | None:
    """Returns the first violating location's dotted label, or None if
    clean. Read-only — never mutates `parsed`."""
    for group, field in _SCALAR_FIELDS:
        text = (parsed.get(group) or {}).get(field)
        if isinstance(text, str) and scan(text):
            return f"{group}.{field}"
    for group, field in _LIST_FIELDS:
        items = (parsed.get(group) or {}).get(field) or []
        for i, text in enumerate(items):
            if isinstance(text, str) and scan(text):
                return f"{group}.{field}[{i}]"
    for group, nested_field, sub_field in _NESTED_SCALAR_FIELDS:
        nested = (parsed.get(group) or {}).get(nested_field)
        if isinstance(nested, dict):
            text = nested.get(sub_field)
            if isinstance(text, str) and scan(text):
                return f"{group}.{nested_field}.{sub_field}"
    return None


def build_refine_degraded_response() -> dict:
    """The same honest-empty shape a genuinely failed specialist call
    produces (specialists/base.py::degraded_response, via
    empty_investment_verdict() — the one shared "no verdict" skeleton
    both paths agree on). Refine's own contract (RefineResponse) is only
    3 dict fields, not the full response shape, so no larger skeleton is
    needed here."""
    return {
        "investment_verdict": empty_investment_verdict(),
        "decision_engine_v2": {}, "ai_conclusion": {},
    }


def log_refine_violation(field_label: str) -> None:
    log.warning(
        "ai_search_v3.refine.recommendation_language_violation",
        field=field_label, violation_code="recommendation_language_pattern_match",
    )
