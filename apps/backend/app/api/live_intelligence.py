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
from app.services.aipe.signal_publisher import slug_for_item

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

    # P0-B (2026-09-01) -- read-only. Each detected signal's permanent
    # /intelligence/signal/{slug} page (homepage audit, Priority 1) still
    # gets a real, durable IntelligenceArticle row -- but that write now
    # happens only from run_signal_publish_cycle's own scheduled job (see
    # signal_publisher.py), never from this GET handler. slug_for_item()
    # is a pure function of the item alone (no DB access), so this returns
    # the exact same slug value the old write path returned -- the
    # response contract is unchanged; only the write side effect is gone.
    # A page can very briefly show a slug before the next cycle has
    # created its durable row (up to ~5 min, matching this cache's own
    # TTL) -- the accepted tradeoff of moving publication onto a
    # scheduled cadence instead of a request.
    for item in items:
        item["slug"] = slug_for_item(item)

    await cache_set(_CACHE_KEY, items, ttl=_CACHE_TTL)
    return {"items": items}
