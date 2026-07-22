"""
Public Intelligence Insights API — read-only, published articles only.

Serves the public /insights pages (SEO article surface). This is distinct
from /api/publishing, which is the internal ops/monitoring dashboard API
and exposes ops-only fields (validation internals, trigger data) that stay
internal. `views` is public — it's a real engaged-read counter, incremented
via POST /{slug}/view (see below), not an ops metric.

GET  /api/insights/            -> paginated list of published articles
GET  /api/insights/{slug}      -> full public detail for one article
POST /api/insights/{slug}/view -> record one engaged read (deduped per
                                   visitor per day via Redis)
POST /api/insights/{slug}/share -> record one share-channel click (no dedup)
"""
from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import cache_get, cache_set
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import get_db

router = APIRouter()

_WORDS_PER_MINUTE = 200


def _read_time_minutes(a: IntelligenceArticle) -> int:
    """Real word count across the article's own body fields, not a fabricated
    estimate — read_time is never invented, just derived from actual content
    already on the row (including fields _list_row doesn't otherwise expose)."""
    text = " ".join(filter(None, [
        a.executive_summary, a.key_takeaway, a.why_it_matters, a.what_happened,
    ]))
    words = len(text.split())
    return max(1, round(words / _WORDS_PER_MINUTE))


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
        # event_score is already the same real 0-100 relevance score the rest
        # of the app calls "impact_score" (Events, etc.) — aliased here for
        # naming consistency across the homepage's article and event cards.
        "impact_score":       a.event_score,
        "read_time_minutes":  _read_time_minutes(a),
        "views":              a.views,
        "share_count":        a.share_count,
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
        "story_version":       a.story_version,
        "update_history":      a.update_history,
        "created_at":          a.created_at.isoformat() if a.created_at else None,
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


@router.post("/{slug}/view")
async def record_view(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Record one engaged read. Called by the frontend after a reader has
    actually spent time with the article (not fired on page load — a bounce
    shouldn't count), so this is a real "people who read at least part of
    this" counter, not a raw hit counter.

    Deduped per visitor per article per day via Redis so reloading the same
    article doesn't inflate the count — returns counted=False (current
    count, unchanged) on a repeat within the window rather than erroring,
    since the caller doesn't need to treat that as a failure.
    """
    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.slug == slug)
        .where(IntelligenceArticle.status == "published")
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")

    visitor_hash = hashlib.sha256(f"{get_remote_address(request)}:{slug}".encode()).hexdigest()[:16]
    dedup_key = f"article_view:{visitor_hash}"
    if await cache_get(dedup_key):
        return {"views": art.views, "counted": False}

    art.views += 1
    await db.commit()
    await cache_set(dedup_key, "1", ttl=86400)
    return {"views": art.views, "counted": True}


@router.post("/{slug}/share")
async def record_share(slug: str, db: AsyncSession = Depends(get_db)):
    """
    Record one share action — called each time a reader actually clicks a
    share channel or copies the link (not when the share popover merely
    opens). No dedup: unlike a view, sharing to three platforms in one
    visit is genuinely three shares, not an inflated count of one.
    """
    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.slug == slug)
        .where(IntelligenceArticle.status == "published")
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")

    art.share_count += 1
    await db.commit()
    return {"share_count": art.share_count}
