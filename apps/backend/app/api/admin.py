"""Protected operational endpoints — admin-key gated, not for end users.

Distinct from /api/publishing (ops dashboard, its own admin-gated endpoints
for content review) — this is infra/db status, for spotting misconfigurations
like an unmounted volume before they cause data loss.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin_key
from app.db.session import get_db

router = APIRouter()


@router.get("/db-status", dependencies=[Depends(require_admin_key)])
async def db_status_endpoint():
    from app.db.session import engine
    from app.db.health import db_status
    return await db_status(engine)


@router.post("/backfill-seo-intelligence", dependencies=[Depends(require_admin_key)])
async def backfill_seo_intelligence(
    limit: int = 500,
    db: AsyncSession = Depends(get_db),
):
    """
    One-time metadata backfill for the AI Newsroom redesign (2026-08-10,
    Decision 1 of 2 per the user's follow-up: "do 1 unconditionally, do 2
    as its own project"). Populates headline_angle/primary_keyword/
    secondary_keywords/entity_keywords/question_keywords/
    internal_link_candidates on articles published BEFORE the SEO
    Intelligence layer existed (those columns are simply NULL on them —
    publisher.py only started writing them going forward).

    Deliberately narrow: computed entirely from each article's own already-
    stored real companies_affected/sectors_affected/headline/article_type —
    no LLM call, no new data. Never touches headline, seo_title,
    meta_description, or any other visibly-published text — this is
    invisible-to-readers metadata only. Rewriting the visible SEO title/
    meta description for already-indexed URLs is a separate, deliberately
    NOT-included follow-up (needs its own batched rollout with Search
    Console monitoring, per the user's explicit call).

    Idempotent and safe to re-run: only touches rows where
    headline_angle IS NULL, so articles already backfilled (or published
    after the SEO Intelligence layer went live) are never re-processed.
    limit caps how many rows one call processes, so a very large backlog
    can be worked through in safe batches rather than one giant transaction.
    """
    from app.db.models.intelligence_article import IntelligenceArticle
    from app.services.seo_intelligence import compute_seo_intelligence
    from app.services.symbol_normalization import normalize_symbol
    from app.services.aipe.publisher import _sector_link

    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .where(IntelligenceArticle.headline_angle.is_(None))
        .limit(limit)
    )
    articles = result.scalars().all()

    updated = 0
    for a in articles:
        seo_intel = compute_seo_intelligence(
            article_type=a.article_type,
            headline=a.headline or "",
            companies_affected=a.companies_affected or [],
            sectors_affected=a.sectors_affected or [],
            themes=[t.get("theme") for t in (a.related_themes or []) if isinstance(t, dict) and t.get("theme")],
            has_historical=bool(a.historical_events),
            sector_link_fn=_sector_link,
            normalize_symbol_fn=normalize_symbol,
        )
        a.headline_angle = seo_intel["headline_angle"]
        a.primary_keyword = seo_intel["primary_keyword"]
        a.secondary_keywords = seo_intel["secondary_keywords"]
        a.entity_keywords = seo_intel["entity_keywords"]
        a.question_keywords = seo_intel["question_keywords"]
        a.internal_link_candidates = seo_intel["internal_link_candidates"]
        updated += 1

    await db.commit()

    remaining = await db.execute(
        select(IntelligenceArticle.id)
        .where(IntelligenceArticle.status == "published")
        .where(IntelligenceArticle.headline_angle.is_(None))
        .limit(1)
    )
    has_more = remaining.scalar_one_or_none() is not None

    return {"updated": updated, "has_more": has_more}


@router.post("/backfill-comparison-content", dependencies=[Depends(require_admin_key)])
async def backfill_comparison_content(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    One-time repair for every already-published comparison_intelligence
    article, after a live bug report (2026-08-11): companies_affected
    hardcoded reason="Comparison subject" and impact="neutral" for BOTH
    companies on every comparison, and key_takeaway was set to the bare
    stance word alone (e.g. "Neutral") with no context — both rendered as
    generic/unhelpful placeholders on the article page's "Why These Are
    Affected" and "30-Second Answer" sections, even though the article's
    OWN already-stored market_context.decision_intelligence (from the
    original run_ai_search call) carried real per-company theses and a
    real decision summary the whole time.

    Recomputes from each article's own already-stored market_context —
    no fresh run_ai_search call, no new AI generation, nothing invented.
    Idempotent and safe to re-run: articles whose companies_affected no
    longer contain the literal placeholder string are skipped.
    """
    from app.db.models.intelligence_article import IntelligenceArticle
    from app.services.aipe.comparison_publisher import _build_companies_affected, compose_key_takeaway

    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .where(IntelligenceArticle.article_type == "comparison_intelligence")
        .limit(limit)
    )
    articles = result.scalars().all()

    updated = 0
    skipped = 0
    for a in articles:
        companies = a.companies_affected or []
        still_placeholder = any((c.get("reason") or "") == "Comparison subject" for c in companies)
        if not still_placeholder:
            skipped += 1
            continue

        di = (a.market_context or {}).get("decision_intelligence") or {}
        if not di:
            skipped += 1
            continue

        # Real symbols/names come from the article's own already-stored
        # companies_affected — never re-derived or guessed.
        if len(companies) != 2:
            skipped += 1
            continue
        name_a, symbol_a = companies[0].get("name", ""), companies[0].get("symbol", "")
        name_b, symbol_b = companies[1].get("name", ""), companies[1].get("symbol", "")

        a.companies_affected = _build_companies_affected(di, name_a, symbol_a, name_b, symbol_b)
        decision_summary = a.executive_summary or di.get("decision_summary") or ""
        a.key_takeaway = compose_key_takeaway(di, decision_summary)
        updated += 1

    await db.commit()
    return {"updated": updated, "skipped": skipped, "total_checked": len(articles)}
