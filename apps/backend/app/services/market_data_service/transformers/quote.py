"""
Transform raw provider quote dicts → standard Quote model.
Each provider calls these helpers so the rest of the app never sees raw data.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..types import Quote

_IST = timezone(timedelta(hours=5, minutes=30))


def _safe_float(v, default: float = 0.0) -> float:
    try:
        f = float(v or default)
        return default if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return default


def _safe_int(v, default: int = 0) -> int:
    try:
        return int(float(v or default))
    except (TypeError, ValueError):
        return default


def _now_ist() -> str:
    return datetime.now(_IST).strftime("%H:%M:%S IST")


# ── YFinance transformer ───────────────────────────────────────────────────────

def from_yfinance_fast_info(symbol: str, fast_info, name: str = "") -> Optional[Quote]:
    """Build a Quote from a yfinance fast_info object."""
    try:
        price      = _safe_float(fast_info.last_price)
        prev_close = _safe_float(fast_info.previous_close)
        if not price or not prev_close:
            return None
        change = price - prev_close
        pct    = (change / prev_close) * 100

        try:
            high = _safe_float(fast_info.day_high or price)
            low  = _safe_float(fast_info.day_low  or price)
        except Exception:
            high, low = price, price

        try:
            vol = _safe_int(fast_info.last_volume or 0)
        except Exception:
            vol = 0

        return Quote(
            symbol        = symbol.upper(),
            name          = name or symbol.upper(),
            exchange      = "NSE",
            price         = round(price,      2),
            change        = round(change,     2),
            change_percent= round(pct,        4),
            open          = round(prev_close, 2),  # yfinance fast_info lacks open
            high          = round(high,       2),
            low           = round(low,        2),
            previous_close= round(prev_close, 2),
            volume        = vol,
            last_updated  = _now_ist(),
        )
    except Exception:
        return None


def from_yfinance_info(symbol: str, info: dict, fast_info=None) -> Optional[Quote]:
    """Build a Quote from a full yfinance info dict."""
    try:
        price      = _safe_float(info.get("currentPrice") or (fast_info.last_price if fast_info else 0))
        prev_close = _safe_float(info.get("previousClose") or (fast_info.previous_close if fast_info else 0))
        if not price or not prev_close:
            return None
        change = price - prev_close
        pct    = (change / prev_close) * 100
        return Quote(
            symbol        = symbol.upper(),
            name          = info.get("longName") or info.get("shortName") or symbol.upper(),
            exchange      = "NSE",
            price         = round(price,                                            2),
            change        = round(change,                                           2),
            change_percent= round(pct,                                              4),
            open          = round(_safe_float(info.get("open") or prev_close),      2),
            high          = round(_safe_float(info.get("dayHigh") or price),        2),
            low           = round(_safe_float(info.get("dayLow")  or price),        2),
            previous_close= round(prev_close,                                       2),
            volume        = _safe_int(info.get("volume") or 0),
            last_updated  = _now_ist(),
        )
    except Exception:
        return None


# ── Fyers transformer ─────────────────────────────────────────────────────────

def from_fyers_quote(raw: dict) -> Optional[Quote]:
    """
    Build a Quote from a Fyers quotes API response item.
    Fyers quote keys: symbol, name, lp (last price), chp (change%), ch (change), open_price, high_price, low_price, prev_close_price, volume
    """
    try:
        symbol = raw.get("symbol", "").split(":")[-1].replace("-EQ", "").replace("-INDEX", "")
        price  = _safe_float(raw.get("lp") or raw.get("v", {}).get("lp"))
        ch     = _safe_float(raw.get("ch") or raw.get("v", {}).get("ch"))
        chp    = _safe_float(raw.get("chp") or raw.get("v", {}).get("chp"))
        if not price:
            return None

        prev   = price - ch if ch else price
        return Quote(
            symbol        = symbol,
            name          = raw.get("name") or symbol,
            exchange      = "NSE",
            price         = round(price, 2),
            change        = round(ch,    2),
            change_percent= round(chp,   4),
            open          = round(_safe_float(raw.get("open_price") or raw.get("v", {}).get("open_price") or prev), 2),
            high          = round(_safe_float(raw.get("high_price") or raw.get("v", {}).get("high_price") or price), 2),
            low           = round(_safe_float(raw.get("low_price")  or raw.get("v", {}).get("low_price")  or price), 2),
            previous_close= round(prev, 2),
            volume        = _safe_int(raw.get("volume") or raw.get("v", {}).get("volume") or 0),
            last_updated  = _now_ist(),
        )
    except Exception:
        return None
