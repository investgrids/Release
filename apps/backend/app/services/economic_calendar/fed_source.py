"""
Federal Reserve FOMC schedule ingestion — Phase 5A.4.

Fetches federalreserve.gov/monetarypolicy/fomccalendars.htm directly —
the Fed's own official calendar page. Tier 1, first-party.

Real structure confirmed live 2026-08-16: each year's meetings sit
under a `<a id="{opaque_id}">{YEAR} FOMC Meetings</a>` heading,
followed by one `<div class="row fomc-meeting">` block per meeting,
each containing `fomc-meeting__month` (month name) and
`fomc-meeting__date` (day range, e.g. "27-28", sometimes with a
trailing "*" for a Summary-of-Economic-Projections meeting — doesn't
affect date parsing). FUTURE meetings (confirmed: September 2026
onward, not yet occurred) have this same month/date structure but
empty statement/press-conference sub-divs — deliberately NOT parsed
via the statement-URL date slug some past meetings expose
(monetary20260128a.htm etc.), since that URL only exists once a
meeting has actually happened and would silently exclude every future
meeting, the exact opposite of what a forward calendar needs.

Decision time: FOMC statements are released at 14:00 America/New_York
on the SECOND day of the (almost always 2-day) meeting window,
followed by a 14:30 press conference for SEP meetings — well-
established, consistent across every 2026 meeting observed so far.
Stored via real timezone localization (America/New_York), never a
fixed UTC offset — DST-correct across the March/November transitions
by construction (see test_economic_calendar_dst.py).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
import structlog

from app.services.economic_calendar.sync_engine import CalendarCandidate

log = structlog.get_logger(__name__)

_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)"}
_NY = ZoneInfo("America/New_York")

_YEAR_HEADING = re.compile(r'<a id="\d+">(\d{4}) FOMC Meetings</a>')
_MEETING_MONTH = re.compile(r'fomc-meeting__month[^>]*><strong>([A-Za-z]+)</strong>')
_MEETING_DATE = re.compile(r'fomc-meeting__date[^>]*>\s*(\d{1,2})(?:-(\d{1,2}))?\*?\s*<')

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_year_sections(html: str) -> list[tuple[int, str]]:
    """Returns [(year, section_html)] — the full HTML slice belonging to
    each year's heading, bounded by the next year heading (or end of
    document for the last one)."""
    headings = list(_YEAR_HEADING.finditer(html))
    out = []
    for i, m in enumerate(headings):
        year = int(m.group(1))
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(html)
        out.append((year, html[start:end]))
    return out


def _parse_meetings(section_html: str) -> list[tuple[str, int, int]]:
    """Returns [(month_name, start_day, decision_day)] in document order.
    Month and date blocks always appear as an adjacent pair per meeting
    (confirmed structurally on the live page) — zipping the two
    findall() results in document order is reliable here."""
    months = _MEETING_MONTH.findall(section_html)
    dates = _MEETING_DATE.findall(section_html)
    out = []
    for month_name, (d1, d2) in zip(months, dates):
        start_day = int(d1)
        decision_day = int(d2) if d2 else start_day
        out.append((month_name, start_day, decision_day))
    return out


async def fetch_fomc_candidates() -> list[CalendarCandidate]:
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=15, follow_redirects=True) as client:
            resp = await client.get(_URL)
            resp.raise_for_status()
    except Exception as exc:
        log.warning("fed_calendar.fetch_failed", error=str(exc)[:200])
        return []

    sections = _parse_year_sections(resp.text)
    if not sections:
        log.warning("fed_calendar.schedule_not_found", url=_URL)
        return []

    candidates = []
    for year, section_html in sections:
        for month_name, _start_day, decision_day in _parse_meetings(section_html):
            month = _MONTHS.get(month_name.lower())
            if month is None:
                continue
            try:
                local_dt = datetime(year, month, decision_day, 14, 0, tzinfo=_NY)
            except ValueError:
                continue
            reference_period = f"{year:04d}-{month:02d}"
            candidates.append(CalendarCandidate(
                identity_key=f"fomc:US:{reference_period}",
                reference_period=reference_period,
                title=f"FOMC Interest Rate Decision ({year})",
                category="fomc",
                country="US",
                scheduled_at=local_dt.astimezone(timezone.utc),
                source_timezone="America/New_York",
                importance="critical",
                source="fed",
                source_url=_URL,
                source_tier="tier_1",
            ))
    return candidates
