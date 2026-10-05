"""
Safety-gate precedence fix (2026-09-23) — real incident found live during
Phase 1.3's single fresh-request verification of "Should I continue
holding BEL or switch to HAL?".

Root cause, reproduced entirely offline here (no provider calls): every
provider was exhausted (a real capacity failure, degraded_reason=
"capacity"), and specialists/base.py's degraded_response() echoed the raw
query verbatim into answer.bottom_line/summary — both scanned fields for
safety_gate.py's advisory-language check. The query itself contains
"continue holding", which advisory_language.py's context-aware hold
pattern (\\b(?:continue|keep)\\s+holding\\b) correctly treats as advisory
PHRASING when it appears in GENERATED text — but this was the user's own
question, not anything the system generated. The safety gate rebuilt the
response and silently overwrote the real degraded_reason ("capacity")
with "recommendation_language_violation", which then made answer_
availability (Phase 1.2) misreport a genuine provider outage as
"no_verified_evidence" instead of "temporarily_unavailable".

Two-part fix: (1) degraded_response() no longer echoes the raw query
into either scanned field (specialists/base.py) — the query is already
shown in the page's own heading. (2) response_finalize.py's safety gate
no longer overwrites an ALREADY-degraded response's degraded_reason on a
hit; it only ever rebuilds (and sets degraded_reason="recommendation_
language_violation") when rejecting an otherwise-successful response — a
hit on an already-degraded response is recorded in telemetry only.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_search.advisory_language import scan
from app.services.ai_search.response_finalize import finalize_v3_response
from app.services.ai_search.specialists.base import degraded_response, parse_specialist_json

client = TestClient(app, raise_server_exceptions=False)

BEL_HAL_QUERY = "Should I continue holding BEL or switch to HAL?"


# ── 1. Reproduce the exact BEL/HAL case offline; record the matched field/phrase ──

def test_degraded_response_no_longer_echoes_a_query_containing_advisory_phrasing():
    """Pins the exact real incident: before this fix, scan() found 'hold'
    in both echoed fields for this exact query (recorded here as the
    matched field/phrase this investigation found)."""
    d = degraded_response(BEL_HAL_QUERY)
    assert scan(d["bottom_line"]) == [], "bottom_line must not echo the raw query into a safety-scanned field"
    assert scan(d["summary"]) == [], "summary must not echo the raw query into a safety-scanned field"
    assert BEL_HAL_QUERY not in d["bottom_line"]
    assert BEL_HAL_QUERY not in d["summary"]


def test_advisory_scanner_itself_still_correctly_flags_this_exact_phrase():
    """Proves the fix is in degraded_response()'s field content, not a
    weakening of the scanner — the same phrase, if it DID appear in
    generated text, must still be caught."""
    assert scan("Given the momentum, investors should continue holding BEL for now.") == ["hold"]


# ── 2 & 3. degraded_reason stays "capacity"; a safety hit cannot overwrite an existing failure ──

def _capacity_degraded_result(query: str) -> dict:
    """Exactly pipeline.py's own construction: parse_specialist_json("",
    query) on total provider exhaustion, folded into a minimal but
    realistic V3 result shape."""
    parsed, was_degraded = parse_specialist_json("", query)
    assert was_degraded is True
    assert parsed["_degraded_reason"] == "capacity"
    return {
        "query": query, "schema_version": "v3.1", "specialist": "comparison",
        "answer": {"bottom_line": parsed["bottom_line"], "summary": parsed["summary"], "sources_count": 0},
        "companies": [], "sectors": [], "related_events": [], "news": [], "policies": [],
        "degraded_reason": "capacity", "synthesis_incomplete": True,
    }


def test_capacity_reason_survives_finalize_v3_response_for_the_real_bel_hal_query():
    result = _capacity_degraded_result(BEL_HAL_QUERY)
    final = finalize_v3_response(BEL_HAL_QUERY, result, was_cached=False)
    assert final["degraded_reason"] == "capacity"
    assert final["synthesis_incomplete"] is True
    assert final["answer_availability"] == {
        "state": "temporarily_unavailable", "evidence_retrieval_completed": True, "evidence_count": 0, "reason": "provider_capacity", "basis": "none",
    }


def test_a_safety_hit_on_an_already_degraded_response_never_overwrites_the_original_reason():
    """Defense in depth, independent of the specific echoed-query bug:
    even if SOME other already-degraded response's text happens to trip
    the scanner, the original degraded_reason must survive."""
    result = {
        "query": "q", "schema_version": "v3.1", "specialist": "company",
        "answer": {"bottom_line": "Investors should continue holding this position.", "summary": "ok", "sources_count": 0},
        "companies": [], "sectors": [], "related_events": [], "news": [], "policies": [],
        "degraded_reason": "grounding_collapsed", "synthesis_incomplete": True,
    }
    final = finalize_v3_response("q", result, was_cached=False)
    assert final["degraded_reason"] == "grounding_collapsed"
    assert final["answer"]["bottom_line"] == "Investors should continue holding this position.", \
        "content is left as-is — this fix changes precedence, not sanitization"


def test_market_pulse_degraded_response_reason_also_cannot_be_overwritten_by_a_safety_hit():
    result = {
        "type": "market_pulse", "query": "top gainers today", "synthesis_incomplete": True,
        "market_status": {"status": "open"}, "indices": [],
        "market_summary": "Investors should continue holding through this volatility.",
        "sector_narrative": "", "leading_sectors": [], "lagging_sectors": [],
        "top_gainers": [], "top_losers": [], "ai_conclusion": "", "what_to_watch_next": [],
    }
    final = finalize_v3_response("top gainers today", result, was_cached=False)
    # Market Pulse's own degraded path never sets a degraded_reason at all
    # (see response_finalize.py's _derive_answer_availability comment) —
    # the invariant under test is simply that it stays absent/unchanged,
    # never promoted to "recommendation_language_violation".
    assert final.get("degraded_reason") != "recommendation_language_violation"
    assert final["synthesis_incomplete"] is True


# ── 4. A successful (non-degraded) unsafe answer still correctly degrades ──

_SUCCESSFUL_BUT_UNSAFE = {
    "schema_version": "v3.1", "response_id": "resp-unsafe",
    "specialist": "company",
    "answer": {"bottom_line": "HDFC Bank remains a solid buy candidate.", "summary": "ok", "sources_count": 1},
    "companies": [{"symbol": "HDFCBANK", "name": "HDFC Bank Ltd"}],
    "sectors": [], "related_events": [{"id": "e1"}], "news": [{"id": "n1"}], "policies": [],
    "synthesis_incomplete": False,
}


def test_a_successful_response_with_unsafe_language_still_becomes_recommendation_language_violation():
    """The exact original protection this gate exists for (2026-09-21
    incident) — proves the precedence fix didn't weaken this case."""
    final = finalize_v3_response("Should I invest in HDFC Bank?", dict(_SUCCESSFUL_BUT_UNSAFE), was_cached=False)
    assert final["synthesis_incomplete"] is True
    assert final["degraded_reason"] == "recommendation_language_violation"
    assert final["answer_availability"]["state"] == "limited_evidence"


