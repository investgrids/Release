"""Live Intelligence (Phase 3, Priority 2) — GET /api/live-intelligence/feed.

Own router, same reasoning as every other dedicated router this session.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import cache_get, cache_set
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import get_db
from app.services import live_intelligence as li
from app.services.aipe.signal_publisher import publish_signal

router = APIRouter()
log = structlog.get_logger(__name__)

_CACHE_KEY = "live_intelligence:feed:v1"
_CACHE_TTL = 300  # 5 min — matches MIE's own refresh cadence; each rebuild
                   # costs a real graph traversal + several DB queries, not
                   # something to redo on every homepage/opportunity-radar hit.


@router.get("/feed")
async def live_intelligence_feed(db: AsyncSession = Depends(get_db)):
    cached = await cache_get(_CACHE_KEY)
    if cached is not None:
        return {"items": cached}

    article = (await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.article_type == "morning_intelligence")
        .order_by(IntelligenceArticle.published_at.desc())
        .limit(1)
    )).scalars().first()

    items = await li.get_live_intelligence(db, article)

    # Give each detected signal a permanent /intelligence/signal/{slug} page
    # (homepage audit, Priority 1) — only on a real cache miss, not on every
    # request, since publishing is a DB write and the underlying signal
    # hasn't changed within the 5-minute cache window anyway. One failing
    # publish (e.g. a transient DB hiccup) drops that item's slug but never
    # breaks the feed itself.
    for item in items:
        try:
            published = await publish_signal(db, item)
            item["slug"] = published["slug"]
        except Exception as exc:
            log.warning("live_intelligence.publish_fail", type=item.get("type"), exc=str(exc)[:160])

    await cache_set(_CACHE_KEY, items, ttl=_CACHE_TTL)
    return {"items": items}
