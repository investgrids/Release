"""BSE corporate announcement provider.

Reliability investigation (2026-08-06): this endpoint is currently failing
in production with a JSON parse error (`Expecting value: line 3 column 1
(char 4)`). Root cause confirmed directly, not guessed: BSE's Akamai-fronted
API returns HTTP 302 -> https://api.bseindia.com/error_Bse.html (a small
HTML redirect page, not JSON) — `raise_for_status()` doesn't catch this
since the redirect target itself returns 200, so `r.json()` fails on HTML
content instead. Confirmed via a direct live test from both the actual
production (Railway/GCP) egress IP and a separate residential IP: the
failure is IDENTICAL from both — this is NOT cloud-IP-specific blocking.
Also confirmed a browser-session warm-up (visiting the BSE announcements
page first, matching the fix that resolved NSE's equivalent reliability
gap in nse_provider.py) does NOT fix it — the API call still returns an
HTML page even with real cookies from a real prior page visit. This looks
like Akamai bot-detection on the request signature itself (TLS/client
fingerprint), which a plain httpx client can't cheaply resolve — flagged
as needing a bigger decision (different HTTP client/fingerprint-matching
approach, or accepting BSE as currently non-functional) rather than fixed
here.
"""
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
