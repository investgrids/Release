"""
NIFTY 50 benchmark backfill — Phase 2D.

Stores the index itself (^NSEI) into PriceBar under the synthetic
canonical symbol "NIFTY50", plus the NIFTYBEES ETF under "NIFTYBEES" as
a recorded fallback/sanity-check series — owner's explicit instruction:
"use ^NSEI as the primary benchmark and only use NIFTYBEES as a
fallback... If ^NSEI history proves incomplete or inconsistent, then
use NIFTYBEES transparently as a fallback and record which benchmark
each result used."

Both tickers are outside symbols.py's to_yfinance() convention (that
module maps bare equity symbols to "<SYMBOL>.NS"; "^NSEI" is an index
ticker, already left untouched by to_yfinance's own "^" passthrough,
but there is no bare canonical symbol that maps TO "^NSEI" — a
made-up canonical name like "NIFTY50" would incorrectly become
"NIFTY50.NS" if run through the generic resolver). This module fetches
both tickers directly rather than teaching symbols.py an index special
case that no other part of the quant layer needs.

Verified live (2026-08-16) before writing this: ^NSEI has 1,245 daily
bars spanning 2021-08-02 -> 2026-08-14, zero null closes, max gap 5
days (a normal weekend/holiday gap) — clean enough to be primary
without needing the fallback in practice. NIFTYBEES.NS backfilled
anyway, unconditionally, so the fallback is always available and the
"record which benchmark was used" requirement is meaningful rather
than hypothetical.
"""
from __future__ import annotations

from app.services.quant.backfill import _fetch_symbol_history_sync, _classify_quality, upsert_price_bars

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

NIFTY50_SYMBOL = "NIFTY50"
NIFTY50_YF_TICKER = "^NSEI"
NIFTYBEES_SYMBOL = "NIFTYBEES"
NIFTYBEES_YF_TICKER = "NIFTYBEES.NS"

_MIN_ACCEPTABLE_ROWS = 1000   # ~4 years of trading days — below this, ^NSEI is "incomplete" per the owner's own framing


def _fetch_ticker_sync(ticker: str, period: str) -> list[dict]:
    """Same fetch/parse logic as backfill._fetch_symbol_history_sync, but
    against an explicit yfinance ticker rather than a canonical symbol
    resolved via to_yfinance() — see module docstring."""
    import math
    try:
        import yfinance as yf

        hist = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True, timeout=15)
        if hist is None or hist.empty:
            return []
        rows: list[dict] = []
        for ts, row in hist.iterrows():
            try:
                o, h, l, c = (float(row[col].iloc[0] if hasattr(row[col], "iloc") else row[col])
                              for col in ("Open", "High", "Low", "Close"))
                vol = row.get("Volume")
                v = int(vol.iloc[0] if hasattr(vol, "iloc") else vol) if vol is not None and not (isinstance(vol, float) and math.isnan(vol)) else None
            except Exception:
                continue
            if any(math.isnan(x) for x in (o, h, l, c)) or c <= 0:
                continue
            bar_date = ts.date() if hasattr(ts, "date") else ts
            rows.append({"bar_date": bar_date, "open": round(o, 2), "high": round(h, 2),
                          "low": round(l, 2), "close": round(c, 2), "volume": v})
        return rows
    except Exception:
        return []


async def backfill_benchmark(db: AsyncSession, period: str = "5y") -> dict:
    """Backfills both NIFTY50 (^NSEI, primary) and NIFTYBEES (fallback)
    unconditionally. Returns row counts for both plus a `primary_usable`
    flag the caller (phase2d_backtest.py) uses to decide, per symbol/date,
    which series to actually read from."""
    loop = asyncio.get_running_loop()

    nifty_raw = await loop.run_in_executor(None, _fetch_ticker_sync, NIFTY50_YF_TICKER, period)
    nifty_rows = _classify_quality(nifty_raw)
    nifty_inserted, nifty_updated = await upsert_price_bars(db, NIFTY50_SYMBOL, nifty_rows, source="yfinance_index")

    await asyncio.sleep(0.5)

    beeps_raw = await loop.run_in_executor(None, _fetch_ticker_sync, NIFTYBEES_YF_TICKER, period)
    beeps_rows = _classify_quality(beeps_raw)
    beeps_inserted, beeps_updated = await upsert_price_bars(db, NIFTYBEES_SYMBOL, beeps_rows, source="yfinance_etf")

    await db.commit()

    return {
        "nifty50_fetched": len(nifty_rows), "nifty50_inserted": nifty_inserted, "nifty50_updated": nifty_updated,
        "niftybees_fetched": len(beeps_rows), "niftybees_inserted": beeps_inserted, "niftybees_updated": beeps_updated,
        "primary_usable": len(nifty_rows) >= _MIN_ACCEPTABLE_ROWS,
    }
