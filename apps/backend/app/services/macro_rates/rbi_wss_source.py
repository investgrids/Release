"""
RBI Weekly Statistical Supplement — India 10Y G-Sec yield + repo rate
history — Phase 5C.

Real, first-party, tier 1 — RBI's own site, same rbi.org.in domain
already trusted by economic_calendar/rbi_source.py. Two-step discovery,
confirmed live 2026-08-17 end-to-end:

  1. GET rbi.org.in/scripts/WSSViewDetail.aspx?TYPE=Basic&PARAM1=<date>
     — a server-rendered index of that week's WSS tables. Contains an
     UNQUOTED href (`href=WSSView.aspx?Id=28642`, no surrounding quotes
     — a real markup quirk that broke an earlier, naive quote-requiring
     grep during this same investigation) next to the visible text
     "Ratios and Rates".
  2. GET rbi.org.in/scripts/WSSView.aspx?Id=<the discovered Id> — a
     plain HTML table containing BOTH "Policy Repo Rate" and
     "10-Year G-Sec Par Yield (FBIL)" rows, each with 6 dated weekly
     columns.

No opaque Id is ever guessed — it's read out of real HTML on every
call. rbidocs.rbi.org.in (the XLSX/PDF document CDN, confirmed live to
sit behind an F5/TSPD bot-detection JS challenge) is never touched.

Column structure (confirmed real, live sample): a header row reading
"Item/Week Ended" is preceded by a year-label row — one year for
column 1 (a same-week year-ago comparison point RBI includes for
context), a colspan=5 year for columns 2-6 (the 5 most recent weekly
Fridays). The 6th (rightmost) column is always the most recent real
observation — this module only ever reports that one, never averages
or otherwise blends across the window; the earlier 5 exist purely so
trend.py can compute a real week-over-week/month-over-month change
without a second fetch.

This is explicitly a HISTORICAL/REGIME data source (weekly cadence,
observation date typically 4-10 days behind the fetch date) — never
wired into any live Pre-Market signal. See package __init__.py.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import httpx
import structlog

log = structlog.get_logger(__name__)

_DETAIL_URL = "https://www.rbi.org.in/scripts/WSSViewDetail.aspx"
_VIEW_URL = "https://www.rbi.org.in/scripts/WSSView.aspx"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)"}

# Real markup: `href=WSSView.aspx?Id=NNNNN` — unquoted attribute value.
_RATIOS_LINK = re.compile(
    r"href=WSSView\.aspx\?Id=(\d+)>Ratios and Rates<", re.IGNORECASE,
)

_ITEM_WEEK_ENDED = re.compile(r"Item/Week Ended", re.IGNORECASE)
_HEAD_SPAN = re.compile(r'<span class="head">([^<]+)</span>')
_YEAR = re.compile(r"^\d{4}$")
_MONTH_DAY = re.compile(r"^([A-Za-z]{3})\.?\s*(\d{1,2})$")

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Anti-bot / challenge-page fingerprints — if any appear, treat the
# fetch as a real failure, never attempt to parse a challenge page as
# if it were data (per owner's explicit instruction).
_CHALLENGE_MARKERS = (
    "please enable javascript", "support id", "human visitor",
    "captcha", "are you a robot", "bot detection",
)

_MAX_WEEKS_BACK = 6  # bounded backward walk if the newest Friday has no published issue yet


@dataclass
class WssRow:
    label: str
    values: list[tuple[date | None, float | None]]  # 6 (date, value) pairs, oldest to newest


@dataclass
class RbiWssState:
    status: str                              # "live" | "unavailable"
    issue_date: date | None = None           # the WSS publication date fetched
    india_10y_gsec: float | None = None
    india_10y_gsec_observed_at: date | None = None
    india_10y_gsec_history: list[tuple[date, float]] | None = None   # oldest→newest, for trend
    repo_rate: float | None = None
    repo_rate_observed_at: date | None = None
    repo_rate_history: list[tuple[date, float]] | None = None
    source: str = "rbi_wss"
    source_url: str | None = None
    reason: str | None = None


def _is_challenge_page(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in _CHALLENGE_MARKERS)


def _fetch_sync(url: str, params: dict | None = None) -> str | None:
    try:
        with httpx.Client(headers=_HEADERS, timeout=20, follow_redirects=True) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            text = resp.text
    except Exception as exc:
        log.warning("rbi_wss.fetch_failed", url=url, error=str(exc)[:200])
        return None
    if _is_challenge_page(text):
        log.warning("rbi_wss.challenge_page_detected", url=url)
        return None
    return text


def _find_ratios_id(detail_html: str) -> int | None:
    m = _RATIOS_LINK.search(detail_html)
    return int(m.group(1)) if m else None


def _parse_week_ended_dates(view_html: str) -> list[date] | None:
    """Finds the "Item/Week Ended" header block and the year-label row
    immediately preceding it, and reconstructs 6 real dates. Returns
    None (never a guessed/partial list) if the structure doesn't match
    exactly what's been confirmed live — a format change should fail
    loudly, not silently misdate a value."""
    m = _ITEM_WEEK_ENDED.search(view_html)
    if not m:
        return None

    # Year-label row: the <tr> immediately before the one containing
    # "Item/Week Ended". Two <span class="head"> years: the first
    # governs column 1, the second (colspan=5) governs columns 2-6.
    tr_start = view_html.rfind("<tr>", 0, m.start())
    prior_tr_start = view_html.rfind("<tr>", 0, tr_start)
    year_row_html = view_html[prior_tr_start:tr_start]
    years = [y for y in _HEAD_SPAN.findall(year_row_html) if _YEAR.match(y)]
    if len(years) != 2:
        return None

    # Date-label row: the same <tr> that contains "Item/Week Ended",
    # spanning to its close.
    tr_end = view_html.find("</tr>", m.start())
    date_row_html = view_html[tr_start:tr_end]
    labels = [l for l in _HEAD_SPAN.findall(date_row_html) if l.lower() != "item/week ended"]
    if len(labels) != 6:
        return None

    dates: list[date] = []
    for i, label in enumerate(labels):
        dm = _MONTH_DAY.match(label.strip())
        if not dm:
            return None
        month = _MONTHS.get(dm.group(1).lower())
        day = int(dm.group(2))
        if month is None:
            return None
        year = int(years[0]) if i == 0 else int(years[1])
        try:
            dates.append(date(year, month, day))
        except ValueError:
            return None
    return dates


def _parse_row_values(view_html: str, row_label: str) -> list[float | None] | None:
    pattern = re.compile(
        rf"<td>{re.escape(row_label)}</td>((?:\s*<td[^>]*>[^<]*</td>){{6}})",
    )
    m = pattern.search(view_html)
    if not m:
        return None
    cells = re.findall(r"<td[^>]*>([^<]*)</td>", m.group(1))
    out: list[float | None] = []
    for c in cells:
        c = c.strip().replace("&nbsp;", "").replace(",", "")
        if not c or c in ("..", "-", "—"):
            out.append(None)
            continue
        try:
            out.append(float(c))
        except ValueError:
            out.append(None)
    return out if len(out) == 6 else None


def _parse_ratios_page(view_html: str, source_url: str, issue_date: date) -> RbiWssState:
    dates = _parse_week_ended_dates(view_html)
    if dates is None:
        return RbiWssState(status="unavailable", reason="week_ended_header_not_found", source_url=source_url)

    gsec_values = _parse_row_values(view_html, "10-Year G-Sec Par Yield (FBIL)")
    repo_values = _parse_row_values(view_html, "Policy Repo Rate")

    def _latest(values: list[float | None] | None) -> tuple[float | None, date | None, list | None]:
        if values is None:
            return None, None, None
        history = [(d, v) for d, v in zip(dates, values) if v is not None]
        if not history:
            return None, None, None
        latest_date, latest_value = history[-1]
        return latest_value, latest_date, history

    gsec_val, gsec_date, gsec_hist = _latest(gsec_values)
    repo_val, repo_date, repo_hist = _latest(repo_values)

    if gsec_val is None and repo_val is None:
        return RbiWssState(status="unavailable", reason="neither_series_found", source_url=source_url, issue_date=issue_date)

    return RbiWssState(
        status="live", issue_date=issue_date,
        india_10y_gsec=gsec_val, india_10y_gsec_observed_at=gsec_date, india_10y_gsec_history=gsec_hist,
        repo_rate=repo_val, repo_rate_observed_at=repo_date, repo_rate_history=repo_hist,
        source_url=source_url,
    )


def _recent_fridays(now: date, count: int) -> list[date]:
    days_since_friday = (now.weekday() - 4) % 7
    most_recent_friday = now - timedelta(days=days_since_friday)
    return [most_recent_friday - timedelta(weeks=i) for i in range(count)]


async def get_rbi_wss_state(as_of: date | None = None) -> RbiWssState:
    """Walks backward through recent Fridays (WSS's own publication day)
    until one has a real, parseable issue — bounded, never infinite,
    never guesses a value when nothing is found within the window.

    Phase 5F.3: records to source_health — see us_treasury_source.py's
    get_us_treasury_state docstring for why this matters (this whole
    package had zero source_health calls before this fix). Recorded
    once per call, for the FINAL outcome of the whole backward walk —
    not once per candidate Friday, since a normal "this week's issue
    isn't published yet, found last week's instead" walk is expected,
    routine behavior, not a string of failures worth alarming on
    individually."""
    import time as _time
    from app.services import source_health
    start = _time.monotonic()
    loop = asyncio.get_event_loop()
    today = as_of or datetime.now().date()

    for candidate_date in _recent_fridays(today, _MAX_WEEKS_BACK):
        param = f"{candidate_date.month}/{candidate_date.day}/{candidate_date.year}"
        detail_html = await loop.run_in_executor(
            None, _fetch_sync, _DETAIL_URL, {"TYPE": "Basic", "PARAM1": param},
        )
        if detail_html is None:
            continue

        ratios_id = _find_ratios_id(detail_html)
        if ratios_id is None:
            continue

        view_html = await loop.run_in_executor(
            None, _fetch_sync, _VIEW_URL, {"Id": ratios_id},
        )
        if view_html is None:
            continue

        source_url = f"{_VIEW_URL}?Id={ratios_id}"
        result = _parse_ratios_page(view_html, source_url, candidate_date)
        if result.status == "live":
            source_health.record_fetch(
                "RBI WSS", success=True, event_count=1, latency_ms=(_time.monotonic() - start) * 1000,
            )
            return result
        # A found-but-unparseable page is a real signal worth logging,
        # but the walk continues rather than giving up on the whole window.
        log.warning("rbi_wss.issue_found_but_unparseable", date=candidate_date.isoformat(), reason=result.reason)

    source_health.record_fetch(
        "RBI WSS", success=False, failure_kind="parse",
        latency_ms=(_time.monotonic() - start) * 1000, error="no_publishable_issue_in_window",
    )
    return RbiWssState(status="unavailable", reason="no_publishable_issue_in_window")
