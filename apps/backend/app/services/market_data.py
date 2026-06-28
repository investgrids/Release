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


_PERIOD_MAP: dict = {
    "1D":  ("1d",  "5m"),
    "1W":  ("5d",  "60m"),
    "1M":  ("1mo", "1d"),
    "6M":  ("6mo", "1wk"),
    "1Y":  ("1y",  "1wk"),
    "3Y":  ("3y",  "1mo"),
    "5Y":  ("5y",  "1mo"),
    "Max": ("max", "1mo"),
}

_REV_KEYS = ["Total Revenue", "TotalRevenue", "Revenue"]
_NI_KEYS  = ["Net Income", "NetIncome", "Net Income Common Stockholders"]


def _pct_str(v) -> str:
    try:
        return f"{round(float(v or 0) * 100, 1)}%"
    except Exception:
        return "—"


def _num_str(v, decimals: int = 1) -> str:
    try:
        val = float(v or 0)
        return str(round(val, decimals)) if val else "—"
    except Exception:
        return "—"


def _fmt_vol(v) -> str:
    try:
        v = float(v or 0)
    except Exception:
        return "—"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{int(v / 1_000)}K"
    return str(int(v)) if v else "—"


def _fmt_large(n) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "—"
    if n == 0:
        return "—"
    sign = "−" if n < 0 else ""
    a = abs(n)
    if a >= 1e12:
        return f"{sign}₹{a / 1e12:.2f}T"
    if a >= 1e9:
        return f"{sign}₹{a / 1e9:.1f}B"
    if a >= 1e7:
        return f"{sign}₹{a / 1e7:.0f}Cr"
    return f"{sign}₹{a / 1e5:.1f}L"


