"""
Phase 6G Slice 2 — deterministic contract test for the V3 migration,
no live LLM call. Stubs run_ai_search_v3's return shape and proves
comparison_publisher.py's consumer logic (_try_generate's quality gate,
generate_comparison's retry behavior, publish_comparison_article's real
compose_*/_build_companies_affected functions) still correctly consumes
it -- the one thing this migration actually changed is which function
gets called; this is what verifies the publisher can consume that
function's result shape, independent of live provider availability.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select

from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services.aipe.comparison_publisher import (
    _try_generate,
    generate_comparison,
    publish_comparison_article,
)


def _v3_response(*, synthesis_incomplete=False, with_decision_intelligence=True) -> dict:
    """A realistic V3 response shape for a genuine 2-entity comparison --
    same decision_intelligence fields comparison.py's build_prompt()
    asks the LLM for, matching what flatten_nested() passes through
    unchanged."""
    di = {}
    if with_decision_intelligence:
        di = {
            "intent": "decision",
            "context_complete": True,
            "missing_context": [],
            "decision_summary": "TCS offers stability; Infosys offers growth upside.",
            "winner": "holding",
            "best_investor_type": {"holding": "Conservative investors", "target": "Growth investors"},
            "holding_analysis": {
                "entity": "TCS", "symbol": "TCS", "sector": "IT",
                "thesis": "TCS's diversified client base supports margin stability.",
                "strengths": ["Margin stability", "Large deal wins"], "risks": ["US demand softness"],
                "catalysts": ["Deal ramp-up"], "near_term_outlook": "neutral", "confidence": 68,
            },
            "target_analysis": {
                "entity": "Infosys", "symbol": "INFY", "sector": "IT",
                "thesis": "Infosys offers higher growth sensitivity to US IT recovery.",
                "strengths": ["Digital revenue mix"], "risks": ["Client concentration"],
                "catalysts": ["US IT spending recovery"], "near_term_outlook": "neutral", "confidence": 65,
            },
            "comparison": [
                {"dimension": "Valuation", "holding": "22x P/E", "target": "24x P/E", "advantage": "holding"},
                {"dimension": "Growth Drivers", "holding": "Stable", "target": "Higher upside", "advantage": "target"},
                {"dimension": "Margins", "holding": "31.1% EBIT", "target": "Lower", "advantage": "holding"},
            ],
            "tradeoff": {
                "reasons_to_switch": ["Higher growth upside", "Digital mix"],
                "reasons_to_hold": ["Margin stability", "Diversified client base"],
                "risks_of_switching": ["Execution risk"], "risks_of_holding": ["Slower growth"],
                "when_to_wait": "Wait for clearer US IT spending signals.",
            },
            "decision_framework": {
                "supports_switch": ["Growth reacceleration"], "argues_against": ["Valuation premium"],
                "key_unknowns": ["US IT budget trajectory"],
                "ai_stance": "Neutral-to-cautious, slight lean toward holding TCS.",
            },
            "engine_recommendation": {
                "favored_entity": "TCS", "margin": "slight",
                "entity_a": {"symbol": "TCS", "rating": "Cautious", "tier": 4},
                "entity_b": {"symbol": "INFY", "rating": "Cautious", "tier": 5},
                "valuation_note": "INFY trades at a lower P/E (22 vs 24)", "basis": "computed",
            },
        }
    return {
        "query": "TCS vs Infosys, which is better for 12 months?",
        "synthesis_incomplete": synthesis_incomplete,
        "specialist": "comparison",
        "answer": {"bottom_line": "TCS edges out Infosys on stability; Infosys leads on growth upside."},
        "investment_verdict": {"confidence": 62, "rating": "Selectively Constructive"},
        "decision_intelligence": di,
        "companies": [
            {"symbol": "TCS", "name": "TCS", "impact_type": "neutral"},
            {"symbol": "INFY", "name": "Infosys", "impact_type": "neutral"},
        ],
    }


@pytest.mark.asyncio
async def test_try_generate_accepts_a_complete_v3_response():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(_v3_response(), False)),
    ):
        async with AsyncSessionLocal() as db:
            result = await _try_generate("TCS vs Infosys, which is better for 12 months?", db)
    assert result is not None
    assert result["decision_intelligence"]["holding_analysis"]["entity"] == "TCS"


@pytest.mark.asyncio
async def test_try_generate_quality_gate_rejects_synthesis_incomplete():
    """Unchanged quality-gate contract: synthesis_incomplete must still
    reject regardless of which pipeline produced the response."""
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(_v3_response(synthesis_incomplete=True), False)),
    ):
        async with AsyncSessionLocal() as db:
            result = await _try_generate("query", db)
    assert result is None


@pytest.mark.asyncio
async def test_try_generate_quality_gate_rejects_missing_decision_intelligence():
    with patch(
        "app.services.ai_search.pipeline.run_ai_search_v3",
        new=AsyncMock(return_value=(_v3_response(with_decision_intelligence=False), False)),
    ):
        async with AsyncSessionLocal() as db:
            result = await _try_generate("query", db)
    assert result is None


@pytest.mark.asyncio
async def test_generate_comparison_retries_bounded_number_of_times_then_gives_up():
    """Unchanged retry contract: _MAX_ATTEMPTS calls, then None -- not
    retry-forever, not a single-shot."""
    mock = AsyncMock(return_value=(_v3_response(synthesis_incomplete=True), False))
    with patch("app.services.ai_search.pipeline.run_ai_search_v3", new=mock):
        async with AsyncSessionLocal() as db:
            result = await generate_comparison(db, "TCS", "INFY", "TCS", "Infosys")
    assert result is None
    assert mock.call_count == 3  # _MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_generate_comparison_stops_retrying_on_first_success():
    mock = AsyncMock(return_value=(_v3_response(), False))
    with patch("app.services.ai_search.pipeline.run_ai_search_v3", new=mock):
        async with AsyncSessionLocal() as db:
            result = await generate_comparison(db, "TCS", "INFY", "TCS", "Infosys")
    assert result is not None
    assert mock.call_count == 1  # succeeded on first attempt, no wasted retries


@pytest.mark.asyncio
async def test_publish_comparison_article_consumes_v3_shape_end_to_end():
    """The real compose_*/_build_companies_affected functions (unmodified
    by this migration) against a stubbed V3 response -- proves the
    publisher's actual consumer logic handles V3's shape correctly,
    independent of live provider availability."""
    slug = "tcs-vs-infy"
    try:
        with patch(
            "app.services.ai_search.pipeline.run_ai_search_v3",
            new=AsyncMock(return_value=(_v3_response(), False)),
        ):
            async with AsyncSessionLocal() as db:
                published = await publish_comparison_article(db, "TCS", "INFY", "TCS", "Infosys", sector="IT")
                assert published is not None
                assert published["slug"] == slug

                article = (await db.execute(
                    select(IntelligenceArticle).where(IntelligenceArticle.slug == slug)
                )).scalar_one_or_none()
                assert article is not None
                # what_happened/why_it_matters are composed from
                # holding_analysis/target_analysis/comparison/tradeoff/
                # decision_framework -- real content here proves those
                # fields survived the V3 response intact.
                assert article.what_happened and "TCS" in article.what_happened
                assert article.why_it_matters
                assert "Margin stability" in article.why_it_matters or "growth upside" in article.why_it_matters.lower()
                # key_takeaway composed from decision_framework.ai_stance + decision_summary
                assert "Neutral-to-cautious" in article.key_takeaway
                # companies_affected derived from comparison[] advantage counts
                # (2 holding, 1 target here -- not a >=2 lean, so both stay neutral)
                assert len(article.companies_affected) == 2
                assert article.market_context["decision_intelligence"]["engine_recommendation"]["favored_entity"] == "TCS"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.slug == slug))
            await db.commit()
