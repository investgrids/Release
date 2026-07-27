"""Homepage Intelligence (Phase 3, Priority 1) — GET /api/homepage/intelligence.

Own router, same reasoning as every ai_search_*.py file this session:
routes appended to a large existing router have proven unreachable under
this FastAPI version.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import get_db
from app.services import homepage_intelligence as hi

router = APIRouter()
log = structlog.get_logger(__name__)


@router.get("/intelligence")
async def homepage_intelligence(db: AsyncSession = Depends(get_db)):
    """Returns {"available": False} when there's no morning_intelligence
    article yet today (first-ever run, or before the 06:00 IST job has
    fired) — the frontend just falls back to its existing AI Market Brief
    card alone. Never a 404."""
    article = (await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.article_type == "morning_intelligence")
        .order_by(IntelligenceArticle.published_at.desc())
        .limit(1)
    )).scalars().first()
    if not article:
        return {"available": False}

    try:
        await hi.record_snapshot_if_missing(db, article)
    except Exception as exc:
        log.warning("homepage_intelligence.snapshot_fail", exc=str(exc)[:160])

    yesterday_changes = await hi.get_yesterday_changes(db, article)
    ai_prediction = hi.get_ai_prediction(article)

    # Today's Biggest Story / Ripple / Companies Most Likely To Move /
    # Biggest Opportunity / Highest Risk now all come from the SAME Latest
    # Biggest Events Engine that ranks the Events page (event_lifecycle.py)
    # — the homepage no longer independently decides what "today's story"
    # is. Confidence / What Changed / AI Prediction stay article-sourced
    # (a market-wide daily read is a genuinely different thing from one
    # event's own confidence, not a second competing version of the same
    # claim). Best-effort: if the events engine finds nothing, the hero
    # falls back to the article's own fields — never a broken section.
    try:
        from app.services.event_lifecycle import get_homepage_event_intelligence
        event_intel = await get_homepage_event_intelligence(db)
    except Exception as exc:
        log.warning("homepage_intelligence.event_engine_fail", exc=str(exc)[:160])
        event_intel = {"available": False}

    return {
        "available": True,
        "article_id": article.id,
        "yesterday_changes": yesterday_changes,
        "ai_prediction": ai_prediction,
        "event": event_intel,
    }
