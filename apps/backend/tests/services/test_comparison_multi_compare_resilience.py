"""
6G Cutover Gate, Step 2B — multi-compare degraded-provider resilience.

Confirmed live (parity harness + direct diagnostic calls): the full
multi-compare schema reproducibly truncates mid-JSON on the weakest
fallback model under heavy provider load, and the generic degraded
fallback (base.py's degraded_response) silently wipes companies to [] --
turning a 3-company question into what looks like a 0/2-company answer.
Fix: one bounded compact-schema retry, then an honest but entity-
preserving degraded response. These tests mock _call_with_fallback to
drive each branch deterministically, no live LLM required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai_search.specialists import comparison


def _entities_3way() -> dict:
    return {
        "companies": ["TCS", "INFY", "WIPRO"],
        "company_matches": [
            {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "match_type": "exact"},
            {"symbol": "INFY", "name": "Infosys Ltd", "match_type": "exact"},
            {"symbol": "WIPRO", "name": "Wipro Ltd", "match_type": "exact"},
        ],
        "sectors": [], "policies": [],
    }


def _entities_2way() -> dict:
    return {"companies": ["TCS", "INFY"], "company_matches": [
        {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "match_type": "exact"},
        {"symbol": "INFY", "name": "Infosys Ltd", "match_type": "exact"},
    ], "sectors": [], "policies": []}


class _FakeEvidence:
    def deduped_events(self):
        return []

    def deduped_news(self):
        return []

    def to_context_text(self):
        return ""


FULL_SCHEMA_SUCCESS = """{
  "investment": {"summary": "ok", "bottom_line": "ok", "direction": "neutral", "rating": "Neutral", "confidence": 60},
  "decision": {},
  "evidence": {"what_happened": "", "why_it_happened": "", "immediate_impact": "", "medium_term": "", "long_term": "", "what_priced_in": "", "key_drivers": []},
  "companies": [
    {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "impact_type": "neutral", "impact_score": 65, "confidence": 60, "reason": ""},
    {"symbol": "INFY", "name": "Infosys Ltd", "impact_type": "neutral", "impact_score": 65, "confidence": 60, "reason": ""},
    {"symbol": "WIPRO", "name": "Wipro Ltd", "impact_type": "neutral", "impact_score": 65, "confidence": 60, "reason": ""}
  ],
  "sectors": [],
  "timeline": {"immediate": "", "one_week": "", "one_to_three_months": "", "six_to_twelve_months": "", "one_to_three_years": ""},
  "risks": {"risks": [], "opportunities": [], "opportunity_matrix": {}, "risk_matrix": {}},
  "decision_intelligence": {
    "intent": "compare_multi", "context_complete": true, "missing_context": [],
    "decision_summary": "all three differ", "entity_analyses": [
      {"entity": "Tata Consultancy Services Ltd", "symbol": "TCS", "sector": "IT", "thesis": "x", "strengths": [], "risks": [], "catalysts": [], "near_term_outlook": "neutral", "confidence": 65},
      {"entity": "Infosys Ltd", "symbol": "INFY", "sector": "IT", "thesis": "x", "strengths": [], "risks": [], "catalysts": [], "near_term_outlook": "neutral", "confidence": 65},
      {"entity": "Wipro Ltd", "symbol": "WIPRO", "sector": "IT", "thesis": "x", "strengths": [], "risks": [], "catalysts": [], "near_term_outlook": "neutral", "confidence": 65}
    ]
  }
}"""

TRUNCATED_JSON = '{"investment": {"summary": "TCS leads with 15.8% FY27 revenue CAGR, but the response got cut off mid'

COMPACT_SUCCESS = """{
  "entity_analyses": {
    "Tata Consultancy Services Ltd": {"view": "Stable margins", "strengths": ["Scale"], "risks": ["US demand"]},
    "Infosys Ltd": {"view": "Growth upside", "strengths": ["Digital mix"], "risks": ["Attrition"]},
    "Wipro Ltd": {"view": "Laggard", "strengths": ["Valuation"], "risks": ["Growth"]}
  },
  "comparison_summary": "TCS offers stability, Infosys growth, Wipro value.",
  "best_for": "TCS for conservative investors.",
  "key_tradeoffs": ["Stability vs growth", "Valuation vs momentum"],
  "confidence": 55
}"""


@pytest.mark.asyncio
async def test_full_schema_success_no_retry_attempted():
    mock = AsyncMock(return_value=FULL_SCHEMA_SUCCESS)
    with patch("app.services.ai_service._call_with_fallback", mock):
        parsed, degraded = await comparison.run("Compare TCS, Infosys, and Wipro", _FakeEvidence(), {}, _entities_3way())
    assert degraded is False
    assert mock.await_count == 1  # no compact retry needed
    assert len(parsed["decision_intelligence"]["entity_analyses"]) == 3


@pytest.mark.asyncio
async def test_full_schema_truncated_compact_retry_succeeds():
    mock = AsyncMock(side_effect=[TRUNCATED_JSON, COMPACT_SUCCESS])
    with patch("app.services.ai_service._call_with_fallback", mock):
        parsed, degraded = await comparison.run("Compare TCS, Infosys, and Wipro", _FakeEvidence(), {}, _entities_3way())
    assert degraded is False  # compact success is a real answer, not a failure
    assert mock.await_count == 2  # exactly one bounded retry, not more

    symbols = {c["symbol"] for c in parsed["companies"]}
    assert symbols == {"TCS", "INFY", "WIPRO"}  # all 3 preserved, none silently dropped

    ea = parsed["decision_intelligence"]["entity_analyses"]
    assert len(ea) == 3
    assert {e["symbol"] for e in ea} == {"TCS", "INFY", "WIPRO"}
    tcs_entry = next(e for e in ea if e["symbol"] == "TCS")
    assert tcs_entry["thesis"] == "Stable margins"


@pytest.mark.asyncio
async def test_full_schema_and_compact_both_fail_still_preserves_all_entities():
    mock = AsyncMock(side_effect=[TRUNCATED_JSON, TRUNCATED_JSON])
    with patch("app.services.ai_service._call_with_fallback", mock):
        parsed, degraded = await comparison.run("Compare TCS, Infosys, and Wipro", _FakeEvidence(), {}, _entities_3way())
    assert degraded is True
    assert mock.await_count == 2  # bounded -- exactly one retry, no infinite/extra attempts

    # The critical invariant: a 3-company question must never silently read
    # back as a 2-company (or 0-company) answer, even in the worst case.
    symbols = {c["symbol"] for c in parsed["companies"]}
    assert symbols == {"TCS", "INFY", "WIPRO"}
    assert parsed["_degraded_reason"] == "multi_compare_capacity"

    ea = parsed["decision_intelligence"]["entity_analyses"]
    assert len(ea) == 3
    assert {e["symbol"] for e in ea} == {"TCS", "INFY", "WIPRO"}


@pytest.mark.asyncio
async def test_two_entity_comparison_never_triggers_multi_compare_retry():
    """No regression to the existing pairwise path -- a 2-entity comparison
    that degrades should hit the ordinary generic degraded_response, never
    the multi-compare compact retry (which would be meaningless for 2)."""
    mock = AsyncMock(return_value=TRUNCATED_JSON)
    with patch("app.services.ai_service._call_with_fallback", mock):
        parsed, degraded = await comparison.run("TCS vs Infosys", _FakeEvidence(), {}, _entities_2way())
    assert degraded is True
    assert mock.await_count == 1  # never retried -- only the multi-compare path gets the bounded retry
    assert parsed["companies"] == []  # untouched generic degraded_response() shape, exactly as before this change


def test_two_entity_build_prompt_unchanged():
    """Structural guard: build_prompt's pairwise branch (build_prompt itself,
    not the multi-compare helper) must be untouched by this change."""
    prompt = comparison.build_prompt("TCS vs Infosys", _FakeEvidence(), {"holding": "TCS", "target": "Infosys"}, _entities_2way())
    assert "holding_analysis" in prompt
    assert "entity_analyses" not in prompt  # pairwise schema, not multi-compare
