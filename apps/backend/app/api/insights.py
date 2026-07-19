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
    return _detail_row(art)
