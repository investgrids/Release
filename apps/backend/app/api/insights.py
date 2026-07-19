"""
Public Intelligence Insights API — read-only, published articles only.

Serves the public /insights pages (SEO article surface). This is distinct
from /api/publishing, which is the internal ops/monitoring dashboard API
and exposes ops-only fields (views, validation internals, trigger data)
that must never be shown to end users.

GET /api/insights/        -> paginated list of published articles
GET /api/insights/{slug}  -> full public detail for one article
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import get_db

router = APIRouter()


def _list_row(a: IntelligenceArticle) -> dict:
    return {
        "id":                 a.id,
        "slug":               a.slug,
        "article_type":       a.article_type,
        "angle":              a.angle,
        "angle_entity":       a.angle_entity,
        "is_evergreen":       a.is_evergreen,
        "headline":           a.headline,
        "key_takeaway":       a.key_takeaway,
        "executive_summary":  a.executive_summary,
        "seo_title":          a.seo_title,
        "meta_description":   a.meta_description,
        "companies_affected": a.companies_affected,
        "sectors_affected":   a.sectors_affected,
        "confidence_score":   a.confidence_score,
        "update_count":       a.update_count,
        "published_at":       a.published_at.isoformat() if a.published_at else None,
        "last_updated":       a.last_updated.isoformat() if a.last_updated else None,
    }


def _detail_row(a: IntelligenceArticle) -> dict:
    base = _list_row(a)
    base.update({
        "why_it_matters":      a.why_it_matters,
        "what_happened":       a.what_happened,
        "opportunities":       a.opportunities,
        "risks":               a.risks,
        "historical_events":   a.historical_events,
        "ripple_effect":       a.ripple_effect,
        "what_to_watch_next":  a.what_to_watch_next,
        "faqs":                a.faqs,
        "sources":             a.sources,
        "internal_links":      a.internal_links,
        "related_companies":   a.related_companies,
        "related_themes":      a.related_themes,
        "canonical_url":       a.canonical_url,
        "json_ld":             a.json_ld,
        "parent_event_group_id": a.parent_event_group_id,
        "related_articles":    [],  # filled in by get_insight() — needs a DB lookup
    })
    return base


@router.get("/")
async def list_insights(
    article_type: Optional[str] = Query(None),
    limit:        int           = Query(20, le=100),
    offset:       int           = Query(0),
    db:           AsyncSession  = Depends(get_db),
):
    q = (
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .order_by(IntelligenceArticle.published_at.desc())
    )
    if article_type:
        q = q.where(IntelligenceArticle.article_type == article_type)
    q = q.offset(offset).limit(limit)

    result = await db.execute(q)
    articles = result.scalars().all()

    cq = select(func.count()).select_from(IntelligenceArticle).where(IntelligenceArticle.status == "published")
    if article_type:
        cq = cq.where(IntelligenceArticle.article_type == article_type)
    total = (await db.execute(cq)).scalar() or 0

    return {
        "total":  total,
        "offset": offset,
        "limit":  limit,
        "items":  [_list_row(a) for a in articles],
    }


@router.get("/company/{symbol}")
async def get_company_insights(
    symbol: str,
    limit: int = Query(10, le=30),
    db: AsyncSession = Depends(get_db),
):
    """
    Company Intelligence Hub feed: real AIPE articles mentioning this
    company (as a primary companies_affected entry or a related_companies
    cross-link) plus real historical_market_events coverage — backs the
    "Latest Intelligence" section on /companies/{symbol}, replacing what
    used to be hardcoded placeholder story cards there.
    """
    symbol = symbol.strip().upper()

    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .order_by(IntelligenceArticle.published_at.desc())
        .limit(300)
    )
    all_articles = result.scalars().all()

    def _mentions(a: IntelligenceArticle) -> bool:
        for c in (a.companies_affected or []):
            if isinstance(c, dict) and str(c.get("symbol", "")).upper() == symbol:
                return True
        for c in (a.related_companies or []):
            if isinstance(c, dict) and str(c.get("symbol", "")).upper() == symbol:
                return True
        return False

    matched = [a for a in all_articles if _mentions(a)][:limit]
    group_ids = {a.parent_event_group_id for a in matched if a.parent_event_group_id}

    from app.db.models.historical_memory import HistoricalMarketEvent
    hist_result = await db.execute(
        select(HistoricalMarketEvent)
        .where(HistoricalMarketEvent.companies.contains([symbol]))
        .order_by(HistoricalMarketEvent.event_date.desc())
        .limit(8)
    )
    historical = hist_result.scalars().all()

    return {
        "symbol": symbol,
        "articles": [_list_row(a) for a in matched],
        "campaign_count": len(group_ids),
        "historical_events": [
            {
                "event": h.event_title,
                "date": h.event_date.strftime("%b %Y") if h.event_date else None,
                "category": h.category,
                "outcome": h.nifty_1d,
                "key_lesson": h.key_lesson,
            }
            for h in historical
        ],
    }


@router.get("/{slug}")
async def get_insight(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.slug == slug)
        .where(IntelligenceArticle.status == "published")
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")

    row = _detail_row(art)

    # Other angles on the same underlying event (primary + per-company +
    # sector-rollup siblings) — only set on articles published after the
    # multi-angle fan-out shipped, so older articles simply have none.
    if art.parent_event_group_id:
        sib_result = await db.execute(
            select(IntelligenceArticle)
            .where(IntelligenceArticle.parent_event_group_id == art.parent_event_group_id)
            .where(IntelligenceArticle.id != art.id)
            .where(IntelligenceArticle.status == "published")
        )
        siblings = sib_result.scalars().all()
        row["related_articles"] = [
            {
                "slug": s.slug, "headline": s.headline, "angle": s.angle,
                "angle_entity": s.angle_entity, "article_type": s.article_type,
            }
            for s in siblings
        ]

    return row
