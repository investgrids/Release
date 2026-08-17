"""
6G Cutover Gate — compatibility-wrapper rehearsal.

POST /api/ai/search (V2's original route) no longer calls V2's own
generation logic (app.services.ai_search_service.run_ai_search) at all --
it's a thin adapter over the canonical run_ai_search_v3 core now. These
tests prove the external contract ({query, cached, result}) still holds
exactly as before for any caller of this route, while the content comes
from V3. Deterministic -- run_ai_search_v3 is mocked, no live LLM calls.
"""
from __future__ import annotations

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


def _rich_v3_response() -> dict:
    """A realistic, V3-shaped response -- includes fields V2's response
    never had (schema_version, response_id, decision_intelligence.
    entity_analyses) to prove the wrapper passes the richer shape through
    unchanged rather than stripping it down to a V2-only subset."""
    return {
        "schema_version": "v3.1",
        "response_id": "resp-abc123",
        "specialist": "comparison",
        "answer": {"summary": "TCS, Infosys, and Wipro compared.", "confidence": 62},
        "companies": [
            {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "impact_type": "neutral"},
            {"symbol": "INFY", "name": "Infosys Ltd", "impact_type": "neutral"},
            {"symbol": "WIPRO", "name": "Wipro Ltd", "impact_type": "neutral"},
        ],
        "decision_intelligence": {
            "intent": "compare_multi",
            "entity_analyses": [
                {"entity": "Tata Consultancy Services Ltd", "symbol": "TCS", "thesis": "x"},
                {"entity": "Infosys Ltd", "symbol": "INFY", "thesis": "y"},
                {"entity": "Wipro Ltd", "symbol": "WIPRO", "thesis": "z"},
            ],
        },
        "confidence_data": {"level": "Medium", "score": 62.0},
    }


def test_wrapper_returns_v3_content_in_v2_envelope():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(_rich_v3_response(), False)),
    ):
        resp = client.post("/api/ai/search", json={"query": "Compare TCS, Infosys, and Wipro as investments."})
    assert resp.status_code == 200
    body = resp.json()

    # Envelope shape unchanged -- exactly {query, cached, result}, nothing added.
    assert set(body.keys()) == {"query", "cached", "result"}
    assert body["query"] == "Compare TCS, Infosys, and Wipro as investments."
    assert body["cached"] is False

    # The richer V3 shape passes through completely unstripped -- the
    # whole point of the wrapper is NOT to lossily downgrade the content.
    assert body["result"]["schema_version"] == "v3.1"
    assert body["result"]["response_id"] == "resp-abc123"
    assert len(body["result"]["decision_intelligence"]["entity_analyses"]) == 3
    assert {c["symbol"] for c in body["result"]["companies"]} == {"TCS", "INFY", "WIPRO"}


def test_wrapper_reports_cache_hit_from_v3():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(_rich_v3_response(), True)),
    ):
        resp = client.post("/api/ai/search", json={"query": "Compare TCS, Infosys, and Wipro as investments."})
    assert resp.status_code == 200
    assert resp.json()["cached"] is True


def test_wrapper_propagates_errors():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(side_effect=RuntimeError("provider exhausted")),
    ):
        resp = client.post("/api/ai/search", json={"query": "TCS outlook"})
    assert resp.status_code == 500


def test_wrapper_rejects_empty_query_before_calling_v3():
    mock = AsyncMock()
    with patch("app.services.ai_search.pipeline.run_ai_search_v3", new=mock):
        resp = client.post("/api/ai/search", json={"query": "  "})
    assert resp.status_code in (400, 422)  # min_length=3 on the Pydantic field, or the explicit strip-check
    mock.assert_not_called()


def test_no_v2_generation_logic_imported_by_this_route():
    """Structural guard: confirms the wrapper conversion actually happened
    (V2's own run_ai_search is not imported into this module at all), not
    just that the new path also happens to work."""
    import app.api.ai_search as route_module
    assert not hasattr(route_module, "run_ai_search")
    import inspect
    source = inspect.getsource(route_module.ai_search)
    assert "run_ai_search_v3" in source
    assert "ai_search_service" not in source
