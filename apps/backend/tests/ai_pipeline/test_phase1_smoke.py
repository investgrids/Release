"""
Pipeline smoke tests — end-to-end through the real pipeline (real DB rows,
real live news/market/AI calls) for all 15 registered intents. These are
integration tests, not unit tests: they exercise `run_pipeline()` exactly
as the CLI harness and, eventually, the live endpoint would call it.

Kept in one file (rather than splitting Phase 1 / Phase 2) so the registry
invariant checks (`test_registries_populated`, `test_no_hardcoded_intent_
branching`) stay in one place as the single source of truth for "what's
actually registered right now" — duplicating them per phase would just
create two counts to keep in sync.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.ai_pipeline.orchestrator import run_pipeline
from app.ai_pipeline.registry import TEMPLATE_REGISTRY

FIXTURE_QUERIES = [
    ("Should I invest in defence stocks after the latest budget?", "investment_decision"),
    ("RBI rate cut impact on banks", "event_impact"),
    ("Explain today's biggest news", "news_intelligence"),
    ("Compare HAL and BEL", "company_comparison"),
    ("Analyze TCS", "company_analysis"),
    ("What sectors should I watch next month?", "sector_analysis"),
    ("What is the outlook for the Indian market tomorrow?", "market_outlook"),
    ("What are the biggest risks to banking?", "risk_analysis"),
    ("AI stocks", "theme_discovery"),
    ("What happened after Budget 2023?", "historical_analysis"),
    ("Who benefits if crude oil falls 10%?", "ripple_analysis"),
    ("SEBI regulations impact", "policy_analysis"),
    ("Inflation impact on markets", "economic_analysis"),
    ("Should I replace Reliance with BEL?", "portfolio"),
    ("What is EV/EBITDA?", "general_education"),
]


# Each fixture query hits real network/AI calls (~10-20s). Cached across
# both tests below so the validator-pass-rate check doesn't re-run all 15
# pipelines a second time on top of the per-query assertions.
_RESULT_CACHE: dict[str, object] = {}


async def _run_cached(db_session, query: str):
    if query not in _RESULT_CACHE:
        _RESULT_CACHE[query] = await run_pipeline(query, db_session)
    return _RESULT_CACHE[query]


@pytest.mark.parametrize("query,expected_intent", FIXTURE_QUERIES)
async def test_pipeline_produces_grounded_result(db_session, query, expected_intent):
    result = await _run_cached(db_session, query)

    assert result.intent == expected_intent, (
        f"classifier routed {query!r} to {result.intent!r}, expected {expected_intent!r}"
    )
    assert 0 <= result.decision.confidence.total_score <= 100
    assert result.decision.confidence.level in ("Low", "Medium", "High", "Very High")

    template = TEMPLATE_REGISTRY.get(result.answer["template"])
    assert template is not None
    for section in template.required_sections:
        assert section in result.answer, f"required section '{section}' missing for {query!r}"


async def test_validator_passes_for_most_fixture_queries(db_session):
    """Hedges for live-AI-provider variability, not pipeline correctness."""
    passed = 0
    for query, _expected in FIXTURE_QUERIES:
        result = await _run_cached(db_session, query)
        if result.validator.passed:
            passed += 1
    total = len(FIXTURE_QUERIES)
    assert passed >= total * 0.8, f"only {passed}/{total} fixture queries passed validation"


def test_no_hardcoded_intent_branching():
    """
    The whole point of the registry pattern: adding an intent should never
    require touching dispatch logic. Fail the build if that invariant ever
    regresses.
    """
    pipeline_dir = Path(__file__).resolve().parents[2] / "app" / "ai_pipeline"
    offenders = []
    for path in pipeline_dir.rglob("*.py"):
        if path.name == "fast_classifier.py":
            continue   # the classifier is allowed to inspect intent keys generically
        text = path.read_text(encoding="utf-8")
        if re.search(r'if\s+\w*intent\w*\s*==', text):
            offenders.append(str(path))
    assert not offenders, f"hardcoded intent branching found in: {offenders}"


def test_registries_populated():
    from app.ai_pipeline.registry import INTENT_REGISTRY, RETRIEVER_REGISTRY, MODEL_TIER_REGISTRY

    assert set(INTENT_REGISTRY.keys()) == {
        "investment_decision", "event_impact", "news_intelligence",
        "company_comparison", "company_analysis", "sector_analysis",
        "market_outlook", "risk_analysis", "theme_discovery",
        "historical_analysis", "ripple_analysis", "policy_analysis",
        "economic_analysis", "portfolio", "general_education",
    }
    assert set(RETRIEVER_REGISTRY.keys()) == {
        "event", "news", "intelligence_publishing", "company", "market",
        "ripple", "intelligence_graph", "quant_signal", "historical_similarity", "macro",
    }
    assert set(TEMPLATE_REGISTRY.keys()) == {
        "verdict_template", "impact_template", "briefing_template",
        "exploratory_template", "profile_template", "education_template",
    }
    assert "medium" in MODEL_TIER_REGISTRY.keys()
