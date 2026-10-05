"""
Proves /api/ai/search, /api/ai/search/v3, and /api/ai/search/stream all
run their response through the exact same finalize_v3_response — not
three independently-wired copies of "safety gate + AEV2" that could
silently drift apart. Mocks run_ai_search_v3 / _run_v3_steps at the same
boundary test_ai_search_v2_wrapper_contract.py already uses (no live
LLM, no live DB) so this is purely about whether the routes route
correctly, not about pipeline internals (those are covered by
test_ai_search_single_pipeline_runtime.py).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_search import instrumentation as ai_search_stats

client = TestClient(app, raise_server_exceptions=False)

_ADVISORY_RESPONSE = {
    "schema_version": "v3.1", "response_id": "resp-shared-finalizer",
    "specialist": "company",
    "answer": {"bottom_line": "HDFC Bank remains a solid buy candidate.", "summary": "ok", "sources_count": 0},
    "companies": [], "sectors": [], "related_events": [], "news": [], "policies": [],
}


def setup_function(_fn):
    ai_search_stats._reset_for_tests()


def teardown_function(_fn):
    ai_search_stats._reset_for_tests()


def test_search_route_degrades_advisory_language_via_the_shared_gate():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(dict(_ADVISORY_RESPONSE), False)),
    ):
        resp = client.post("/api/ai/search", json={"query": "Should I invest in HDFC Bank?"})
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["synthesis_incomplete"] is True
    assert result["degraded_reason"] == "recommendation_language_violation"


def test_search_v3_route_degrades_the_identical_advisory_language():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(dict(_ADVISORY_RESPONSE), False)),
    ):
        resp = client.post("/api/ai/search/v3", json={"query": "Should I invest in HDFC Bank?"})
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["synthesis_incomplete"] is True
    assert result["degraded_reason"] == "recommendation_language_violation"


def test_search_stream_route_degrades_the_identical_advisory_language():
    async def _fake_run_v3_steps(query, db, session_context=None):
        yield "intent", "Understanding your question", None
        yield "entities", "Detecting companies", None
        yield "evidence", "Collecting evidence", None
        yield "reasoning", "Running specialist analysis", None
        yield "finalizing", "Building investment decision", dict(_ADVISORY_RESPONSE)

    with patch("app.services.ai_search.pipeline._run_v3_steps", new=_fake_run_v3_steps):
        with client.stream(
            "GET", "/api/ai/search/stream", params={"q": "Should I invest in HDFC Bank?"},
        ) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())

    assert "event: answer" in body
    import json as _json
    answer_line = next(line for line in body.splitlines() if line.startswith("data: ") and '"result"' in line)
    envelope = _json.loads(answer_line[len("data: "):])
    result = envelope["result"]
    assert result["synthesis_incomplete"] is True
    assert result["degraded_reason"] == "recommendation_language_violation"


def test_all_three_routes_produce_byte_identical_degraded_answer_shapes():
    """The strongest form of "same finalizer": not just that each route
    independently degrades, but that the resulting `answer` sub-shape is
    identical across all three — proving one shared code path, not three
    routes that each happen to reach the same conclusion differently."""
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(dict(_ADVISORY_RESPONSE), False)),
    ):
        r1 = client.post("/api/ai/search", json={"query": "Should I invest in HDFC Bank?"}).json()["result"]
        r2 = client.post("/api/ai/search/v3", json={"query": "Should I invest in HDFC Bank?"}).json()["result"]

    assert r1["answer"] == r2["answer"]
    assert r1["degraded_reason"] == r2["degraded_reason"] == "recommendation_language_violation"


# ── Internal-only attribution plumbing ("announcements") never reaches an
# actual HTTP response, on any of the three routes, cached or fresh. ───────

_CLEAN_RESPONSE_WITH_ANNOUNCEMENTS = {
    "schema_version": "v3.1", "response_id": "resp-announcements-leak-check",
    "specialist": "company",
    "answer": {"bottom_line": "Reliance Industries reported strong results.", "summary": "ok", "sources_count": 1},
    "companies": [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}],
    "sectors": [], "related_events": [], "news": [], "policies": [],
    "announcements": [{"id": "a1", "symbol": "RELIANCE", "subject": "Board approves capex plan"}],
}


def _assert_no_announcement_leak(body: dict) -> None:
    assert "announcements" not in body
    serialized = str(body)
    assert "Board approves capex plan" not in serialized, "internal announcement content leaked into the HTTP response"


def test_search_route_never_leaks_internal_announcements():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(dict(_CLEAN_RESPONSE_WITH_ANNOUNCEMENTS), False)),
    ):
        resp = client.post("/api/ai/search", json={"query": "Should I invest in Reliance Industries?"})
    assert resp.status_code == 200
    _assert_no_announcement_leak(resp.json()["result"])


def test_search_v3_route_never_leaks_internal_announcements():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(dict(_CLEAN_RESPONSE_WITH_ANNOUNCEMENTS), False)),
    ):
        resp = client.post("/api/ai/search/v3", json={"query": "Should I invest in Reliance Industries?"})
    assert resp.status_code == 200
    _assert_no_announcement_leak(resp.json()["result"])


def test_search_v3_route_never_leaks_internal_announcements_on_a_cache_hit():
    """was_cached=True — the branch that proves the CACHED object may
    carry the internal field, but what's returned to THIS caller never
    does."""
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(dict(_CLEAN_RESPONSE_WITH_ANNOUNCEMENTS), True)),
    ):
        resp = client.post("/api/ai/search/v3", json={"query": "Should I invest in Reliance Industries?"})
    assert resp.status_code == 200
    assert resp.json()["cached"] is True
    _assert_no_announcement_leak(resp.json()["result"])


def test_search_stream_route_never_leaks_internal_announcements():
    async def _fake_run_v3_steps(query, db, session_context=None):
        yield "intent", "Understanding your question", None
        yield "entities", "Detecting companies", None
        yield "evidence", "Collecting evidence", None
        yield "reasoning", "Running specialist analysis", None
        yield "finalizing", "Building investment decision", dict(_CLEAN_RESPONSE_WITH_ANNOUNCEMENTS)

    with patch("app.services.ai_search.pipeline._run_v3_steps", new=_fake_run_v3_steps):
        with client.stream(
            "GET", "/api/ai/search/stream", params={"q": "Should I invest in Reliance Industries?"},
        ) as resp:
            assert resp.status_code == 200
            body_text = "".join(resp.iter_text())

    import json as _json
    answer_line = next(line for line in body_text.splitlines() if line.startswith("data: ") and '"result"' in line)
    envelope = _json.loads(answer_line[len("data: "):])
    _assert_no_announcement_leak(envelope["result"])
    assert "Board approves capex plan" not in body_text, "internal announcement content leaked into the raw SSE stream"
