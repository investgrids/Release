"""
EIA Europe Brent spot price — appropriately-licensed Brent source.

Replaces the yfinance/Yahoo Brent value (redistribution rights unresolved) with
the U.S. Energy Information Administration's own series RBRTE ("Europe Brent Spot
Price FOB, Dollars per Barrel"). EIA data is U.S. government public domain and is
free to reuse with attribution — so a Brent value sourced here is publicly
clearable, unlike the Yahoo-sourced commodities.

IMPORTANT — this is NOT a live quote. EIA publishes a DAILY spot series with a
lag of several business days. We therefore always carry the observation date and
a `stale` flag, compute change day-over-day (not intraday), and never present the
latest observation as a real-time tick. There is no intraday high/low.

Key handling: the API key is read ONLY from settings.eia_api_key (backend env
var EIA_API_KEY). It is never logged, never put into a logged URL, never returned
in an API response. On any error we log the status/kind only — never the request
URL (which carries the key as a query param).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx
import structlog

log = structlog.get_logger(__name__)

_EIA_URL = "https://api.eia.gov/v2/petroleum/pri/spt/data/"
_SERIES = "RBRTE"                 # Europe Brent Spot Price FOB (Dollars per Barrel), daily
_EXPECTED_UNIT_HINT = "BBL"      # EIA v2 reports units like "$/BBL"; we validate loosely
# EIA's daily spot lags several business days; older than this we flag stale so no
# caller can present it as current. Not a hard failure — the dated value is still real.
_STALE_AFTER_DAYS = 10
_TIMEOUT_S = 15


@dataclass
class EiaBrentState:
    status: str                       # "live" | "unavailable"
    latest_date: date | None = None   # observation date (NOT "now")
    value: float | None = None        # USD per barrel
    prev_value: float | None = None
    change: float | None = None       # day-over-day (latest - prior observation)
    pct: float | None = None
    unit: str = "USD / bbl"
    source: str = "U.S. Energy Information Administration"
    stale: bool = False               # observation older than _STALE_AFTER_DAYS
    age_days: int | None = None
    reason: str | None = None


def _coerce_float(x) -> float | None:
    try:
        v = float(x)
        return v if v == v else None   # reject NaN
    except (TypeError, ValueError):
        return None


def fetch_eia_brent(api_key: str, now: datetime | None = None) -> EiaBrentState:
    """Fetch the latest two EIA Brent spot observations and derive value, day-over-day
    change and staleness. Pure w.r.t. settings — the caller passes the key. Never
    raises: every failure returns status='unavailable' with a reason."""
    now = now or datetime.now(timezone.utc)
    if not (api_key or "").strip():
        return EiaBrentState(status="unavailable", reason="missing_api_key")

    params = {
        "api_key": api_key,
        "frequency": "daily",
        "data[0]": "value",
        "facets[series][]": _SERIES,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "offset": 0,
        "length": 5,
    }
    try:
        with httpx.Client(timeout=_TIMEOUT_S) as client:
            resp = client.get(_EIA_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.TimeoutException:
        log.warning("eia_brent.timeout")
        return EiaBrentState(status="unavailable", reason="timeout")
    except httpx.HTTPStatusError as exc:
        # Never log the URL (carries the key); only the status code.
        log.warning("eia_brent.http_error", status_code=exc.response.status_code)
        return EiaBrentState(status="unavailable", reason=f"http_{exc.response.status_code}")
    except Exception as exc:
        log.warning("eia_brent.request_failed", error_kind=type(exc).__name__)
        return EiaBrentState(status="unavailable", reason="request_error")

    # ----- validate metadata before mapping -----
    rows = (((payload or {}).get("response") or {}).get("data")) or []
    if not isinstance(rows, list) or not rows:
        return EiaBrentState(status="unavailable", reason="no_data_rows")

    def _ok_series(r: dict) -> bool:
        sid = (r.get("series") or r.get("seriesId") or "")
        return str(sid).upper() == _SERIES

    series_rows = [r for r in rows if isinstance(r, dict) and _ok_series(r)]
    # Some EIA v2 facet responses omit an explicit series id per row; if the whole
    # query was faceted to RBRTE and rows carry no conflicting id, accept them.
    if not series_rows and all(isinstance(r, dict) and not (r.get("series") or r.get("seriesId")) for r in rows):
        series_rows = [r for r in rows if isinstance(r, dict)]
    if not series_rows:
        return EiaBrentState(status="unavailable", reason="series_mismatch")

    unit = next((str(r.get("units")) for r in series_rows if r.get("units")), "")
    if unit and _EXPECTED_UNIT_HINT not in unit.upper():
        # units not what we expect — refuse rather than mislabel the value
        log.warning("eia_brent.unexpected_units", units=unit)
        return EiaBrentState(status="unavailable", reason="unexpected_units")

    # rows are sorted desc by period; find the two most recent with a real value
    parsed: list[tuple[date, float]] = []
    for r in series_rows:
        p = r.get("period")
        v = _coerce_float(r.get("value"))
        if not p or v is None:
            continue
        try:
            d = datetime.strptime(str(p)[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        parsed.append((d, v))
    if not parsed:
        return EiaBrentState(status="unavailable", reason="no_valid_observations")

    parsed.sort(key=lambda t: t[0], reverse=True)
    latest_date, value = parsed[0]
    prev_value = parsed[1][1] if len(parsed) > 1 else None
    change = round(value - prev_value, 2) if prev_value is not None else None
    pct = round((change / prev_value) * 100, 2) if (change is not None and prev_value) else None

    age_days = (now.date() - latest_date).days
    stale = age_days > _STALE_AFTER_DAYS

    return EiaBrentState(
        status="live",
        latest_date=latest_date,
        value=round(value, 2),
        prev_value=prev_value,
        change=change,
        pct=pct,
        unit="USD / bbl",
        stale=stale,
        age_days=age_days,
    )


def get_eia_brent_state(now: datetime | None = None) -> EiaBrentState:
    """settings-aware convenience wrapper. Returns unavailable (missing_api_key)
    when EIA_API_KEY is not configured — callers then fall back to their prior
    source."""
    from app.core.config import settings
    return fetch_eia_brent(getattr(settings, "eia_api_key", "") or "", now=now)
