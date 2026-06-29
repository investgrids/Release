"""RBI press release RSS provider."""
from __future__ import annotations

import hashlib
from datetime import date
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx

from .base import BaseProvider, RawItem

_URL = "https://www.rbi.org.in/Scripts/RSS.aspx"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}


def _parse_date(s: str) -> str:
    if not s:
        return ""
    try:
        return parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except Exception:
        return s[:10]


class RBIProvider(BaseProvider):
    source_name = "RBI"

    async def fetch_latest(self) -> list[dict]:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=12, follow_redirects=True) as c:
            r = await c.get(_URL)
            r.raise_for_status()
        return _parse_xml(r.text)

    async def fetch_by_date(self, target: date) -> list[dict]:
        items = await self.fetch_latest()
        ts = target.isoformat()
        return [i for i in items if i.get("published_at", "").startswith(ts)]

    def normalize(self, raw: dict) -> RawItem | None:
        headline = (raw.get("headline") or "").strip()
        if not headline:
            return None
        return RawItem(
            id=raw.get("id") or f"rbi-{hashlib.md5(headline.encode()).hexdigest()[:12]}",
            headline=headline[:512],
            summary=raw.get("summary", "")[:1000],
            source="RBI",
            url=raw.get("url", ""),
            published_at=raw.get("published_at", ""),
            impact_score=9.0,
            event_type="policy",
            ministry="Reserve Bank of India",
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
        results.append({
            "id":           f"rbi-{hashlib.md5(title.encode()).hexdigest()[:12]}",
            "headline":     title,
            "summary":      (item.findtext("description") or "").strip()[:1000],
            "url":          (item.findtext("link") or "").strip(),
            "published_at": _parse_date((item.findtext("pubDate") or "").strip()),
        })
    return results[:20]
