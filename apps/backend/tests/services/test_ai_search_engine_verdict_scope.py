"""
Step 5 update: the engine verdict is no longer produced at all. It rated from the public answer confidence, and that confidence was never measured (see postprocess.compute_confidence_breakdown), while inside
the engine a missing direction, confidence, opportunity score and VIX each fall back to a constant. The scope table below is kept because the market-wide rule is what the verdict must obey if a measured
confidence ever exists. Original (Step 3.4D-2.1) text follows.

Step 3.4D-2.1: the deterministic engine verdict is a MARKET-WIDE read (market direction, confidence, VIX). It stays computed and available internally, but is public only for a market-wide / macro
scope. Independent scope checks: company research, comparison, event impact, sector, macro. No provider call.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services.ai_search import pipeline as P
from app.services.ai_search.response_finalize import finalize_v3_response
from tests.services.test_ai_search_fail_closed import ann, bundle, ent, news_row, ev_row, pipe  # noqa: F401
from tests.services.test_ai_search_structured_authorization import real_assembly  # noqa: F401

REPORT = SimpleNamespace(repairs=[], omissions=[], contradiction_flagged=False, grounding_collapsed=False)

CASES = [
    # id, query, specialist, plan, entities, intent_data, expected ui_mode, engine verdict public?
    ("company", "How is TCS doing as a business?", "company", "company", ent(["TCS"]), {}, "direct_company_research", False),
    ("comparison", "TCS vs Infosys, which is stronger?", "comparison", "comparison", ent(["TCS", "INFY"]), {"is_comparison": True, "holding": "Tata Consultancy Services Ltd", "target": "Infosys Ltd"}, "company_comparison", False),
    ("event", "BEL just won a new defence order, what does this mean for the stock?", "company", "company", ent(["BEL"]), {"intent": "news_reaction"}, "event_impact", False),
    ("sector", "What is the outlook for the IT services sector?", "sector", "topic", ent(sectors=["it"]), {}, "sector_theme_research", False),
    ("macro", "What happens to Indian banks if the RBI cuts the repo rate?", "company", "topic", ent(sectors=["banking"], policies=["rbi", "repo rate"]), {}, "policy_macro_impact", True),
]


def assemble(case):
    _id, query, kind, plan, entities, intent_data, _mode, _public = case
    ev = bundle(plan, news=[news_row("n1", "Markets edge higher")])
    ev.mie_state = {"signals": {"direction": "bullish"}}
    ev.vix_level = 14.0
    ai = {"summary": "S.", "bottom_line": "S.", "claim_sources": []}
    return asyncio.run(P._assemble_response(query, ai, ev, kind, False, REPORT, None, entities, intent_data=intent_data, conclusion_scope={}))


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_no_engine_verdict_is_produced_without_a_measured_confidence(real_assembly, case):
    res = assemble(case)
    assert res["ui_mode"] == case[6], res["ui_mode"]                                           # routing and ui_mode are unchanged
    assert res["investment_verdict"]["engine_verdict"] is None and res["_engine_verdict_internal"] is None
    assert res["confidence_breakdown"]["final_confidence"] is None and res["answer"]["confidence"] is None


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_the_internal_copy_is_stripped_from_the_client_response(real_assembly, case):
    res = assemble(case)
    async def go():
        return finalize_v3_response(case[1], res, x_admin_key=None, was_cached=False)
    final = asyncio.run(go())
    assert "_engine_verdict_internal" not in final
    assert "Market view" not in str(final) and "_engine_verdict" not in str(final)


def test_market_wide_modes_are_exactly_macro_and_market_pulse():
    assert P.MARKET_WIDE_UI_MODES == frozenset({"policy_macro_impact", "market_pulse"})


def test_a_company_answer_never_carries_a_market_rating_in_investment_verdict(real_assembly):
    res = assemble(CASES[0])
    v = res["investment_verdict"]
    assert v["engine_verdict"] is None
    assert "bullish" not in str({k: v[k] for k in v if k != "engine_verdict"}).lower()
