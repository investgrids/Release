"""
Market Intelligence API — 13 aggregated endpoints for the Market Intelligence page.
Reuses existing service functions; adds futures, global indices, and AI-derived signals.
"""
from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor as _TP, TimeoutError as _TE
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query

# Dedicated thread pool for yfinance calls so they don't share the default
# executor with other I/O work.  result(timeout=9) gives each call a hard cap
# — if Yahoo doesn't respond in 9 s, we return None and serve stale/empty data
# instead of blocking the gunicorn worker indefinitely.
_YF_POOL = _TP(max_workers=6, thread_name_prefix="yf-market")
_YF_TIMEOUT = 9.0


def _yf_run(fn):
    """Run a zero-arg callable in the yfinance pool with a hard timeout."""
    try:
        return _YF_POOL.submit(fn).result(timeout=_YF_TIMEOUT)
    except (_TE, Exception):
        return None

from app.services.market_data import (
    get_premarket_data,
    get_top_movers,
    get_market_status,
    get_extended_indices,
    get_sector_changes,
)

router = APIRouter()
_IST = timezone(timedelta(hours=5, minutes=30))

# ── Simple TTL cache ───────────────────────────────────────────────────────────
_cache: dict[str, tuple[float, object]] = {}


def _cached_sync(key: str, ttl: int, fn):
    now = time.time()
    if key in _cache and now - _cache[key][0] < ttl:
        return _cache[key][1]
    result = fn()
    _cache[key] = (now, result)
    return result


# ── Shared yfinance helpers ────────────────────────────────────────────────────
def _yf_quote(ticker: str) -> dict | None:
    def _inner():
        import yfinance as yf
        fi = yf.Ticker(ticker).fast_info
        price = float(fi.last_price or 0)
        prev  = float(fi.previous_close or 0)
        if not price or not prev:
            return None
        change = price - prev
        pct    = (change / prev) * 100
        return {"price": price, "change": change, "pct": pct, "positive": change >= 0}
    return _yf_run(_inner)


def _yf_mini(ticker: str, period: str = "1d", interval: str = "60m") -> list[dict]:
    def _inner():
        import yfinance as yf, math
        hist = yf.download(ticker, period=period, interval=interval,
                           progress=False, auto_adjust=True, timeout=8)
        if hist.empty:
            return []
        res = []
        for idx, row in hist.iterrows():
            c = row["Close"]
            if hasattr(c, "iloc"):
                c = c.iloc[0]
            v = float(c)
            if math.isnan(v) or math.isinf(v):
                continue
            res.append({"label": idx.strftime("%H:%M"), "value": round(v, 2)})
        return res[-20:]
    return _yf_run(_inner) or []


# ── Pre-market ticker sets ────────────────────────────────────────────────────

def _banknifty_futures_ticker() -> str:
    """Construct the current-month NSE Bank Nifty futures ticker (e.g. BANKNIFTY26JULFUT.NS)."""
    now = datetime.now()
    months = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
    return f"BANKNIFTY{str(now.year)[-2:]}{months[now.month - 1]}FUT.NS"

_US_FUTURES_TICKERS: dict[str, str] = {
    "S&P 500 Fut.":    "ES=F",
    "Nasdaq 100 Fut.": "NQ=F",
    "Dow Futures":     "YM=F",
}

_EUROPEAN_INDICES: dict[str, tuple[str, str]] = {
    "FTSE 100": ("^FTSE",  "🇬🇧"),
    "DAX":      ("^GDAXI", "🇩🇪"),
    "CAC 40":   ("^FCHI",  "🇫🇷"),
}

_CURRENCY_PAIRS: dict[str, tuple[str, str]] = {
    "USD/INR": ("USDINR=X", "💵"),
    "EUR/INR": ("EURINR=X", "💶"),
    "GBP/INR": ("GBPINR=X", "💷"),
}

_ADR_TICKERS: dict[str, dict] = {
    "INFY": {"name": "Infosys",    "nse": "INFY.NS",      "ratio": 1.0},
    "WIT":  {"name": "Wipro",      "nse": "WIPRO.NS",     "ratio": 1.0},
    "HDB":  {"name": "HDFC Bank",  "nse": "HDFCBANK.NS",  "ratio": 3.0},
    "IBN":  {"name": "ICICI Bank", "nse": "ICICIBANK.NS", "ratio": 2.0},
}

_GLOBAL_INDICES = {
    "Dow Jones":          ("^DJI",      "🇺🇸"),
    "S&P 500":            ("^GSPC",     "🇺🇸"),
    "Nasdaq":             ("^IXIC",     "🇺🇸"),
    "FTSE 100":           ("^FTSE",     "🇬🇧"),
    "DAX":                ("^GDAXI",    "🇩🇪"),
    "CAC 40":             ("^FCHI",     "🇫🇷"),
    "Nikkei 225":         ("^N225",     "🇯🇵"),
    "Hang Seng":          ("^HSI",      "🇭🇰"),
    "Shanghai Composite": ("000001.SS", "🇨🇳"),
    "KOSPI":              ("^KS11",     "🇰🇷"),
}


