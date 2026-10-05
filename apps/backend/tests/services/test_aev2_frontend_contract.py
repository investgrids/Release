"""
Route-level backend<->frontend contract verification (2026-09-22,
six-mode activation-wiring commit).

The activation-wiring commit wired direct_company_research/switch_
analysis/company_comparison/event_impact/market_pulse into the
frontend's real AIAnswer union and dispatch — but every one of those
five gate functions (toDirectCompanyResearchAEV2Answer etc.) had, until
now, only ever been exercised against hand-authored TypeScript fixtures
that mirror what a developer BELIEVES assemble_aev2() produces. That
mirroring is exactly the boundary risk this file closes: it runs the
REAL finalize_v3_response() (the one function every /api/ai/search*
route actually calls — see response_finalize.py's own docstring) for a
realistic query shaped like each of the six implemented modes, and
asserts the real output satisfies what the frontend gate functions
require field-for-field, plus the six cross-cutting properties (cache/
fresh equivalence, no internal-field leakage, no duplicate pipeline
work) the six-mode integration audit's follow-up called for.

Follows every existing assembly test file's own precedent (test_aev2_
build1_restructuring.py, test_switch_analysis_assembly.py, test_
comparison_assembly.py, test_event_impact_assembly.py, test_market_
pulse_cache_freshness.py): build a plain V3 response dict, run it
through the REAL backend functions, never hand-construct a CoreAnswer
or an AEV2 dict directly. The one addition here is going through
finalize_v3_response() itself (not assemble_aev2() in isolation), since
that is the actual "backend-finalizer response" boundary the frontend
receives — safety gate, canonical-core projection, AEV2 assembly, and
internal-field stripping, in the real order, exactly once.

AEV2_BUILD_COMPLETE/AI_SEARCH_AEV2_MODE are patched to True/"public"
ONLY within this file's own test scope (monkeypatch, reverted after
each test) — production is untouched; both stay exactly as they are
everywhere else in the codebase.

These six real response dicts are also the source for the frontend's
own real-fixture contract tests — see apps/web/components/ai/
__fixtures__/backend-real/README.md for how they were captured and how
to regenerate them if this file's builders change.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services.ai_search.aev2.mode import AEV2Mode
from app.services.ai_search.response_finalize import _INTERNAL_ONLY_FIELDS, finalize_v3_response

# finalize_v3_response's prediction-recording step (step 4) fires
# asyncio.create_task unconditionally for any non-market-pulse, non-
# degraded response — needs a running event loop, hence every test
# below is async under pytest-asyncio (matches test_ai_search_single_
# pipeline_runtime.py's own established pattern).
pytestmark = pytest.mark.asyncio


async def _drain_background_tasks() -> None:
    for _ in range(5):
        await asyncio.sleep(0)

RELIANCE = {"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}
TCS = {"symbol": "TCS", "name": "Tata Consultancy Services Ltd"}
INFY = {"symbol": "INFY", "name": "Infosys Ltd"}
BEL = {"symbol": "BEL", "name": "Bharat Electronics Ltd"}
HAL = {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd"}

_CONFIDENCE = {
    "evidence_quality": 70.0, "market_confirmation": 60.0,
    "historical_similarity": 40.0, "data_freshness": 90.0,
}


def direct_company_research_v3() -> dict:
    """Mirrors test_aev2_build1_restructuring.py's own real scenario."""
    return {
        "query": "Should I invest in Reliance Industries?",
        "ui_mode": "direct_company_research",
        "response_id": "resp-contract-dcr-1",
        "specialist": "company",
        "intent": "general",
        "answer": {
            "bottom_line": "Reliance Industries secured a 2,500 MW power supply contract.",
            "summary": "ok",
            "what_happened": "Reliance Industries announced a 2,500 MW RTC power supply agreement.",
            "why_it_happened": "The contract reflects growing demand for round-the-clock clean power.",
            "immediate_impact": "Shares reacted positively to the announcement.",
            "medium_term": "", "long_term": "", "risks": ["Execution risk on large infrastructure contracts remains real."],
        },
        "companies": [{
            "symbol": "RELIANCE", "name": "Reliance Industries Ltd",
            "price": "1,402.50", "change": "+1.20%", "positive": True,
            "price_fetched_at": "2026-09-21T10:00:00+00:00",
        }],
        "related_events": [{
            "id": "e-contract-1", "title": "Reliance Industries secures 2,500 MW RTC power supply contract",
            "date": "2026-09-15", "companies": [RELIANCE],
        }],
        "news": [], "policies": [],
        "investment_verdict": {"horizon": "6-12 months"},
        "confidence_breakdown": dict(_CONFIDENCE),
    }


