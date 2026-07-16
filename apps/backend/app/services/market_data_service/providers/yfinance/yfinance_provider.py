"""
YFinanceProvider — implements MarketDataProvider using yfinance.

This wraps the existing market data logic and normalises it into
the standard domain models. It is used as the fallback provider
when Fyers credentials are unavailable, and always supports the
full interface except WebSocket (no live tick feed in yfinance).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import math
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, AsyncIterator

import yfinance as yf

from ...interfaces import MarketDataProvider
from ...types import Quote, Company, Candle, IndexQuote, SectorPerformance, MarketStatus, TopMover
from ...transformers import quote as qt, candle as ct, indices as it, sector as st

_IST = timezone(timedelta(hours=5, minutes=30))

# ── Ticker registries ─────────────────────────────────────────────────────────

_EXTENDED_INDICES: dict[str, tuple[str, str]] = {
    "NIFTY 50":       ("^NSEI",       "🇮🇳"),
    "SENSEX":         ("^BSESN",      "🇮🇳"),
    "BANK NIFTY":     ("^NSEBANK",    "🇮🇳"),
    "NIFTY IT":       ("^CNXIT",      "🇮🇳"),
    "INDIA VIX":      ("^INDIAVIX",   "🇮🇳"),
    "Dow Jones":      ("^DJI",        "🇺🇸"),
    "S&P 500":        ("^GSPC",       "🇺🇸"),
    "Nasdaq":         ("^IXIC",       "🇺🇸"),
    "FTSE 100":       ("^FTSE",       "🇬🇧"),
    "DAX":            ("^GDAXI",      "🇩🇪"),
    "CAC 40":         ("^FCHI",       "🇫🇷"),
    "Nikkei 225":     ("^N225",       "🇯🇵"),
    "Hang Seng":      ("^HSI",        "🇭🇰"),
    "Shanghai":       ("000001.SS",   "🇨🇳"),
    "KOSPI":          ("^KS11",       "🇰🇷"),
}

_SECTOR_ETFS: dict[str, str] = {
    "IT":           "MOFSL-BSE-IT.NS",
    "Banking":      "BANKBEES.NS",
    "Pharma":       "PHARMABEES.NS",
    "Auto":         "AUTOBEES.NS",
    "Energy":       "ENERGYBEES.NS",
    "FMCG":         "FMCGBEES.NS",
    "Infra":        "INFRABEES.NS",
    "Metal":        "METALBEES.NS",
    "Realty":       "REALTYBEES.NS",
}

_NIFTY500_SAMPLE = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC", "KOTAKBANK",
    "BAJFINANCE", "SBIN", "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "TATAMOTORS",
    "WIPRO", "HCLTECH", "TECHM", "SUNPHARMA", "DRREDDY", "TATASTEEL", "JSWSTEEL",
    "ONGC", "NTPC", "POWERGRID", "BPCL", "IOC", "COALINDIA", "HINDALCO", "VEDL",
    "BEL", "HAL", "RVNL", "IRCON", "BHEL", "TATAPOWER", "ADANIENT", "ADANIGREEN",
    "BAJAJ-AUTO", "HEROMOTOCO", "M&M", "EICHERMOT", "ULTRACEMCO", "GRASIM", "SHREECEM",
    "DIVISLAB", "CIPLA", "AUROPHARMA", "NESTLEIND", "BRITANNIA",
]

_SYMBOL_NAMES: dict[str, str] = {
    "RELIANCE": "Reliance Industries", "TCS": "Tata Consultancy Services",
    "HDFCBANK": "HDFC Bank", "ICICIBANK": "ICICI Bank", "INFY": "Infosys",
    "HINDUNILVR": "Hindustan Unilever", "ITC": "ITC Ltd", "KOTAKBANK": "Kotak Mahindra Bank",
    "BAJFINANCE": "Bajaj Finance", "SBIN": "State Bank of India", "LT": "Larsen & Toubro",
    "AXISBANK": "Axis Bank", "ASIANPAINT": "Asian Paints", "MARUTI": "Maruti Suzuki",
    "TATAMOTORS": "Tata Motors", "WIPRO": "Wipro", "HCLTECH": "HCL Technologies",
    "TECHM": "Tech Mahindra", "SUNPHARMA": "Sun Pharma", "DRREDDY": "Dr. Reddy's",
    "TATASTEEL": "Tata Steel", "JSWSTEEL": "JSW Steel", "ONGC": "ONGC",
    "NTPC": "NTPC Ltd", "POWERGRID": "Power Grid Corp", "BPCL": "BPCL",
    "IOC": "Indian Oil Corp", "COALINDIA": "Coal India", "HINDALCO": "Hindalco",
    "VEDL": "Vedanta", "BEL": "Bharat Electronics", "HAL": "HAL",
    "RVNL": "Rail Vikas Nigam", "IRCON": "IRCON International", "BHEL": "BHEL",
    "TATAPOWER": "Tata Power", "ADANIENT": "Adani Enterprises", "ADANIGREEN": "Adani Green Energy",
    "BAJAJ-AUTO": "Bajaj Auto", "HEROMOTOCO": "Hero MotoCorp", "M&M": "Mahindra & Mahindra",
    "EICHERMOT": "Eicher Motors", "ULTRACEMCO": "UltraTech Cement", "GRASIM": "Grasim Industries",
    "SHREECEM": "Shree Cement", "DIVISLAB": "Divi's Laboratories", "CIPLA": "Cipla",
    "AUROPHARMA": "Aurobindo Pharma", "NESTLEIND": "Nestlé India", "BRITANNIA": "Britannia Industries",
}

_PERIOD_MAP: dict[str, tuple[str, str]] = {
    "1D":  ("1d",  "5m"),
    "1W":  ("5d",  "60m"),
    "1M":  ("1mo", "1d"),
    "6M":  ("6mo", "1wk"),
    "1Y":  ("1y",  "1wk"),
    "3Y":  ("3y",  "1mo"),
    "5Y":  ("5y",  "1mo"),
}

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=24, thread_name_prefix="yf-")


def _run(fn):
    """Run a sync callable in the shared thread pool."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(_executor, fn)


