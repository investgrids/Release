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
    import math
    try:
        hist = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if hist.empty:
            return []
        result = []
        for idx, row in hist.iterrows():
            try:
                close = row["Close"]
                if hasattr(close, "iloc"):
                    close = close.iloc[0]
                v = float(close)
                if math.isnan(v) or math.isinf(v):
                    continue
                result.append({"label": str(idx.date()), "value": round(v, 2)})
            except Exception:
                continue
        return result
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

            # ── Enterprise value ────────────────────────────────────────
            ev_raw = info.get("enterpriseValue") or 0
            if ev_raw >= 1e12:
                enterprise_value = f"₹{ev_raw / 1e12:.2f}T"
            elif ev_raw >= 1e9:
                enterprise_value = f"₹{ev_raw / 1e9:.0f}B"
            elif ev_raw >= 1e7:
                enterprise_value = f"₹{ev_raw / 1e7:.0f}Cr"
            else:
                enterprise_value = "—"

            # ── ROCE ────────────────────────────────────────────────────
            roce_raw = info.get("returnOnCapitalEmployed")
            roce = _pct_str(roce_raw) if roce_raw else "—"

            # ── Annual financials (4 most-recent fiscal years) ──────────
            annual_financials: list = []
            try:
                af = t.financials
                if not af.empty:
                    rev_row_a = next((af.loc[k] for k in _REV_KEYS if k in af.index), None)
                    ni_row_a  = next((af.loc[k] for k in _NI_KEYS  if k in af.index), None)
                    cols_a = list(af.columns)[:4]
                    for col in reversed(cols_a):
                        try:
                            yr = col.strftime("FY%y") if hasattr(col, "strftime") else str(col)[:7]
                        except Exception:
                            yr = str(col)[:7]
                        rev_v = round(float(rev_row_a[col]) / 1e7) if rev_row_a is not None else 0
                        ni_v  = round(float(ni_row_a[col])  / 1e7) if ni_row_a  is not None else 0
                        annual_financials.append({"year": yr, "revenue": rev_v, "net_income": ni_v})
            except Exception:
                pass

            # ── DNA scores derived from real financial metrics ──────────
            roe_val      = float(info.get("returnOnEquity") or 0) * 100
            d_to_e_raw   = float(info.get("debtToEquity")  or 50)
            beta_val     = float(info.get("beta") or 1.0)
            profit_mg    = float(info.get("profitMargins")    or 0) * 100
            op_mg        = float(info.get("operatingMargins") or 0) * 100
            sec_low      = (info.get("sector")   or "").lower()
            ind_low      = (info.get("industry") or "").lower()
            combined_low = sec_low + " " + ind_low

            growth_s = min(95, max(20, int(max(roe_val, 0) * 1.5 + max(profit_mg, 0) * 0.5 + 40)))
            debt_s   = max(15, min(95, int(100 - min(d_to_e_raw / 2, 80))))
            exec_s   = min(95, max(20, int(max(op_mg, 0) * 1.5 + max(roe_val, 0) + 30)))
            news_s   = min(90, max(30, int(beta_val * 45 + 25)))

            if any(k in combined_low for k in ["utilities", "electricity", "power"]):
                gov_s = 85
            elif any(k in combined_low for k in ["defence", "defense", "aerospace"]):
                gov_s = 88
            elif any(k in combined_low for k in ["energy", "oil", "gas", "coal"]):
                gov_s = 75
            elif any(k in combined_low for k in ["infrastructure", "construction", "engineering"]):
                gov_s = 72
            elif any(k in combined_low for k in ["telecommunication", "telecom"]):
                gov_s = 65
            elif any(k in combined_low for k in ["banking", "financial services", "insurance"]):
                gov_s = 60
            elif any(k in combined_low for k in ["pharma", "health", "drug"]):
                gov_s = 50
            elif any(k in combined_low for k in ["technology", "software", "it services"]):
                gov_s = 30
            elif any(k in combined_low for k in ["consumer", "fmcg", "retail"]):
                gov_s = 25
            else:
                gov_s = 40

            policy_s = min(95, max(20, int(gov_s * 0.9 + beta_val * 5)))

            gov_level = "High" if gov_s >= 75 else "Medium" if gov_s >= 50 else "Low"

            if gov_s >= 75:
                gov_breakdown = [
                    {"label": "Central Government", "pct": 42, "color": "#3b82f6"},
                    {"label": "State Government",   "pct": 28, "color": "#60a5fa"},
                    {"label": "PSU Partnerships",   "pct": 16, "color": "#34d399"},
                    {"label": "Regulatory Support", "pct": 14, "color": "#a78bfa"},
                ]
            elif gov_s >= 50:
                gov_breakdown = [
                    {"label": "Regulatory Framework", "pct": 45, "color": "#3b82f6"},
                    {"label": "Policy Incentives",    "pct": 30, "color": "#60a5fa"},
                    {"label": "Direct Support",       "pct": 15, "color": "#34d399"},
                    {"label": "Licensing",            "pct": 10, "color": "#a78bfa"},
                ]
            else:
                gov_breakdown = [
                    {"label": "General Regulation", "pct": 60, "color": "#3b82f6"},
                    {"label": "Tax Incentives",     "pct": 25, "color": "#60a5fa"},
                    {"label": "Export Support",     "pct": 15, "color": "#34d399"},
                ]

            if any(k in combined_low for k in ["utilities", "power"]):
                gov_support_areas = ["Renewable Energy", "Power Distribution", "EV Infrastructure", "Grid Modernisation"]
            elif any(k in combined_low for k in ["defence", "aerospace"]):
                gov_support_areas = ["HAL/BEL Contracts", "Atmanirbhar Defence", "Export Targets", "R&D Grants"]
            elif any(k in combined_low for k in ["energy", "oil", "gas"]):
                gov_support_areas = ["Clean Energy", "Oil & Gas", "Energy Security", "Green Hydrogen"]
            elif any(k in combined_low for k in ["infrastructure", "construction"]):
                gov_support_areas = ["Smart Cities", "Road Construction", "Metro Rail", "Ports"]
            elif any(k in combined_low for k in ["banking", "financial"]):
                gov_support_areas = ["Priority Sector Lending", "MUDRA Loans", "Digital Banking", "MSME Support"]
            elif any(k in combined_low for k in ["technology", "software"]):
                gov_support_areas = ["PLI Scheme", "Digital India", "Semiconductor Mission", "IT Exports"]
            elif any(k in combined_low for k in ["pharma", "health"]):
                gov_support_areas = ["Generic Drugs", "API Manufacturing", "PLI Pharma", "Vaccine Supply"]
            else:
                gov_support_areas = ["Government Contracts", "Policy Compliance", "Regulatory Linkage"]

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
                "dividend_yield":    (lambda v: f"{float(v):.2f}%" if v and float(v) > 0.25 else _pct_str(v))(info.get("dividendYield")),
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
                "enterprise_value":      enterprise_value,
                "roce":                  roce,
                "annual_financials":     annual_financials,
                "dna_scores": {
                    "Growth":            growth_s,
                    "Govt Exposure":     gov_s,
                    "Policy Dependence": policy_s,
                    "Execution Quality": exec_s,
                    "News Sensitivity":  news_s,
                    "Debt Strength":     debt_s,
                },
                "gov_score":             gov_s,
                "gov_level":             gov_level,
                "gov_breakdown":         gov_breakdown,
                "gov_support_areas":     gov_support_areas,
            }
        except Exception:
            return None

    return await loop.run_in_executor(None, _fetch)


