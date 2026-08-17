"""BSE corporate announcement provider.

STATUS: DEFERRED_BOT_PROTECTED (Phase 5D, 2026-08-17 — reconfirmed the
2026-08-06 finding below, then went further and closed off the
remaining escape hatches). Not fixed; deferred by explicit decision,
matching this codebase's Eurostat precedent
(app/services/economic_calendar/deferred_sources.py): an official
source whose acquisition method isn't reliable enough for this
architecture doesn't get a headless-browser dependency added just to
reach it. `company_announcements_service.py`'s independent BSE fetch
(the one AI Search and Weekend Intelligence's evidence pipeline
actually read) fails the same way for the same reason — see that
module's own docstring for the fix that stops BSE's failure from also
taking NSE's data down with it, which was the real Phase 5D bug.

Original investigation (2026-08-06): this endpoint is currently failing
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

Follow-up investigation (2026-08-17, Phase 5D): tested whether a real
TLS/browser fingerprint (not just headers) would pass Akamai's check —
it doesn't. `curl_cffi` with `impersonate="chrome"` (a genuine Chrome
JA3/TLS fingerprint, the standard fix for TLS-fingerprint-based bot
walls) still gets the identical 302 -> error_Bse.html on the very first
request. A cookie warm-up using that same Chrome-fingerprint session
(visiting BSE's real announcements page first) sets zero cookies at
all — meaning BSE's Akamai configuration requires an actual
JavaScript-executed challenge to even receive a session cookie, not
just a matching TLS fingerprint. Also checked for a non-API escape
hatch: BSE's static bulk "bhavcopy" downloads (a different dataset —
end-of-day prices, not announcements) sit on a non-Akamai-gated path,
but the announcements endpoint itself has no equivalent; the only other
URL found for it (on www.bseindia.com rather than api.bseindia.com)
just serves the same client-rendered Angular SPA shell, which calls the
identical gated API via JavaScript after presumably solving the
challenge client-side. Conclusion: a real JS-capable client (headless
browser) is very likely the only reliable fix — deliberately not added
here; see company_announcements_service.py's docstring for what was
fixed instead, and this session's audit for BSE's official "Corporate
Data API" / "Self Data Feed" as a possible paid/registered alternative
worth investigating separately before ever reaching for Playwright.
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
