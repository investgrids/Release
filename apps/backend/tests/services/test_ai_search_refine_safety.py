"""
/api/ai/search/refine safety gate — Phase 1 fix (2026-09-21 intent audit
finding: this endpoint had zero references to safety_gate,
finalize_v3_response, or recommendation_language — confirmed via grep
before this fix). Public generated prose reached the client completely
unscanned by the deterministic advisory-language check every other
serving route already runs through.

Hardened in the next review pass: the first version of this fix only
checked 2 of the 9 real free-text locations Refine's own output can
carry (decision_engine_v2.why and ai_conclusion.investor_action_note) —
exactly the "bypass the two known paths" risk the review named.
test_refine_contract_covers_every_generated_free_text_field below
enumerates all 9 explicitly (importing refine_safety.py's own field
registry, so a future registry change is exercised automatically) and
injects a violation into each ONE AT A TIME.

Also confirms (per the audit's explicit ask): RefineAnalysisPanel.tsx
has no useEffect and calls this endpoint only from its "Regenerate
Decision" button's onClick — refine does NOT auto-trigger on every
result. This endpoint being reachable only via explicit user action is
a frontend-side fact (verified by reading RefineAnalysisPanel.tsx
directly, not testable from the backend), noted here for the record.
"""
from __future__ import annotations

import re
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.limiter import limiter
from app.main import app
from app.services.ai_search import refine_safety
from app.services.ai_search import schema as schema_mod

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """This module alone makes >15 requests to a route limited to
    15/minute (the exhaustive contract test below is 10 by itself) —
    reset slowapi's in-memory counter before each test so tests are
    isolated from each other's request count, not just from real abuse."""
    limiter.reset()
    yield
    limiter.reset()

_SNAPSHOT = {
    "query": "Should I invest in HDFC Bank?",
    "specialist_kind": "company",
    "is_comparison": False,
    "evidence_context": "HDFC Bank reported steady quarterly results.",
    "companies": [{"symbol": "HDFCBANK", "name": "HDFC Bank Ltd"}],
}

_CLEAN_REFINE_OUTPUT = {
    "investment_verdict": {"rating": "Positive", "direction": "bullish", "horizon": "6-12 months"},
    "decision_engine_v2": {"verdict_scale": "Positive", "why": "Loan growth and NIM trends remain supportive."},
    "ai_conclusion": {
        "current_view": "Positive", "reason": "Steady fundamentals.",
        "investor_action_note": "Watch the next quarter's NIM trend for confirmation.",
    },
}

_UNSAFE_REFINE_OUTPUT = {
    "investment_verdict": {"rating": "Positive", "direction": "bullish", "horizon": "6-12 months"},
    "decision_engine_v2": {"verdict_scale": "Positive", "why": "This is a solid buy candidate right now."},
    "ai_conclusion": {
        "current_view": "Positive", "reason": "Steady fundamentals.",
        "investor_action_note": "Investors should buy this dip.",
    },
}


def _post_refine(body: dict | None = None):
    return client.post("/api/ai/search/refine", json={"response_id": "resp-1", **(body or {})})


def test_refine_returns_404_when_snapshot_missing():
    with patch("app.services.ai_search.cache.get_snapshot", return_value=None):
        resp = _post_refine()
    assert resp.status_code == 404


def test_refine_passes_through_clean_output_unchanged():
    with patch("app.services.ai_search.cache.get_snapshot", return_value=dict(_SNAPSHOT)), \
         patch(
             "app.services.ai_search.specialists.refine.run",
             new=AsyncMock(return_value=(dict(_CLEAN_REFINE_OUTPUT), False)),
         ):
        resp = _post_refine()
    assert resp.status_code == 200
    body = resp.json()
    assert body["synthesis_incomplete"] is False
    assert body["decision_engine_v2"]["why"] == "Loan growth and NIM trends remain supportive."
    assert body["ai_conclusion"]["investor_action_note"] == "Watch the next quarter's NIM trend for confirmation."


