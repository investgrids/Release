"""
ECB press & statistical press-release RSS provider (Phase 1, 2026-10-25).

Consumes ONLY the verified official ECB RSS feeds (confirmed live 2026-10-25,
HTTP 200, application/rss+xml, dated items):
  - https://www.ecb.europa.eu/rss/press.html      (press releases, incl. monetary-policy pressers)
  - https://www.ecb.europa.eu/rss/statpress.html  (statistical press releases)

Mirrors fed_provider.py. Reuse terms (ECB/ESCB usage policy): free reuse WITH
"Source: ECB" attribution, no alteration, excludes third-party data — so only
headline + a brief excerpt are retained (never the full release text), always
linking to the original, with explicit attribution. Impact left None (computed
downstream). NOT a forward meeting calendar (deliberately out of scope — ECB has
no machine-readable calendar feed; see economic_calendar/deferred_sources.py).
"""
from __future__ import annotations

import hashlib
from datetime import date
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx

from .base import BaseProvider, RawItem

_UA = {
    "User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}
_FEEDS = [
    "https://www.ecb.europa.eu/rss/press.html",
    "https://www.ecb.europa.eu/rss/statpress.html",
]
_DC_NS = "{http://purl.org/dc/elements/1.1/}"


def _parse_date(s: str) -> str:
    if not s:
        return ""
    try:
        return parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except Exception:
        return s[:10]


def _parse_rss(data: bytes) -> list[dict]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    results: list[dict] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        pub = (item.findtext("pubDate") or item.findtext(f"{_DC_NS}date") or "").strip()
        results.append({
            "headline": title,
            "summary": (item.findtext("description") or "").strip(),
            "url": (item.findtext("link") or "").strip(),
            "published_at": _parse_date(pub),
        })
    return results[:20]


class EcbProvider(BaseProvider):
    source_name = "ECB"
    capture_raw_evidence = True
    FEEDS = _FEEDS

    async def fetch_latest(self) -> list[dict]:
        raws: list[dict] = []
        async with httpx.AsyncClient(headers=_UA, timeout=12, follow_redirects=True) as c:
            for url in self.FEEDS:
                try:
                    r = await c.get(url)
                    r.raise_for_status()
                    raws.extend(_parse_rss(r.content))
                except Exception:
                    # Per-feed failure isolated — one feed failing never drops the other.
                    continue
        return raws

    async def fetch_by_date(self, target: date) -> list[dict]:
        items = await self.fetch_latest()
        ts = target.isoformat()
        return [i for i in items if (i.get("published_at", "") or "").startswith(ts)]

    def normalize(self, raw: dict) -> RawItem | None:
        headline = (raw.get("headline") or "").strip()
        if not headline:
            return None
        # Brief excerpt only — never the full release text. ECB feed items often
        # carry no <description> at all, so we always retain the ORIGINAL URL +
        # attribution so downstream can reach the source (Event has no url column
        # — no schema change). This is verbatim ECB title/excerpt + link, never an
        # altered reproduction of protected material.
        excerpt = (raw.get("summary") or "").strip()
        if len(excerpt) > 600:
            excerpt = excerpt[:597] + "…"
        url = (raw.get("url") or "").strip()
        parts: list[str] = []
        if excerpt:
            parts.append(excerpt)
        parts.append("(Source: ECB)")
        if url:
            parts.append(url)
        summary = " ".join(parts)
        return RawItem(
            id=f"ecb-{hashlib.md5(headline.encode()).hexdigest()[:12]}",
            headline=headline[:512],
            summary=summary[:1000],
            source="ECB",
            url=raw.get("url", ""),
            published_at=raw.get("published_at", ""),
            companies=[],
            impact_score=None,
            event_type="policy",
            ministry="European Central Bank",
        )
