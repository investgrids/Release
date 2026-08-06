"""NSE corporate announcement provider."""
from __future__ import annotations

import hashlib
from datetime import date

import httpx

from .base import BaseProvider, RawItem

_URL = "https://www.nseindia.com/api/corporate-announcements?index=equities"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/",
}


class NSEProvider(BaseProvider):
    source_name = "NSE"

    async def _get(self, params: dict | None = None) -> list[dict]:
        # Reliability hardening (2026-08-06): confirmed via a direct live test
        # from the actual production (Railway) egress IP that this endpoint
        # currently works fine bare — unlike BSE's, which is actively broken
        # for an unrelated reason (see bse_provider.py's module docstring).
        # Added this warm-up defensively anyway, per a known-reliable
        # community NSE client's documented pattern (github.com/
        # BennyThadikaran/NseIndiaApi): NSE's own site visits the homepage
        # first to pick up session cookies before any /api/* call, and a
        # bare API call with only a static User-Agent is documented there to
        # work intermittently, not reliably. One shared client/cookie-jar
        # for the warm-up + the real call, not two independent connections.
        async with httpx.AsyncClient(headers=_HEADERS, timeout=12, follow_redirects=True) as c:
            await c.get("https://www.nseindia.com/")
            r = await c.get(_URL, params=params)
            r.raise_for_status()
            data = r.json()
            return (data if isinstance(data, list) else data.get("data", []))[:50]

    async def fetch_latest(self) -> list[dict]:
        return await self._get()

    async def fetch_by_date(self, target: date) -> list[dict]:
        params = {"from_date": target.isoformat(), "to_date": target.isoformat()}
        return await self._get(params)

    def normalize(self, raw: dict) -> RawItem | None:
        headline = (raw.get("desc") or raw.get("subject") or "").strip()
        if not headline:
            return None
        an_no = raw.get("an_no", "")
        uid = f"nse-{an_no}" if an_no else f"nse-{hashlib.md5(headline.encode()).hexdigest()[:10]}"
        return RawItem(
            id=uid,
            headline=headline[:512],
            summary=(raw.get("attchmntText") or headline)[:1000],
            source="NSE",
            published_at=(raw.get("sort_date") or "")[:10],
            companies=[raw["symbol"]] if raw.get("symbol") else [],
            impact_score=7.5,
            event_type="corporate",
        )