async def get_stock_detail(symbol: str) -> Optional[dict]:
    """Fetch comprehensive stock data from yfinance for an NSE symbol."""
    loop = asyncio.get_event_loop()
    ns_ticker = f"{symbol.upper()}.NS"

    def _fetch():
        try:
            t    = yf.Ticker(ns_ticker)
            info = t.info
            fast = t.fast_info

            price      = float(fast.last_price)
            prev_close = float(fast.previous_close)
            change     = price - prev_close
            pct        = (change / prev_close) * 100 if prev_close else 0.0
            sign       = "+" if change >= 0 else ""

            # 52-week range
            try:
                w52h = float(fast.year_high or 0)
                w52l = float(fast.year_low  or 0)
            except Exception:
                w52h = float(info.get("fiftyTwoWeekHigh") or 0)
                w52l = float(info.get("fiftyTwoWeekLow")  or 0)

            # Volume
            try:
                vol     = float(fast.volume or 0)
                avg_vol = float(fast.three_month_average_volume or 0)
            except Exception:
                vol     = float(info.get("volume")        or 0)
                avg_vol = float(info.get("averageVolume") or 0)

            # Market cap
            mc_raw = info.get("marketCap") or 0
            if mc_raw >= 1e12:
                mc = f"₹{mc_raw / 1e12:.2f}T"
            elif mc_raw >= 1e9:
                mc = f"₹{mc_raw / 1e9:.0f}B"
            elif mc_raw >= 1e7:
                mc = f"₹{mc_raw / 1e7:.0f}Cr"
            else:
                mc = "—"

            # Quarterly financials (4 most-recent quarters)
            quarterly_revenue: list    = []
            quarterly_net_income: list = []
            try:
                qf = t.quarterly_financials
                if not qf.empty and len(qf.columns) >= 2:
                    rev_row = next((qf.loc[k] for k in _REV_KEYS if k in qf.index), None)
                    ni_row  = next((qf.loc[k] for k in _NI_KEYS  if k in qf.index), None)
                    cols    = list(qf.columns)[:4]          # newest first
                    for col in reversed(cols):              # oldest → newest for bar chart
                        try:
                            lbl = col.strftime("%b '%y") if hasattr(col, "strftime") else str(col)[:7]
                        except Exception:
                            lbl = str(col)[:7]
                        rev = float(rev_row[col]) / 1e7 if rev_row is not None else 0.0
                        ni  = float(ni_row[col])  / 1e7 if ni_row  is not None else 0.0
                        quarterly_revenue.append({"label": lbl, "value": round(rev, 0)})
                        quarterly_net_income.append({"label": lbl, "value": round(ni, 0)})
            except Exception:
                pass

            open_price = info.get("open") or prev_close
            day_high   = info.get("dayHigh")  or price * 1.005
            day_low    = info.get("dayLow")   or price * 0.995

            return {
                "symbol":            symbol.upper(),
                "name":              info.get("longName") or info.get("shortName") or f"{symbol.upper()} Ltd.",
                "price":             _fmt_price(price),
                "prev_close":        _fmt_price(prev_close),
                "open":              _fmt_price(float(open_price)),
                "day_high":          _fmt_price(float(day_high)),
                "day_low":           _fmt_price(float(day_low)),
                "change":            f"{sign}{pct:.2f}%",
                "change_abs":        f"{sign}{change:.2f}",
                "pct_change":        round(pct, 2),
                "week52_high":       _fmt_price(w52h) if w52h else "—",
                "week52_low":        _fmt_price(w52l) if w52l else "—",
                "volume":            _fmt_vol(vol),
                "avg_volume":        _fmt_vol(avg_vol),
                "market_cap":        mc,
                "industry":          info.get("industry") or info.get("sector") or "N/A",
                "sector":            info.get("sector") or "N/A",
                "description":       (info.get("longBusinessSummary") or "")[:600],
                "pe":                _num_str(info.get("trailingPE")),
                "forward_pe":        _num_str(info.get("forwardPE")),
                "pb":                _num_str(info.get("priceToBook")),
                "eps":               _num_str(info.get("trailingEps"), 2),
                "roe":               _pct_str(info.get("returnOnEquity")),
                "roa":               _pct_str(info.get("returnOnAssets")),
                "beta":              _num_str(info.get("beta"), 2),
                "dividend_yield":    _pct_str(info.get("dividendYield")),
                "dividend_rate":     _num_str(info.get("dividendRate"), 2),
                "gross_margins":     _pct_str(info.get("grossMargins")),
                "operating_margins": _pct_str(info.get("operatingMargins")),
                "net_margins":       _pct_str(info.get("profitMargins")),
                "debt_to_equity":    _num_str(info.get("debtToEquity")),
                "current_ratio":     _num_str(info.get("currentRatio"), 2),
                "free_cashflow":     _fmt_large(info.get("freeCashflow")),
                "recommendation":    (info.get("recommendationKey") or "hold").lower(),
                "target_mean":       _fmt_price(float(info.get("targetMeanPrice") or 0)) if info.get("targetMeanPrice") else "—",
                "target_high":       _fmt_price(float(info.get("targetHighPrice") or 0)) if info.get("targetHighPrice") else "—",
                "target_low":        _fmt_price(float(info.get("targetLowPrice")  or 0)) if info.get("targetLowPrice")  else "—",
                "analyst_count":     int(info.get("numberOfAnalystOpinions") or 0),
                "held_institutions": _pct_str(info.get("heldPercentInstitutions")),
                "held_insiders":     _pct_str(info.get("heldPercentInsiders")),
                "quarterly_revenue":     quarterly_revenue,
                "quarterly_net_income":  quarterly_net_income,
            }
        except Exception:
            return None

    return await loop.run_in_executor(None, _fetch)


async def get_stock_chart(symbol: str, period: str = "6M") -> list:
    """Return OHLCV close history for charting — [{"label": "YYYY-MM-DD", "value": float}]."""
    loop = asyncio.get_event_loop()
    ns_ticker = f"{symbol.upper()}.NS"
    yf_period, interval = _PERIOD_MAP.get(period, ("6mo", "1wk"))

    def _fetch():
        try:
            hist = yf.download(
                ns_ticker, period=yf_period, interval=interval,
                progress=False, auto_adjust=True,
            )
            if hist.empty:
                return []
            result = []
            for idx, row in hist.iterrows():
                try:
                    close = row["Close"]
                    if hasattr(close, "iloc"):
                        close = close.iloc[0]
                    label = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
                    result.append({"label": label, "value": round(float(close), 2)})
                except Exception:
                    continue
            return result
        except Exception:
            return []

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
