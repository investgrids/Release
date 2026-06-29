"""BSE corporate announcement provider."""
from __future__ import annotations

import hashlib
from datetime import date

import httpx

from .base import BaseProvider, RawItem

_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnGetAnnouncemnt/w?scrip_cd=&ann_type=C&segment=&strSearch="
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Referer": "https://www.bseindia.com/",
}


class BSEProvider(BaseProvider):
    source_name = "BSE"

    async def fetch_latest(self) -> list[dict]:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=12, follow_redirects=True) as c:
            r = await c.get(_URL)
            r.raise_for_status()
            data = r.json()
            items = data.get("Table", data) if isinstance(data, dict) else data
            return (items if isinstance(items, list) else [])[:50]

    async def fetch_by_date(self, target: date) -> list[dict]:
        url = f"{_URL}&dtFrom={target.strftime('%Y%m%d')}&dtTo={target.strftime('%Y%m%d')}"
        async with httpx.AsyncClient(headers=_HEADERS, timeout=12, follow_redirects=True) as c:
            r = await c.get(url)
            r.raise_for_status()
            data = r.json()
            items = data.get("Table", data) if isinstance(data, dict) else data
            return (items if isinstance(items, list) else [])[:50]

    def normalize(self, raw: dict) -> RawItem | None:
        headline = (raw.get("NEWSSUB") or "").strip()
        if not headline:
            return None
        news_id = raw.get("NEWSID", "")
        uid = f"bse-{news_id}" if news_id else f"bse-{hashlib.md5(headline.encode()).hexdigest()[:10]}"
        return RawItem(
            id=uid,
            headline=headline[:512],
            summary=headline[:1000],
            source="BSE",
            published_at=str(raw.get("NEWS_DT", ""))[:10],
            companies=[raw["scrip_cd"]] if raw.get("scrip_cd") else [],
            impact_score=6.5,
            event_type="corporate",
        )
