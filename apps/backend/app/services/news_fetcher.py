"""
Free live financial news from yfinance + RSS feeds.
No API key required. Cache TTL = 15 minutes.
"""

import asyncio
import hashlib
import re
import time
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx
import yfinance as yf

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_YF_SYMBOLS = [
    "^NSEI", "^BSESN", "^NSEBANK",
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "LT.NS",
]

RSS_FEEDS = [
    (
        "https://news.google.com/rss/search?q=india+stock+market+nifty+sensex&hl=en-IN&gl=IN&ceid=IN:en",
        "Google News",
    ),
    (
        "https://news.google.com/rss/search?q=BSE+NSE+india+shares+equity&hl=en-IN&gl=IN&ceid=IN:en",
        "Google News",
    ),
    (
        "https://news.google.com/rss/search?q=RBI+SEBI+india+economy+budget&hl=en-IN&gl=IN&ceid=IN:en",
        "Google News",
    ),
]

# Headline keyword → impact score
_IMPACT_RULES: list[tuple[float, list[str]]] = [
    (9.5, ["repo rate", "rbi rate cut", "rbi rate hike", "budget 2026", "gdp growth", "recession"]),
    (8.5, ["rbi", "sebi", "defence", "capex", "inflation", "fii", "sensex", "nifty",
           "rate cut", "rate hike", "fiscal deficit", "crude oil", "rupee", "foreign reserve"]),
    (7.5, ["results", "earnings", "profit", "revenue", "merger", "acquisition", "ipo",
           "quarterly", "q1 ", "q2 ", "q3 ", "q4 ", "dividend", "buyback", "delisting"]),
]

