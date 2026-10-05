"""
answer_availability (2026-09-23, Phase 1.2) — the backend's own honest
account of WHY a response has limited or no evidence, so the frontend
never again infers "no evidence exists" from an empty array alone (an
empty related_events/news/policies list can just as easily mean
retrieval itself never completed, e.g. a provider/capacity failure).

Two layers: (1) the pure derivation function's own branch coverage, and
(2) proof that all three real routes (/search, /search/v3, /search/stream)
attach the identical field via the one shared finalizer — same pattern
as test_ai_search_shared_finalizer_routes.py.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_search.response_finalize import _derive_answer_availability, finalize_v3_response

client = TestClient(app, raise_server_exceptions=False)


def _core(avail: dict) -> dict:
    """The three original answer_availability fields. Step 4C added `reason` and `basis` (covered in test_ai_search_response_semantics.py); these tests guard that the original three are unchanged."""
    return {k: avail[k] for k in ("state", "evidence_retrieval_completed", "evidence_count")}

# ── 1. Pure function branch coverage ──────────────────────────────────────

_BASE_RESEARCH = {
    "schema_version": "v3.1", "response_id": "resp-availability",
    "answer": {"bottom_line": "Reliance reported strong results.", "summary": "ok", "sources_count": 2},
    "companies": [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}],
    "sectors": [], "related_events": [{"id": "e1"}], "news": [{"id": "n1"}], "policies": [],
}


def test_available_when_synthesis_completed():
    result = {**_BASE_RESEARCH, "synthesis_incomplete": False}
    avail = _derive_answer_availability(result, is_market_pulse=False)
    assert _core(avail) == {"state": "available", "evidence_retrieval_completed": True, "evidence_count": 2}


def test_available_with_zero_evidence_is_still_available_not_no_verified_evidence():
    """A real, successful synthesis over genuinely thin/zero evidence is
    NOT the same failure mode as retrieval never completing — synthesis_
    incomplete is the only gate; `available` with evidence_count=0 is a
    legitimate, honest state (a thin but real answer)."""
    result = {**_BASE_RESEARCH, "related_events": [], "news": [], "synthesis_incomplete": False}
    avail = _derive_answer_availability(result, is_market_pulse=False)
    assert avail["state"] == "available"
    assert avail["evidence_count"] == 0


def test_pre_retrieval_reasons_map_to_no_verified_evidence_with_retrieval_not_completed():
    for reason in ("referential_no_context", "ambiguous_entity", "unsupported_entity"):
        result = {
            "synthesis_incomplete": True, "degraded_reason": reason,
            "related_events": [], "news": [], "policies": [],
        }
        avail = _derive_answer_availability(result, is_market_pulse=False)
        assert _core(avail) == {"state": "no_verified_evidence", "evidence_retrieval_completed": False, "evidence_count": 0}, reason


def test_capacity_and_parse_failure_map_to_temporarily_unavailable_even_with_real_evidence():
    """The exact conflation this contract exists to prevent: a provider/
    LLM failure must never be reported as 'no evidence exists', even
    when real evidence happens to already be sitting in the response."""
    for reason in ("capacity", "parse_failure"):
        result = {
            "synthesis_incomplete": True, "degraded_reason": reason,
            "related_events": [{"id": "e1"}], "news": [{"id": "n1"}], "policies": [],
        }
        avail = _derive_answer_availability(result, is_market_pulse=False)
        assert _core(avail) == {"state": "temporarily_unavailable", "evidence_retrieval_completed": True, "evidence_count": 2}, reason


def test_capacity_with_zero_evidence_is_still_temporarily_unavailable_not_no_verified_evidence():
    result = {
        "synthesis_incomplete": True, "degraded_reason": "capacity",
        "related_events": [], "news": [], "policies": [],
    }
    avail = _derive_answer_availability(result, is_market_pulse=False)
    assert avail["state"] == "temporarily_unavailable"
    assert avail["evidence_retrieval_completed"] is True
    assert avail["evidence_count"] == 0


def test_grounding_collapsed_with_real_evidence_is_limited_evidence():
    result = {
        "synthesis_incomplete": True, "degraded_reason": "grounding_collapsed",
        "related_events": [{"id": "e1"}], "news": [], "policies": [{"id": "p1"}],
    }
    avail = _derive_answer_availability(result, is_market_pulse=False)
    assert _core(avail) == {"state": "limited_evidence", "evidence_retrieval_completed": True, "evidence_count": 2}


def test_multi_entity_partial_with_real_evidence_is_limited_evidence():
    result = {
        "synthesis_incomplete": True, "degraded_reason": "multi_entity_partial",
        "related_events": [{"id": "e1"}], "news": [{"id": "n1"}], "policies": [],
    }
    avail = _derive_answer_availability(result, is_market_pulse=False)
    assert avail["state"] == "limited_evidence"


def test_recommendation_language_violation_with_real_evidence_is_limited_evidence():
    """The safety-gate rebuild (safety_gate.build_v3_safety_degraded_
    response) goes through build_degraded_shape's explicit field
    whitelist — this proves evidence_count is still read correctly off
    that reconstructed shape, not silently zeroed by the rebuild."""
    result = {
        "synthesis_incomplete": True, "degraded_reason": "recommendation_language_violation",
        "related_events": [{"id": "e1"}], "news": [{"id": "n1"}], "policies": [{"id": "p1"}],
    }
    avail = _derive_answer_availability(result, is_market_pulse=False)
    assert _core(avail) == {"state": "limited_evidence", "evidence_retrieval_completed": True, "evidence_count": 3}


def test_a_degraded_reason_with_genuinely_zero_evidence_is_no_verified_evidence_not_limited():
    """grounding_collapsed etc. CAN legitimately have zero surviving
    evidence — must not be misreported as 'limited' (which implies real
    evidence is being shown)."""
    result = {
        "synthesis_incomplete": True, "degraded_reason": "grounding_collapsed",
        "related_events": [], "news": [], "policies": [],
    }
    avail = _derive_answer_availability(result, is_market_pulse=False)
    assert _core(avail) == {"state": "no_verified_evidence", "evidence_retrieval_completed": True, "evidence_count": 0}


def test_unrecognized_degraded_reason_fails_closed_to_limited_evidence_or_no_verified_evidence_never_available():
    """A future degraded_reason this function doesn't yet know about
    must never resolve to 'available' — the one mistake this contract
    exists to prevent."""
    result = {
        "synthesis_incomplete": True, "degraded_reason": "some_future_reason_not_yet_mapped",
        "related_events": [{"id": "e1"}], "news": [], "policies": [],
    }
    avail = _derive_answer_availability(result, is_market_pulse=False)
    assert avail["state"] != "available"


# ── Market Pulse ────────────────────────────────────────────────────────

def test_market_pulse_available_when_synthesis_completed():
    result = {"type": "market_pulse", "synthesis_incomplete": False, "market_status": {"status": "open"}, "indices": [{"name": "NIFTY"}]}
    avail = _derive_answer_availability(result, is_market_pulse=True)
    assert _core(avail) == {"state": "available", "evidence_retrieval_completed": True, "evidence_count": 1}


def test_market_pulse_degraded_is_temporarily_unavailable_never_no_verified_evidence():
    """Market Pulse's only degraded path is an LLM narrative failure over
    real, already-fetched market data — there is no honest 'zero
    evidence' state for market-wide data."""
    result = {
        "type": "market_pulse", "synthesis_incomplete": True,
        "market_status": {"status": "open"}, "indices": [{"name": "NIFTY"}], "top_gainers": [{"ticker": "TCS"}],
    }
    avail = _derive_answer_availability(result, is_market_pulse=True)
    assert avail["state"] == "temporarily_unavailable"
    assert avail["evidence_retrieval_completed"] is True
    assert avail["evidence_count"] == 2