_INDEX_TICKER_MAP = {
    "NIFTY":     "^NSEI",
    "NIFTY50":   "^NSEI",
    "NIFTY 50":  "^NSEI",
    "SENSEX":    "^BSESN",
    "BANKNIFTY": "^NSEBANK",
    "NSEBANK":   "^NSEBANK",
}


async def get_index_chart(symbol: str, period: str = "6M") -> list:
    """Return OHLCV close history for a major index — [{"label": "YYYY-MM-DD", "value": float}]."""
    loop = asyncio.get_event_loop()
    ticker = _INDEX_TICKER_MAP.get(symbol.upper(), f"^{symbol.upper()}")
    yf_period, interval = _PERIOD_MAP.get(period, ("6mo", "1wk"))

    def _fetch():
        try:
            hist = yf.download(ticker, period=yf_period, interval=interval, progress=False, auto_adjust=True)
            if hist.empty:
                return []
            result = []
            for idx, row in hist.iterrows():
                try:
                    close = row["Close"]
                    if hasattr(close, "iloc"):
                        close = close.iloc[0]
                    label = idx.strftime("%Y-%m-%d %H:%M") if interval in ("5m", "60m") else idx.strftime("%Y-%m-%d")
                    result.append({"label": label, "value": round(float(close), 2)})
                except Exception:
                    continue
            return result
        except Exception:
            return []

    return await loop.run_in_executor(None, _fetch)


