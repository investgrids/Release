"""
Provenance contract (2026-10-19) unit coverage at the triage_worker.py
level, independent of the schema_patches.py / EventTriage DB tests in
test_schema_patches.py. Those prove the column and ORM write path work;
these prove the two real code paths that decide the VALUE -- the AI
success branch and _rule_based_fallback() -- each set their own explicit
triage_source, never leaving it to an implicit default.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.intelligence.triage_worker import _ai_triage, _rule_based_fallback


def test_rule_based_fallback_marks_its_own_provenance():
    result = _rule_based_fallback("RBI announces repo rate decision")
    assert result["triage_source"] == "rule_based_fallback"


@pytest.mark.asyncio
async def test_ai_triage_success_marks_ai_provenance():
    fake_json = (
        '{"urgency": 7, "importance": 6, "confidence": 8, "sentiment": "bullish", '
        '"horizon": "short", "market_impact": "medium", "is_structural": false, '
        '"direction": "up", "one_liner": "Test one-liner", "themes": [], "sectors": [], "tickers": []}'
    )
    with patch("app.services.ai_service._call_with_fallback", new=AsyncMock(return_value=fake_json)):
        scores = await _ai_triage("Some real headline", "Some real summary")
    assert scores["triage_source"] == "ai"
    assert scores["one_liner"] == "Test one-liner"


@pytest.mark.asyncio
async def test_ai_triage_falls_back_to_rule_based_on_empty_provider_response():
    with patch("app.services.ai_service._call_with_fallback", new=AsyncMock(return_value="")):
        scores = await _ai_triage("RBI announces repo rate decision", "summary")
    assert scores["triage_source"] == "rule_based_fallback"
    # Internal debug-only keys must still be stripped before the dict
    # reaches TriagedEvent construction, same as before this change.
    assert "_fallback_matched_category" not in scores
    assert "_fallback_matched_keyword" not in scores


@pytest.mark.asyncio
async def test_ai_triage_falls_back_to_rule_based_on_malformed_json():
    # log.warning mocked out here: this except-branch's real call passes
    # exception=True (a bool) to structlog's dev ConsoleRenderer, which
    # only accepts a string for that key and crashes -- a pre-existing bug
    # unrelated to triage_source, found incidentally by exercising this
    # path for the first time. Not fixed here; out of scope for the
    # provenance contract. Mocking isolates this test from it.
    with patch("app.services.ai_service._call_with_fallback", new=AsyncMock(return_value="not valid json")), \
         patch("app.services.intelligence.triage_worker.log.warning"):
        scores = await _ai_triage("RBI announces repo rate decision", "summary")
    assert scores["triage_source"] == "rule_based_fallback"