def test_market_pulse_degraded_with_failed_data_fetch_still_temporarily_unavailable():
    result = {"type": "market_pulse", "synthesis_incomplete": True, "market_status": {}}
    avail = _derive_answer_availability(result, is_market_pulse=True)
    assert avail["state"] == "temporarily_unavailable"
    assert avail["evidence_retrieval_completed"] is False


# ── 2. Route-level wiring — same pattern as test_ai_search_shared_finalizer_routes.py ──

_AVAILABLE_RESPONSE = {
    "schema_version": "v3.1", "response_id": "resp-availability-route",
    "specialist": "company",
    "answer": {"bottom_line": "Reliance Industries reported strong results.", "summary": "ok", "sources_count": 1},
    "companies": [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}],
    "sectors": [], "related_events": [{"id": "e1"}], "news": [], "policies": [],
    "synthesis_incomplete": False,
}

_CAPACITY_DEGRADED_RESPONSE = {
    "schema_version": "v3.1", "response_id": "resp-availability-capacity",
    "specialist": "company",
    "answer": {"bottom_line": "", "summary": "", "sources_count": 0},
    "companies": [], "sectors": [], "related_events": [{"id": "e1"}], "news": [], "policies": [],
    "synthesis_incomplete": True, "degraded_reason": "capacity",
}


