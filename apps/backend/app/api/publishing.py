"""
AIPE Operations API — serves the /operations/intelligence monitoring dashboard.

This is NOT a CMS. There are NO create/edit endpoints.
All publishing is fully autonomous.

GET  /api/publishing/status          → engine + system health
GET  /api/publishing/articles        → paginated article list
GET  /api/publishing/articles/{id}   → single article (full content)
GET  /api/publishing/metrics         → publishing metrics + daily chart
GET  /api/publishing/market-coverage → what topics were covered today
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import get_db
from app.services.aipe.publisher import get_engine_stats

router = APIRouter()

_IST = timezone(timedelta(hours=5, minutes=30))


def _today_utc():
    today_ist = datetime.now(_IST).replace(hour=0, minute=0, second=0, microsecond=0)
    return today_ist.astimezone(timezone.utc)


# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/status")
async def engine_status(db: AsyncSession = Depends(get_db)):
    stats = get_engine_stats()
    today_utc = _today_utc()

    # Article totals
    total_r = await db.execute(select(func.count()).select_from(IntelligenceArticle))
    total = total_r.scalar() or 0

    pub_r = await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
    )
    published = pub_r.scalar() or 0

    # Today's published
    today_pub_r = await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(IntelligenceArticle.published_at >= today_utc)
        .where(IntelligenceArticle.status == "published")
    )
    published_today = today_pub_r.scalar() or 0

    # Today's updated
    today_upd_r = await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(IntelligenceArticle.last_updated >= today_utc)
        .where(IntelligenceArticle.lifecycle_status == "updated")
    )
    updated_today = today_upd_r.scalar() or 0

    # Avg confidence
    conf_r = await db.execute(
        select(func.avg(IntelligenceArticle.confidence_score))
        .where(IntelligenceArticle.status == "published")
    )
    avg_conf = round(float(conf_r.scalar() or 0) * 100, 1)

    # Avg SEO
    seo_r = await db.execute(
        select(func.avg(IntelligenceArticle.seo_score))
        .where(IntelligenceArticle.status == "published")
    )
    avg_seo = round(float(seo_r.scalar() or 0), 1)

    # Validation failures today
    fail_r = await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(IntelligenceArticle.created_at >= today_utc)
        .where(IntelligenceArticle.status == "failed")
    )
    failed_today = fail_r.scalar() or 0

    # KG and historical — read from DB availability
    # (future: query actual counts from those tables)
    return {
        "engine": {
            "status":              stats.get("scheduler_status", "idle"),
            "running":             stats.get("running", False),
            "last_run":            stats.get("last_run"),
            "avg_publish_time_s":  stats.get("avg_publish_time_s", 0),
            "errors":              stats.get("errors", 0),
            "articles_waiting":    stats.get("articles_waiting", 0),
        },
        "market_story": {
            "status":              stats.get("market_story_status", "unknown"),
            "mie_hash":            stats.get("last_mie_hash"),
        },
        "today": {
            "published":           published_today,
            "updated":             updated_today,
            "generated":           stats.get("generated_today", 0),
            "validation_failures": failed_today,
            "max_per_day":         8,
            "remaining_slots":     max(0, 8 - published_today),
        },
        "totals": {
            "total":     total,
            "published": published,
        },
        "quality": {
            "avg_confidence": avg_conf,
            "avg_seo_score":  avg_seo,
        },
        "subsystems": {
            "knowledge_graph":    "active",
            "historical_memory":  "active",
            "learning_engine":    "active",
            "mie":                "active",
            "duplicate_detector": "active",
        },
    }


# ── Articles ───────────────────────────────────────────────────────────────────

@router.get("/articles")
async def list_articles(
    status:       Optional[str] = Query(None),
    article_type: Optional[str] = Query(None),
    lifecycle:    Optional[str] = Query(None),
    limit:        int           = Query(20, le=100),
    offset:       int           = Query(0),
    db:           AsyncSession  = Depends(get_db),
):
    q = select(IntelligenceArticle).order_by(IntelligenceArticle.created_at.desc())
    if status:
        q = q.where(IntelligenceArticle.status == status)
    if article_type:
        q = q.where(IntelligenceArticle.article_type == article_type)
    if lifecycle:
        q = q.where(IntelligenceArticle.lifecycle_status == lifecycle)
    q = q.offset(offset).limit(limit)

    result = await db.execute(q)
    articles = result.scalars().all()

    # Count
    cq = select(func.count()).select_from(IntelligenceArticle)
    if status:   cq = cq.where(IntelligenceArticle.status == status)
    if article_type: cq = cq.where(IntelligenceArticle.article_type == article_type)
    if lifecycle: cq = cq.where(IntelligenceArticle.lifecycle_status == lifecycle)
    total = (await db.execute(cq)).scalar() or 0

    return {
        "total":    total,
        "offset":   offset,
        "limit":    limit,
        "articles": [_list_row(a) for a in articles],
    }


@router.get("/articles/{article_id}")
async def get_article(article_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IntelligenceArticle).where(IntelligenceArticle.id == article_id)
    )
    art = result.scalar_one_or_none()
    if not art:
        result = await db.execute(
            select(IntelligenceArticle).where(IntelligenceArticle.slug == article_id)
        )
        art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    return _full_row(art)


# ── Metrics ────────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def publishing_metrics(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)

    # 7-day daily published chart
    daily = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        r = await db.execute(
            select(func.count()).select_from(IntelligenceArticle)
            .where(IntelligenceArticle.published_at >= day)
            .where(IntelligenceArticle.published_at < day + timedelta(days=1))
        )
        daily.append({"date": day.strftime("%b %d"), "count": r.scalar() or 0})

    # By article type
    type_r = await db.execute(
        select(IntelligenceArticle.article_type, func.count())
        .where(IntelligenceArticle.status == "published")
        .group_by(IntelligenceArticle.article_type)
    )
    by_type = [{"type": r[0], "count": r[1]} for r in type_r.all()]

    # Lifecycle distribution
    lc_r = await db.execute(
        select(IntelligenceArticle.lifecycle_status, func.count())
        .group_by(IntelligenceArticle.lifecycle_status)
    )
    by_lifecycle = [{"status": r[0], "count": r[1]} for r in lc_r.all()]

    # Avg update count on updated articles
    upd_r = await db.execute(
        select(func.avg(IntelligenceArticle.update_count))
        .where(IntelligenceArticle.update_count > 0)
    )
    avg_updates = round(float(upd_r.scalar() or 0), 1)

    # Avg scores
    scores_r = await db.execute(
        select(
            func.avg(IntelligenceArticle.seo_score),
            func.avg(IntelligenceArticle.quality_score),
            func.avg(IntelligenceArticle.confidence_score),
        ).where(IntelligenceArticle.status == "published")
    )
    row = scores_r.one_or_none()
    return {
        "daily_published": daily,
        "by_type":         by_type,
        "by_lifecycle":    by_lifecycle,
        "avg_updates":     avg_updates,
        "avg_seo_score":   round(float(row[0] or 0), 1) if row else 0,
        "avg_quality":     round(float(row[1] or 0) * 100, 1) if row else 0,
        "avg_confidence":  round(float(row[2] or 0) * 100, 1) if row else 0,
    }


# ── Market coverage ────────────────────────────────────────────────────────────

@router.get("/market-coverage")
async def market_coverage(db: AsyncSession = Depends(get_db)):
    """What intelligence topics were covered today."""
    today_utc = _today_utc()
    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.published_at >= today_utc)
        .where(IntelligenceArticle.status == "published")
        .order_by(IntelligenceArticle.published_at)
    )
    today_articles = result.scalars().all()

    coverage = []
    for a in today_articles:
        coverage.append({
            "id":           a.id,
            "slug":         a.slug,
            "type":         a.article_type,
            "headline":     a.headline,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "update_count": a.update_count,
            "lifecycle":    a.lifecycle_status,
            "sectors":      [s.get("name", s) if isinstance(s, dict) else s
                             for s in (a.sectors_affected or [])[:3]],
            "story_id":     a.story_id,
        })

    return {
        "date":           datetime.now(_IST).strftime("%Y-%m-%d"),
        "count":          len(coverage),
        "articles":       coverage,
        "remaining_slots": max(0, 8 - len(coverage)),
    }


# ── Serializers ────────────────────────────────────────────────────────────────

def _list_row(a: IntelligenceArticle) -> dict:
    return {
        "id":                a.id,
        "slug":              a.slug,
        "article_type":      a.article_type,
        "story_id":          a.story_id,
        "story_version":     a.story_version,
        "lifecycle_status":  a.lifecycle_status,
        "status":            a.status,
        "headline":          a.headline,
        "key_takeaway":      a.key_takeaway,
        "executive_summary": a.executive_summary,
        "sectors_affected":  a.sectors_affected,
        "companies_affected": a.companies_affected,
        "update_count":      a.update_count,
        "validation_passed": a.validation_passed,
        "validation_failures": a.validation_failures,
        "event_score":       a.event_score,
        "confidence_score":  a.confidence_score,
        "quality_score":     a.quality_score,
        "seo_score":         a.seo_score,
        "views":             a.views,
        "trigger_type":      a.trigger_type,
        "trigger_event_id":  a.trigger_event_id,
        "published_at":      a.published_at.isoformat() if a.published_at else None,
        "last_updated":      a.last_updated.isoformat() if a.last_updated else None,
        "created_at":        a.created_at.isoformat() if a.created_at else None,
    }


def _full_row(a: IntelligenceArticle) -> dict:
    base = _list_row(a)
    base.update({
        "why_it_matters":     a.why_it_matters,
        "what_happened":      a.what_happened,
        "opportunities":      a.opportunities,
        "risks":              a.risks,
        "historical_events":  a.historical_events,
        "ripple_effect":      a.ripple_effect,
        "what_to_watch_next": a.what_to_watch_next,
        "faqs":               a.faqs,
        "sources":            a.sources,
        "internal_links":     a.internal_links,
        "related_companies":  a.related_companies,
        "related_themes":     a.related_themes,
        "seo_title":          a.seo_title,
        "meta_description":   a.meta_description,
        "canonical_url":      a.canonical_url,
        "json_ld":            a.json_ld,
        "market_context":     a.market_context,
        "update_history":     a.update_history,
        "validation_results": a.validation_results,
        "historical_refs":    a.historical_refs,
    })
    return base
