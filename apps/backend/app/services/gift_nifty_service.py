"""
GIFT Nifty — Phase 5B.

Real, first-party GIFT Nifty futures data from NSE India's own
marketStatus endpoint (nseindia.com/api/marketStatus), which carries a
"giftnifty" object with live price/change/expiry/timestamp for the
actual NSE IX GIFT City contract — confirmed live 2026-08-16 at
02:29 IST, genuinely inside GIFT Nifty's documented overnight session
(16:35-02:45 IST), not domestic cash-market hours. Same host and
header/session-cookie convention already established in
app/providers/nse_provider.py, reused here rather than reinvented.

Replaces a real, confirmed correctness bug (not just a quality
improvement): the prior implementation (market.py's now-removed
_nifty_futures_ticker()) constructed an NSE DOMESTIC Nifty futures
ticker (e.g. "NIFTY26AUGFUT.NS") and labeled it "Gift City proxy" —
that instrument only trades during NSE's normal session, so it
structurally cannot provide the overnight signal GIFT Nifty exists
for. When that ticker failed, the code fell further back to plain
Nifty spot, STILL labeled "gift_nifty" — silently changing what the
number meant without telling any consumer.

The rule enforced here, per owner instruction: GIFT Nifty is either
real (fetched from this source) or explicitly unavailable — spot may
be shown separately, but is NEVER substituted and relabeled as GIFT
Nifty. One shared adapter, one normalization contract — market.py and
opening_prediction_service.py both consume the same GiftNiftyResult
instead of each reimplementing the fetch.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import httpx
import structlog

log = structlog.get_logger(__name__)

_IST = ZoneInfo("Asia/Kolkata")
_MARKET_STATUS_URL = "https://www.nseindia.com/api/marketStatus"
_HOMEPAGE_URL = "https://www.nseindia.com/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/market-data/live-market-indices",
}
# GIFT Nifty's own documented session gap is 02:45-06:30 IST (~3h45m) —
# _STALE_AFTER_HOURS is set generously beyond that so the normal daily
# close-of-session doesn't itself get flagged as a data problem. A
# genuinely broken feed (many hours old — e.g. a weekend stall, or a
# silently frozen upstream value) still gets caught. Documented as an
# explicit, testable choice, not a guess at GIFT Nifty's exact weekly
# calendar (which this module does not claim to model).
_STALE_AFTER_HOURS = 8


@dataclass
class GiftNiftyResult:
    status: str                              # "live" | "stale" | "unavailable"
    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    expiry: date | None = None
    source_timestamp: datetime | None = None  # UTC-aware; source reports IST
    spot_price: float | None = None
    premium_points: float | None = None
    premium_pct: float | None = None
    source: str = "nse_market_status"
    reason: str | None = None


def _parse_ist_timestamp(raw: str) -> datetime | None:
    """"15-Aug-2026 02:29" -> aware UTC datetime (source reports IST)."""
    try:
        naive = datetime.strptime(raw.strip(), "%d-%b-%Y %H:%M")
        return naive.replace(tzinfo=_IST).astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError):
        return None


def _parse_expiry(raw: str) -> date | None:
    try:
        return datetime.strptime(raw.strip(), "%d-%b-%Y").date()
    except (ValueError, AttributeError, TypeError):
        return None


def _fetch_market_status_sync() -> dict | None:
    try:
        with httpx.Client(headers=_HEADERS, timeout=15, follow_redirects=True) as client:
            client.get(_HOMEPAGE_URL)   # establishes the session cookies NSE's anti-bot layer requires
            resp = client.get(_MARKET_STATUS_URL)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.warning("gift_nifty.fetch_failed", error=str(exc)[:200])
        return None


def _fetch_spot_sync() -> float | None:
    try:
        import yfinance as yf
        hist = yf.Ticker("^NSEI").history(period="1d", interval="1m", auto_adjust=True)
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as exc:
        log.warning("gift_nifty.spot_fetch_failed", error=str(exc)[:200])
        return None


def normalize(raw: dict | None, spot_price: float | None, now: datetime) -> GiftNiftyResult:
    """Pure function — kept separate from the network calls so every
    case (malformed row, missing row, stale timestamp, spot failure,
    fetch failure) can be tested deterministically without hitting the
    real network."""
    if raw is None:
        return GiftNiftyResult(status="unavailable", reason="source_fetch_failed", spot_price=spot_price)

    gift_row = raw.get("giftnifty")
    if not gift_row or not isinstance(gift_row, dict):
        return GiftNiftyResult(status="unavailable", reason="giftnifty_row_missing", spot_price=spot_price)

    try:
        price = float(gift_row["LASTPRICE"])
        change = float(gift_row["DAYCHANGE"])
        change_pct = float(gift_row["PERCHANGE"])
    except (KeyError, TypeError, ValueError):
        return GiftNiftyResult(status="unavailable", reason="giftnifty_row_malformed", spot_price=spot_price)

    expiry = _parse_expiry(gift_row.get("EXPIRYDATE", ""))
    source_ts = _parse_ist_timestamp(gift_row.get("TIMESTMP", ""))

    status, reason = "live", None
    if source_ts is None:
        status, reason = "stale", "source_timestamp_unparseable"
    elif (now - source_ts).total_seconds() > _STALE_AFTER_HOURS * 3600:
        status, reason = "stale", "source_timestamp_too_old"

    premium_points = premium_pct = None
    if spot_price and spot_price > 0:
        premium_points = round(price - spot_price, 2)
        premium_pct = round((price - spot_price) / spot_price * 100, 3)

    return GiftNiftyResult(
        status=status, price=price, change=change, change_pct=change_pct,
        expiry=expiry, source_timestamp=source_ts,
        spot_price=spot_price, premium_points=premium_points, premium_pct=premium_pct,
        source="nse_market_status", reason=reason,
    )


async def get_gift_nifty(spot_price: float | None = None) -> GiftNiftyResult:
    """The one shared entry point — market.py, opening_prediction_service.py,
    and any future consumer all call this instead of independently
    fetching/parsing NSE's endpoint. Pass spot_price if the caller
    already has a fresh one (avoids a duplicate fetch); otherwise this
    fetches it independently. A spot-fetch failure never blocks GIFT
    Nifty itself from being reported — premium is simply null."""
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, _fetch_market_status_sync)
    if spot_price is None:
        spot_price = await loop.run_in_executor(None, _fetch_spot_sync)
    now = datetime.now(timezone.utc)
    return normalize(raw, spot_price, now)


def get_gift_nifty_sync(spot_price: float | None = None) -> GiftNiftyResult:
    """Sync wrapper for callers that are themselves sync functions
    (market.py's _fetch_enhanced_premarket, opening_prediction_service's
    _fetch_signals_sync) — both run inside a plain executor thread in
    production, where a bare asyncio.run() is safe. But asyncio.run()
    raises if the calling thread already has a running loop (a real
    risk for tests, scripts, or future callers), so this checks first
    and falls back to a dedicated thread rather than crashing."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(get_gift_nifty(spot_price))
    else:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, get_gift_nifty(spot_price)).result()
