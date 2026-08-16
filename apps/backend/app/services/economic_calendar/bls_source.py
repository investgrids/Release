"""
BLS CPI / Employment Situation (NFP) schedule ingestion — Phase 5A.4.

Fetches bls.gov/schedule/news_release/{cpi,empsit}.htm directly — BLS's
own official release-schedule pages. Tier 1, first-party.

Real structure confirmed live 2026-08-16: a clean `<table
class="release-list">` with explicit `<th>Reference Month</th>
<th>Release Date</th><th>Release Time</th>` columns — unlike MOSPI's
document, BLS states the REFERENCE PERIOD explicitly per row ("November
2025", "December 2025", ...), so reference_period is read directly
from the source rather than inferred by position. Release time is
consistently "08:30 AM" (Eastern) on every row observed across both
schedules.

Same shared table parser for both CPI and the Employment Situation
(NFP) — the two pages are structurally identical, differing only in
URL and title.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
import structlog

from app.services.economic_calendar.sync_engine import CalendarCandidate

log = structlog.get_logger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)"}
_NY = ZoneInfo("America/New_York")

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# One <tr>...</tr> per release, matching the real release-list table —
# tolerant of the exact abbreviated-vs-full month spelling BLS uses in
# the "Release Date" column ("Dec. 18, 2025" / "Jan. 09, 2026").
_ROW = re.compile(
    r"<td>([A-Za-z]+)\s+(\d{4})</td>\s*"                                    # Reference Month: "November 2025"
    r"<td>([A-Za-z]{3,4})\.?\s+(\d{1,2}),?\s+(\d{4})</td>\s*"               # Release Date: "Dec. 18, 2025"
    r"<td>(\d{1,2}):(\d{2})\s*(AM|PM)</td>",                                # Release Time: "08:30 AM"
    re.IGNORECASE,
)


def _parse_release_table(html: str) -> list[dict]:
    out = []
    for m in _ROW.finditer(html):
        ref_month_name, ref_year, rel_month_name, rel_day, rel_year, hour, minute, ampm = m.groups()
        ref_month = _MONTHS.get(ref_month_name.lower()[:3])
        rel_month = _MONTHS.get(rel_month_name.lower()[:3])
        if ref_month is None or rel_month is None:
            continue
        hour_24 = int(hour) % 12 + (12 if ampm.upper() == "PM" else 0)
        out.append({
            "reference_period": f"{int(ref_year):04d}-{ref_month:02d}",
            "release_year": int(rel_year), "release_month": rel_month, "release_day": int(rel_day),
            "release_hour": hour_24, "release_minute": int(minute),
        })
    return out


async def _fetch_schedule(url: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception as exc:
        log.warning("bls_calendar.fetch_failed", url=url, error=str(exc)[:200])
        return []

    rows = _parse_release_table(resp.text)
    if not rows:
        log.warning("bls_calendar.schedule_not_found", url=url)
    return rows


def _to_candidates(rows: list[dict], category: str, title: str, url: str) -> list[CalendarCandidate]:
    candidates = []
    for r in rows:
        try:
            local_dt = datetime(
                r["release_year"], r["release_month"], r["release_day"],
                r["release_hour"], r["release_minute"], tzinfo=_NY,
            )
        except ValueError:
            continue
        candidates.append(CalendarCandidate(
            identity_key=f"{category}:US:{r['reference_period']}",
            reference_period=r["reference_period"],
            title=title,
            category=category,
            country="US",
            scheduled_at=local_dt.astimezone(timezone.utc),
            source_timezone="America/New_York",
            importance="critical",
            source="bls",
            source_url=url,
            source_tier="tier_1",
        ))
    return candidates


async def fetch_us_cpi_candidates() -> list[CalendarCandidate]:
    url = "https://www.bls.gov/schedule/news_release/cpi.htm"
    rows = await _fetch_schedule(url)
    return _to_candidates(rows, "us_cpi", "US CPI (Consumer Price Index)", url)


async def fetch_us_jobs_candidates() -> list[CalendarCandidate]:
    url = "https://www.bls.gov/schedule/news_release/empsit.htm"
    rows = await _fetch_schedule(url)
    return _to_candidates(rows, "us_jobs", "US Employment Situation (Jobs Report / NFP)", url)