class YFinanceProvider(MarketDataProvider):
    """
    Fallback market data provider using yfinance.
    No authentication required. Used when Fyers is unavailable.
    All responses are normalized to standard domain models.
    """

    @property
    def name(self) -> str:
        return "YFinance"

    @property
    def supports_websocket(self) -> bool:
        return False

    # ── Quote ─────────────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> Optional[Quote]:
        ticker = f"{symbol.upper()}.NS"

        def _fetch():
            try:
                t   = yf.Ticker(ticker)
                fi  = t.fast_info
                name = _SYMBOL_NAMES.get(symbol.upper(), symbol.upper())
                return qt.from_yfinance_fast_info(symbol, fi, name)
            except Exception:
                return None

        return await _run(_fetch)

    async def get_quotes(self, symbols: list[str]) -> list[Quote]:
        tasks = [self.get_quote(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, Quote)]

    # ── Company ───────────────────────────────────────────────────────────────

    async def get_company(self, symbol: str) -> Optional[Company]:
        ticker = f"{symbol.upper()}.NS"

        def _fetch():
            try:
                t    = yf.Ticker(ticker)
                info = t.info
                return Company(
                    symbol         = symbol.upper(),
                    name           = info.get("longName") or symbol.upper(),
                    sector         = info.get("sector") or "N/A",
                    industry       = info.get("industry") or "N/A",
                    market_cap     = float(info.get("marketCap") or 0),
                    pe             = float(info.get("trailingPE") or 0),
                    eps            = float(info.get("trailingEps") or 0),
                    roe            = float(info.get("returnOnEquity") or 0) * 100,
                    book_value     = float(info.get("bookValue") or 0),
                    dividend_yield = float(info.get("dividendYield") or 0) * 100,
                    description    = (info.get("longBusinessSummary") or "")[:600],
                )
            except Exception:
                return None

        return await _run(_fetch)

    # ── Historical candles ────────────────────────────────────────────────────

    async def get_historical_candles(self, symbol: str, period: str = "6M", interval: str = "1d") -> list[Candle]:
        ticker = f"{symbol.upper()}.NS"
        yf_period, yf_interval = _PERIOD_MAP.get(period, ("6mo", "1wk"))

        def _fetch():
            try:
                hist = yf.download(ticker, period=yf_period, interval=yf_interval,
                                   progress=False, auto_adjust=True, timeout=10)
                if hist.empty:
                    return []
                candles = []
                for idx, row in hist.iterrows():
                    c = ct.from_yfinance_row(idx, row)
                    if c:
                        candles.append(c)
                return candles
            except Exception:
                return []

        return await _run(_fetch)

    # ── Indices ───────────────────────────────────────────────────────────────

    async def get_indices(self) -> list[IndexQuote]:
        async def _one(name: str, ticker: str, flag: str) -> Optional[IndexQuote]:
            def _fetch():
                try:
                    fi = yf.Ticker(ticker).fast_info
                    return it.from_yfinance_fast_info(name, ticker, fi, flag)
                except Exception:
                    return None
            return await _run(_fetch)

        tasks = [_one(n, t, f) for n, (t, f) in _EXTENDED_INDICES.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, IndexQuote)]

    # ── Top movers ────────────────────────────────────────────────────────────

    async def get_top_movers(self) -> dict[str, list[TopMover]]:
        def _fetch():
            def _one(sym: str):
                try:
                    fi  = yf.Ticker(f"{sym}.NS").fast_info
                    cur = float(fi.last_price or 0)
                    prv = float(fi.previous_close or 0)
                    vol = float(getattr(fi, "last_volume", None) or 0)
                    if not cur or not prv or prv == 0:
                        return None
                    if math.isnan(cur) or math.isnan(prv):
                        return None
                    pct = (cur - prv) / prv * 100
                    return {"sym": sym, "cur": cur, "pct": pct, "vol_cr": vol * cur / 1e7}
                except Exception:
                    return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
                rows = [r for r in pool.map(_one, _NIFTY500_SAMPLE) if r]

            def _mover(r: dict, direction: str) -> TopMover:
                return TopMover(
                    symbol        = r["sym"],
                    name          = _SYMBOL_NAMES.get(r["sym"], r["sym"]),
                    price         = round(r["cur"], 2),
                    change_percent= round(r["pct"], 2),
                    volume_cr     = round(r["vol_cr"], 1),
                    direction     = direction,
                )

            rows.sort(key=lambda r: r["pct"], reverse=True)
            gainers = [_mover(r, "up")   for r in rows if r["pct"] > 0][:4]
            losers  = [_mover(r, "down") for r in reversed(rows) if r["pct"] < 0][:4]

            rows.sort(key=lambda r: r["vol_cr"], reverse=True)
            active  = [_mover(r, "up")   for r in rows[:4]]

            return {"gainers": gainers, "losers": losers, "active": active}

        return await _run(_fetch)

    # ── Market status ─────────────────────────────────────────────────────────

    async def get_market_status(self) -> MarketStatus:
        now   = datetime.now(_IST)
        total = now.hour * 60 + now.minute

        if now.weekday() >= 5:
            status = "weekend"
        elif total < 9 * 60:
            status = "pre_market"
        elif total < 9 * 60 + 15:
            status = "pre_open"
        elif total <= 15 * 60 + 30:
            status = "open"
        else:
            status = "closed"

        return MarketStatus(
            is_open  = status == "open",
            status   = status,
            time_ist = now.strftime("%I:%M %p"),
            date     = now.strftime("%d %b %Y"),
        )

    # ── Sector performance ────────────────────────────────────────────────────

    async def get_sector_performance(self) -> list[SectorPerformance]:
        async def _one(name: str, ticker: str) -> Optional[SectorPerformance]:
            sector_id = name.lower().replace(" ", "-")

            def _fetch():
                try:
                    fi = yf.Ticker(ticker).fast_info
                    return st.from_yfinance_fast_info(sector_id, name, fi)
                except Exception:
                    return None

            return await _run(_fetch)

        tasks   = [_one(n, t) for n, t in _SECTOR_ETFS.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, SectorPerformance)]

    # ── WebSocket (not supported) ─────────────────────────────────────────────

    async def subscribe_quotes(self, symbols: list[str]) -> AsyncIterator[Quote]:
        raise NotImplementedError("YFinance does not support WebSocket live quotes.")

    async def unsubscribe(self, symbols: list[str]) -> None:
        pass

    async def disconnect(self) -> None:
        _executor.shutdown(wait=False)
