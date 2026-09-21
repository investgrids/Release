"""
/api/ai/search/refine safety gate — Phase 1 fix (2026-09-21 intent audit
finding: this endpoint had zero references to safety_gate,
finalize_v3_response, or recommendation_language — confirmed via grep
before this fix). Public generated prose (decision_engine_v2.why,
ai_conclusion.investor_action_note) reached the client completely
unscanned by the deterministic advisory-language check every other
serving route already runs through.

Also confirms (per the audit's explicit ask): RefineAnalysisPanel.tsx
has no useEffect and calls this endpoint only from its "Regenerate
Decision" button's onClick — refine does NOT auto-trigger on every
result. This endpoint being reachable only via explicit user action is
a frontend-side fact (verified by reading RefineAnalysisPanel.tsx
directly, not testable from the backend), noted here for the record.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)

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