def _quote_row(name: str, ticker: str, prefix: str = "") -> dict:
    q = _yf_quote(ticker)
    if not q:
        return {"name": name, "ticker": ticker, "value": "—",
                "change": "—", "pct": "—", "change_str": "—", "positive": True, "chart": []}
    sign = "+" if q["positive"] else ""
    val  = f"{prefix}{q['price']:,.2f}" if prefix else f"{q['price']:,.2f}"
    change_str = f"{sign}{q['pct']:.2f}%"
    return {
        "name":       name,
        "ticker":     ticker,
        "value":      val,
        "price_raw":  round(q["price"], 2),
        "change":     f"{sign}{q['change']:,.2f}",
        "change_str": change_str,
        "pct":        change_str,
        "positive":   q["positive"],
        "chart":      [],
    }


def _quote_row_with_chart(name: str, ticker: str, prefix: str = "") -> dict:
    row = _quote_row(name, ticker, prefix)
    row["chart"] = _yf_mini(ticker, "5d", "60m")[-12:]
    return row


def _fetch_fii_dii() -> dict:
    """Fetch previous session FII/DII net flow from NSE India. Cached 6 hours."""
    try:
        import requests
        session = requests.Session()
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        hdrs_html = {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml,*/*;q=0.9", "Accept-Language": "en-US,en;q=0.9"}
        hdrs_json = {"User-Agent": ua, "Accept": "application/json, text/plain, */*", "Referer": "https://www.nseindia.com/", "Accept-Language": "en-US,en;q=0.9"}
        session.get("https://www.nseindia.com/", headers=hdrs_html, timeout=6)
        r = session.get("https://www.nseindia.com/api/fiidiiTradeReact", headers=hdrs_json, timeout=8)
        if r.ok:
            data = r.json()
            if not isinstance(data, list):
                raise ValueError("unexpected format")
            def _clean(v):
                try:
                    return round(float(str(v).replace(",", "")), 2)
                except Exception:
                    return 0.0
            fii = next((d for d in data if "FII" in str(d.get("category", "")).upper()), None)
            dii = next((d for d in data if d.get("category", "").upper().startswith("DII")), None)
            if fii or dii:
                fii_net = _clean(fii.get("netValue", 0)) if fii else 0.0
                dii_net = _clean(dii.get("netValue", 0)) if dii else 0.0
                return {
                    "available": True,
                    "fii_net":  fii_net,
                    "dii_net":  dii_net,
                    "fii_buy":  _clean(fii.get("buyValue",  0)) if fii else 0.0,
                    "fii_sell": _clean(fii.get("sellValue", 0)) if fii else 0.0,
                    "dii_buy":  _clean(dii.get("buyValue",  0)) if dii else 0.0,
                    "dii_sell": _clean(dii.get("sellValue", 0)) if dii else 0.0,
                    "note": "Previous session (₹Cr)",
                }
    except Exception:
        pass
    return {"available": False, "fii_net": None, "dii_net": None, "note": "NSE data unavailable"}


def _fetch_pcr_data() -> dict:
    """Fetch Nifty Put-Call Ratio + Max Pain from NSE option chain. Cached 15 min."""
    try:
        import requests
        session = requests.Session()
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        hdrs_html = {"User-Agent": ua, "Accept": "text/html,*/*"}
        hdrs_json = {"User-Agent": ua, "Accept": "application/json, text/plain, */*", "Referer": "https://www.nseindia.com/"}
        session.get("https://www.nseindia.com/", headers=hdrs_html, timeout=6)
        r = session.get(
            "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY",
            headers=hdrs_json, timeout=10,
        )
        if r.ok:
            oc = r.json()
            records = oc.get("records", {}).get("data", [])
            total_put_oi = 0
            total_call_oi = 0
            oi_by_strike: dict[float, dict] = {}
            for row in records:
                strike = float(row.get("strikePrice", 0))
                ce_oi  = int(row.get("CE", {}).get("openInterest", 0) or 0)
                pe_oi  = int(row.get("PE", {}).get("openInterest", 0) or 0)
                total_call_oi += ce_oi
                total_put_oi  += pe_oi
                oi_by_strike[strike] = {"ce": ce_oi, "pe": pe_oi}
            if total_call_oi > 0:
                pcr = round(total_put_oi / total_call_oi, 2)
                max_pain = None
                if oi_by_strike:
                    def _total_loss(target: float) -> float:
                        loss = 0.0
                        for s, oi in oi_by_strike.items():
                            if s > target:
                                loss += oi["ce"] * (s - target)
                            elif s < target:
                                loss += oi["pe"] * (target - s)
                        return loss
                    max_pain = int(min(oi_by_strike.keys(), key=_total_loss))
                if pcr >= 1.4:
                    label, color = "Very Bullish", "emerald"
                elif pcr >= 1.2:
                    label, color = "Bullish", "emerald"
                elif pcr >= 0.9:
                    label, color = "Neutral", "amber"
                elif pcr >= 0.7:
                    label, color = "Bearish", "orange"
                else:
                    label, color = "Very Bearish", "rose"
                return {"available": True, "pcr": pcr, "max_pain": max_pain, "label": label, "color": color}
    except Exception:
        pass
    return {"available": False, "pcr": None, "max_pain": None, "label": None, "color": "slate"}


def _gift_nifty_row() -> dict:
    """Real GIFT Nifty (NSE IX, GIFT City) via the shared adapter
    (app/services/gift_nifty_service.py) — Phase 5B. Replaces the old
    domestic-futures-ticker-mislabeled-as-GIFT-Nifty approach. Status is
    always honest: "unavailable" never gets silently backfilled with
    spot. Both this endpoint and opening_prediction_service.py's
    primary signal path read this same dict — they share it through
    _fetch_enhanced_premarket's own TTL cache, so they can never
    disagree about what GIFT Nifty is doing right now."""
    from app.services.gift_nifty_service import get_gift_nifty_sync

    spot_q  = _yf_quote("^NSEI")
    spot_px = spot_q["price"] if spot_q else None
    result  = get_gift_nifty_sync(spot_price=spot_px)

    row: dict = {
        "name": "GIFT Nifty", "ticker": "GIFT_NIFTY_NSEIX",
        "status": result.status, "is_spot": False, "chart": [],
    }
    if spot_px:
        row["spot_value"] = f"{spot_px:,.2f}"

    if result.status == "unavailable" or result.price is None:
        row.update({
            "value": "—", "change": "—", "change_str": "—", "pct": "—",
            "positive": True, "premium_pct": None,
            "note": "GIFT Nifty unavailable" + (f" ({result.reason})" if result.reason else ""),
        })
        return row

    sign       = "+" if (result.change or 0) >= 0 else ""
    change_str = f"{sign}{result.change_pct:.2f}%" if result.change_pct is not None else "—"
    row.update({
        "value":      f"{result.price:,.2f}",
        "price_raw":  round(result.price, 2),
        "change":     f"{sign}{result.change:,.2f}" if result.change is not None else "—",
        "change_str": change_str,
        "pct":        change_str,
        "positive":   (result.change or 0) >= 0,
        "note":       "Real GIFT Nifty (NSE IX)" if result.status == "live" else "GIFT Nifty — data is a few hours old, treat cautiously",
        "expiry":            result.expiry.isoformat() if result.expiry else None,
        "source_timestamp":  result.source_timestamp.isoformat() if result.source_timestamp else None,
        "premium_pct": None,
    })
    if result.premium_points is not None:
        s = "+" if result.premium_points >= 0 else ""
        row["premium_pct"] = f"{s}{result.premium_pct:.2f}%"
        row["is_premium"]  = result.premium_points >= 0
    return row


def _fetch_enhanced_premarket() -> dict:
    """Build rich pre-market snapshot (sync, runs in executor, cached 15 min)."""
    # 1. GIFT Nifty — real NSE IX data, never relabeled from spot.
    gift = _gift_nifty_row()

    # 2. Bank Nifty Futures
    bnf_ticker = _banknifty_futures_ticker()
    banknifty = _quote_row_with_chart("Bank Nifty Fut.", bnf_ticker)
    if banknifty["value"] == "—":
        banknifty = _quote_row("Bank Nifty (Spot)", "^NSEBANK")
        banknifty["chart"] = _yf_mini("^NSEBANK", "5d", "60m")[-12:]
        banknifty["note"]  = "Spot price (futures unavailable)"
    else:
        bnspot_q = _yf_quote("^NSEBANK")
        if bnspot_q and bnspot_q["price"]:
            fut_px  = banknifty.get("price_raw", 0)
            spot_px = bnspot_q["price"]
            prem    = ((fut_px - spot_px) / spot_px) * 100
            s       = "+" if prem >= 0 else ""
            banknifty["premium_pct"] = f"{s}{prem:.2f}%"
            banknifty["is_premium"]  = prem >= 0
            banknifty["spot_value"]  = f"{spot_px:,.2f}"
        banknifty["note"] = "NSE near-month contract"

    # 3. India VIX
    vix = _quote_row_with_chart("India VIX", "^INDIAVIX")
    vix_val_float = 15.0
    if vix["value"] != "—":
        try:
            vix_val_float = float(vix["value"].replace(",", ""))
        except Exception:
            pass
        if vix_val_float < 12:
            vix.update({"level": "very_low",  "level_label": "VERY LOW",  "color": "emerald",
                         "interpretation": "Extreme market calm — stable open"})
        elif vix_val_float < 15:
            vix.update({"level": "low",        "level_label": "LOW",        "color": "emerald",
                         "interpretation": "Low volatility — stable open expected"})
        elif vix_val_float < 20:
            vix.update({"level": "moderate",   "level_label": "MODERATE",   "color": "amber",
                         "interpretation": "Moderate volatility — stay selective"})
        elif vix_val_float < 25:
            vix.update({"level": "elevated",   "level_label": "ELEVATED",   "color": "orange",
                         "interpretation": "Elevated risk — trade with caution"})
        else:
            vix.update({"level": "high",       "level_label": "HIGH",       "color": "rose",
                         "interpretation": "High volatility — defensive stance"})
    else:
        vix.update({"level": "unknown", "level_label": "N/A", "color": "slate",
                     "interpretation": "Data currently unavailable"})

    # Compute opening range based on Nifty Futures + VIX
    if gift.get("price_raw") and gift["value"] != "—":
        if vix_val_float < 12:    band = 0.10
        elif vix_val_float < 15:  band = 0.15
        elif vix_val_float < 20:  band = 0.20
        else:                     band = 0.30
        fut_px = gift["price_raw"]
        gift["opening_range"] = {
            "low":      f"{fut_px * (1 - band / 100):,.2f}",
            "high":     f"{fut_px * (1 + band / 100):,.2f}",
            "band_pct": band,
        }

    # 4. US Futures (with sparklines)
    us_futures = [_quote_row_with_chart(n, t) for n, t in _US_FUTURES_TICKERS.items()]

    # 5. European markets
    european: list[dict] = []
    for name, (ticker, flag) in _EUROPEAN_INDICES.items():
        row = _quote_row(name, ticker)
        row["flag"]  = flag
        row["chart"] = []
        european.append(row)

    # 6. Currency pairs
    currencies: list[dict] = []
    usd_rate = 84.0
    for name, (ticker, icon) in _CURRENCY_PAIRS.items():
        row = _quote_row(name, ticker)
        row["icon"]  = icon
        row["chart"] = []
        currencies.append(row)
        if name == "USD/INR" and row.get("price_raw"):
            usd_rate = row["price_raw"]

    # 7. Indian ADRs (NYSE/NASDAQ-listed) with premium vs NSE price
    adrs: list[dict] = []
    for adr_sym, meta in _ADR_TICKERS.items():
        adr_q = _yf_quote(adr_sym)
        nse_q = _yf_quote(meta["nse"])
        if adr_q:
            s = "+" if adr_q["positive"] else ""
            entry: dict = {
                "ticker":   adr_sym,
                "name":     meta["name"],
                "adr_price": f"${adr_q['price']:.2f}",
                "pct":       f"{s}{adr_q['pct']:.2f}%",
                "positive":  adr_q["positive"],
                "nse_price": "—",
                "premium_pct": "—",
                "premium_positive": True,
            }
            if nse_q and nse_q["price"]:
                adr_inr  = adr_q["price"] * usd_rate / meta["ratio"]
                prem     = (adr_inr - nse_q["price"]) / nse_q["price"] * 100
                ps       = "+" if prem >= 0 else ""
                entry["nse_price"]       = f"₹{nse_q['price']:,.2f}"
                entry["premium_pct"]     = f"{ps}{prem:.1f}%"
                entry["premium_positive"] = prem >= 0
            adrs.append(entry)

    return {
        "gift_nifty":       gift,
        "banknifty":        banknifty,
        "india_vix":        vix,
        "us_futures":       us_futures,
        "european":         european,
        "currencies":       currencies,
        "adrs":             adrs,
    }


def _fetch_global_indices() -> list[dict]:
    result = []
    for name, (ticker, flag) in _GLOBAL_INDICES.items():
        q = _yf_quote(ticker)
        if q:
            sign = "+" if q["positive"] else ""
            result.append({
                "name":     name,
                "flag":     flag,
                "value":    f"{q['price']:,.2f}",
                "pct":      f"{sign}{q['pct']:.2f}%",
                "positive": q["positive"],
            })
        else:
            result.append({"name": name, "flag": flag, "value": "—", "pct": "—", "positive": True})
    return result


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/session")
async def market_session():
    now   = datetime.now(_IST)
    total = now.hour * 60 + now.minute
    dow   = now.weekday()

    if dow >= 5:
        session = "weekend"
    elif total < 9 * 60:
        session = "pre_market"
    elif total < 9 * 60 + 15:
        session = "pre_open"
    elif total <= 15 * 60 + 30:
        session = "open"
    else:
        session = "after_market"

    if session in ("pre_market", "pre_open"):
        active_tab = "pre-market"
        open_at    = 9 * 60 + 15
        countdown  = max(0, (open_at - total) * 60)
    elif session == "open":
        active_tab = "live-market"
        close_at   = 15 * 60 + 30
        countdown  = max(0, (close_at - total) * 60)
    elif session == "after_market":
        active_tab = "after-market"
        countdown  = None
    else:
        active_tab = "overview"
        countdown  = None

    return {
        "session":           session,
        "active_tab":        active_tab,
        "is_open":           session == "open",
        "time_ist":          now.strftime("%I:%M %p"),
        "date":              now.strftime("%d %b %Y"),
        "countdown_seconds": countdown,
    }


_overview_cache: dict = {"ts": 0.0, "data": None}
_OVERVIEW_TTL = 300  # 5 minutes


@router.get("/overview")
async def market_overview():
    now = time.time()
    if _overview_cache["data"] and now - _overview_cache["ts"] < _OVERVIEW_TTL:
        return _overview_cache["data"]

    indices, sectors, movers = await asyncio.gather(
        get_extended_indices(),
        get_sector_changes(),
        get_top_movers(),
    )
    status = get_market_status()
    pos_idx = sum(1 for i in indices if i.get("positive"))
    sentiment_score = min(90, max(20, int(50 + (pos_idx / max(len(indices), 1) - 0.5) * 80)))
    # Real breadth derived from the movers sample — previously a hardcoded
    # {1124, 387, 89, 47, 12} identical to /live's own placeholder,
    # unchanging regardless of actual market conditions (this is the
    # response After Market's Advances/Declines cards ultimately read via
    # initialData, so the frontend "—" users saw traced back to this).
    sample_pos = movers.get("advancing_count", len(movers.get("gainers", [])))
    sample_neg = movers.get("declining_count", len(movers.get("losers", [])))
    sample_total = max(sample_pos + sample_neg, 1)
    est_advances = round(sample_pos / sample_total * 1200)
    est_declines = round(sample_neg / sample_total * 1200)
    result = {
        "status":   status,
        "indices":  indices[:6],
        "sectors":  sectors,
        "movers":   movers,
        "sentiment_score": sentiment_score,
        "breadth":  {
            "advances": est_advances, "declines": est_declines,
            "unchanged": max(0, 1500 - est_advances - est_declines),
            "high52w": None, "low52w": None,
            "note": "Estimated from Nifty 500 sample",
        },
    }
    _overview_cache["ts"]   = now
    _overview_cache["data"] = result
    return result


@router.get("/premarket")
async def market_premarket():
    loop = asyncio.get_event_loop()
    base, enhanced, movers, fii_dii, pcr = await asyncio.gather(
        get_premarket_data(),
        loop.run_in_executor(None, lambda: _cached_sync("pm_enh",    900,   _fetch_enhanced_premarket)),
        get_top_movers(),
        loop.run_in_executor(None, lambda: _cached_sync("fii_dii",   21600, _fetch_fii_dii)),
        loop.run_in_executor(None, lambda: _cached_sync("pcr_nifty", 900,   _fetch_pcr_data)),
    )

    asian = base.get("asian", [])
    us    = base.get("us",    [])
    comms = base.get("commodities", [])

    # Derive sentiment from real data
    all_pos = asian + us + enhanced["us_futures"] + enhanced["european"]
    pos_count = sum(1 for m in all_pos if m.get("positive"))
    total = len(all_pos) or 1
    bull  = max(30, min(80, int(pos_count / total * 100)))
    bear  = max(5,  min(40, 100 - bull - 15))
    neut  = 100 - bull - bear
    conf  = min(92, int(pos_count / total * 65 + 48))
    sent  = "Bullish" if bull >= 60 else "Neutral" if bull >= 45 else "Bearish"

    # Global sentiment score 0-100
    global_sentiment_score = min(95, max(10, int(pos_count / total * 100)))

    # Build dynamic AI reasons from actual live data
    reasons: list[str] = []
    gift = enhanced["gift_nifty"]
    vix  = enhanced["india_vix"]

    if gift["value"] != "—":
        direction = "positive" if gift.get("positive") else "negative"
        prem_note = f" ({gift['premium_pct']} vs spot)" if gift.get("premium_pct") else ""
        stale_note = " [stale]" if gift.get("status") == "stale" else ""
        reasons.append(f"GIFT Nifty trading {direction} at {gift['value']}{prem_note}{stale_note}")

    bnf = enhanced.get("banknifty", {})
    if bnf.get("value") and bnf["value"] != "—":
        word = "up" if bnf.get("positive") else "down"
        reasons.append(f"Bank Nifty Futures {word} at {bnf['value']} ({bnf.get('pct', '—')})")

    if vix["value"] != "—":
        reasons.append(f"India VIX at {vix['value']} — {vix.get('interpretation', '')}")

    sp = next((f for f in enhanced["us_futures"] if "S&P" in f["name"]), None)
    if sp and sp["value"] != "—":
        word = "rallied" if sp.get("positive") else "fell"
        reasons.append(f"S&P 500 Futures {word} to {sp['value']} ({sp['pct']})")

    nq = next((f for f in enhanced["us_futures"] if "Nasdaq" in f["name"]), None)
    if nq and nq["value"] != "—":
        word = "positive" if nq.get("positive") else "under pressure"
        reasons.append(f"Nasdaq 100 Futures {word} at {nq['value']}")

    usd = next((c for c in enhanced["currencies"] if "USD" in c["name"]), None)
    if usd and usd["value"] != "—":
        rupee = "Rupee weakening — watch import costs" if usd.get("positive") else "Rupee holding firm"
        reasons.append(f"USD/INR at {usd['value']} — {rupee}")

    crude = next((c for c in comms if "Brent" in c["name"]), None)
    if crude and crude["value"] != "—":
        reasons.append(f"Brent crude at {crude['value']} ({crude.get('change_str', '—')})")

    if fii_dii.get("available") and fii_dii.get("fii_net") is not None:
        fii_n = fii_dii["fii_net"]
        s = "+" if fii_n >= 0 else ""
        reasons.append(f"FII previous session: {s}₹{fii_n:,.0f}Cr — {'buying' if fii_n >= 0 else 'selling'}")

    if not reasons:
        reasons = ["Global markets showing mixed signals", "Monitor NSE opening session closely"]

    strat = (
        "Gap-up expected. Look for dip-buying in banking and infra. Watch Nifty resistance levels."
        if sent == "Bullish" else
        "Cautious open likely. Wait for price confirmation before entering. Consider hedging."
        if sent == "Bearish" else
        "Flat to mild open. Prefer quality large-caps over momentum. Avoid aggressive bets."
    )

    # Stocks to watch: real top movers (not hardcoded)
    gainers = movers.get("gainers", [])[:3]
    losers  = movers.get("losers",  [])[:2]
    watch: list[dict] = []
    for g in gainers:
        try:
            pct_v = abs(float(g.get("value", "0%").replace("+", "").replace("%", "")))
        except Exception:
            pct_v = 1.0
        watch.append({
            "ticker": g["ticker"], "name": g.get("company", g["ticker"]),
            "reason": f"Top pre-market gainer · {g.get('value', '—')}",
            "score":  min(95, 65 + int(pct_v * 3)), "direction": "up", "sector": "Market",
        })
    for l in losers:
        try:
            pct_v = abs(float(l.get("value", "0%").replace("-", "").replace("%", "")))
        except Exception:
            pct_v = 1.0
        watch.append({
            "ticker": l["ticker"], "name": l.get("company", l["ticker"]),
            "reason": f"Under pressure · {l.get('value', '—')}",
            "score":  min(80, 55 + int(pct_v * 3)), "direction": "down", "sector": "Market",
        })

    if not watch:
        watch = [
            {"ticker": "LT",        "name": "Larsen & Toubro",   "reason": "Infrastructure momentum", "score": 89, "direction": "up",     "sector": "Infrastructure"},
            {"ticker": "HDFCBANK",  "name": "HDFC Bank",          "reason": "Banking sector leader",   "score": 85, "direction": "up",     "sector": "Banking"},
            {"ticker": "RELIANCE",  "name": "Reliance Industries", "reason": "Broad market bellwether", "score": 82, "direction": "up",     "sector": "Conglomerate"},
            {"ticker": "ICICIBANK", "name": "ICICI Bank",          "reason": "Loan growth strong",      "score": 78, "direction": "up",     "sector": "Banking"},
            {"ticker": "POWERGRID", "name": "Power Grid Corp",     "reason": "Regulatory tailwinds",    "score": 75, "direction": "stable", "sector": "Utilities"},
        ]

    # Real market breadth derived from movers sample
    all_rows = movers.get("gainers", []) + movers.get("losers", []) + movers.get("active", [])
    sample_pos = movers.get("advancing_count", len(movers.get("gainers", [])))
    sample_neg = movers.get("declining_count", len(movers.get("losers", [])))
    sample_total = max(sample_pos + sample_neg, 1)
    est_advances = round(sample_pos / sample_total * 1200)
    est_declines = round(sample_neg / sample_total * 1200)
    est_unchanged = max(0, 1500 - est_advances - est_declines)

    return {
        "gift_nifty":           enhanced["gift_nifty"],
        "banknifty_futures":    enhanced.get("banknifty"),
        "india_vix":            enhanced["india_vix"],
        "us_futures":           enhanced["us_futures"],
        "european":             enhanced["european"],
        "currencies":           enhanced["currencies"],
        "adrs":                 enhanced.get("adrs", []),
        "asian":                asian,
        "us":                   us,
        "commodities":          comms,
        "fii_dii":              fii_dii,
        "pcr":                  pcr,
        "global_sentiment_score": global_sentiment_score,
        "market_breadth": {
            "advances":  est_advances,
            "declines":  est_declines,
            "unchanged": est_unchanged,
            "note":      "Estimated from Nifty 500 sample",
        },
        "ai_prediction": {
            "sentiment":        sent,
            "bull_pct":         bull,
            "neutral_pct":      neut,
            "bear_pct":         bear,
            "confidence":       conf,
            "reasons":          reasons[:6],
            "opening_strategy": strat,
        },
        "stocks_to_watch": watch,
        # Legacy backward-compat fields
        "futures":           [enhanced["gift_nifty"]] + enhanced["us_futures"],
        "extra_commodities": comms,
    }


@router.get("/live")
async def market_live():
    indices, sectors, movers = await asyncio.gather(
        get_extended_indices(),
        get_sector_changes(),
        get_top_movers(),
    )
    # Real breadth derived from the movers sample — this was previously a
    # hardcoded {1124, 387, 89, 47, 12} that never changed regardless of
    # actual market conditions (same copy-pasted placeholder found in
    # /overview below). high52w/low52w/volume_cr have no real source
    # available here, so they're now honestly None rather than static
    # fake numbers alongside a real advances/declines figure.
    sample_pos = movers.get("advancing_count", len(movers.get("gainers", [])))
    sample_neg = movers.get("declining_count", len(movers.get("losers", [])))
    sample_total = max(sample_pos + sample_neg, 1)
    est_advances = round(sample_pos / sample_total * 1200)
    est_declines = round(sample_neg / sample_total * 1200)
    return {
        "indices": indices,
        "sectors": sectors,
        "movers":  movers,
        "breadth": {
            "advances": est_advances, "declines": est_declines,
            "unchanged": max(0, 1500 - est_advances - est_declines),
            "high52w": None, "low52w": None, "volume_cr": None,
            "note": "Estimated from Nifty 500 sample",
        },
    }


@router.get("/after-market")
async def market_after_market():
    indices, movers, sectors = await asyncio.gather(
        get_extended_indices(),
        get_top_movers(),
        get_sector_changes(),
    )
    nifty  = next((i for i in indices if "NIFTY 50" in i["name"]), {})
    sensex = next((i for i in indices if "SENSEX"   in i["name"]), {})

    # Real market breadth derived from the movers sample — same approach
    # already used by the premarket endpoint. Previously this response had
    # no breadth field at all, so the frontend's Advances/Declines cards
    # always rendered "—" regardless of real market conditions.
    sample_pos = movers.get("advancing_count", len(movers.get("gainers", [])))
    sample_neg = movers.get("declining_count", len(movers.get("losers", [])))
    sample_total = max(sample_pos + sample_neg, 1)
    est_advances = round(sample_pos / sample_total * 1200)
    est_declines = round(sample_neg / sample_total * 1200)

    return {
        "closing": {
            "nifty":          nifty.get("value", "—"),
            "sensex":         sensex.get("value","—"),
            "nifty_change":   nifty.get("change","—"),
            "sensex_change":  sensex.get("change","—"),
            "nifty_positive": nifty.get("positive", True),
            "sensex_positive":sensex.get("positive",True),
        },
        "sectors":  sectors,
        "gainers":  movers.get("gainers", []),
        "losers":   movers.get("losers",  []),
        "breadth": {
            "advances":  est_advances,
            "declines":  est_declines,
            "unchanged": max(0, 1500 - est_advances - est_declines),
            "note":      "Estimated from Nifty 500 sample",
        },
        # tomorrow_watchlist / ai_summary intentionally removed — both were
        # hardcoded placeholder content the frontend never actually reads
        # (it builds a real watchlist from live event data and a real
        # summary from the shared market-story service instead).
    }


@router.get("/global")
async def market_global():
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        None, lambda: _cached_sync("global_idx", 900, _fetch_global_indices)
    )
    return {"indices": data}