def test_refine_degrades_advisory_language_in_decision_engine_why():
    with patch("app.services.ai_search.cache.get_snapshot", return_value=dict(_SNAPSHOT)), \
         patch(
             "app.services.ai_search.specialists.refine.run",
             new=AsyncMock(return_value=(dict(_UNSAFE_REFINE_OUTPUT), False)),
         ):
        resp = _post_refine()
    assert resp.status_code == 200
    body = resp.json()
    assert body["synthesis_incomplete"] is True
    assert body["decision_engine_v2"] == {}
    assert body["ai_conclusion"] == {}
    assert body["investment_verdict"]["rating"] == "Not Applicable"


def test_refine_degrades_advisory_language_in_investor_action_note_only():
    unsafe = {
        **_CLEAN_REFINE_OUTPUT,
        "ai_conclusion": {**_CLEAN_REFINE_OUTPUT["ai_conclusion"], "investor_action_note": "Hold your position for now."},
    }
    with patch("app.services.ai_search.cache.get_snapshot", return_value=dict(_SNAPSHOT)), \
         patch("app.services.ai_search.specialists.refine.run", new=AsyncMock(return_value=(unsafe, False))):
        resp = _post_refine()
    body = resp.json()
    assert body["synthesis_incomplete"] is True
    assert body["ai_conclusion"] == {}


def test_refine_does_not_cache_a_new_snapshot_on_a_gate_violation():
    with patch("app.services.ai_search.cache.get_snapshot", return_value=dict(_SNAPSHOT)) as mock_get, \
         patch("app.services.ai_search.cache.set_snapshot") as mock_set, \
         patch(
             "app.services.ai_search.specialists.refine.run",
             new=AsyncMock(return_value=(dict(_UNSAFE_REFINE_OUTPUT), False)),
         ):
        _post_refine()
    mock_set.assert_not_called()


def test_refine_still_marks_synthesis_incomplete_on_a_genuine_specialist_failure():
    """The gate is additive — a genuinely failed specialist call (was_
    degraded=True from refine_specialist.run itself) must still degrade
    exactly as before, independent of the language gate."""
    with patch("app.services.ai_search.cache.get_snapshot", return_value=dict(_SNAPSHOT)), \
         patch("app.services.ai_search.specialists.refine.run", new=AsyncMock(return_value=({}, True))):
        resp = _post_refine()
    body = resp.json()
    assert body["synthesis_incomplete"] is True


# ── Exhaustive contract: every free-text location, injected one at a time ──

def _base_refine_output() -> dict:
    """A clean baseline covering every field refine_safety.py registers
    — including the comparison-only explain_why_not — so any ONE field
    can be overwritten with unsafe text without the others accidentally
    masking the result (e.g. an empty list never gets scanned at all)."""
    return {
        "investment_verdict": {
            "rating": "Positive", "direction": "bullish", "horizon": "6-12 months",
            "catalysts": ["Strong loan growth reported last quarter.", "NIM expansion expected next quarter."],
        },
        "decision_engine_v2": {
            "verdict_scale": "Positive",
            "why": "Loan growth and NIM trends remain supportive.",
            "what_changes_the_view": ["A surprise rate hike.", "A sharp rise in NPAs."],
            "what_invalidates_the_thesis": ["Asset quality deterioration.", "A sustained NIM compression."],
            "explain_why_not": {"alternative": "ICICI Bank", "reason_rejected": "Slightly weaker deposit growth this quarter."},
        },
        "ai_conclusion": {
            "current_view": "Positive",
            "reason": "Steady fundamentals support the current view.",
            "biggest_opportunity": "Continued market share gains in retail lending.",
            "biggest_risk": "A sharper-than-expected rate cut cycle.",
            "investor_action_note": "Watch the next quarter's NIM trend for confirmation.",
        },
    }


def _inject(base: dict, group: str, field: str, text: str, *, index: int | None = None, nested: str | None = None) -> dict:
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in base.items()}
    out[group] = dict(out[group])
    if nested is not None:
        out[group][nested] = {**out[group][nested], field: text}
    elif index is not None:
        items = list(out[group][field])
        items[index] = text
        out[group][field] = items
    else:
        out[group][field] = text
    return out


