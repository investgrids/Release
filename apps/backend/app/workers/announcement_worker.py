"""
Announcement Worker — runs every hour.
Fetches RBI + PIB press releases.
Writes to:
  - news_articles (raw ingestion)
  - government_policies (normalised policy store)
  - events (pending enrichment) for high-impact policy releases
"""
from __future__ import annotations

import asyncio
import hashlib
import structlog
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)

_RBI_RSS = "https://www.rbi.org.in/Scripts/RSS.aspx"
_PIB_RSS = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}

_MINISTRY_MAP = {
    "RBI": "Reserve Bank of India",
    "PIB": "Press Information Bureau",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_id(source: str, title: str) -> str:
    h = hashlib.md5(title.lower().strip().encode()).hexdigest()[:12]
    return f"{source.lower()}-{h}"


def _parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        try:
            return datetime.fromisoformat(date_str[:10])
        except Exception:
            return None


async def _fetch_rss(url: str, source: str, impact: float = 8.5) -> list[dict]:
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=12, follow_redirects=True) as c:
            resp = await c.get(url)
            resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            desc = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            link = (item.findtext("link") or "").strip()
            items.append({
                "id": _make_id(source, title),
                "headline": title[:512],
                "summary": desc[:1000],
                "source": source,
                "published_at": pub_date[:10] if pub_date else "—",
                "pub_date_raw": pub_date,
                "companies": [],
                "impact_score": impact,
                "url": link,
                "ministry": _MINISTRY_MAP.get(source, source),
            })
        return items[:20]
    except Exception as exc:
        logger.debug("%s RSS fetch failed: %s", source, exc)
        return []


async def _persist_articles(db: AsyncSession, items: list[dict]) -> list[str]:
    from sqlalchemy import select
    from app.db.models_legacy import NewsArticle

    new_ids: list[str] = []
    for art in items:
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
            source=art["source"],
            published_at=art.get("published_at", "—"),
            companies=[],
            impact_score=art.get("impact_score", 8.0),
        ))
        new_ids.append(art["id"])
    if new_ids:
        await db.commit()
    return new_ids


async def _persist_policies(db: AsyncSession, items: list[dict]) -> int:
    from app.repositories.government_policy_repository import GovernmentPolicyRepository

    repo = GovernmentPolicyRepository(db)
    saved = 0
    for item in items:
        if not item.get("id") or not item.get("headline"):
            continue
        parsed_date = _parse_date(item.get("pub_date_raw", ""))
        await repo.upsert({
            "external_id": item["id"],
            "title": item["headline"],
            "ministry": item.get("ministry", ""),
            "announcement_date": parsed_date,
            "summary": item.get("summary", ""),
            "url": item.get("url", ""),
        })
        saved += 1
    if saved:
        await db.commit()
    return saved


async def _create_events(db: AsyncSession, items: list[dict], new_ids: set[str]) -> int:
    from sqlalchemy import select
    from app.db.models.event import Event

    saved = 0
    for item in items:
        if item["id"] not in new_ids:
            continue
        exists = await db.execute(select(Event.id).where(Event.id == item["id"]))
        if exists.scalar_one_or_none() is not None:
            continue

        parsed_date = _parse_date(item.get("pub_date_raw", ""))
        db.add(Event(
            id=item["id"],
            title=item["headline"],
            summary=item.get("summary", ""),
            description=item.get("summary", ""),
            source=item["source"],
            event_type="policy",
            companies=[],
            impact_score=item.get("impact_score", 8.0),
            confidence=0.0,
            event_date=parsed_date,
            published_at=_now(),
            created_at=_now(),
            updated_at=_now(),
            enrichment_status="pending",
        ))
        saved += 1

    if saved:
        await db.commit()
    return saved


async def run_announcement_worker() -> None:
    logger.info("Announcement worker started")
    from app.core.config import settings

    while True:
        try:
            rbi, pib = await asyncio.gather(
                _fetch_rss(_RBI_RSS, "RBI", impact=9.0),
                _fetch_rss(_PIB_RSS, "PIB", impact=8.0),
                return_exceptions=True,
            )
            items: list[dict] = []
            for batch in [rbi, pib]:
                if isinstance(batch, list):
                    items.extend(batch)

            async with AsyncSessionLocal() as db:
                new_ids = await _persist_articles(db, items)
                policies_saved = await _persist_policies(db, items)
                events_created = await _create_events(db, items, set(new_ids))

            logger.info(
                "Announcement worker: %d articles, %d policies, %d events",
                len(new_ids), policies_saved, events_created,
            )
        except Exception as exc:
            logger.error("Announcement worker error: %s", exc, exc_info=True)

        await asyncio.sleep(settings.announce_worker_interval_sec)