@router.get("/calendar")
async def market_calendar_endpoint():
    from app.db.session import AsyncSessionLocal
    from app.db.crud import get_calendar
    try:
        async with AsyncSessionLocal() as db:
            rows = await get_calendar(db)
            return {"events": [
                {"id": r.id, "category": r.category, "title": r.title,
                 "date": r.date, "description": r.description}
                for r in rows
            ]}
    except Exception:
        return {"events": []}


@router.get("/top-movers")
async def market_top_movers():
    return await get_top_movers()


@router.get("/heatmap")
async def market_heatmap():
    sectors = await get_sector_changes()
    return {"sectors": sectors}


@router.get("/news")
async def market_news(limit: int = Query(10, le=30)):
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.db.models_legacy import NewsArticle
    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(NewsArticle).order_by(NewsArticle.created_at.desc()).limit(limit)
            )).scalars().all()
            return {"news": [
                {"id": str(r.id), "headline": r.headline, "summary": r.summary,
                 "source": r.source, "published_at": r.published_at,
                 "impact_score": round(r.impact_score or 0),
                 "companies": r.companies or []}
                for r in rows
            ]}
    except Exception:
        return {"news": []}


@router.get("/events")
async def market_events(limit: int = Query(10, le=30)):
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.db.models_legacy import Event
    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(Event).order_by(Event.impact_score.desc()).limit(limit)
            )).scalars().all()
            return {"events": [
                {"id": str(r.id), "title": r.title, "summary": r.summary or "",
                 "impact_score": round(r.impact_score or 0),
                 "confidence": round(r.confidence or 0),
                 "category": r.category or "Macro",
                 "sectors": r.sectors or [],
                 "companies": r.companies or [],
                 "published_at": r.published_at.isoformat() if r.published_at else None}
                for r in rows
            ]}
    except Exception:
        return {"events": []}


