"""
Real NSE financial-results client — the exact endpoint/query pattern
validated live in S3/S3-A, not a guess. `corporates-financial-results` is a
real, separate NSE endpoint from `corporate-announcements` (the one
app/providers/nse_provider.py already uses); it needs a per-symbol,
per-period query to return anything current — confirmed live 2026-08-25,
after an earlier session's own note that a bulk/dateless query returns
empty. Each real result links to a real, well-formed XBRL file (not a
PDF), which this module also fetches and parses.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import requests

_BASE_URL = "https://www.nseindia.com"
_RESULTS_URL = "https://www.nseindia.com/api/corporates-financial-results"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
}


def _session() -> requests.Session:
    """NSE requires a real browser-shaped session handshake before its API
    endpoints respond — confirmed live, same real pattern this codebase's
    existing NSE provider already relies on."""
    s = requests.Session()
    s.get(_BASE_URL, headers=_HEADERS, timeout=10)
    return s


def _parse_broadcast_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, "%d-%b-%Y %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fetch_financial_results(symbol: str, period: str, session: requests.Session | None = None) -> list[dict]:
    """Real metadata rows for `symbol`'s filings of the given `period`
    ("Quarterly" | "Annual" | "Half-Yearly"). Each row is NSE's own real
    JSON — includes `consolidated` ("Non-Consolidated" | "Consolidated"),
    `xbrl` (a real file URL, or a "-" placeholder when none was filed for
    this row), `broadCastDate`, `relatingTo`, `seqNumber`. Never filters
    or interprets here — that's the caller's job, since what counts as
    "real, usable" data depends on the metric being extracted."""
    s = session or _session()
    r = s.get(_RESULTS_URL, headers=_HEADERS, params={"index": "equities", "symbol": symbol.upper(), "period": period}, timeout=15)
    r.raise_for_status()
    rows = r.json() or []
    for row in rows:
        row["_broadcast_dt"] = _parse_broadcast_date(row.get("broadCastDate"))
    rows.sort(key=lambda d: d["_broadcast_dt"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return rows


def non_consolidated_with_real_xbrl(rows: list[dict]) -> list[dict]:
    """The load-bearing filter (see FinancialFact's own module docstring,
    rule 1) — bank-regulatory ratios only ever appear on the Non-
    Consolidated filing, confirmed live across all 5 reference banks."""
    return [r for r in rows if r.get("consolidated") == "Non-Consolidated" and r.get("xbrl") and "xbrl/-" not in r["xbrl"]]


def fetch_xbrl_text(url: str, session: requests.Session | None = None) -> str:
    s = session or requests.Session()
    r = s.get(url, headers=_HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def extract_tag_value(xbrl_content: str, tag: str) -> float | None:
    """The exact real regex validated in S3/S3-A against 20 real filings.
    Returns the FIRST occurrence (the current-period context; the second
    occurrence in these real filings is consistently the year-to-date
    cumulative figure, not needed here). None when the tag is genuinely
    absent from this real filing — the caller distinguishes "absent
    entirely" (TAG_MISSING/SOURCE_UNAVAILABLE) from "present but zero"
    (a real, if suspicious, POPULATED value) itself."""
    matches = re.findall(rf"<in-bse-fin:{tag}[^>]*>([^<]*)</in-bse-fin:{tag}>", xbrl_content)
    if not matches:
        return None
    try:
        return float(matches[0])
    except (TypeError, ValueError):
        return None
