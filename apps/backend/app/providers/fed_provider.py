"""
US Federal Reserve press-release RSS provider (Phase 5, 2026-08 audit).

Verified live before implementing (per this task's own "verify source
availability before integrating" rule): federalreserve.gov/feeds/
press_all.xml is a real, currently-live, standard RSS 2.0 feed — public
domain content (US government work, 17 U.S.C. §105), free, no auth,
already used pattern-for-pattern by rbi_provider.py/pib_provider.py.

The feed mixes 5 real <category> values (confirmed live): Monetary
Policy, Banking and Consumer Regulatory Policy, Orders on Banking
Applications, Enforcement Actions, Other Announcements — routine banking-
merger approvals dominate the volume. Filtered to "Monetary Policy" only
here, matching this task's Phase 5 priority (the Fed's rate/FOMC
decisions specifically — the ones ripple_service.py's global_monetary
template already knows how to model), not routine bank-application
noise.
"""
from __future__ import annotations

import hashlib
from datetime import date
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx

from .base import BaseProvider, RawItem

_URL = "https://www.federalreserve.gov/feeds/press_all.xml"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}
_CATEGORY_FILTER = "monetary policy"


def _parse_date(s: str) -> str:
    if not s:
        return ""
    try:
        return parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except Exception:
        return s[:10]


class FedProvider(BaseProvider):
    source_name = "Fed"
    capture_raw_evidence = True   # Phase 1B Batch 2, 2026-08-23

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
        return RawItem(
            id=raw.get("id") or f"fed-{hashlib.md5(headline.encode()).hexdigest()[:12]}",
            headline=headline[:512],
            summary=raw.get("summary", "")[:1000],
            source="Fed",
            url=raw.get("url", ""),
            published_at=raw.get("published_at", ""),
            impact_score=None,  # see RawItem's docstring -- not a real per-event score
            event_type="policy",
            ministry="US Federal Reserve",
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
        category = (item.findtext("category") or "").strip()
        if _CATEGORY_FILTER not in category.lower():
            continue
        results.append({
            "id":           f"fed-{hashlib.md5(title.encode()).hexdigest()[:12]}",
            "headline":     title,
            "summary":      (item.findtext("description") or "").strip()[:1000],
            "url":          (item.findtext("link") or "").strip(),
            "published_at": _parse_date((item.findtext("pubDate") or "").strip()),
        })
    return results[:20]
