"""
Finnhub.io API client — free tier (60 req/min).
NSE symbols use NSE: prefix  →  NSE:RELIANCE, NSE:TCS, etc.
"""
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.core.config import settings

_BASE  = "https://finnhub.io/api/v1"
_cache: dict = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nse(symbol: str) -> str:
    s = symbol.upper().strip()
    return s if s.startswith("NSE:") else f"NSE:{s}"


def _cached(key: str, ttl: int) -> Optional[object]:
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < ttl:
        return entry["data"]
    return None


def _store(key: str, data) -> None:
    _cache[key] = {"ts": time.time(), "data": data}


def _time_ago(ts: float) -> str:
    diff = max(0, time.time() - float(ts or 0))
    if diff < 3600:
        return f"{int(diff // 60)}m ago"
    if diff < 86400:
        return f"{int(diff // 3600)}h ago"
    return f"{int(diff // 86400)}d ago"


async def _get(path: str, params: dict) -> Optional[object]:
    params["token"] = settings.finnhub_api_key
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{_BASE}{path}", params=params)
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

async def get_quote(symbol: str) -> Optional[dict]:
    """
    Real-time quote.
    Returns: {c, d, dp, h, l, o, pc, t}
      c=current  d=change  dp=%change  h=high  l=low  o=open  pc=prev_close
    """
    key = f"q:{symbol}"
    hit = _cached(key, 30)       # 30-second cache for live price
    if hit is not None:
        return hit
    data = await _get("/quote", {"symbol": _nse(symbol)})
    if data and data.get("c"):
        _store(key, data)
    return data


async def get_peers(symbol: str) -> list[str]:
    """
    Live peer list. Returns bare NSE symbols (no NSE: prefix).
    """
    key = f"peers:{symbol}"
    hit = _cached(key, 3600)     # 1-hour cache
    if hit is not None:
        return hit
    data = await _get("/stock/peers", {"symbol": _nse(symbol)})
    if not isinstance(data, list):
        return []
    peers = [
        p.replace("NSE:", "")
        for p in data
        if isinstance(p, str) and p.startswith("NSE:") and p != _nse(symbol)
    ][:5]
    _store(key, peers)
    return peers


async def get_recommendation(symbol: str) -> Optional[dict]:
    """
    Most recent analyst recommendation.
    Returns: {buy, hold, sell, strongBuy, strongSell, period, symbol}
    """
    key = f"rec:{symbol}"
    hit = _cached(key, 3600)
    if hit is not None:
        return hit
    data = await _get("/stock/recommendation", {"symbol": _nse(symbol)})
    if isinstance(data, list) and data:
        result = data[0]
        _store(key, result)
        return result
    return None


async def get_price_target(symbol: str) -> Optional[dict]:
    """
    Analyst price targets.
    Returns: {targetHigh, targetLow, targetMean, targetMedian, lastUpdated}
    """
    key = f"pt:{symbol}"
    hit = _cached(key, 3600)
    if hit is not None:
        return hit
    data = await _get("/stock/price-target", {"symbol": _nse(symbol)})
    if data and data.get("targetMean"):
        _store(key, data)
        return data
    return None


async def get_company_news(symbol: str, days: int = 7) -> list[dict]:
    """
    Recent company-specific news from Finnhub.
    Returns normalised article dicts compatible with NewsArticle schema.
    """
    key = f"cnews:{symbol}"
    hit = _cached(key, 900)      # 15-minute cache
    if hit is not None:
        return hit
    to_dt   = datetime.now()
    from_dt = to_dt - timedelta(days=days)
    data = await _get("/company-news", {
        "symbol": _nse(symbol),
        "from":   from_dt.strftime("%Y-%m-%d"),
        "to":     to_dt.strftime("%Y-%m-%d"),
    })
    if not isinstance(data, list):
        return []
    articles = [
        {
            "id":           f"fh-{a.get('id', i)}",
            "headline":     (a.get("headline") or "").strip(),
            "summary":      ((a.get("summary") or a.get("headline") or "")[:300]).strip(),
            "source":       (a.get("source") or "Finnhub"),
            "published_at": _time_ago(a.get("datetime", 0)),
            "url":          a.get("url") or "",
            "impact_score": 7.5,
            "companies":    [],
        }
        for i, a in enumerate(data[:20])
        if a.get("headline")
    ]
    _store(key, articles)
    return articles


async def get_market_news(category: str = "general") -> list[dict]:
    """
    General market/financial news headlines from Finnhub.
    """
    key = f"mnews:{category}"
    hit = _cached(key, 900)
    if hit is not None:
        return hit
    data = await _get("/news", {"category": category})
    if not isinstance(data, list):
        return []
    articles = [
        {
            "id":           f"fh-{a.get('id', i)}",
            "headline":     (a.get("headline") or "").strip(),
            "summary":      ((a.get("summary") or a.get("headline") or "")[:300]).strip(),
            "source":       (a.get("source") or "Finnhub"),
            "published_at": _time_ago(a.get("datetime", 0)),
            "url":          a.get("url") or "",
            "impact_score": 7.0,
            "companies":    [],
        }
        for i, a in enumerate(data[:20])
        if a.get("headline")
    ]
    _store(key, articles)
    return articles