_COMPANY_KEYWORDS: list[tuple[str, str]] = [
    ("reliance", "Reliance Industries"),
    ("tata consultancy", "TCS"),
    (" tcs ", "TCS"),
    ("hdfc bank", "HDFC Bank"),
    ("hdfc", "HDFC Bank"),
    ("infosys", "Infosys"),
    (" infy", "Infosys"),
    ("wipro", "Wipro"),
    ("icici bank", "ICICI Bank"),
    ("icici", "ICICI Bank"),
    ("tata motors", "Tata Motors"),
    ("tata steel", "Tata Steel"),
    ("adani green", "Adani Green"),
    ("adani ports", "Adani Ports"),
    ("adani", "Adani Group"),
    ("airtel", "Bharti Airtel"),
    ("bel ", "Bharat Electronics"),
    ("bharat electronics", "Bharat Electronics"),
    ("hal ", "HAL"),
    ("hindustan aeronautics", "HAL"),
    ("ntpc", "NTPC"),
    ("ongc", "ONGC"),
    ("itc ", "ITC"),
    ("bajaj finance", "Bajaj Finance"),
    ("bajaj auto", "Bajaj Auto"),
    ("maruti", "Maruti Suzuki"),
    ("zomato", "Zomato"),
    ("sun pharma", "Sun Pharma"),
    ("ultratech", "UltraTech Cement"),
    ("kotak", "Kotak Mahindra Bank"),
    ("axis bank", "Axis Bank"),
    ("sbi", "SBI"),
    ("state bank", "SBI"),
    ("coal india", "Coal India"),
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CACHE_TTL = 900  # 15 minutes
_cache: dict = {"ts": 0.0, "data": []}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_id(headline: str) -> str:
    return "live-" + hashlib.md5(headline.lower().strip().encode()).hexdigest()[:12]


def _time_ago(ts: float) -> str:
    diff = max(0, time.time() - ts)
    if diff < 60:
        return "Just now"
    if diff < 3600:
        return f"{int(diff // 60)}m ago"
    if diff < 86400:
        return f"{int(diff // 3600)}h ago"
    return f"{int(diff // 86400)}d ago"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _impact_score(headline: str) -> float:
    h = headline.lower()
    for score, keywords in _IMPACT_RULES:
        if any(kw in h for kw in keywords):
            return score
    return 7.0


def _extract_companies(headline: str) -> list[str]:
    h = " " + headline.lower() + " "
    found: list[str] = []
    for kw, name in _COMPANY_KEYWORDS:
        if kw in h and name not in found:
            found.append(name)
        if len(found) >= 4:
            break
    return found


def _normalize(headline: str, summary: str, source: str, ts: float, url: str = "") -> dict:
    headline = headline.strip()
    summary = (_strip_html(summary) or headline).strip()
    if len(summary) > 400:
        summary = summary[:397] + "…"
    return {
        "id": _make_id(headline),
        "headline": headline,
        "summary": summary,
        "source": source,
        "published_at": _time_ago(ts),
        "url": url,
        "_ts": ts,
        "companies": _extract_companies(headline),
        "impact_score": _impact_score(headline),
    }


def get_cached_article(article_id: str) -> dict | None:
    """Return a single article from cache by id."""
    for a in _cache.get("data", []):
        if a.get("id") == article_id:
            return a
    return None


# ---------------------------------------------------------------------------
# yfinance fetcher (sync, run in executor)
# ---------------------------------------------------------------------------

def _sync_fetch_yfinance() -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for sym in _YF_SYMBOLS:
        try:
            news_items = yf.Ticker(sym).news or []
            for item in news_items[:6]:
                headline = (item.get("title") or "").strip()
                if not headline or headline in seen:
                    continue
                seen.add(headline)
                ts = float(item.get("providerPublishTime") or time.time())
                results.append(
                    _normalize(
                        headline=headline,
                        summary=item.get("summary") or item.get("title") or "",
                        source=item.get("publisher") or "Yahoo Finance",
                        ts=ts,
                        url=item.get("link") or "",
                    )
                )
        except Exception:
            continue
    return results


# ---------------------------------------------------------------------------
# RSS fetcher (async)
# ---------------------------------------------------------------------------

async def _fetch_rss(url: str, source: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, follow_redirects=True, timeout=10
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.text
    except Exception:
        return []

    items: list[dict] = []
    try:
        root = ET.fromstring(content)
        for item in root.iter("item"):
            headline = _strip_html(item.findtext("title") or "").strip()
            if not headline:
                continue
            desc = item.findtext("description") or ""
            pub_raw = item.findtext("pubDate") or ""
            try:
                ts = parsedate_to_datetime(pub_raw).timestamp()
            except Exception:
                ts = time.time()

            items.append(
                _normalize(
                    headline=headline,
                    summary=desc,
                    source=source,
                    ts=ts,
                    url=item.findtext("link") or "",
                )
            )
    except ET.ParseError:
        return []
    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def _fetch_finnhub_news() -> list[dict]:
    """Pull general market news from Finnhub if API key is set."""
    try:
        from app.services.finnhub import get_market_news
        articles = await get_market_news("general")
        # Finnhub articles may lack _ts — stamp them now so sort works
        now = time.time()
        for a in articles:
            a.setdefault("_ts", now)
        return articles
    except Exception:
        return []


async def get_live_news(limit: int = 20) -> list[dict]:
    """Return live news, cached for CACHE_TTL seconds. Empty list on total failure."""
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"][:limit]

    loop = asyncio.get_event_loop()

    # Run yfinance (sync) + all RSS feeds + Finnhub concurrently
    tasks = [loop.run_in_executor(None, _sync_fetch_yfinance)]
    tasks += [_fetch_rss(url, src) for url, src in RSS_FEEDS]
    tasks += [_fetch_finnhub_news()]

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    merged: list[dict] = []
    seen_ids: set[str] = set()

    for batch in raw_results:
        if isinstance(batch, Exception) or not batch:
            continue
        for article in batch:
            aid = article["id"]
            if aid not in seen_ids:
                seen_ids.add(aid)
                merged.append(article)

    # Sort newest first
    merged.sort(key=lambda x: x.get("_ts", 0), reverse=True)

    # Strip internal _ts field before caching
    clean = [{k: v for k, v in a.items() if k != "_ts"} for a in merged[:limit]]

    _cache["ts"] = now
    _cache["data"] = clean
    return clean
