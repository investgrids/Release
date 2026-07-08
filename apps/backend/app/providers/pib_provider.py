"""PIB (Press Information Bureau) press release provider."""
from __future__ import annotations

import hashlib
from datetime import date
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx

from .base import BaseProvider, RawItem

# Finance ministry feed — ModId=6 targets Finance & Economic Affairs
_URL = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}

_MINISTRY_KEYWORDS = {
    "finance": "Ministry of Finance",
    "commerce": "Ministry of Commerce",
    "defence": "Ministry of Defence",
    "railways": "Ministry of Railways",
    "energy": "Ministry of Power",
    "petroleum": "Ministry of Petroleum",
    "rbi": "Reserve Bank of India",
    "sebi": "Securities and Exchange Board",
    "niti": "NITI Aayog",
}


def _guess_ministry(text: str) -> str:
    low = text.lower()
    for kw, name in _MINISTRY_KEYWORDS.items():
        if kw in low:
            return name
    return "Government of India"


def _parse_date(s: str) -> str:
    if not s:
        return ""
    try:
        return parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except Exception:
        return s[:10]


class PIBProvider(BaseProvider):
    source_name = "PIB"

    async def fetch_latest(self) -> list[dict]:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=12, follow_redirects=True) as c:
            r = await c.get(_URL)
            r.raise_for_status()
        return _parse_xml(r.content)

    async def fetch_by_date(self, target: date) -> list[dict]:
        items = await self.fetch_latest()
        ts = target.isoformat()
        return [i for i in items if i.get("published_at", "").startswith(ts)]

    def normalize(self, raw: dict) -> RawItem | None:
        headline = (raw.get("headline") or "").strip()
        if not headline:
            return None
        ministry = _guess_ministry(headline + " " + raw.get("summary", ""))
        return RawItem(
            id=raw.get("id") or f"pib-{hashlib.md5(headline.encode()).hexdigest()[:12]}",
            headline=headline[:512],
            summary=raw.get("summary", "")[:1000],
            source="PIB",
            url=raw.get("url", ""),
            published_at=raw.get("published_at", ""),
            impact_score=8.0,
            event_type="policy",
            ministry=ministry,
        )


def _parse_xml(data: bytes) -> list[dict]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    results = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        results.append({
            "id":           f"pib-{hashlib.md5(title.encode()).hexdigest()[:12]}",
            "headline":     title,
            "summary":      (item.findtext("description") or "").strip()[:1000],
            "url":          (item.findtext("link") or "").strip(),
            "published_at": _parse_date((item.findtext("pubDate") or "").strip()),
        })
    return results[:20]