def test_refine_contract_covers_every_generated_free_text_field():
    """Enumerates every (group, field) refine_safety.py actually
    registers — scalar, list, and nested — and proves a violation
    injected into EACH ONE, one at a time, degrades the response. A
    future field added to refine_safety.py's registry without also
    being wired into find_refine_violation would show up here as a
    location that fails to degrade."""
    unsafe_text = "This is a solid buy candidate regardless of the scenario."

    for group, field in refine_safety._SCALAR_FIELDS:
        unsafe = _inject(_base_refine_output(), group, field, unsafe_text)
        with patch("app.services.ai_search.cache.get_snapshot", return_value=dict(_SNAPSHOT)), \
             patch("app.services.ai_search.specialists.refine.run", new=AsyncMock(return_value=(unsafe, False))):
            resp = _post_refine()
        body = resp.json()
        assert body["synthesis_incomplete"] is True, f"{group}.{field} did not degrade"
        assert body["decision_engine_v2"] == {} and body["ai_conclusion"] == {}

    for group, field in refine_safety._LIST_FIELDS:
        unsafe = _inject(_base_refine_output(), group, field, unsafe_text, index=0)
        with patch("app.services.ai_search.cache.get_snapshot", return_value=dict(_SNAPSHOT)), \
             patch("app.services.ai_search.specialists.refine.run", new=AsyncMock(return_value=(unsafe, False))):
            resp = _post_refine()
        body = resp.json()
        assert body["synthesis_incomplete"] is True, f"{group}.{field}[0] did not degrade"

    for group, nested_field, sub_field in refine_safety._NESTED_SCALAR_FIELDS:
        unsafe = _inject(_base_refine_output(), group, sub_field, unsafe_text, nested=nested_field)
        with patch("app.services.ai_search.cache.get_snapshot", return_value=dict(_SNAPSHOT)), \
             patch("app.services.ai_search.specialists.refine.run", new=AsyncMock(return_value=(unsafe, False))):
            resp = _post_refine()
        body = resp.json()
        assert body["synthesis_incomplete"] is True, f"{group}.{nested_field}.{sub_field} did not degrade"


def test_refine_contract_registers_at_least_nine_locations():
    """A concrete floor, not just "some fields" — the exact count found
    live when this was audited (6 scalar + 3 list, one of the scalars
    itself only reachable in comparison mode via a nested dict)."""
    total = len(refine_safety._SCALAR_FIELDS) + len(refine_safety._LIST_FIELDS) + len(refine_safety._NESTED_SCALAR_FIELDS)
    assert total >= 9


def test_refine_safety_registry_matches_the_actual_schema_templates():
    """Structural drift guard: every free-text key schema.py's own
    INVESTMENT_GROUP/DECISION_GROUP templates actually declare (minus the
    enums/numbers/always-empty-for-refine fields explicitly excluded —
    see refine_safety.py's own docstring) must appear somewhere in
    refine_safety.py's field registry. Catches a new prompt field added
    to schema.py without also being wired into the scanner."""
    combined = schema_mod.INVESTMENT_GROUP + schema_mod.DECISION_GROUP + schema_mod.DECISION_GROUP_EXPLAIN_WHY_NOT
    all_keys = set(re.findall(r'"([a-z_]+)":', combined))

    # Enums, numbers, and fields refine.py's own prompt never populates
    # (no evidence/risks/extras group is ever requested) — deliberately
    # excluded, not missed. See refine_safety.py's own docstring.
    excluded = {
        "summary", "bottom_line", "confidence", "confidence_self_rating",
        "sentiment", "rating", "direction", "horizon", "verdict_scale", "alternative",
        # Group/nested-object wrapper keys themselves, not fields.
        "investment", "decision", "explain_why_not",
    }
    registered = (
        {field for _, field in refine_safety._SCALAR_FIELDS}
        | {field for _, field in refine_safety._LIST_FIELDS}
        | {sub_field for _, _, sub_field in refine_safety._NESTED_SCALAR_FIELDS}
    )
    unaccounted = all_keys - excluded - registered
    assert unaccounted == set(), f"schema.py has free-text field(s) refine_safety.py never scans: {unaccounted}"
