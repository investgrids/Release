"""SEBI circulars provider — scrapes the SEBI RSS/sitemap feed."""
from __future__ import annotations

import hashlib
from datetime import date
from xml.etree import ElementTree as ET

import httpx

from .base import BaseProvider, RawItem

_URL = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doPmDetails=yes&rss=1"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}


class SEBIProvider(BaseProvider):
    source_name = "SEBI"

    async def fetch_latest(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=12, follow_redirects=True) as c:
                r = await c.get(_URL)
                r.raise_for_status()
            return _parse_xml(r.text)
        except Exception:
            # SEBI RSS is often unreliable; return empty gracefully
            return []

    async def fetch_by_date(self, target: date) -> list[dict]:
        items = await self.fetch_latest()
        ts = target.isoformat()
        return [i for i in items if i.get("published_at", "").startswith(ts)]

    def normalize(self, raw: dict) -> RawItem | None:
        headline = (raw.get("headline") or "").strip()
        if not headline:
            return None
        return RawItem(
            id=raw.get("id") or f"sebi-{hashlib.md5(headline.encode()).hexdigest()[:12]}",
            headline=headline[:512],
            summary=raw.get("summary", "")[:1000],
            source="SEBI",
            url=raw.get("url", ""),
            published_at=raw.get("published_at", ""),
            impact_score=8.5,
            event_type="regulatory",
            ministry="Securities and Exchange Board of India",
        )


def _parse_xml(text: str) -> list[dict]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    results = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        pub = (item.findtext("pubDate") or item.findtext("dc:date") or "").strip()
        results.append({
            "id":           f"sebi-{hashlib.md5(title.encode()).hexdigest()[:12]}",
            "headline":     title,
            "summary":      (item.findtext("description") or "").strip()[:1000],
            "url":          (item.findtext("link") or "").strip(),
            "published_at": pub[:10] if pub else "",
        })
    return results[:20]