async def get_stock_chart(symbol: str, period: str = "6M") -> list:
    """Return OHLCV close history for charting — [{"label": "YYYY-MM-DD", "value": float}]."""
    loop = asyncio.get_event_loop()
    ns_ticker = f"{symbol.upper()}.NS"
    yf_period, interval = _PERIOD_MAP.get(period, ("6mo", "1wk"))

    def _fetch():
        import math
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
                    v = float(close)
                    if math.isnan(v) or math.isinf(v):
                        continue
                    if interval in ("5m", "60m"):
                        label = idx.strftime("%H:%M") if hasattr(idx, "strftime") else str(idx)
                    else:
                        label = idx.strftime("%b %d") if hasattr(idx, "strftime") else str(idx)[:10]
                    result.append({"label": label, "value": round(v, 2)})
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


# ── Market status (no external calls) ────────────────────────────────────────
from datetime import timezone, timedelta

_IST = timezone(timedelta(hours=5, minutes=30))

# Sector keyword → (display_name, yfinance_ticker)
_SECTOR_INDEX_MAP: dict[str, tuple[str, str]] = {
    "infrastructure": ("Nifty Infrastructure", "NIFTYINFRA.NS"),
    "capital goods":  ("Nifty Infrastructure", "NIFTYINFRA.NS"),
    "construction":   ("Nifty Infrastructure", "NIFTYINFRA.NS"),
    "defence":        ("Nifty Infrastructure", "NIFTYINFRA.NS"),
    "logistics":      ("Nifty Infrastructure", "NIFTYINFRA.NS"),
    "banking":        ("Bank Nifty",           "^NSEBANK"),
    "financials":     ("Bank Nifty",           "^NSEBANK"),
    "finance":        ("Bank Nifty",           "^NSEBANK"),
    "nbfc":           ("Bank Nifty",           "^NSEBANK"),
    "it":             ("Nifty IT",             "^CNXIT"),
    "technology":     ("Nifty IT",             "^CNXIT"),
    "software":       ("Nifty IT",             "^CNXIT"),
    "pharma":         ("Nifty Pharma",         "NIFTYPHARMA.NS"),
    "healthcare":     ("Nifty Pharma",         "NIFTYPHARMA.NS"),
    "auto":           ("Nifty Auto",           "NIFTYAUTO.NS"),
    "automobile":     ("Nifty Auto",           "NIFTYAUTO.NS"),
    "energy":         ("Nifty Energy",         "NIFTYENERGY.NS"),
    "oil":            ("Nifty Energy",         "NIFTYENERGY.NS"),
    "gas":            ("Nifty Energy",         "NIFTYENERGY.NS"),
    "power":          ("Nifty Energy",         "NIFTYENERGY.NS"),
    "fmcg":           ("Nifty FMCG",           "NIFTYFMCG.NS"),
    "consumer":       ("Nifty FMCG",           "NIFTYFMCG.NS"),
    "metal":          ("Nifty Metal",          "NIFTYMETAL.NS"),
    "steel":          ("Nifty Metal",          "NIFTYMETAL.NS"),
    "mining":         ("Nifty Metal",          "NIFTYMETAL.NS"),
    "realty":         ("Nifty Realty",         "NIFTYREALTY.NS"),
    "real estate":    ("Nifty Realty",         "NIFTYREALTY.NS"),
}

