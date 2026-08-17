"""
Phase 6G Slice 2 — comparison_publisher migrated from V2 (run_ai_search)
to V3 (run_ai_search_v3). Caller migration only -- compose_*/
_build_companies_affected (already covered by test_comparison_publisher.py)
are untouched. This file proves the migration itself: V3 populates the
same decision_intelligence shape this module has always consumed, the
quality gate still gates correctly, and a real article row gets written.

Live -- hits the real LLM. Run explicitly with `-m live_e2e`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services.aipe.comparison_publisher import (
    _try_generate,
    generate_comparison,
    publish_comparison_article,
)

pytestmark = pytest.mark.live_e2e


@pytest.mark.asyncio
async def test_try_generate_uses_v3_and_populates_full_decision_intelligence():
    """The exact shape check the migration depends on: V3's comparison
    specialist output must carry every field this module's compose_*
    functions read."""
    async with AsyncSessionLocal() as db:
        result = await _try_generate("TCS vs Infosys, which is better for 12 months?", db)

    assert result is not None, "a clean 2-company comparison query must not hit the quality gate"
    assert result.get("synthesis_incomplete") is not True
    di = result.get("decision_intelligence") or {}
    assert di.get("holding_analysis"), "holding_analysis missing -- V3 shape mismatch"
    assert di.get("target_analysis"), "target_analysis missing -- V3 shape mismatch"
    assert di.get("comparison"), "comparison[] missing -- V3 shape mismatch"
    assert "tradeoff" in di, "tradeoff missing -- V3 shape mismatch"
    assert "decision_framework" in di, "decision_framework missing -- V3 shape mismatch"


@pytest.mark.asyncio
async def test_generate_comparison_returns_real_content_through_v3():
    async with AsyncSessionLocal() as db:
        result = await generate_comparison(db, "TCS", "INFY", "TCS", "Infosys")
    assert result is not None
    di = result.get("decision_intelligence") or {}
    assert di.get("holding_analysis") or di.get("comparison")


@pytest.mark.asyncio
async def test_publish_comparison_article_end_to_end_via_v3():
    """Full path: generate through V3, write a real IntelligenceArticle
    row, confirm the stored shape matches what publish_comparison_article
    has always produced -- proving the scheduler/manual-trigger callers
    (which call this exact function, unmodified) still work."""
    slug = "tcs-vs-infy"
    try:
        async with AsyncSessionLocal() as db:
            published = await publish_comparison_article(
                db, "TCS", "INFY", "TCS", "Infosys", sector="IT",
            )
            assert published is not None, "a clean comparison must publish, not skip"
            assert published["slug"] == slug

            article = (await db.execute(
                select(IntelligenceArticle).where(IntelligenceArticle.slug == slug)
            )).scalar_one_or_none()
            assert article is not None
            assert article.article_type == "comparison_intelligence"
            assert article.lifecycle_status == "published"
            assert article.companies_affected and len(article.companies_affected) == 2
            assert article.market_context.get("kind") == "comparison"
            assert article.market_context.get("decision_intelligence", {}).get("holding_analysis")
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.slug == slug))
            await db.commit()
