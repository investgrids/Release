"""6G Cutover Gate, Step 1 — shared AI Search instrumentation.

Proves two things:
1. The relocation is behavior-preserving: `/api/ai/search` (and the
   `get_search_stats()` shape app/api/publishing.py::ops_overview depends on)
   tick exactly as before the counters moved out of app/api/ai_search.py.
   Updated for the later compatibility-wrapper slice, which changed what
   `/api/ai/search` calls internally (run_ai_search_v3, not V2's own
   run_ai_search) without changing this instrumentation contract at all —
   these tests now mock the new call site.
2. The actual fix: `/api/ai/search/v3` and `/api/ai/search/stream` report
   into the *same* counters `/api/ai/search` does — the Ops Dashboard's
   "AI Search" card doesn't go blind to traffic from any of the 3 routes.

No live LLM calls -- run_ai_search_v3 / _run_v3_steps are mocked; only the
instrumentation contract is under test.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_search import instrumentation as ai_search_stats

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _reset_stats():
    ai_search_stats._reset_for_tests()
    yield
    ai_search_stats._reset_for_tests()


def _v3_result() -> dict:
    return {"answer": {"summary": "ok"}, "response_id": "r-1"}


# ── Module-level unit tests ─────────────────────────────────────────────────

def test_record_success_and_get_stats_math():
    ai_search_stats.record_query()
    ai_search_stats.record_success(100.0)
    ai_search_stats.record_query()
    ai_search_stats.record_success(300.0)
    stats = ai_search_stats.get_stats()
    assert stats["total_today"] == 2
    assert stats["avg_response_ms"] == 200.0
    assert stats["success_rate"] == 100.0


def test_cache_hits_excluded_from_latency_denominator():
    ai_search_stats.record_query()
    ai_search_stats.record_cache_hit()
    ai_search_stats.record_query()
    ai_search_stats.record_success(150.0)
    stats = ai_search_stats.get_stats()
    assert stats["total_today"] == 2
    assert stats["cache_hits"] == 1
    # resolved = total - cache_hits = 1, so avg is over the one real call
    assert stats["avg_response_ms"] == 150.0


def test_timeout_detection_matches_original_v2_logic():
    ai_search_stats.record_query()
    ai_search_stats.record_error(TimeoutError("slow"))
    ai_search_stats.record_query()
    ai_search_stats.record_error(RuntimeError("Upstream request timeout"))
    ai_search_stats.record_query()
    ai_search_stats.record_error(RuntimeError("plain failure"))
    stats = ai_search_stats.get_stats()
    assert stats["errors"] == 3
    assert stats["timeouts"] == 2  # TimeoutError instance + "timeout" substring match


# ── V2 route: behavior-preservation contract ────────────────────────────────

def test_v2_route_still_ticks_query_and_success():
    """6G Cutover Gate compatibility-wrapper slice: /api/ai/search now
    delegates to run_ai_search_v3 internally (V2's own generation logic is
    no longer called here) -- the instrumentation contract this test
    guards is the route's, not any particular pipeline's, so it's updated
    to mock the new call site rather than deleted."""
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(_v3_result(), False)),
    ):
        resp = client.post("/api/ai/search", json={"query": "TCS outlook next quarter"})
    assert resp.status_code == 200
    stats = ai_search_stats.get_stats()
    assert stats["total_today"] == 1
    assert stats["cache_hits"] == 0
    assert stats["errors"] == 0


def test_v2_route_still_ticks_error():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        resp = client.post("/api/ai/search", json={"query": "TCS outlook next quarter"})
    assert resp.status_code == 500
    stats = ai_search_stats.get_stats()
    assert stats["total_today"] == 1
    assert stats["errors"] == 1


def test_v2_route_ticks_cache_hit():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(_v3_result(), True)),
    ):
        resp = client.post("/api/ai/search", json={"query": "TCS outlook next quarter"})
    assert resp.status_code == 200
    stats = ai_search_stats.get_stats()
    assert stats["cache_hits"] == 1


def test_get_search_stats_import_path_unchanged():
    """app/api/publishing.py::ops_overview imports get_search_stats from
    app.api.ai_search by name -- confirm that path still resolves and
    returns the shared module's data, not a stale local dict."""
    from app.api.ai_search import get_search_stats
    ai_search_stats.record_query()
    ai_search_stats.record_success(50.0)
    assert get_search_stats()["total_today"] == 1


# ── V3 JSON route: the actual fix ───────────────────────────────────────────

def test_v3_json_route_now_ticks_shared_stats():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(_v3_result(), False)),
    ):
        resp = client.post("/api/ai/search/v3", json={"query": "TCS vs Infosys"})
    assert resp.status_code == 200
    stats = ai_search_stats.get_stats()
    assert stats["total_today"] == 1
    assert stats["cache_hits"] == 0  # was_cached=False -> success, not a cache hit


def test_v3_json_route_cache_hit_ticks_cache_hits_not_latency():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(_v3_result(), True)),
    ):
        resp = client.post("/api/ai/search/v3", json={"query": "TCS vs Infosys"})
    assert resp.status_code == 200
    stats = ai_search_stats.get_stats()
    assert stats["cache_hits"] == 1


def test_v3_json_route_error_ticks_shared_errors():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(side_effect=RuntimeError("provider exhausted")),
    ):
        resp = client.post("/api/ai/search/v3", json={"query": "TCS vs Infosys"})
    assert resp.status_code == 500
    stats = ai_search_stats.get_stats()
    assert stats["errors"] == 1


# ── V3 SSE route: the actual fix, streaming variant ─────────────────────────

async def _fake_steps_success(query, db, session_context):
    yield "evidence", "Gathering evidence", None
    yield "reasoning", "Reasoning", None
    yield "done", "Finalizing", {"answer": {"summary": "ok"}, "response_id": "r-2"}


async def _fake_steps_cache_hit(query, db, session_context):
    yield "done", "Finalizing", {"answer": {"summary": "ok"}, "response_id": "r-3"}


async def _fake_steps_error(query, db, session_context):
    yield "evidence", "Gathering evidence", None
    raise RuntimeError("stream failure")


def test_v3_stream_route_ticks_shared_stats_on_success():
    with patch("app.services.ai_search.pipeline._run_v3_steps", new=_fake_steps_success):
        with client.stream("GET", "/api/ai/search/stream", params={"q": "TCS outlook"}) as resp:
            events = list(resp.iter_lines())
    assert any("event: answer" in e for e in events)
    stats = ai_search_stats.get_stats()
    assert stats["total_today"] == 1
    assert stats["cache_hits"] == 0


def test_v3_stream_route_ticks_cache_hit():
    with patch("app.services.ai_search.pipeline._run_v3_steps", new=_fake_steps_cache_hit):
        with client.stream("GET", "/api/ai/search/stream", params={"q": "TCS outlook"}) as resp:
            list(resp.iter_lines())
    stats = ai_search_stats.get_stats()
    assert stats["cache_hits"] == 1


def test_v3_stream_route_ticks_error():
    with patch("app.services.ai_search.pipeline._run_v3_steps", new=_fake_steps_error):
        with client.stream("GET", "/api/ai/search/stream", params={"q": "TCS outlook"}) as resp:
            events = list(resp.iter_lines())
    assert any("event: error" in e for e in events)
    stats = ai_search_stats.get_stats()
    assert stats["errors"] == 1