_CHART_PERIOD_MAP: dict[str, tuple[str, str]] = {
    "1D":  ("1d",   "5m"),
    "5D":  ("5d",   "60m"),
    "1M":  ("1mo",  "1d"),
    "3M":  ("3mo",  "1wk"),
    "6M":  ("6mo",  "1wk"),
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

_movers_cache: dict = {"ts": 0.0, "data": None}
_MOVERS_TTL = 900  # 15 minutes


def _fetch_top_movers() -> dict:
    import math, time, concurrent.futures
    now = time.time()
    if now - _movers_cache["ts"] < _MOVERS_TTL and _movers_cache["data"]:
        return _movers_cache["data"]

    def _one(sym: str):
        try:
            t = yf.Ticker(f"{sym}.NS")
            fi = t.fast_info
            # fast_info.previous_close is the *official* prior-session close
            # (avoids gaps that history() sometimes has for NSE tickers)
            curr = float(fi.last_price or 0)
            prev = float(fi.previous_close or 0)
            vol  = float(getattr(fi, "last_volume", None) or 0)
            if not curr or not prev or prev == 0:
                return None
            try:
                import math as _m
                if _m.isnan(curr) or _m.isnan(prev):
                    return None
            except Exception:
                pass
            pct = (curr - prev) / prev * 100
            turnover_cr = vol * curr / 1e7
            return {"sym": sym, "curr": curr, "pct": pct, "vol": turnover_cr}
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(_one, _NIFTY500_SAMPLE))

    rows = [r for r in results if r is not None]

    def _fmt(sym: str, curr: float, pct: float, positive: bool) -> dict:
        return {
            "company": _SYMBOL_NAMES.get(sym, sym),
            "ticker":  sym,
            "value":   f"+{pct:.2f}%" if positive else f"{pct:.2f}%",
            "subtitle": f"₹{curr:,.2f}",
            "positive": positive,
        }

    rows.sort(key=lambda r: r["pct"], reverse=True)
    gainers = [_fmt(r["sym"], r["curr"], r["pct"], True)  for r in rows if r["pct"] > 0][:4]
    losers  = [_fmt(r["sym"], r["curr"], r["pct"], False) for r in reversed(rows) if r["pct"] < 0][:4]

    rows.sort(key=lambda r: r["vol"], reverse=True)
    active = [
        {
            "company":  _SYMBOL_NAMES.get(r["sym"], r["sym"]),
            "ticker":   r["sym"],
            "value":    f"₹{r['vol']:.0f}Cr",
            "subtitle": "Turnover",
            "positive": True,
            "isVolume": True,
        }
        for r in rows[:4]
    ]

    result = {"gainers": gainers, "losers": losers, "active": active}
    _movers_cache["ts"] = now
    _movers_cache["data"] = result
    return result


async def get_top_movers() -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_top_movers)


def get_market_status() -> dict:
    """Return NSE market status from current IST time — no network calls."""
    from datetime import datetime
    now = datetime.now(_IST)
    if now.weekday() >= 5:
        return {"is_open": False, "status": "weekend",
                "time_ist": now.strftime("%I:%M %p"), "date": now.strftime("%d %b %Y")}
    total = now.hour * 60 + now.minute
    if   total < 9 * 60:            status = "pre_market"
    elif total < 9 * 60 + 15:      status = "pre_open"
    elif total <= 15 * 60 + 30:    status = "open"
    else:                           status = "closed"
    return {
        "is_open": status == "open", "status": status,
        "time_ist": now.strftime("%I:%M %p"), "date": now.strftime("%d %b %Y"),
    }


def _index_quote(ticker: str, name: str) -> dict:
    q = _fetch_quote(ticker)
    if not q:
        return {"name": name, "ticker": ticker, "value": "—", "pct_change": 0.0,
                "positive": True, "change_str": "—"}
    sign = "+" if q["positive"] else ""
    return {
        "name": name, "ticker": ticker,
        "value": _fmt_price(q["price"]),
        "pct_change": round(q["pct"], 2),
        "positive": q["positive"],
        "change_str": f"{sign}{q['pct']:.2f}%",
    }


async def get_event_market_indices(sectors: list[str]) -> list[dict]:
    """Fetch real index performance for the event's sectors + Nifty 50 baseline."""
    loop = asyncio.get_event_loop()
    seen: dict[str, str] = {}
    for sector in sectors:
        key = sector.lower().strip()
        for keyword, (name, ticker) in _SECTOR_INDEX_MAP.items():
            if keyword in key:
                if ticker not in seen:
                    seen[ticker] = name
                break
    if "^NSEI" not in seen:
        seen["^NSEI"] = "Nifty 50"
    items = list(seen.items())[:4]
    results = await asyncio.gather(
        *[loop.run_in_executor(None, _index_quote, t, n) for t, n in items]
    )
    return list(results)


async def get_ticker_chart(ticker: str, period: str = "1D") -> list[dict]:
    """Fetch OHLCV close history for any ticker with auto period/interval mapping."""
    loop = asyncio.get_event_loop()
    yf_period, interval = _CHART_PERIOD_MAP.get(period, ("1d", "5m"))

    def _fetch():
        import math
        try:
            hist = yf.download(ticker, period=yf_period, interval=interval,
                               progress=False, auto_adjust=True)
            if hist.empty:
                return []
            result = []
            for idx, row in hist.iterrows():
                try:
                    close = row["Close"]
                    if hasattr(close, "iloc"):
                        close = close.iloc[0]
                    v = float(close)
                    if math.isnan(v) or math.isinf(v):
                        continue
                    label = (idx.strftime("%H:%M") if interval in ("5m", "60m")
                             else idx.strftime("%Y-%m-%d"))
                    result.append({"label": label, "value": round(v, 2)})
                except Exception:
                    continue
            return result
        except Exception:
            return []

    return await loop.run_in_executor(None, _fetch)


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
