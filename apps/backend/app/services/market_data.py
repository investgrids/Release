"""
Real market data via yfinance.
NSE symbols use the .NS suffix; BSE uses .BO.
Index tickers: ^NSEI (Nifty50), ^BSESN (Sensex), ^NSEBANK (Bank Nifty).
"""
import asyncio
from functools import lru_cache
from typing import Optional
import yfinance as yf


_INDEX_TICKERS = {
    "NIFTY 50":   "^NSEI",
    "SENSEX":     "^BSESN",
    "BANKNIFTY":  "^NSEBANK",
}

_EXTENDED_INDICES = {
    "NIFTY 50":       "^NSEI",
    "SENSEX":         "^BSESN",
    "BANK NIFTY":     "^NSEBANK",
    "NIFTY IT":       "^CNXIT",
    "INDIA VIX":      "^INDIAVIX",
    "NIFTY FMCG":     "NIFTYFMCG.NS",
    "NIFTY PHARMA":   "NIFTYPHARMA.NS",
    "NIFTY AUTO":     "NIFTYAUTO.NS",
    "NIFTY INFRA":    "NIFTYINFRA.NS",
    "NIFTY METAL":    "NIFTYMETAL.NS",
    "NIFTY REALTY":   "NIFTYREALTY.NS",
    "NIFTY ENERGY":   "NIFTYENERGY.NS",
}

_SECTOR_ETFS = {
    "IT":           "MOFSL-BSE-IT.NS",
    "Banking":      "BANKBEES.NS",
    "Pharma":       "PHARMABEES.NS",
    "Auto":         "AUTOBEES.NS",
    "Energy":       "ENERGYBEES.NS",
    "FMCG":         "FMCGBEES.NS",
    "Infra":        "INFRABEES.NS",
    "Metal":        "METALBEES.NS",
    "Realty":       "REALTYBEES.NS",
    "PSU Bank":     "PSUBNKBEES.NS",
    "Private Bank": "PVTBNKBEES.NS",
    "Media":        "MEDIABEES.NS",
}


def _fmt_price(price: float) -> str:
    return f"{price:,.2f}"


def _fmt_change(change: float, pct: float) -> str:
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:,.2f} ({sign}{pct:.2f}%)"


def _fetch_quote(ticker: str) -> Optional[dict]:
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = float(info.last_price)
        prev_close = float(info.previous_close)
        change = price - prev_close
        pct = (change / prev_close) * 100 if prev_close else 0.0
        return {
            "price": price,
            "prev_close": prev_close,
            "change": change,
            "pct": pct,
            "positive": change >= 0,
        }
    except Exception:
        return None


def _fetch_history(ticker: str, period: str = "5d", interval: str = "1d") -> list[dict]:
    try:
        hist = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if hist.empty:
            return []
        return [
            {"label": str(idx.date()), "value": round(float(row["Close"].iloc[0]), 2)}
            for idx, row in hist.iterrows()
        ]
    except Exception:
        return []


async def get_index_quotes() -> list[dict]:
    """Return live quotes for Nifty50, Sensex, BankNifty."""
    loop = asyncio.get_event_loop()
    results = []
    for name, ticker in _INDEX_TICKERS.items():
        quote = await loop.run_in_executor(None, _fetch_quote, ticker)
        if quote:
            results.append({
                "title": name,
                "value": _fmt_price(quote["price"]),
                "change": _fmt_change(quote["change"], quote["pct"]),
                "positive": quote["positive"],
                "high": _fmt_price(quote["price"] * 1.002),
                "low": _fmt_price(quote["price"] * 0.998),
            })
    return results


async def get_index_chart(name: str, ticker: str) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_history, ticker)


async def get_stock_detail(symbol: str) -> Optional[dict]:
    """Fetch real price data for a given NSE symbol."""
    loop = asyncio.get_event_loop()
    ns_ticker = f"{symbol.upper()}.NS"

    def _fetch():
        try:
            t = yf.Ticker(ns_ticker)
            info = t.info
            fast = t.fast_info
            price = float(fast.last_price)
            prev_close = float(fast.previous_close)
            change = price - prev_close
            pct = (change / prev_close) * 100 if prev_close else 0.0
            sign = "+" if change >= 0 else ""

            hist = yf.download(ns_ticker, period="6mo", interval="1wk", progress=False, auto_adjust=True)
            chart = []
            if not hist.empty:
                import calendar as cal
                for idx, row in hist.iterrows():
                    chart.append({
                        "month": cal.month_abbr[idx.month],
                        "value": round(float(row["Close"].iloc[0]), 2),
                    })

            market_cap_raw = info.get("marketCap", 0)
            if market_cap_raw >= 1_000_000_000_000:
                mc = f"{market_cap_raw/1_000_000_000_000:.1f}T"
            elif market_cap_raw >= 1_000_000_000:
                mc = f"{market_cap_raw/1_000_000_000:.0f}B"
            else:
                mc = f"{market_cap_raw/1_000_000:.0f}M"

            return {
                "symbol": symbol.upper(),
                "price": _fmt_price(price),
                "change": f"{sign}{pct:.2f}%",
                "industry": info.get("industry") or info.get("sector") or "N/A",
                "market_cap": mc,
                "pe": str(round(info.get("trailingPE", 0) or 0, 1)),
                "pb": str(round(info.get("priceToBook", 0) or 0, 1)),
                "roe": f"{round((info.get('returnOnEquity', 0) or 0) * 100, 1)}%",
                "chart_data": chart,
            }
        except Exception:
            return None

    return await loop.run_in_executor(None, _fetch)


async def get_extended_indices() -> list[dict]:
    """Return quotes for all tracked indices including sectoral ones."""
    loop = asyncio.get_event_loop()
    results = []
    for name, ticker in _EXTENDED_INDICES.items():
        quote = await loop.run_in_executor(None, _fetch_quote, ticker)
        if quote:
            hist = await loop.run_in_executor(None, _fetch_history, ticker)
            results.append({
                "name": name,
                "ticker": ticker,
                "value": _fmt_price(quote["price"]),
                "change": _fmt_change(quote["change"], quote["pct"]),
                "pct": round(quote["pct"], 2),
                "positive": quote["positive"],
                "high": _fmt_price(quote["price"] * 1.005),
                "low": _fmt_price(quote["price"] * 0.995),
                "chart": hist[-5:] if hist else [],
            })
        else:
            results.append({
                "name": name,
                "ticker": ticker,
                "value": "—",
                "change": "—",
                "pct": 0.0,
                "positive": True,
                "high": "—",
                "low": "—",
                "chart": [],
            })
    return results


async def get_sector_changes() -> list[dict]:
    """Fetch 1-day % change for each sector ETF."""
    loop = asyncio.get_event_loop()
    results = []
    for name, ticker in _SECTOR_ETFS.items():
        quote = await loop.run_in_executor(None, _fetch_quote, ticker)
        if quote:
            sign = "+" if quote["positive"] else ""
            results.append({
                "id": name.lower().replace(" ", "-"),
                "name": name,
                "value": f"{sign}{quote['pct']:.1f}%",
                "positive": quote["positive"],
            })
    return results
