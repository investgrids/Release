"""
Yahoo Finance details the company page did not show before: next result date and EPS estimate vs actual, growth / valuation multiples, dividend history.
Labelled Yahoo on the page and NOT used by the MarketRipple Score (the filing-backed contract is the source of record for score inputs).
Lazily called and cached; every field is None / empty when Yahoo has nothing, never a guessed zero.
"""
from __future__ import annotations

import asyncio
import math
import time
from datetime import date, datetime

import yfinance as yf

from app.services.market_data import _fmt_large

_PREFIX = {"INR": "₹", "USD": "$"}
_TTL = 3600.0
_CACHE: dict[str, tuple[float, dict]] = {}


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else f


def _ratio(v, decimals: int = 2) -> str | None:
    f = _num(v)
    return None if f is None else f"{f:.{decimals}f}"


def _pct(v) -> str | None:
    f = _num(v)
    return None if f is None else f"{f * 100:.1f}%"


def _money(v, prefix: str | None, decimals: int = 2) -> str | None:
    f = _num(v)
    return None if (f is None or not prefix) else f"{'−' if f < 0 else ''}{prefix}{abs(f):,.{decimals}f}"


def growth_valuation_rows(info: dict) -> list[dict]:
    """Label/value rows from Yahoo's info dict; a row is left out when its value is missing."""
    fc = info.get("financialCurrency")
    rows = [
        ("Revenue growth (YoY)", _pct(info.get("revenueGrowth"))),
        ("Earnings growth (YoY)", _pct(info.get("earningsGrowth"))),
        ("EV / EBITDA", _ratio(info.get("enterpriseToEbitda"))),
        ("EV / Revenue", _ratio(info.get("enterpriseToRevenue"))),
        ("Price / Sales", _ratio(info.get("priceToSalesTrailing12Months"))),
        ("PEG ratio", _ratio(info.get("trailingPegRatio") or info.get("pegRatio"))),
        ("Payout ratio", _pct(info.get("payoutRatio"))),
        ("Quick ratio", _ratio(info.get("quickRatio"))),
        ("EBITDA", _fmt_large(info.get("ebitda"), fc) if _num(info.get("ebitda")) else None),
        ("Total cash", _fmt_large(info.get("totalCash"), fc) if _num(info.get("totalCash")) else None),
        ("Total debt", _fmt_large(info.get("totalDebt"), fc) if _num(info.get("totalDebt")) else None),
    ]
    return [{"label": k, "value": v} for k, v in rows if v and v != "—"]


def earnings_block(df, prefix: str | None, today: date | None = None) -> dict:
    """Next result date + EPS estimate, and the last 4 reported quarters (estimate, actual, surprise). `df` is yfinance's earnings_dates frame."""
    today = today or date.today()
    out: dict = {"next_date": None, "next_eps_estimate": None, "history": []}
    if df is None or getattr(df, "empty", True):
        return out
    upcoming, past = [], []
    for idx, row in df.iterrows():
        d = idx.date() if hasattr(idx, "date") else None
        if d is None:
            continue
        est, act, sur = _num(row.get("EPS Estimate")), _num(row.get("Reported EPS")), _num(row.get("Surprise(%)"))
        (past if act is not None else upcoming).append((d, est, act, sur))
    future = sorted([u for u in upcoming if u[0] >= today])
    if future:
        out["next_date"] = future[0][0].isoformat()
        out["next_eps_estimate"] = _money(future[0][1], prefix)
    for d, est, act, sur in sorted(past, reverse=True)[:4]:
        out["history"].append({"date": d.isoformat(), "estimate": _money(est, prefix), "actual": _money(act, prefix),
                               "surprise_pct": None if sur is None else f"{sur:+.1f}%"})
    return out


def dividends_block(series, info: dict, prefix: str | None) -> dict:
    hist = []
    if series is not None and len(series) > 0:
        for idx, amt in list(series.items())[-8:][::-1]:
            hist.append({"date": idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10], "amount": _money(amt, prefix)})
    y = _num(info.get("dividendYield"))
    # Yahoo has returned this both as a fraction (0.0123) and as a percent (1.23): above 0.5 as a fraction would be a 50% yield, so treat it as percent.
    yld = None if y is None else (f"{y:.2f}%" if y > 0.5 else f"{y * 100:.2f}%")
    return {"yield": yld, "rate": _money(info.get("dividendRate"), prefix), "history": [h for h in hist if h["amount"]]}


def _fetch(symbol: str) -> dict:
    t = yf.Ticker(f"{symbol.upper()}.NS")
    try:
        info = t.info or {}
    except Exception:
        info = {}
    prefix = _PREFIX.get((info.get("financialCurrency") or "").upper())
    try:
        ed = t.get_earnings_dates(limit=12)
    except Exception:
        ed = None
    try:
        dv = t.dividends
    except Exception:
        dv = None
    return {
        "symbol": symbol.upper(), "source": "Yahoo Finance",
        "earnings": earnings_block(ed, prefix),
        "growth_valuation": growth_valuation_rows(info),
        "dividends": dividends_block(dv, info, prefix),
    }


async def get_stock_extras(symbol: str) -> dict:
    key = symbol.upper()
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    data = await asyncio.get_running_loop().run_in_executor(None, _fetch, key)
    if data["growth_valuation"] or data["earnings"]["history"] or data["earnings"]["next_date"] or data["dividends"]["history"]:
        _CACHE[key] = (time.monotonic(), data)   # an empty result is never cached
    return data
