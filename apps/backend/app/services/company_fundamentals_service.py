"""
Company Fundamentals — P/E, P/B, market cap, and 52-week range via yfinance.

Extracted as a standalone, reusable service from the pattern already proven
in `ai_search_service._fetch_valuation_sync` (left untouched there — this
is a parallel implementation, not a refactor of existing, shipped code).
The outer retriever's own timeout wrapper (see
`app/ai_pipeline/retrieval/base.py::RetrieverSpec.timeout_s`) is what
actually guards against yfinance hangs; this module doesn't need to
duplicate that plumbing.
"""
from __future__ import annotations

import asyncio


def _fetch_fundamentals_sync(symbols: list[str]) -> dict[str, dict]:
    import yfinance as yf

    result: dict[str, dict] = {}
    for sym in symbols[:5]:
        try:
            info = yf.Ticker(f"{sym}.NS").info or {}
            pe = info.get("trailingPE") or info.get("forwardPE")
            pb = info.get("priceToBook")
            hi = info.get("fiftyTwoWeekHigh")
            lo = info.get("fiftyTwoWeekLow")
            market_cap = info.get("marketCap")
            fields = {
                "pe": round(float(pe), 1) if pe else None,
                "pb": round(float(pb), 2) if pb else None,
                "52w_high": round(float(hi), 1) if hi else None,
                "52w_low": round(float(lo), 1) if lo else None,
                "market_cap": int(market_cap) if market_cap else None,
            }
            result[sym] = {k: v for k, v in fields.items() if v is not None}
        except Exception:
            continue
    return result


async def get_fundamentals(symbols: list[str]) -> dict[str, dict]:
    """Returns {symbol: {pe, pb, 52w_high, 52w_low, market_cap}} for up to 5 symbols."""
    if not symbols:
        return {}
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _fetch_fundamentals_sync, symbols)
