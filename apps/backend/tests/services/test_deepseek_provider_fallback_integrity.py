"""
CD3-D (D6) — deepseek_provider.py's _safe_json_call fallback dicts used to
be byte-identical in shape to a real success: nothing distinguished a
genuine AI-generated classification/summary/impact-analysis from static
exception-path boilerplate, at any layer. Confirmed still open by both
the CD3-C and CD3-D audits (finding #5 in the CD3-D report).

_safe_json_call now returns (value, integrity_status); every dict-shaped
caller (classify_event/generate_radar/summarize_event/
generate_impact_analysis/generate_graph) attaches the tag onto its
result.

Event Enrichment R1 correction (2026-09-08 audit): extract_companies/
extract_sectors used to be treated the same as generate_timeline/
find_similar_events -- list-shaped callers whose only fallback is [],
assumed "already self-evidently honest, no tag needed." That assumption
was WRONG specifically for extract_companies/extract_sectors: an empty
list is byte-identical whether the AI genuinely found zero companies/
sectors (VALID) or the call itself failed (FALLBACK), and this pipeline
has no other way to detect a stage-4-specific provider failure (its only
health check is on stage 2's classify_event). Both now return
(list, integrity_status) tuples, matching every dict-shaped call site's
own contract. find_similar_events remains UNCHANGED -- out of scope,
tracked separately; its [] fallback feeds a non-gated similarity list.

Integrity-status propagation fix (2026-10-17): generate_timeline had the
exact same gap R1 fixed for extract_companies/extract_sectors -- it also
discarded _safe_json_call's status and returned a bare list, so a
provider failure at stage 6 was invisible at every layer above this
function (an open gap this codebase's own earlier audits explicitly
flagged: "the AI answers stage 2 for real but then falls back on stage
4, 6, or 8 -- still completes as done with partially-fallback data,
undetected"). generate_timeline now returns {items, integrity_status},
matching extract_companies/extract_sectors' corrected contract rather
than the dict-shaped callers' in-place tag (a bare list has nowhere to
attach a key). event_pipeline.py's stage 6 does not yet act on the
status (no new retry trigger -- that's a separate, later change); this
fix only makes the signal reach the caller, same scope as R1's own
first step.

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
async def test_generate_timeline_tags_fallback_on_provider_failure():
    """Integrity-status propagation fix (2026-10-17): a provider failure
    must surface as {"items": [], "integrity_status": "fallback"}, not a
    bare [] indistinguishable from a genuine empty timeline."""
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(side_effect=RuntimeError("provider down"))):
        result = await provider.generate_timeline("Title", "text", "macro")
    assert result == {"items": [], "integrity_status": IntegrityStatus.FALLBACK.value}


@pytest.mark.asyncio
async def test_generate_timeline_tags_valid_on_real_success():
    """A genuine, well-formed AI answer must be tagged VALID, with its
    real items intact -- the positive case the FALLBACK test above is
    meant to be distinguishable from."""
    provider = _provider()
    payload = '[{"date": "2026-01-01", "title": "Phase 1", "description": "x", "order": 1}]'
    with patch.object(provider, "_chat", new=AsyncMock(return_value=payload)):
        result = await provider.generate_timeline("Title", "text", "macro")
    assert result["integrity_status"] == IntegrityStatus.VALID.value
    assert result["items"] == [{"date": "2026-01-01", "title": "Phase 1", "description": "x", "order": 1}]


@pytest.mark.asyncio
async def test_generate_timeline_valid_empty_is_distinguishable_from_fallback():
    """A genuine 'no phases' answer (VALID, empty) must not be
    byte-identical to a FALLBACK empty result -- the exact ambiguity
    this fix exists to resolve."""
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(return_value="[]")):
        result = await provider.generate_timeline("Title", "text", "macro")
    assert result == {"items": [], "integrity_status": IntegrityStatus.VALID.value}


@pytest.mark.asyncio
async def test_generate_timeline_malformed_shape_stays_tagged_valid():
    """_parse_json succeeding but returning a non-list (e.g. the model
    wrapped its JSON object instead of an array) must resolve to an
    empty items list -- and, unlike before this fix, that is now
    reachable in the integrity_status it was actually tagged with by
    _safe_json_call (VALID: the call succeeded, only the shape was
    wrong -- a different failure mode than an exception, and the two
    must stay distinguishable, not collapsed into one 'fallback' bucket)."""
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(return_value='{"not": "a list"}')):
        result = await provider.generate_timeline("Title", "text", "macro")
    assert result["items"] == []
    assert result["integrity_status"] == IntegrityStatus.VALID.value


# ── Event Enrichment R1 (2026-09-08): extract_companies/extract_sectors ────
# now return (list, integrity_status) tuples -- tests A-D from the
# remediation task spec.

@pytest.mark.asyncio
async def test_extract_companies_valid_empty_is_tagged_valid():
    """Test A: a real AI response that genuinely lists zero companies
    must tag VALID, not FALLBACK -- this is a legitimate result, never a
    reason to retry."""
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(return_value="[]")):
        companies, status = await provider.extract_companies("Title", "text")
    assert companies == []
    assert status == IntegrityStatus.VALID.value


@pytest.mark.asyncio
async def test_extract_companies_failure_is_tagged_fallback():
    """Test B: a real provider failure must tag FALLBACK -- previously
    indistinguishable from test A's legitimate empty result."""
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(side_effect=RuntimeError("provider down"))):
        companies, status = await provider.extract_companies("Title", "text")
    assert companies == []
    assert status == IntegrityStatus.FALLBACK.value


@pytest.mark.asyncio
async def test_extract_sectors_valid_empty_is_tagged_valid():
    """Test C: same distinction as A, for extract_sectors."""
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(return_value="[]")):
        sectors, status = await provider.extract_sectors("Title", "text")
    assert sectors == []
    assert status == IntegrityStatus.VALID.value


@pytest.mark.asyncio
async def test_extract_sectors_failure_is_tagged_fallback():
    """Test D: same distinction as B, for extract_sectors."""
    provider = _provider()
    with patch.object(provider, "_chat", new=AsyncMock(side_effect=RuntimeError("provider down"))):
        sectors, status = await provider.extract_sectors("Title", "text")
    assert sectors == []
    assert status == IntegrityStatus.FALLBACK.value


@pytest.mark.asyncio
async def test_extract_companies_real_success_returns_tagged_tuple_no_leak_into_items():
    provider = _provider()
    fake = '[{"symbol": "RELIANCE", "name": "Reliance Industries", "impact_type": "beneficiary", "reason": "test", "impact_score": 7.0}]'
    with patch.object(provider, "_chat", new=AsyncMock(return_value=fake)):
        companies, status = await provider.extract_companies("Title", "text")
    assert companies == [{"symbol": "RELIANCE", "name": "Reliance Industries", "impact_type": "beneficiary", "reason": "test", "impact_score": 7.0}]
    assert status == IntegrityStatus.VALID.value
    assert "integrity_status" not in companies[0]  # the tag lives on the tuple, never leaks into list items
