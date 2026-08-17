"""
US Treasury 2Y/10Y par yield + curve state — Phase 5C.

Fetches home.treasury.gov's own Daily Treasury Par Yield Curve Rates
XML feed directly — tier 1, first-party, the Treasury's own data
warehouse (Office of Debt Management). Confirmed live 2026-08-17: a
single request for a given year returns every trading day of that year
(156 rows for 2026 through Aug 14) as OData/Atom entries with
`d:NEW_DATE`, `d:BC_2YEAR`, `d:BC_10YEAR` (and other maturities, not
used here). One fetch is therefore enough for both "today's level" and
a real 4-week lookback for trend — no persistence needed, unlike the
event-driven India/Fed sources.

Trend thresholds are NOT guessed: computed from the real 2026 daily
series (see trend.py's docstring for the full derivation) — the
observed standard deviation of 20-trading-day (~4 calendar week)
changes was ~15bps for both 2Y and 10Y, so a move past that band is
treated as a real trend, not noise.

Curve-state thresholds (inverted/flat/normal/steep) are NOT derived
from this dataset — 2026's spread never left the 27-74bps band, so it
never demonstrates what "inverted" or "steep" actually look like. These
use well-established fixed-income market convention instead (documented
inline), which the empirical 2026 data is consistent with but can't itself
prove.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
from xml.etree import ElementTree as ET

import httpx
import structlog

from app.services.macro_rates.config import YIELD_TREND_THRESHOLD_BPS, YIELD_TREND_WINDOW_TRADING_DAYS

log = structlog.get_logger(__name__)

_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xmlview"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)"}
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
    "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
}

# See app/services/macro_rates/config.py for the derivation and version.
_LOOKBACK_TRADING_DAYS = YIELD_TREND_WINDOW_TRADING_DAYS
_TREND_THRESHOLD_BPS = YIELD_TREND_THRESHOLD_BPS

# Standard fixed-income convention (not derived from the 2026 sample —
# that sample never spans these regimes; see module docstring).
_CURVE_INVERTED_MAX = 0.0
_CURVE_FLAT_MAX = 0.25
_CURVE_NORMAL_MAX = 1.00


@dataclass
class UsTreasuryState:
    status: str                          # "live" | "unavailable"
    latest_date: date | None = None
    y2: float | None = None
    y10: float | None = None
    spread: float | None = None          # 10Y - 2Y, percentage points
    y2_change_bps: float | None = None   # over _LOOKBACK_TRADING_DAYS trading days
    y10_change_bps: float | None = None
    y2_trend: str | None = None          # "rising" | "falling" | "stable"
    y10_trend: str | None = None
    curve_state: str | None = None       # "inverted" | "flat" | "normal" | "steep"
    source: str = "us_treasury_par_yield_curve"
    reason: str | None = None


def _fetch_year_sync(year: int) -> str | None:
    try:
        with httpx.Client(headers=_HEADERS, timeout=20, follow_redirects=True) as client:
            resp = client.get(_URL, params={"data": "daily_treasury_yield_curve", "field_tdr_date_value": year})
            resp.raise_for_status()
            return resp.text
    except Exception as exc:
        log.warning("us_treasury.fetch_failed", year=year, error=str(exc)[:200])
        return None


def _parse_entries(xml_text: str) -> list[tuple[date, float | None, float | None]]:
    """Real OData/Atom XML, not regex-matched text — attribute order and
    whitespace in this feed aren't guaranteed stable, so a real parser is
    the honest choice here (unlike the plain-HTML sources elsewhere in
    this codebase, where regex over known-stable markup is deliberate)."""
    out: list[tuple[date, float | None, float | None]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.warning("us_treasury.parse_failed", error=str(exc)[:200])
        return out

    for entry in root.findall(".//atom:entry", _NS):
        props = entry.find(".//m:properties", _NS)
        if props is None:
            continue
        date_el = props.find("d:NEW_DATE", _NS)
        y2_el = props.find("d:BC_2YEAR", _NS)
        y10_el = props.find("d:BC_10YEAR", _NS)
        if date_el is None or not date_el.text:
            continue
        try:
            d = datetime.strptime(date_el.text[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        y2 = float(y2_el.text) if y2_el is not None and y2_el.text else None
        y10 = float(y10_el.text) if y10_el is not None and y10_el.text else None
        out.append((d, y2, y10))

    out.sort(key=lambda r: r[0])
    return out


def _classify_trend(change_bps: float | None) -> str | None:
    if change_bps is None:
        return None
    if change_bps > _TREND_THRESHOLD_BPS:
        return "rising"
    if change_bps < -_TREND_THRESHOLD_BPS:
        return "falling"
    return "stable"


def _classify_curve(spread: float | None) -> str | None:
    if spread is None:
        return None
    if spread < _CURVE_INVERTED_MAX:
        return "inverted"
    if spread < _CURVE_FLAT_MAX:
        return "flat"
    if spread < _CURVE_NORMAL_MAX:
        return "normal"
    return "steep"


async def get_us_treasury_state() -> UsTreasuryState:
    """Fetches the current year (and, if fewer than _LOOKBACK_TRADING_DAYS
    trading days have occurred so far this calendar year, the tail of the
    prior year too — the only way to get a real 4-week lookback in early
    January) and derives current level, 4-week change, and curve state.
    Never fabricates a trend from a partial/short series — returns None
    for that field instead."""
    loop = asyncio.get_event_loop()
    now = datetime.now(timezone.utc)

    text = await loop.run_in_executor(None, _fetch_year_sync, now.year)
    if text is None:
        return UsTreasuryState(status="unavailable", reason="source_fetch_failed")

    rows = _parse_entries(text)
    if len(rows) < _LOOKBACK_TRADING_DAYS + 1:
        prior_text = await loop.run_in_executor(None, _fetch_year_sync, now.year - 1)
        if prior_text is not None:
            prior_rows = _parse_entries(prior_text)
            rows = prior_rows + rows

    if not rows:
        return UsTreasuryState(status="unavailable", reason="no_data_rows_parsed")

    latest_date, y2, y10 = rows[-1]
    spread = round(y10 - y2, 2) if (y2 is not None and y10 is not None) else None

    y2_change = y10_change = None
    if len(rows) > _LOOKBACK_TRADING_DAYS:
        _, past_y2, past_y10 = rows[-1 - _LOOKBACK_TRADING_DAYS]
        if y2 is not None and past_y2 is not None:
            y2_change = round((y2 - past_y2) * 100, 1)
        if y10 is not None and past_y10 is not None:
            y10_change = round((y10 - past_y10) * 100, 1)

    return UsTreasuryState(
        status="live",
        latest_date=latest_date,
        y2=y2, y10=y10, spread=spread,
        y2_change_bps=y2_change, y10_change_bps=y10_change,
        y2_trend=_classify_trend(y2_change), y10_trend=_classify_trend(y10_change),
        curve_state=_classify_curve(spread),
    )
