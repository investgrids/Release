"""
RSS news provider — aggregates multiple India-finance RSS feeds.
Each feed config is a (url, source_name, impact_score) tuple.
"""
from __future__ import annotations

import hashlib
import time
from datetime import date
from email.utils import parsedate_to_datetime

import httpx

from .base import BaseProvider, RawItem

_FEEDS: list[tuple[str, str, float]] = [
    ("https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "Economic Times", 8.0),
    ("https://www.moneycontrol.com/rss/latestnews.xml",                      "Moneycontrol",   7.5),
    ("https://feeds.feedburner.com/ndtvprofit-latest",                        "NDTV Profit",    7.5),
    ("https://www.business-standard.com/rss/markets-106.rss",                 "Business Standard", 7.5),
    ("https://www.livemint.com/rss/markets",                                  "Livemint",       7.0),
    ("https://news.google.com/rss/search?q=Indian+stock+market+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en",
     "Google News India", 6.5),
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}

_INDIA_KEYWORDS = {
    "nifty", "sensex", "nse", "bse", "sebi", "rbi", "india", "rupee", "inr",
    "crore", "lakh", "ndtv", "moneycontrol", "zerodha", "reliance", "tata",
    "infosys", "hdfc", "icici", "bajaj", "adani", "wipro", "ipo", "budget",
}


def _is_india_relevant(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in _INDIA_KEYWORDS)


def _parse_pub_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        return date_str[:10]


class RSSProvider(BaseProvider):
    source_name = "RSS"

    async def fetch_latest(self) -> list[dict]:
        results: list[dict] = []
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10, follow_redirects=True) as c:
            for url, source, score in _FEEDS:
                try:
                    r = await c.get(url)
                    if r.status_code != 200:
                        continue
                    items = _parse_rss_xml(r.content, source, score)
                    results.extend(items)
                except Exception:
                    continue
        return results

    async def fetch_by_date(self, target: date) -> list[dict]:
        all_items = await self.fetch_latest()
        target_str = target.isoformat()
        return [i for i in all_items if i.get("published_at", "").startswith(target_str)]

    def normalize(self, raw: dict) -> RawItem | None:
        headline = (raw.get("headline") or "").strip()
        if not headline or not _is_india_relevant(headline + " " + raw.get("summary", "")):
            return None
        uid = raw.get("id") or f"rss-{hashlib.md5(headline.encode()).hexdigest()[:10]}"
        return RawItem(
            id=uid,
            headline=headline[:512],
            summary=raw.get("summary", "")[:1000],
            source=raw.get("source", "RSS"),
            url=raw.get("url", ""),
            published_at=raw.get("published_at", ""),
            companies=[],
            impact_score=raw.get("impact_score", 6.5),
            event_type="news",
        )


def _parse_rss_xml(data: bytes, source: str, score: float) -> list[dict]:
    """Parse RSS XML without feedparser (stdlib only)."""
    from xml.etree import ElementTree as ET
    results: list[dict] = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        desc  = (item.findtext("description") or "").strip()
        pub   = (item.findtext("pubDate") or "").strip()
        link  = (item.findtext("link") or "").strip()
        uid   = f"rss-{hashlib.md5((source + title).encode()).hexdigest()[:12]}"
        results.append({
            "id":           uid,
            "headline":     title,
            "summary":      desc[:1000],
            "source":       source,
            "url":          link,
            "published_at": _parse_pub_date(pub),
            "impact_score": score,
        })
    return results[:25]