@router.get("/opportunities")
async def market_opportunities(limit: int = Query(6, le=20)):
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.db.models_legacy import RadarOpportunity
    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(RadarOpportunity).order_by(RadarOpportunity.score.desc()).limit(limit)
            )).scalars().all()
            return {"opportunities": [
                {"id": str(r.id), "theme": r.theme,
                 "score": r.score, "confidence": round(r.confidence or 0),
                 "reason": r.reason or "",
                 "beneficiaries": r.beneficiaries or []}
                for r in rows
            ]}
    except Exception:
        return {"opportunities": []}


@router.get("/opening-prediction")
async def market_opening_prediction():
    """Tomorrow's Nifty opening prediction — 5-layer AI analysis with 30-min
    cache. Phase 1C: also loads Weekend Intelligence context for the
    session this prediction targets (tomorrow, IST) when a valid one
    exists — additive only, see opening_prediction_service's module
    docstring. This is the ONE call site wired to weekend context in
    Phase 1C (daily_brief_intelligence.py and fact_registry.py's calls
    to build_opening_prediction are deliberately left unchanged — see
    final report §D for why)."""
    from app.db.session import AsyncSessionLocal
    from app.services.opening_prediction_service import build_opening_prediction
    from app.services.weekend_intelligence.context import get_weekend_context_for_session
    from app.services.weekend_intelligence.session_resolution import resolve_opening_prediction_session
    try:
        async with AsyncSessionLocal() as db:
            weekend_context = None
            try:
                # Phase 1C fix: the session Weekend Intelligence context
                # is looked up for is NOT the same thing as
                # opening_prediction_service's own "tomorrow" event-layer
                # bucketing (_ist_tomorrow, still used internally by
                # _gather_events — untouched) — resolve_opening_prediction_session
                # answers "which trading session is being predicted right
                # now" (Sat/Sun -> Monday; a weekday before close -> that
                # day; after close -> the next weekday), which is what
                # actually needs to match snapshot.target_trading_date.
                prediction_session = resolve_opening_prediction_session()
                weekend_context = await get_weekend_context_for_session(db, prediction_session)
            except Exception as wexc:
                import structlog
                structlog.get_logger(__name__).warning("opening_prediction.weekend_context_load_error", error=str(wexc))

            result = await build_opening_prediction(db, weekend_context)

            if weekend_context is not None and weekend_context.status != "insufficient_evidence":
                try:
                    from app.services.weekend_intelligence.prediction_recording import (
                        record_weekend_intelligence_predictions,
                    )
                    await record_weekend_intelligence_predictions(weekend_context)
                except Exception as rexc:
                    import structlog
                    structlog.get_logger(__name__).warning("opening_prediction.weekend_recording_error", error=str(rexc))

            return result
    except Exception as exc:
        import structlog
        structlog.get_logger(__name__).warning("opening_prediction.endpoint_error", error=str(exc))
        return {
            "signals":    {},
            "events":     {"today": [], "tomorrow": [], "mie_signals": []},
            "historical": {"similar_events": [], "count": 0, "avg_nifty_1d": None},
            "prediction": {
                "direction": "Neutral", "confidence": 55,
                "range_low": -15, "range_high": 25,
                "primary_drivers": ["Data unavailable"],
                "risks": ["Check backend logs"],
                "conflicting_signals": [],
                "reasoning": "Prediction service encountered an error.",
                "historical_note": None,
                "uncertainty_note": "AI layer unavailable.",
                "ai_generated": False,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
        }


@router.get("/insights")
async def market_insights():
    movers = await get_top_movers()
    g = len(movers.get("gainers", []))
    conf = min(95, 55 + g * 8)
    return {
        "confidence": conf,
        "fear_greed": min(90, max(20, conf + 8)),
        "sentiment":  "Bullish" if conf >= 65 else "Neutral" if conf >= 45 else "Bearish",
        "summary": "Markets showing bullish momentum with institutional buying. Key support at Nifty 24,500.",
        "key_themes": ["Infrastructure Push", "Banking Strength", "FII Inflows", "IT Sector Pressure"],
        "risks": ["Global rate uncertainty", "Crude oil volatility", "INR depreciation"],
    }