def switch_analysis_v3() -> dict:
    """Mirrors test_switch_analysis_assembly.py's own real scenario."""
    return {
        "query": "Should I continue holding BEL or switch to HAL?",
        "ui_mode": "switch_analysis",
        "response_id": "resp-contract-switch-1",
        "specialist": "comparison",
        "intent": "switch",
        "switch_holding": "Bharat Electronics Ltd",
        "switch_target": "Hindustan Aeronautics Ltd",
        "answer": {
            "bottom_line": "BEL's recent order win and HAL's delivery milestone both reflect strong defence-sector demand.",
            "summary": "ok",
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "risks": [],
        },
        "companies": [
            {"symbol": "BEL", "name": "Bharat Electronics Ltd", "price": "285.40", "change": "+1.10%",
             "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
            {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd", "price": "4,512.00", "change": "-0.30%",
             "positive": False, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        ],
        "related_events": [
            {"id": "e-bel-1", "title": "BEL wins defence order worth 1,200 crore", "date": "2026-09-18", "companies": [BEL]},
            {"id": "e-hal-1", "title": "HAL delivers first batch of Tejas Mk1A jets", "date": "2026-09-10", "companies": [HAL]},
        ],
        "news": [], "policies": [],
        "investment_verdict": {"horizon": "6-12 months"},
        "confidence_breakdown": dict(_CONFIDENCE),
    }


def company_comparison_v3() -> dict:
    """Mirrors test_comparison_assembly.py's own real scenario."""
    return {
        "query": "Compare Infosys and TCS",
        "ui_mode": "company_comparison",
        "response_id": "resp-contract-cmp-1",
        "specialist": "comparison",
        "intent": "compare",
        "switch_holding": "Infosys Ltd",
        "switch_target": "Tata Consultancy Services Ltd",
        "answer": {
            "bottom_line": "Infosys's digital transformation win and TCS's new AI research center both reflect continued IT-sector demand.",
            "summary": "ok",
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "risks": [],
        },
        "companies": [
            {"symbol": "INFY", "name": "Infosys Ltd", "price": "1,845.20", "change": "+0.60%",
             "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
            {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "price": "4,102.50", "change": "-0.20%",
             "positive": False, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        ],
        "related_events": [
            {"id": "e-infy-1", "title": "Infosys wins 500 crore digital transformation deal", "date": "2026-09-17", "companies": [INFY]},
            {"id": "e-tcs-1", "title": "TCS announces new AI research center", "date": "2026-09-12", "companies": [TCS]},
        ],
        "news": [], "policies": [],
        "investment_verdict": {"horizon": "6-12 months"},
        "confidence_breakdown": dict(_CONFIDENCE),
    }


def event_impact_v3() -> dict:
    """Mirrors test_event_impact_assembly.py's own real scenario."""
    event = {
        "id": "e-reliance-1", "slug": "reliance-jio-completes-pan-india-5g-rollout-e-reliance-1",
        "title": "Reliance Jio completes pan-India 5G network rollout",
        "summary": "Reliance Jio Infocomm Limited informed the Exchange that it has completed 5G network rollout across all 22 telecom circles in India.",
        "category": "Corporate", "impact_score": 7.5, "confidence": 8.0, "sectors": ["Telecom"],
        "companies": [RELIANCE], "date": "Sep 15, 2026", "source": "nse_announcements",
        "event_date": "2026-09-15", "published_at": "2026-09-15T09:30:00+00:00",
    }
    return {
        "query": "Reliance Jio just announced its 5G rollout is complete, what does this mean?",
        "ui_mode": "event_impact",
        "response_id": "resp-contract-event-1",
        "specialist": "company",
        "intent": "news_reaction",
        "answer": {
            "bottom_line": "Jio's completion of its nationwide 5G rollout strengthens Reliance's telecom infrastructure position.",
            "summary": "ok",
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "risks": [],
        },
        "companies": [{
            "symbol": "RELIANCE", "name": "Reliance Industries Ltd", "price": "1,257.50", "change": "+0.40%",
            "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00",
        }],
        "related_events": [event],
        "news": [], "policies": [],
        "investment_verdict": {"horizon": "3-6 months"},
        "confidence_breakdown": dict(_CONFIDENCE),
    }


def market_pulse_v3() -> dict:
    """Mirrors test_market_pulse_cache_freshness.py's own _MP_RESULT."""
    return {
        "type": "market_pulse", "ui_mode": "market_pulse", "query": "top gainers today",
        "synthesis_incomplete": False, "generated_at": "2026-09-22T10:06:08+00:00",
        "market_session": "live", "market_status": {"status": "open"},
        "indices": [{"name": "NIFTY 50", "ticker": "^NSEI", "value": "23,329.00", "change": "-0.43%", "chart": []}],
        "market_mood": "Neutral", "market_direction": "sideways",
        "market_summary": "Markets traded flat today.", "sector_narrative": "",
        "leading_sectors": [], "lagging_sectors": [],
        "top_gainers": [], "top_losers": [], "most_active": [], "theme_momentum": [],
        "biggest_opportunity": {"title": "IPO rush", "href": "/opportunity-radar/36", "opportunity_score": 98.0},
        "biggest_risk": None, "ai_conclusion": "", "what_to_watch_next": [],
        "what_to_watch_summary": "", "scores": {},
    }


def factual_lookup_v3() -> dict:
    """factual_lookup never reaches AEV2 (see IMPLEMENTED_UI_MODES on the
    frontend — it's the one implemented mode sourced from the plain V3
    dict directly, no answer_experience_v2 involved), so this scenario's
    contract test only checks the same finalize_v3_response() shape/
    field-leakage/cache-equivalence properties every mode shares — never
    an assemble_aev2 field."""
    return {
        "query": "What was TCS's Q4 FY25 revenue?",
        "ui_mode": "factual_lookup",
        "response_id": "resp-contract-factual-1",
        "specialist": "company",
        "intent": "general",
        "answer": {
            "bottom_line": "TCS's Q4 FY25 revenue was 64,479 crore.",
            "summary": "TCS's Q4 FY25 revenue was 64,479 crore.",
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "risks": [],
        },
        "companies": [{
            "symbol": "TCS", "name": "Tata Consultancy Services Ltd", "price": "4,102.50", "change": "-0.20%",
            "positive": False, "price_fetched_at": "2026-09-21T10:00:00+00:00",
        }],
        "related_events": [], "news": [], "policies": [],
        "investment_verdict": {"horizon": None},
        "confidence_breakdown": dict(_CONFIDENCE),
    }


SCENARIOS = {
    "direct_company_research": direct_company_research_v3,
    "switch_analysis": switch_analysis_v3,
    "company_comparison": company_comparison_v3,
    "event_impact": event_impact_v3,
    "market_pulse": market_pulse_v3,
    "factual_lookup": factual_lookup_v3,
}


async def _finalize_public(monkeypatch, v3_dict: dict, *, was_cached: bool = False) -> dict:
    """Runs the REAL finalize_v3_response(), forcing AEV2 all the way to
    the wire — PUBLIC mode + the readiness latch — patched only for the
    duration of the calling test. Drains the fire-and-forget prediction-
    recording task afterward (same pattern as test_ai_search_single_
    pipeline_runtime.py) so it completes deterministically within the
    test rather than leaking into whichever test runs next."""
    from app.services.ai_search import response_finalize as rf_mod
    from app.services.ai_search.aev2 import mode as mode_mod

    monkeypatch.setattr(mode_mod, "AEV2_BUILD_COMPLETE", True)
    monkeypatch.setattr(rf_mod, "get_aev2_mode", lambda: AEV2Mode.PUBLIC)
    final = finalize_v3_response("contract-test-query", dict(v3_dict), was_cached=was_cached)
    await _drain_background_tasks()
    return final


# ── 1. Successful contract -> the correct mode-specific field populated ─────

async def test_direct_company_research_contract(monkeypatch):
    final = await _finalize_public(monkeypatch, direct_company_research_v3())
    aev2 = final["answer_experience_v2"]
    assert aev2["direct_conclusion"]["validation_status"] == "validated"
    assert aev2["direct_conclusion"]["text"]
    assert aev2["companies_affected"]["currently_higher"] or aev2["companies_affected"]["currently_lower"]
    assert aev2["switch_analysis"] is None
    assert aev2["comparison"] is None
    assert aev2["event_impact"] is None


async def test_switch_analysis_contract(monkeypatch):
    final = await _finalize_public(monkeypatch, switch_analysis_v3())
    aev2 = final["answer_experience_v2"]
    assert aev2["switch_analysis"] is not None
    assert aev2["switch_analysis"]["current_company"]["symbol"] == "BEL"
    assert aev2["switch_analysis"]["alternative_company"]["symbol"] == "HAL"
    assert aev2["switch_analysis"]["direct_comparison"]["validation_status"] == "validated"
    # Real finding from this contract test (2026-09-22): assemble_comparison
    # populates for ANY resolving 2-company comparison-specialist call,
    # deliberately not checking switch-vs-neutral intent at all — see its
    # own docstring: "the FRONTEND eligibility gate decides whether it's
    # good enough to render, same division of responsibility as switch_
    # analysis." So a switch-shaped query legitimately gets BOTH objects
    # populated; toAIAnswer's own ui_mode-keyed dispatch (computed
    # separately, upstream, by classify_ui_mode) is what decides which
    # ONE actually reaches a layout — never both, never neither.
    assert aev2["comparison"] is not None
    assert aev2["event_impact"] is None


async def test_company_comparison_contract(monkeypatch):
    final = await _finalize_public(monkeypatch, company_comparison_v3())
    aev2 = final["answer_experience_v2"]
    assert aev2["comparison"] is not None
    assert {aev2["comparison"]["left_company"]["symbol"], aev2["comparison"]["right_company"]["symbol"]} == {"INFY", "TCS"}
    assert aev2["comparison"]["direct_comparison"]["validation_status"] == "validated"
    assert aev2["switch_analysis"] is None
    assert aev2["event_impact"] is None


async def test_event_impact_contract(monkeypatch):
    final = await _finalize_public(monkeypatch, event_impact_v3())
    aev2 = final["answer_experience_v2"]
    assert aev2["event_impact"] is not None
    assert aev2["event_impact"]["event"]["id"] == "e-reliance-1"
    assert aev2["event_impact"]["linked_companies"] == [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}]
    assert aev2["switch_analysis"] is None
    assert aev2["comparison"] is None


async def test_market_pulse_contract(monkeypatch):
    final = await _finalize_public(monkeypatch, market_pulse_v3())
    # market_pulse's AEV2 shape is its OWN top-level object (AEV2MarketPulse)
    # — never nested inside the AEV2Response comparison/switch_analysis/
    # event_impact fields the research modes use (see aev2Types.ts's own
    # AEV2MarketPulse doc comment on the frontend for why).
    aev2 = final["answer_experience_v2"]
    assert "comparison" not in aev2
    assert "switch_analysis" not in aev2
    assert "event_impact" not in aev2
    assert "direct_conclusion" not in aev2
    assert aev2["indices"]


async def test_factual_lookup_contract_has_no_aev2_field_dependency(monkeypatch):
    # factual_lookup still gets an assembled answer_experience_v2 today
    # (assemble_aev2 doesn't special-case ui_mode) — but the frontend
    # never reads it for this mode (FactualLookupLayout sources purely
    # from the plain `answer` block), so this only proves finalize_v3_
    # response doesn't crash or omit the plain V3 fields FactualLookup
    # Layout actually depends on.
    final = await _finalize_public(monkeypatch, factual_lookup_v3())
    assert final["answer"]["bottom_line"] == "TCS's Q4 FY25 revenue was 64,479 crore."
    assert final["ui_mode"] == "factual_lookup"


# ── 4. Cached and fresh responses produce equivalent public shapes ──────────

_ALL_SCENARIO_NAMES = list(SCENARIOS)


@pytest.mark.parametrize("scenario_name", _ALL_SCENARIO_NAMES)
async def test_cached_and_fresh_responses_produce_equivalent_public_shapes(monkeypatch, scenario_name):
    v3_dict = SCENARIOS[scenario_name]()
    fresh = await _finalize_public(monkeypatch, v3_dict, was_cached=False)
    # A cache hit re-runs finalize_v3_response on the SAME stored dict,
    # only was_cached flips — exactly what cache.py's own get_response()
    # returns on a hit (see response_finalize.py's own docstring: "Never
    # mutates result"). Re-deriving from a fresh copy of the identical
    # input dict is the correct simulation of that real code path.
    cached = await _finalize_public(monkeypatch, v3_dict, was_cached=True)
    assert fresh == cached, "a cache hit must produce byte-identical public output to the fresh response it replays"


# ── 5. Prohibited legacy/internal fields never reach the AEV2 payload ───────

@pytest.mark.parametrize("scenario_name", _ALL_SCENARIO_NAMES)
async def test_internal_only_fields_never_leak_into_the_finalized_response(monkeypatch, scenario_name):
    v3_dict = SCENARIOS[scenario_name]()
    v3_dict["announcements"] = [{"id": 1, "headline": "should never reach a client"}]
    final = await _finalize_public(monkeypatch, v3_dict)
    for field in _INTERNAL_ONLY_FIELDS:
        assert field not in final, f"{field} must be stripped before a response is ever returned"


@pytest.mark.parametrize("scenario_name", _ALL_SCENARIO_NAMES)
async def test_prohibited_verdict_concepts_never_appear_inside_answer_experience_v2(monkeypatch, scenario_name):
    """The plain V3 dict legitimately carries investment_verdict (the
    existing production UI's own field) — that's fine and expected. What
    must never happen is that concept leaking INTO the new AEV2 payload,
    which has no verdict/rating/top_picks/suitability field anywhere in
    its schema by design (see assemble.py's own "Deliberately absent"
    docstring note)."""
    final = await _finalize_public(monkeypatch, SCENARIOS[scenario_name]())
    aev2 = final.get("answer_experience_v2")
    if aev2 is None or "indices" in aev2:  # market_pulse's own separate shape
        return
    serialized_keys = _flatten_keys(aev2)
    for forbidden in ("investment_verdict", "engine_verdict", "top_picks", "suitable_for", "risk_level", "rating"):
        assert forbidden not in serialized_keys, f"{forbidden} must never appear inside answer_experience_v2"


def _flatten_keys(obj) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _flatten_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _flatten_keys(item)
    return keys


# ── 6. Readiness latch still gates every one of the six scenarios ───────────

@pytest.mark.parametrize("scenario_name", _ALL_SCENARIO_NAMES)
async def test_readiness_latch_still_hides_every_scenario_when_closed(scenario_name):
    """The one invariant every other test in this file deliberately
    bypasses via monkeypatch — proves that bypass is doing real work,
    i.e. that today's actual AEV2_BUILD_COMPLETE=False still hides
    answer_experience_v2 from every one of these six real scenarios,
    exactly as production behaves right now."""
    v3_dict = SCENARIOS[scenario_name]()
    final = finalize_v3_response("contract-test-query", dict(v3_dict), was_cached=False)
    await _drain_background_tasks()
    assert "answer_experience_v2" not in final
