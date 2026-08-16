"""
RBI MPC schedule ingestion — Phase 5A.3.

Fetches https://www.rbi.org.in/scripts/annualpolicy.aspx directly (RBI's
own official Monetary Policy page — confirmed live 2026-08-16: contains
a "Meeting Schedule of the Monetary Policy Committee for <FY>" header
followed by a table of six 3-day meeting windows, e.g. "April 6, 7 and
8, 2026"). Tier 1 — first-party, the issuing institution's own page,
not a secondary aggregator.

RBI Act 1934 Section 45ZI requires this schedule to be published in
advance, and it's published once per fiscal year as a single table, not
as a per-meeting feed — so this is a single-page parse, not a per-event
subscription. Re-running this source re-fetches the same page and is a
no-op once nothing has changed (idempotent by construction, not by a
special-cased check).

Announcement time: RBI policy decisions are announced at 10:00 IST on
the final day of the 3-day meeting window (governor's statement
livestreamed 10:00, press conference 12:00) — confirmed via multiple
2026 meeting-day reports, consistent across the year's actual meetings
observed so far. `scheduled_at` is set to 10:00 IST on that final day.

Never guesses: if the expected header/table text isn't found on the
page, this returns an empty list rather than falling back to any
cadence assumption — the sync engine then simply has nothing new to
apply, and last_verified_at on any already-stored rows is untouched
(source-failure isolation, proven in the test suite).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
import structlog

from app.services.economic_calendar.sync_engine import CalendarCandidate

log = structlog.get_logger(__name__)

_URL = "https://www.rbi.org.in/scripts/annualpolicy.aspx"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)"}
_IST = ZoneInfo("Asia/Kolkata")

# "Meeting Schedule of the Monetary Policy Committee for 2026-2027" — the
# real header text confirmed on the live page.
_SCHEDULE_HEADER = re.compile(
    r"Meeting Schedule of the Monetary Policy Committee for (\d{4}-\d{4})",
    re.IGNORECASE,
)
# "April 6, 7 and 8, 2026" — confirmed real format for every one of the
# six rows on the live page.
_MEETING_ROW = re.compile(
    r"([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{1,2})\s+and\s+(\d{1,2}),\s*(\d{4})"
)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_schedule_html(html: str) -> list[dict]:
    """Returns [{fiscal_year, month, decision_day, year}], real regex
    extraction over the actual page text — no HTML tree walk needed
    since the header and table sit close together in document order and
    the row pattern is unambiguous."""
    header_match = _SCHEDULE_HEADER.search(html)
    if not header_match:
        return []
    fiscal_year = header_match.group(1)

    # Only search the table immediately following the header (next ~2000
    # chars) — bounds the regex to the actual schedule table, not any
    # other date-shaped text elsewhere on the page.
    window = html[header_match.end(): header_match.end() + 2000]
    out = []
    for m in _MEETING_ROW.finditer(window):
        month_name, _d1, _d2, d3, year = m.groups()
        month = _MONTHS.get(month_name.lower())
        if month is None:
            continue
        out.append({"fiscal_year": fiscal_year, "month": month, "decision_day": int(d3), "year": int(year)})
    return out


async def fetch_rbi_mpc_candidates() -> list[CalendarCandidate]:
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=15, follow_redirects=True) as client:
            resp = await client.get(_URL)
            resp.raise_for_status()
    except Exception as exc:
        log.warning("rbi_calendar.fetch_failed", error=str(exc)[:200])
        return []

    meetings = _parse_schedule_html(resp.text)
    if not meetings:
        log.warning("rbi_calendar.schedule_not_found", url=_URL)
        return []

    candidates = []
    for meeting in meetings:
        local_dt = datetime(meeting["year"], meeting["month"], meeting["decision_day"], 10, 0, tzinfo=_IST)
        scheduled_at_utc = local_dt.astimezone(timezone.utc)
        reference_period = f"{meeting['year']:04d}-{meeting['month']:02d}"
        candidates.append(CalendarCandidate(
            identity_key=f"rbi_mpc:IN:{reference_period}",
            reference_period=reference_period,
            title=f"RBI Monetary Policy Committee Decision ({meeting['fiscal_year']})",
            category="rbi_mpc",
            country="IN",
            scheduled_at=scheduled_at_utc,
            source_timezone="Asia/Kolkata",
            importance="critical",
            source="rbi",
            source_url=_URL,
            source_tier="tier_1",
        ))
    return candidates