def test_search_v3_route_attaches_answer_availability_on_success():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(dict(_AVAILABLE_RESPONSE), False)),
    ):
        resp = client.post("/api/ai/search/v3", json={"query": "Should I invest in Reliance Industries?"})
    assert resp.status_code == 200
    avail = resp.json()["result"]["answer_availability"]
    assert _core(avail) == {"state": "available", "evidence_retrieval_completed": True, "evidence_count": 1}


def test_search_route_attaches_temporarily_unavailable_on_capacity_failure():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(dict(_CAPACITY_DEGRADED_RESPONSE), False)),
    ):
        resp = client.post("/api/ai/search", json={"query": "Should I invest in Reliance Industries?"})
    assert resp.status_code == 200
    avail = resp.json()["result"]["answer_availability"]
    assert avail["state"] == "temporarily_unavailable"
    assert avail["evidence_retrieval_completed"] is True


def test_search_stream_route_attaches_the_identical_availability():
    async def _fake_run_v3_steps(query, db, session_context=None):
        yield "intent", "Understanding your question", None
        yield "entities", "Detecting companies", None
        yield "evidence", "Collecting evidence", None
        yield "reasoning", "Running specialist analysis", None
        yield "finalizing", "Building investment decision", dict(_CAPACITY_DEGRADED_RESPONSE)

    with patch("app.services.ai_search.pipeline._run_v3_steps", new=_fake_run_v3_steps):
        with client.stream(
            "GET", "/api/ai/search/stream", params={"q": "Should I invest in Reliance Industries?"},
        ) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())

    import json as _json
    answer_line = next(line for line in body.splitlines() if line.startswith("data: ") and '"result"' in line)
    envelope = _json.loads(answer_line[len("data: "):])
    assert envelope["result"]["answer_availability"]["state"] == "temporarily_unavailable"


def test_all_three_routes_produce_byte_identical_availability():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(dict(_CAPACITY_DEGRADED_RESPONSE), False)),
    ):
        r1 = client.post("/api/ai/search", json={"query": "Should I invest in Reliance Industries?"}).json()["result"]
        r2 = client.post("/api/ai/search/v3", json={"query": "Should I invest in Reliance Industries?"}).json()["result"]
    assert r1["answer_availability"] == r2["answer_availability"]


def test_cached_response_still_gets_freshly_derived_availability_not_a_stale_cached_value():
    """was_cached=True — proves this is computed at SERVE time from
    `result`'s own current content, never something baked into the
    cached object itself (which would let a stale value survive)."""
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(dict(_AVAILABLE_RESPONSE), True)),
    ):
        resp = client.post("/api/ai/search/v3", json={"query": "Should I invest in Reliance Industries?"})
    assert resp.json()["cached"] is True
    assert resp.json()["result"]["answer_availability"]["state"] == "available"


# ── 3. No additional provider/retrieval/prediction call ────────────────

def test_finalize_v3_response_makes_no_llm_or_retrieval_call_deriving_availability():
    """_derive_answer_availability is pure dict inspection — this proves
    the finalizer's new step doesn't sneak in a retrieval or LLM call to
    compute it."""
    with patch("app.services.ai_service._call_with_fallback", new=AsyncMock(side_effect=AssertionError("must not be called"))), \
         patch("app.services.ai_search.evidence.collect", new=AsyncMock(side_effect=AssertionError("must not be called"))):
        result = finalize_v3_response("Should I invest in Reliance Industries?", dict(_CAPACITY_DEGRADED_RESPONSE), was_cached=False)
    assert result["answer_availability"]["state"] == "temporarily_unavailable"
