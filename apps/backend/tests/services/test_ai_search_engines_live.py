"""
Regression suite — Tier 2: live end-to-end, through the real pipeline.

Hits the real ai_search_service.run_ai_search() against this backend's
actual dev database (same convention as
tests/ai_pipeline/test_phase1_smoke.py: real DB rows, real market-data/
yfinance calls, real LLM provider chain — not mocked). Each query takes
30-180s depending on provider latency, so this tier is NOT meant to run on
every commit. Select it explicitly with `pytest -m live_e2e`; wire that as
its own CI job gated on release, not on every push.

Assertions here are deliberately structural, never exact-text — an LLM's
prose is nondeterministic between runs even for the same query. What's
checked is exactly what a data-first architecture promises: verdict_basis/
engine output presence and validity, only real (never invented) ticker
symbols, and honest degradation (empty, not fabricated) when there's no
real data behind an entity.

Because this depends on the live content of ig_dev.db (real Opportunity
rows for Banking/Defence etc.), a test can start failing if that data is
later cleared or changes shape — that's a real signal worth seeing, not
flakiness to suppress.
"""
from __future__ import annotations

import pytest

from app.api.companies import _NSE_UNIVERSE
from app.db.session import AsyncSessionLocal
from app.services.ai_search_service import run_ai_search

pytestmark = pytest.mark.live_e2e

_REAL_SYMBOLS = {c["symbol"] for c in _NSE_UNIVERSE}
_VALID_RATINGS = {
    "Strongly Constructive", "Constructive", "Positive Outlook",
    "Selectively Constructive", "Neutral", "Cautious",
    "Elevated Risk", "High Uncertainty",
}


async def _run(query: str) -> dict:
    async with AsyncSessionLocal() as db:
        return await run_ai_search(query, db)


@pytest.mark.parametrize("query", [
    "Should I buy Reliance?",
    "Should I hold TCS?",
    "Should I sell SBI?",
])
async def test_investment_verdict_live(query):
    result = await _run(query)
    iv = result["investment_verdict"]
    assert iv["rating"] in _VALID_RATINGS, f"{query!r}: {iv['rating']!r} is not a valid research-outlook label"
    ev = iv.get("engine_verdict")
    assert ev is not None, f"{query!r}: Investment Verdict Engine did not run"
    assert ev["rating"] in _VALID_RATINGS
    assert 0 <= ev["confidence_used"] <= 100


@pytest.mark.parametrize("query", [
    "HDFC or ICICI?",
    "Compare Infosys and TCS",
    "Switch from SBI to Axis",
    "Move investment from Reliance to ONGC",
])
async def test_decision_engine_live(query):
    result = await _run(query)
    di = result.get("decision_intelligence")
    assert di is not None, f"{query!r}: decision_intelligence missing — is_comparison likely False"
    rec = di.get("engine_recommendation")
    assert rec is not None, f"{query!r}: Decision Engine did not run"
    assert rec["basis"] == "computed"
    assert rec["margin"] in ("clear", "slight", "no_clear_edge")
    for side in ("entity_a", "entity_b"):
        assert rec[side]["rating"] in _VALID_RATINGS
        assert rec[side]["symbol"] in _REAL_SYMBOLS, f"{query!r}: fabricated symbol {rec[side]['symbol']!r}"


@pytest.mark.parametrize("query", [
    "Best defence companies",
    "Top banking stocks",
])
async def test_recommendation_engine_live(query):
    result = await _run(query)
    picks = result["investment_verdict"].get("top_picks") or []
    assert picks, f"{query!r}: no picks returned at all"
    for sym in picks:
        assert sym in _REAL_SYMBOLS, f"{query!r}: {sym!r} is not a real NSE symbol — fabricated pick"


async def test_edge_case_unknown_ticker_live():
    result = await _run("Should I buy XZQPLM?")
    assert result["entities"]["companies"] == [], "unknown ticker must not resolve to a fabricated company"
    ev = result["investment_verdict"].get("engine_verdict")
    assert ev is not None
    assert ev["opportunity_score_used"] is None, "no real opportunity match should exist for an unknown ticker"


async def test_edge_case_multiple_companies_live():
    result = await _run("What about Reliance, TCS, HDFC Bank and Infosys?")
    companies = set(result["entities"]["companies"])
    for expected in ("RELIANCE", "TCS", "HDFCBANK", "INFY"):
        assert expected in companies, f"multi-company query missed {expected}"


async def test_edge_case_empty_query_live():
    # The API layer (api/ai_search.py's SearchRequest) rejects an empty
    # query before it ever reaches this function — this test covers the
    # service layer's own behavior in isolation: it must not crash even
    # when called directly with no upstream validation.
    result = await _run("")
    assert isinstance(result, dict)
    assert result["entities"]["companies"] == []
