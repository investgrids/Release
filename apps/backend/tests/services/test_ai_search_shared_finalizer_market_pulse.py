"""
Market Pulse joins the canonical-core union (2026-09-22, Market Pulse
AEV2 audit) — proves it two ways:

  1. pipeline.py's _run_v3_steps gives Market Pulse the SAME query-cache
     discipline every other V3 query gets (a real gap this audit closed
     — previously this branch never checked or wrote the cache at all).
  2. response_finalize.py's finalize_v3_response routes BOTH canonical-
     core variants through the identical shared steps — no second,
     independently-wired finalization pipeline for either shape.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai_search import cache as cache_mod
from app.services.ai_search import pipeline
from app.services.ai_search.core_answer import CoreAnswer, from_v3_response as _real_from_v3_response
from app.services.ai_search.core_market_pulse import CoreMarketPulse, from_market_pulse_response as _real_from_market_pulse_response
from app.services.ai_search.response_finalize import finalize_v3_response

_MP_RESULT = {
    "type": "market_pulse", "query": "top gainers today", "synthesis_incomplete": False,
    "generated_at": "2026-09-22T10:06:08+00:00", "market_session": "live",
    "market_status": {"status": "open"}, "indices": [], "market_mood": "Neutral", "market_direction": "sideways",
    "market_summary": "Markets traded flat today.", "sector_narrative": "", "leading_sectors": [], "lagging_sectors": [],
    "top_gainers": [], "top_losers": [], "most_active": [], "theme_momentum": [],
    "biggest_opportunity": None, "biggest_risk": None, "ai_conclusion": "", "what_to_watch_next": [],
    "what_to_watch_summary": "", "scores": {},
}

_RESEARCH_RESULT = {
    "schema_version": "v3.1", "response_id": "resp-research-1", "specialist": "company",
    "answer": {"bottom_line": "HDFC Bank's asset quality remains stable.", "summary": "ok", "sources_count": 1},
    "companies": [{"symbol": "HDFCBANK", "name": "HDFC Bank"}],
    "sectors": [], "related_events": [], "news": [], "policies": [],
}


@pytest.fixture(autouse=True)
def _clear_cache():
    cache_mod._CACHE.clear()
    yield
    cache_mod._CACHE.clear()


# ── Cache discipline — a cache hit makes zero new market/LLM calls ───────

async def test_market_pulse_cache_hit_makes_zero_new_market_or_llm_calls():
    call_count = {"n": 0}

    async def _fake_run_market_pulse_search(query: str) -> dict:
        call_count["n"] += 1
        return dict(_MP_RESULT)

    with patch("app.services.ai_search.market_pulse._run_market_pulse_search", new=_fake_run_market_pulse_search), \
         patch("app.services.ai_search.market_pulse._detect_market_pulse_async", new=AsyncMock(return_value=True)):
        from unittest.mock import MagicMock
        db = MagicMock()

        results = []
        async for stage, _label, payload in pipeline._run_v3_steps("top gainers today", db):
            if payload is not None:
                results.append(payload)
        async for stage, _label, payload in pipeline._run_v3_steps("top gainers today", db):
            if payload is not None:
                results.append(payload)

    assert call_count["n"] == 1, "second identical query must be served from cache, not re-collected"
    assert len(results) == 2
    assert results[0]["query"] == results[1]["query"] == "top gainers today"


async def test_market_pulse_cache_miss_writes_the_cache_for_next_time():
    async def _fake_run_market_pulse_search(query: str) -> dict:
        return dict(_MP_RESULT)

    with patch("app.services.ai_search.market_pulse._run_market_pulse_search", new=_fake_run_market_pulse_search), \
         patch("app.services.ai_search.market_pulse._detect_market_pulse_async", new=AsyncMock(return_value=True)):
        from unittest.mock import MagicMock
        db = MagicMock()
        async for _stage, _label, _payload in pipeline._run_v3_steps("top gainers today", db):
            pass

    assert cache_mod.get_market_pulse_response("top gainers today") is not None
    # And never leaks into the generic research-answer namespace.
    assert cache_mod.get_response("top gainers today") is None


# ── Shared finalizer — one function, dispatched by shape, never two
# independently-wired pipelines. ──────────────────────────────────────────

def test_finalizer_builds_core_market_pulse_only_for_the_market_pulse_shape():
    with patch(
        "app.services.ai_search.response_finalize.from_market_pulse_response",
        wraps=_real_from_market_pulse_response,
    ) as mp_spy, patch(
        "app.services.ai_search.response_finalize.from_v3_response",
        wraps=_real_from_v3_response,
    ) as research_spy:
        finalize_v3_response("top gainers today", dict(_MP_RESULT))
        assert mp_spy.call_count == 1
        assert research_spy.call_count == 0

        mp_spy.reset_mock()
        research_spy.reset_mock()

        # Prediction recording (step 4, research-only) fires asyncio.
        # create_task, which needs a running loop this sync test doesn't
        # have — patched out here since it's irrelevant to what this
        # test actually checks (which core-builder was called).
        with patch("app.services.ai_search.response_finalize.asyncio.create_task"):
            finalize_v3_response("Should I invest in HDFC Bank?", dict(_RESEARCH_RESULT))
        assert research_spy.call_count == 1
        assert mp_spy.call_count == 0


def test_finalizer_calls_assemble_aev2_exactly_once_for_either_shape():
    """Same call site, same function, dispatched internally — not two
    separate assembly call sites wired per shape."""
    with patch("app.services.ai_search.response_finalize.assemble_aev2", return_value=None) as assemble_spy, \
         patch("app.services.ai_search.response_finalize.should_assemble", return_value=True):
        finalize_v3_response("top gainers today", dict(_MP_RESULT))
        assert assemble_spy.call_count == 1
        core_arg = assemble_spy.call_args.args[0]
        assert isinstance(core_arg, CoreMarketPulse)

        assemble_spy.reset_mock()
        with patch("app.services.ai_search.response_finalize.asyncio.create_task"):
            finalize_v3_response("Should I invest in HDFC Bank?", dict(_RESEARCH_RESULT))
        assert assemble_spy.call_count == 1
        core_arg = assemble_spy.call_args.args[0]
        assert isinstance(core_arg, CoreAnswer)


def test_legacy_market_pulse_response_unchanged_while_aev2_mode_is_off():
    """AEV2_BUILD_COMPLETE/mode default (no AI_SEARCH_AEV2_MODE set in
    tests) means OFF — the real HTTP-facing Market Pulse response must
    be byte-identical to what it always was, canonical-core plumbing
    notwithstanding, aside from the one intentional 2026-09-23 addition
    (answer_availability — see test_answer_availability.py for its own
    dedicated coverage)."""
    result = finalize_v3_response("top gainers today", dict(_MP_RESULT))
    assert result == {
        **_MP_RESULT,
        "answer_availability": {"state": "available", "evidence_retrieval_completed": True, "evidence_count": 0, "reason": None, "basis": "market_data", "kind": "research", "scope": "full", "conclusion_authorized": False},
    }
    assert "answer_experience_v2" not in result
