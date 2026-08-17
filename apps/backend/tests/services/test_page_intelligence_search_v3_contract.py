"""
Phase 6G Slice 3 — deterministic contract test for
page_intelligence_service.get_search_intelligence()'s V2->V3 migration,
no live LLM call. Stubs run_ai_search_v3's return shape and proves the
wrapper's own logic (unchanged by this migration) still produces the
same IntelligenceObject shape, and that in-memory caching still works.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import app.services.page_intelligence_service as pis


def _v3_response() -> dict:
    """Only the fields get_search_intelligence() actually reads --
    confirmed exhaustively by the migration audit."""
    return {
        "answer": {
            "summary": "TCS shows resilient margins amid IT sector headwinds.",
            "immediate_impact": "Near-term muted reaction expected.",
            "opportunities": ["Deal ramp-up in FY27", "Margin expansion via automation"],
            "risks": ["US client budget cuts", "Currency headwinds"],
        },
        "companies": [
            {"symbol": "TCS", "name": "TCS", "impact_type": "beneficiary", "reason": "Deal pipeline strength", "confidence": 78},
            {"symbol": "INFY", "name": "Infosys", "impact_type": "at_risk", "reason": "Client concentration", "confidence": 55},
        ],
        "sectors": [
            {"name": "IT", "positive": True, "score": 72, "outlook": "Cautiously optimistic"},
        ],
        "confidence_data": {
            "level": "Medium", "score": 61.5,
            "reasons": ["12 independent developments, corroborated by 15 sources"],
            "breakdown": {"evidence_quality": 60.0, "market_confirmation": 40.0, "historical_similarity": 30.0,
                          "data_freshness": 90.0, "reasoning_confidence": 70.0},
            "caveats": [],
        },
    }


@pytest.fixture(autouse=True)
def _clear_cache():
    pis._CACHE.clear()
    yield
    pis._CACHE.clear()


@pytest.mark.asyncio
async def test_get_search_intelligence_uses_v3_and_preserves_wrapper_shape():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(_v3_response(), False)),
    ):
        result = await pis.get_search_intelligence("What is the investment case for TCS?")

    assert result["market_story"] == "TCS shows resilient margins amid IT sector headwinds."
    assert result["key_takeaway"] == "Near-term muted reaction expected."
    assert len(result["opportunities"]) == 2
    assert result["opportunities"][0]["title"] == "Deal ramp-up in FY27"
    assert len(result["risks"]) == 2
    # monitoring_points reuses the RAW risk strings (not the reshaped
    # {title,description,severity} dicts risks[] holds) -- a real, if
    # slightly odd, pre-existing behavior this migration must preserve.
    assert result["monitoring_points"] == ["US client budget cuts", "Currency headwinds"]

    assert len(result["companies"]) == 2
    assert result["companies"][0]["symbol"] == "TCS"
    assert result["companies"][0]["stance"] == "bullish"  # beneficiary -> bullish
    assert result["companies"][1]["stance"] == "bearish"  # at_risk -> bearish

    assert len(result["sectors"]) == 1
    assert result["sectors"][0]["outlook"] == "positive"
    assert result["sectors"][0]["reason"] == "Cautiously optimistic"  # sector.outlook mapped to reason

    assert result["confidence"]["level"] == "Medium"
    assert result["confidence"]["score"] == 61.5
    assert result["confidence"]["breakdown"]["evidence_quality"] == 60.0  # the pipeline.py fix -- real breakdown, not {}

    assert result["context_type"] == "search"
    assert result["context_id"] == "What is the investment case for TCS?"


@pytest.mark.asyncio
async def test_get_search_intelligence_caches_across_calls():
    mock = AsyncMock(return_value=(_v3_response(), False))
    with patch("app.services.ai_search.pipeline.run_ai_search_v3", new=mock):
        first = await pis.get_search_intelligence("Same query text")
        second = await pis.get_search_intelligence("Same query text")

    assert mock.call_count == 1  # second call served from page_intelligence_service's own cache
    assert first == second


@pytest.mark.asyncio
async def test_get_search_intelligence_falls_back_cleanly_on_exception():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(side_effect=RuntimeError("simulated failure")),
    ):
        result = await pis.get_search_intelligence("A query that will fail")

    assert result["market_story"] == ""
    assert result["confidence"]["level"] == "Low"
    assert result["context_type"] == "search"


def test_v3_confidence_data_breakdown_is_wired_not_hardcoded_empty():
    """Structural guard for the accompanying pipeline.py fix: confidence_data
    ["breakdown"] must be built from confidence_breakdown's 5 real
    components, not left as the literal {} the audit found. A full live
    call already proves this end-to-end (test_p5_stage4_v3_live.py etc.);
    this catches a future revert without needing the full pipeline/LLM."""
    import inspect
    from app.services.ai_search import pipeline
    source = inspect.getsource(pipeline._assemble_response)
    assert '"breakdown": {},' not in source
    for key in ("evidence_quality", "market_confirmation", "historical_similarity",
                "data_freshness", "reasoning_confidence"):
        assert f'confidence_breakdown["{key}"]' in source


@pytest.mark.asyncio
async def test_no_v2_import_remains_in_get_search_intelligence():
    """Structural guard: confirms the migration actually happened, not
    just that the new path also happens to work. Checks the real import
    statement, not the docstring (which legitimately mentions V2's old
    module name as migration history)."""
    import inspect
    source = inspect.getsource(pis.get_search_intelligence)
    assert "from app.services.ai_search.pipeline import run_ai_search_v3" in source
    assert "from app.services.ai_search_service import run_ai_search" not in source
