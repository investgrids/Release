"""
News Worker — runs every 15 minutes.
Fetches NSE/BSE announcements + RSS news.
Writes to news_articles (raw) and creates events (pending enrichment).
"""
from __future__ import annotations

import asyncio
import hashlib
import structlog
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.services.news_fetcher import get_live_news

logger = structlog.get_logger(__name__)

_NSE_URL = "https://www.nseindia.com/api/corporate-announcements?index=equities"
_BSE_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnGetAnnouncemnt/w?scrip_cd=&ann_type=C&segment=&strSearch="

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_id(source: str, value: str) -> str:
    h = hashlib.md5(value.encode()).hexdigest()[:10]
    return f"{source.lower()}-{h}"


async def _fetch_nse() -> list[dict]:
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10, follow_redirects=True) as c:
            resp = await c.get(_NSE_URL)
            resp.raise_for_status()
            data = resp.json()
            items = data if isinstance(data, list) else data.get("data", [])
            return [
                {
                    "id": f"nse-{i.get('an_no', _make_id('nse', i.get('desc', '')))}",
                    "headline": (i.get("desc") or i.get("subject") or "")[:512],
                    "summary": (i.get("attchmntText") or i.get("desc") or "")[:1000],
                    "source": "NSE",
                    "published_at": (i.get("sort_date") or "")[:10] or "—",
                    "companies": [i["symbol"]] if i.get("symbol") else [],
                    "impact_score": 7.5,
                    "event_source": "NSE",
                }
                for i in items[:30]
                if i.get("desc") or i.get("subject")
            ]
    except Exception as exc:
        logger.debug("NSE fetch failed: %s", exc)
        return []


async def _fetch_bse() -> list[dict]:
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10, follow_redirects=True) as c:
            resp = await c.get(_BSE_URL)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("Table", data) if isinstance(data, dict) else data
            return [
                {
                    "id": f"bse-{i.get('NEWSID', _make_id('bse', i.get('NEWSSUB', '')))}",
                    "headline": (i.get("NEWSSUB") or "")[:512],
                    "summary": (i.get("NEWSSUB") or "")[:1000],
                    "source": "BSE",
                    "published_at": str(i.get("NEWS_DT", ""))[:10] or "—",
                    "companies": [],
                    "impact_score": 6.5,
                    "event_source": "BSE",
                }
                for i in (items[:30] if isinstance(items, list) else [])
                if i.get("NEWSSUB")
            ]
    except Exception as exc:
        logger.debug("BSE fetch failed: %s", exc)
        return []


async def _persist_articles(db: AsyncSession, articles: list[dict]) -> list[str]:
    """Save to news_articles; return list of newly-saved IDs."""
    from sqlalchemy import select
    from app.db.models_legacy import NewsArticle

    new_ids: list[str] = []
    for art in articles:
        if not art.get("id") or not art.get("headline"):
            continue
        exists = await db.execute(
            select(NewsArticle.id).where(NewsArticle.id == art["id"])
        )
        if exists.scalar_one_or_none() is not None:
            continue
        db.add(NewsArticle(
            id=art["id"],
            headline=art["headline"],
            summary=art.get("summary", ""),
            source=art.get("source", ""),
            published_at=art.get("published_at", "—"),
            companies=art.get("companies", []),
            impact_score=art.get("impact_score", 7.0),
        ))
        new_ids.append(art["id"])
    if new_ids:
        await db.commit()
    return new_ids


async def _create_events(db: AsyncSession, articles: list[dict], new_ids: set[str]) -> int:
    """Create an event row for each newly-saved NSE/BSE announcement."""
    from sqlalchemy import select
    from app.db.models.event import Event

    saved = 0
    # Only create events for exchange announcements (not generic RSS)
    exchange_sources = {"NSE", "BSE"}
    for art in articles:
        if art["id"] not in new_ids:
            continue
        if art.get("event_source") not in exchange_sources:
            continue
        # Avoid duplicates in events table
        exists = await db.execute(select(Event.id).where(Event.id == art["id"]))
        if exists.scalar_one_or_none() is not None:
            continue

        db.add(Event(
            id=art["id"],
            title=art["headline"],
            summary=art.get("summary", ""),
            description=art.get("summary", ""),
            source=art.get("source", ""),
            event_type="corporate",
            companies=art.get("companies", []),
            impact_score=art.get("impact_score", 7.0),
            confidence=0.0,
            published_at=_now(),
            created_at=_now(),
            updated_at=_now(),
            enrichment_status="pending",
        ))
        saved += 1

    if saved:
        await db.commit()
    return saved


async def run_news_worker() -> None:
    logger.info("News worker started")
    from app.core.config import settings

    while True:
        try:
            nse, bse, rss = await asyncio.gather(
                _fetch_nse(),
                _fetch_bse(),
                get_live_news(limit=40),
                return_exceptions=True,
            )
            articles: list[dict] = []
            for batch in [nse, bse, rss]:
                if isinstance(batch, list):
                    articles.extend(batch)

            async with AsyncSessionLocal() as db:
                new_ids = await _persist_articles(db, articles)
                events_created = await _create_events(db, articles, set(new_ids))

            logger.info(
                "News worker: saved %d articles, created %d events",
                len(new_ids), events_created,
            )
        except Exception as exc:
            logger.error("News worker error: %s", exc, exc_info=True)

        await asyncio.sleep(settings.news_worker_interval_sec)