# ── 5. All three HTTP routes ─────────────────────────────────────────────

def test_all_three_routes_preserve_capacity_over_a_safety_hit():
    capacity_result = _capacity_degraded_result(BEL_HAL_QUERY)

    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(dict(capacity_result), False)),
    ):
        r_search = client.post("/api/ai/search", json={"query": BEL_HAL_QUERY}).json()["result"]
        r_v3 = client.post("/api/ai/search/v3", json={"query": BEL_HAL_QUERY}).json()["result"]

    async def _fake_run_v3_steps(query, db, session_context=None):
        yield "intent", "Understanding your question", None
        yield "entities", "Detecting companies", None
        yield "evidence", "Collecting evidence", None
        yield "reasoning", "Running specialist analysis", None
        yield "finalizing", "Building investment decision", dict(capacity_result)

    with patch("app.services.ai_search.pipeline._run_v3_steps", new=_fake_run_v3_steps):
        with client.stream("GET", "/api/ai/search/stream", params={"q": BEL_HAL_QUERY}) as resp:
            body = "".join(resp.iter_text())
    import json as _json
    answer_line = next(line for line in body.splitlines() if line.startswith("data: ") and '"result"' in line)
    r_stream = _json.loads(answer_line[len("data: "):])["result"]

    for label, r in (("search", r_search), ("v3", r_v3), ("stream", r_stream)):
        assert r["degraded_reason"] == "capacity", label
        assert r["answer_availability"]["state"] == "temporarily_unavailable", label


# ── 6. Cached response finalization ─────────────────────────────────────

def test_cached_capacity_response_still_preserves_the_original_reason():
    capacity_result = _capacity_degraded_result(BEL_HAL_QUERY)
    final = finalize_v3_response(BEL_HAL_QUERY, dict(capacity_result), was_cached=True)
    assert final["degraded_reason"] == "capacity"
    assert final["answer_availability"]["state"] == "temporarily_unavailable"


# ── 7. No extra provider/retrieval/prediction calls ─────────────────────

def test_precedence_fix_makes_no_extra_provider_retrieval_or_prediction_call():
    capacity_result = _capacity_degraded_result(BEL_HAL_QUERY)
    with patch("app.services.ai_service._call_with_fallback", new=AsyncMock(side_effect=AssertionError("must not be called"))), \
         patch("app.services.ai_search.evidence.collect", new=AsyncMock(side_effect=AssertionError("must not be called"))), \
         patch("app.services.ai_search.response_finalize.asyncio.create_task", side_effect=AssertionError("must not record a prediction for a degraded response")):
        final = finalize_v3_response(BEL_HAL_QUERY, dict(capacity_result), was_cached=False)
    assert final["degraded_reason"] == "capacity"
