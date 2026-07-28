"""
Comparison research pages (SEO Phase 2, §2.2) — permanent, indexable
/research/{slug} pages generated from a real AI Search comparison run.

Deliberately reuses ai_search_service.run_ai_search (V2, live in
production today) rather than waiting on the V3 pipeline — but with a
real quality gate this module adds: V2's own documented failure rate
(~47% synthesis-incomplete on comparison-shaped queries, per the V3
planning benchmark) means a naive "generate once, publish unconditionally"
approach would regularly publish hollow pages. generate_comparison()
retries a bounded number of times and ONLY returns a result when the
answer is genuinely complete (real decision_intelligence, not the
templated "didn't complete" fallback) — callers must treat None as "skip
this pair," never force-publish a degraded run.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

_MAX_ATTEMPTS = 3


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s


async def _try_generate(query: str, db: AsyncSession) -> dict | None:
    from app.services.ai_search_service import run_ai_search

    try:
        result = await run_ai_search(query, db)
    except Exception:
        return None
    if not result or result.get("synthesis_incomplete"):
        return None
    di = result.get("decision_intelligence") or {}
    # A genuinely complete comparison has real per-entity analysis, not
    # just intent detection + the deterministic engine_recommendation
    # block (present even on a degraded run).
    if not di.get("holding_analysis") and not di.get("comparison"):
        return None
    return result


async def generate_comparison(
    db: AsyncSession, symbol_a: str, symbol_b: str, name_a: str, name_b: str,
) -> dict | None:
    """Real comparison content or None — never a partial/degraded publish.
    Tries up to _MAX_ATTEMPTS times since V2's free-tier provider chain is
    genuinely flaky run-to-run for the same query (confirmed live: the
    exact same query succeeded on one attempt and hit the templated
    fallback on another)."""
    query = f"{name_a} vs {name_b}, which is better for 12 months?"
    for _ in range(_MAX_ATTEMPTS):
        result = await _try_generate(query, db)
        if result:
            return result
    return None


async def publish_comparison_article(
    db: AsyncSession, symbol_a: str, symbol_b: str, name_a: str, name_b: str, sector: str | None = None,
) -> dict | None:
    """Generates (with retry+quality-gate) and stores a comparison as a
    permanent IntelligenceArticle row. Returns the stored row's public
    fields, or None if no attempt produced real content — the caller
    (a seed script or an on-demand admin trigger) must treat None as
    "nothing published," not retry-forever or fabricate a stand-in."""
    from app.db.models.intelligence_article import IntelligenceArticle
    from sqlalchemy import select

    result = await generate_comparison(db, symbol_a, symbol_b, name_a, name_b)
    if not result:
        return None

    di = result.get("decision_intelligence") or {}
    verdict = result.get("investment_verdict") or {}
    ai_answer = result.get("answer") or {}

    slug = f"{_slugify(symbol_a)}-vs-{_slugify(symbol_b)}"
    site_url = (settings.frontend_url or "https://www.marketripple.in").rstrip("/")
    canonical_url = f"{site_url}/research/{slug}"

    headline = f"{name_a} vs {name_b}: Which Is The Better Investment?"
    decision_summary = di.get("decision_summary") or ai_answer.get("bottom_line") or ""
    meta_description = (decision_summary or f"AI-powered comparison of {name_a} and {name_b} — valuation, growth drivers, risks, and a research-framed verdict on MarketRipple.")[:160]

    now = datetime.now(timezone.utc)
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": headline,
        "description": meta_description,
        "datePublished": now.isoformat(),
        "dateModified": now.isoformat(),
        "author": {"@type": "Organization", "name": "MarketRipple AI Intelligence Engine"},
        "publisher": {"@type": "Organization", "name": "MarketRipple"},
        "mainEntityOfPage": canonical_url,
        "breadcrumb": {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "MarketRipple", "item": site_url},
                {"@type": "ListItem", "position": 2, "name": "Research", "item": f"{site_url}/research"},
                {"@type": "ListItem", "position": 3, "name": headline, "item": canonical_url},
            ],
        },
    }

    companies_affected = [
        {"name": name_a, "symbol": symbol_a, "impact": "neutral", "reason": "Comparison subject"},
        {"name": name_b, "symbol": symbol_b, "impact": "neutral", "reason": "Comparison subject"},
    ]
    sectors_affected = [{"name": sector, "impact": "neutral", "magnitude": "medium"}] if sector else []

    # market_context is the generic free-form JSON field on this model —
    # stashes the full comparison structure (holding/target analysis,
    # dimension-by-dimension table, tradeoff, decision_framework) without
    # a schema migration, same reasoning as market_context's existing use
    # elsewhere in the AIPE pipeline for "real structured context that
    # doesn't fit the fixed columns."
    market_context = {
        "kind": "comparison",
        "decision_intelligence": di,
        "investment_verdict": verdict,
    }

    existing = (await db.execute(
        select(IntelligenceArticle).where(IntelligenceArticle.slug == slug)
    )).scalar_one_or_none()

    if existing:
        existing.headline = headline
        existing.executive_summary = decision_summary
        existing.key_takeaway = di.get("decision_framework", {}).get("ai_stance") or decision_summary
        existing.companies_affected = companies_affected
        existing.sectors_affected = sectors_affected
        existing.seo_title = headline
        existing.meta_description = meta_description
        existing.canonical_url = canonical_url
        existing.json_ld = json_ld
        existing.market_context = market_context
        existing.last_updated = now
        existing.update_count = (existing.update_count or 0) + 1
        article = existing
    else:
        article = IntelligenceArticle(
            id=str(uuid.uuid4()), slug=slug, article_type="comparison_intelligence",
            angle="comparison", is_evergreen=True,
            lifecycle_status="published", status="published",
            headline=headline, executive_summary=decision_summary,
            key_takeaway=di.get("decision_framework", {}).get("ai_stance") or decision_summary,
            companies_affected=companies_affected, sectors_affected=sectors_affected,
            sources=["MarketRipple AI Search Engine"],
            seo_title=headline, meta_description=meta_description,
            canonical_url=canonical_url, json_ld=json_ld, market_context=market_context,
            confidence_score=float(verdict.get("confidence", 50) or 50) / 100,
            published_at=now, last_updated=now,
        )
        db.add(article)

    await db.commit()
    return {"slug": slug, "headline": headline}
