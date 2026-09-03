"""
CD3-D (D6) — deepseek_provider.py's _safe_json_call fallback dicts used to
be byte-identical in shape to a real success: nothing distinguished a
genuine AI-generated classification/summary/impact-analysis from static
exception-path boilerplate, at any layer. Confirmed still open by both
the CD3-C and CD3-D audits (finding #5 in the CD3-D report).

_safe_json_call now returns (value, integrity_status); every dict-shaped
caller (classify_event/generate_radar/summarize_event/
generate_impact_analysis/generate_graph) attaches the tag onto its
result. List-shaped callers (extract_companies/extract_sectors/
generate_timeline/find_similar_events) fall back to [] only -- already
self-evidently honest, no tag needed.

Pure unit tests against DeepSeekProvider directly (mocking _chat), same
convention as this module's sibling suites.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.deepseek_provider import DeepSeekProvider
from app.services.measurement_semantics import IntegrityStatus


def _provider() -> DeepSeekProvider:
    return DeepSeekProvider(api_key="test-key")


@pytest.mark.asyncio
async def test_classify_event_real_success_tags_valid():
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(return_value='{"category": "corporate", "confidence": 0.9, "subcategory": "capex"}')):
        result = await provider.classify_event("Some real event text")
    assert result["integrity_status"] == IntegrityStatus.VALID.value
    assert result["category"] == "corporate"


@pytest.mark.asyncio
async def test_classify_event_provider_failure_tags_fallback():
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(side_effect=RuntimeError("provider down"))):
        result = await provider.classify_event("Some event")
    assert result["integrity_status"] == IntegrityStatus.FALLBACK.value
    # The fallback's own placeholder content is still exactly what it was
    # before this change -- D6 tags the fallback, it doesn't change it.
    assert result["category"] == "macro"
    assert result["confidence"] == 0.7


@pytest.mark.asyncio
async def test_summarize_event_fallback_is_tagged():
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(side_effect=RuntimeError("provider down"))):
        result = await provider.summarize_event("Test Title", "Test body text", "Test Source")
    assert result["integrity_status"] == IntegrityStatus.FALLBACK.value
    assert result["summary"] == "Test Title"


@pytest.mark.asyncio
async def test_generate_impact_analysis_fallback_is_tagged():
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(side_effect=RuntimeError("provider down"))):
        result = await provider.generate_impact_analysis("Title", "text", [], [])
    assert result["integrity_status"] == IntegrityStatus.FALLBACK.value
    assert result["analysis"]["bull_case"] == "Positive fundamentals could drive upside."


@pytest.mark.asyncio
async def test_generate_impact_analysis_real_success_tags_valid():
    provider = _provider()
    fake = '{"impact_score": 75, "confidence": 80, "market_reaction": {"short_term": "bullish", "medium_term": "neutral", "volatility": "low", "sentiment": "positive"}, "analysis": {"bull_case": "real bull case", "bear_case": "real bear case", "base_case": "real base case", "key_risks": [], "catalysts": []}}'
    with patch.object(provider, "_chat", new=AsyncMock(return_value=fake)):
        result = await provider.generate_impact_analysis("Title", "text", [], [])
    assert result["integrity_status"] == IntegrityStatus.VALID.value
    assert result["analysis"]["bull_case"] == "real bull case"


@pytest.mark.asyncio
async def test_generate_graph_fallback_is_tagged():
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(side_effect=RuntimeError("provider down"))):
        result = await provider.generate_graph("Title", [], [])
    assert result["integrity_status"] == IntegrityStatus.FALLBACK.value
    assert result["nodes"] == []
    assert result["edges"] == []


@pytest.mark.asyncio
async def test_generate_graph_malformed_json_shape_also_tagged_fallback():
    """_parse_json succeeding but returning a non-dict (e.g. the model
    wrapped its JSON array wrong) must still resolve to the fallback
    shape, tagged -- not silently return whatever malformed value it got."""
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(return_value="[1, 2, 3]")):
        result = await provider.generate_graph("Title", [], [])
    assert result["integrity_status"] == IntegrityStatus.FALLBACK.value
    assert result["nodes"] == []
    assert result["edges"] == []


@pytest.mark.asyncio
async def test_list_shaped_callers_still_return_plain_lists_on_fallback():
    """extract_companies/extract_sectors/generate_timeline/find_similar_events
    never got a tag added (a list can't carry a scalar field, and their
    only fallback is [] -- already self-evidently honest). Confirms the
    tuple-unpacking refactor didn't change their public return shape."""
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(side_effect=RuntimeError("provider down"))):
        companies = await provider.extract_companies("Title", "text")
        sectors = await provider.extract_sectors("Title", "text")
        timeline = await provider.generate_timeline("Title", "text", "macro")
    assert companies == []
    assert sectors == []
    assert timeline == []


@pytest.mark.asyncio
async def test_extract_companies_real_success_returns_plain_list_no_tag_leak():
    provider = _provider()
    fake = '[{"symbol": "RELIANCE", "name": "Reliance Industries", "impact_type": "beneficiary", "reason": "test", "impact_score": 7.0}]'
    with patch.object(provider, "_chat", new=AsyncMock(return_value=fake)):
        result = await provider.extract_companies("Title", "text")
    assert result == [{"symbol": "RELIANCE", "name": "Reliance Industries", "impact_type": "beneficiary", "reason": "test", "impact_score": 7.0}]
    assert "integrity_status" not in result[0]
