"""
Free live financial news from yfinance + RSS feeds.
No API key required. Cache TTL = 15 minutes.
"""

import asyncio
from contextvars import ContextVar
import hashlib
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx
import yfinance as yf

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_YF_SYMBOLS = [
    # Indices
    "^NSEI", "^BSESN", "^NSEBANK",
    # Large-cap NSE stocks across sectors
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "LT.NS",
    "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "MARUTI.NS", "TATAMOTORS.NS",
    "WIPRO.NS", "HCLTECH.NS", "ONGC.NS", "NTPC.NS", "ADANIENT.NS",
    "BAJFINANCE.NS", "SUNPHARMA.NS",
]

RSS_FEEDS = [
    # ── Google News (topic-targeted) ──────────────────────────────────────────
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
    (
        "https://news.google.com/rss/search?q=india+corporate+earnings+results+NSE&hl=en-IN&gl=IN&ceid=IN:en",
        "Google News",
    ),
    # ── Direct publisher RSS feeds ────────────────────────────────────────────
    (
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "Economic Times",
    ),
    (
        "https://www.moneycontrol.com/rss/business.xml",
        "Moneycontrol",
    ),
    (
        "https://www.moneycontrol.com/rss/latestnews.xml",
        "Moneycontrol",
    ),
    (
        "https://www.business-standard.com/rss/markets-106.rss",
        "Business Standard",
    ),
    (
        "https://www.livemint.com/rss/markets",
        "Livemint",
    ),
    (
        "https://feeds.feedburner.com/ndtvprofit-latest",
        "NDTV Profit",
    ),
]

# Headline keyword → impact score. The "budget <year>" keyword tracks the
# current year automatically (evaluated at process start) instead of a
# hardcoded year that silently stops matching once that year's budget cycle
# passes — India's Union Budget lands early Feb, so "current year" is
# correct for essentially the whole year.
_IMPACT_RULES: list[tuple[float, list[str]]] = [
    (9.5, ["repo rate", "rbi rate cut", "rbi rate hike", f"budget {datetime.now(timezone.utc).year}", "gdp growth", "recession"]),
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
    ("adani enterprises", "Adani Enterprises"),
    ("adani ports", "Adani Ports"),
    ("vizhinjam", "Adani Ports"),   # Vizhinjam port is operated by Adani Ports
    ("adani", "Adani Ports"),       # generic "adani" mention → Adani Ports (most traded)
    ("airtel", "Bharti Airtel"),
    ("bharti", "Bharti Airtel"),
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
    ("hcltech", "HCL Technologies"),
    ("hcl tech", "HCL Technologies"),
    ("tech mahindra", "Tech Mahindra"),
    ("tata power", "Tata Power"),
    ("power grid", "Power Grid"),
    ("l&t", "Larsen & Toubro"),
    ("larsen", "Larsen & Toubro"),
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

# Article must contain at least one of these to be shown
_INDIA_KEYWORDS = [
    "india", "indian", "nse", "bse", "nifty", "sensex", "sebi", "rbi",
    "rupee", "₹", "crore", "lakh", "mumbai", "bengaluru", "hyderabad",
    "reliance", "tata ", "infosys", "wipro", "hdfc", "icici", "sbin", "sbi",
    "adani", "airtel", "bajaj", "maruti", "ongc", "ntpc", "itc ", "itc's",
    "hul ", "hindustan unilever", "kotak", "axis bank", "larsen", "l&t",
    "sun pharma", "cipla", "dr reddy", "zomato", "paytm", "swiggy",
    "nifty 50", "sensex", "dalal street", "fii", "dii", "sebi", "rbi policy",
    "repo rate", "india gdp", "india cpi", "india budget", "make in india",
    "psu ", "disinvestment", "ipo ", "ofss", "techm", "hcltech",
]

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


def _is_india_relevant(headline: str, summary: str = "") -> bool:
    text = (headline + " " + summary).lower()
    return any(kw in text for kw in _INDIA_KEYWORDS)


# _is_india_relevant is a geography filter, not a topic one — any Indian
# entertainment/sports story mentioning "India" or reporting collections in
# "crore" trivially passes it (confirmed live: this fetcher's own
# NDTV Profit feed — "feeds.feedburner.com/ndtvprofit-latest", not
# markets-scoped — produced two fully-indexed box-office pages via this
# exact function; their live- prefixed ids match _make_id() above). This
# second filter targets the off-topic content itself. Phrase-based rather
# than a bare "box office" ban so it doesn't catch a legitimate article
# like "PVR Inox profit jumps on strong box office, stock rallies" — real
# finance content about a listed cinema chain reacting to box-office
# numbers, which should still pass.
_OFF_TOPIC_PHRASES = (
    "box office collection",
    "movie review", "film review",
    "ott release", "web series review",
)
_MARKET_CONTEXT_OVERRIDE = {"stock", "shares", "nse", "bse", "multiplex", "listed"}


def _is_off_topic(headline: str, summary: str = "") -> bool:
    text = (headline + " " + summary).lower()
    if not any(kw in text for kw in _OFF_TOPIC_PHRASES):
        return False
    return not any(kw in text for kw in _MARKET_CONTEXT_OVERRIDE)


def _extract_companies(headline: str, summary: str = "") -> list[str]:
    # Search headline + first 300 chars of summary to catch company mentions not in title
    text = " " + (headline + " " + summary[:300]).lower() + " "
    found: list[str] = []
    for kw, name in _COMPANY_KEYWORDS:
        if kw in text and name not in found:
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
        "companies": _extract_companies(headline, summary),
        "impact_score": _impact_score(headline),
    }


def get_cached_article(article_id: str) -> dict | None:
    """Return a single article from cache by id (served form: relative label derived now)."""
    for a in _snapshot["items"]:
        if a.get("id") == article_id:
            return _served(a)
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
    items, _err = await _fetch_rss_status(url, source)
    return items


async def _fetch_rss_status(url: str, source: str) -> tuple[list[dict], str | None]:
    """(items, error). error is None for a feed that answered and parsed (even with zero items); otherwise the failure class. Step 3.4H.3: a failure must stay distinguishable from an empty feed."""
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, follow_redirects=True, timeout=10
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.text
    except Exception as exc:
        return [], type(exc).__name__

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
        return [], "ParseError"
    return items, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _served(item: dict) -> dict:
    """The caller-facing form of a snapshot item: internal `_ts` removed, `published_ts` (absolute epoch) added, and the relative label derived NOW from the stored timestamp, never cached as truth."""
    out = {k: v for k, v in item.items() if k != "_ts"}
    ts = item.get("_ts")
    if ts:
        out["published_at"] = _time_ago(ts)
        out["published_ts"] = ts
    return out


def _aggregate(batches: list[list[dict]]) -> list[dict]:
    """Merge, dedupe, India-relevance filter, newest first, keep 60. Items keep their absolute `_ts`."""
    merged: list[dict] = []
    seen_ids: set[str] = set()
    for batch in batches:
        for article in batch or []:
            aid = article["id"]
            if (
                aid not in seen_ids
                and _is_india_relevant(article.get("headline", ""), article.get("summary", ""))
                and not _is_off_topic(article.get("headline", ""), article.get("summary", ""))
            ):
                seen_ids.add(aid)
                merged.append(article)
    merged.sort(key=lambda x: x.get("_ts", 0), reverse=True)
    return merged[:60]      # up to 60 so tab filters have enough


# ---------------------------------------------------------------------------
# Snapshot lifecycle (Step 3.4H.3): stale-while-revalidate, single flight, last-known-good
#   fresh (age < CACHE_TTL)            -> serve immediately
#   stale, age < max stale             -> serve immediately, start (or join) ONE background refresh
#   none / older than max stale        -> bounded foreground wait for the RSS phase of a shared refresh
# A refresh publishes the RSS result as soon as feeds answer; yfinance is a separate, bounded, background-only phase that can only add to an already published snapshot.
# Snapshot age is not article age: every item keeps its own absolute timestamp, and eligibility stays with retrieval and ranking.
# ---------------------------------------------------------------------------

class LiveNewsUnavailable(RuntimeError):
    """The live feed could not be obtained (cold start cut off or all sources failed): an infrastructure condition, not evidence that no news exists."""


_snapshot: dict = {"items": [], "fetched_at": 0.0, "last_success_at": 0.0, "source_failures": {}, "consecutive_failures": 0, "last_error": None, "installed": False}
_refresh_task: asyncio.Task | None = None
_refresh_loop = None
_rss_event: asyncio.Event | None = None
_yf_future = None
_last_status: ContextVar = ContextVar("live_news_status", default=None)


def live_news_status() -> str | None:
    """Outcome of the most recent get_live_news call in this context: ok | empty | stale | failed | timeout (None when not called)."""
    return _last_status.get()


def reset_live_news_status() -> None:
    _last_status.set(None)


def _settings():
    from app.core.config import settings
    return settings


def _install(items: list[dict], failures: dict, usable: bool) -> None:
    """Atomically replace the snapshot (one dict assignment). `usable=False` means the refresh produced nothing and failed: keep the last known good items and only record the failure."""
    global _snapshot
    now = time.time()
    if not usable:
        _snapshot = {**_snapshot, "source_failures": dict(failures), "consecutive_failures": _snapshot["consecutive_failures"] + 1,
                     "last_error": next(iter(failures.values()), None)}
        return
    _snapshot = {"items": list(items), "fetched_at": now, "last_success_at": now, "source_failures": dict(failures), "consecutive_failures": 0, "last_error": None, "installed": True}
    _cache["ts"] = now
    _cache["data"] = [_served(a) for a in items]      # legacy mirror; readers should use the snapshot


async def _refresh(rss_ready: asyncio.Event, include_yfinance: bool = True) -> None:
    """One refresh. Phase 1: all RSS feeds concurrently; the snapshot is published as soon as the first window closes (or all feeds answered), stragglers merge in when they finish.
    Phase 2 (background only): bounded yfinance, merged into the published snapshot, never a precondition for it."""
    global _yf_future
    cfg = _settings()
    failures: dict[str, str] = {}
    collected: list[list[dict]] = []
    tasks = {asyncio.ensure_future(_fetch_rss_status(url, src)): url for url, src in RSS_FEEDS}
    pending = set(tasks)
    window = cfg.live_news_rss_publish_window_seconds
    published = False
    try:
        started = time.monotonic()
        first_pass = True
        while pending:
            left = cfg.live_news_rss_max_seconds - (time.monotonic() - started)
            if left <= 0:
                break
            if published:
                done, pending = await asyncio.wait(pending, timeout=left)                                   # stragglers, up to the hard limit
            elif first_pass:
                done, pending = await asyncio.wait(pending, timeout=min(window, left))                      # the publish window: ideally every feed
            else:
                done, pending = await asyncio.wait(pending, timeout=left, return_when=asyncio.FIRST_COMPLETED)   # nothing usable yet: publish on the first usable answer
            first_pass = False
            for t in done:
                url = tasks[t]
                try:
                    items, err = t.result()
                except Exception as exc:        # a feed task must never take the refresh down
                    items, err = [], type(exc).__name__
                if err:
                    failures[url] = err
                else:
                    collected.append(items)
            merged = _aggregate(collected)
            if merged:
                _install(merged, failures, True)
                published = True
                rss_ready.set()
        for t in pending:
            t.cancel()
            failures[tasks[t]] = "timeout"
        merged = _aggregate(collected)
        if merged:
            _install(merged, failures, True)
            published = True
        elif collected and not failures:
            _install([], failures, True)         # every feed answered and nothing relevant: a legitimate empty result
            published = True
        else:
            _install([], failures or {"rss": "no usable result"}, False)      # total failure: last known good stays
    except BaseException:
        for t in pending:
            t.cancel()
        raise
    finally:
        rss_ready.set()

    if not include_yfinance or not _snapshot["installed"]:
        return
    loop = asyncio.get_running_loop()
    if _yf_future is not None and not _yf_future.done():
        return                                      # a previous yfinance thread is still running (threads cannot be cancelled): never stack another
    fut = loop.run_in_executor(None, _sync_fetch_yfinance)
    _yf_future = fut
    try:
        yf_items = await asyncio.wait_for(asyncio.shield(fut), timeout=cfg.live_news_yfinance_timeout_seconds)
    except asyncio.TimeoutError:
        failures["yfinance"] = "timeout"
        _snapshot["source_failures"]["yfinance"] = "timeout"
        return
    except Exception as exc:
        _snapshot["source_failures"]["yfinance"] = type(exc).__name__
        return
    if yf_items:
        extended = _aggregate([_snapshot["items"], yf_items])
        _install(extended, {**_snapshot["source_failures"]}, True)


def _ensure_refresh() -> tuple[asyncio.Task, asyncio.Event]:
    """Single flight: start a refresh unless one is already running on this loop. A finished or failed task never counts as running."""
    global _refresh_task, _refresh_loop, _rss_event
    loop = asyncio.get_running_loop()
    if _refresh_task is not None and not _refresh_task.done() and _refresh_loop is loop:
        return _refresh_task, _rss_event
    event = asyncio.Event()
    task = asyncio.ensure_future(_refresh(event))

    def _clear(t: asyncio.Task) -> None:
        global _refresh_task
        if _refresh_task is t:
            _refresh_task = None
        if not t.cancelled() and t.exception() is not None:
            logger.warning("live_news.refresh_failed", exc=str(t.exception())[:160])

    task.add_done_callback(_clear)
    _refresh_task, _refresh_loop, _rss_event = task, loop, event
    return task, event


async def refresh_live_news() -> None:
    """Warm-up entry point for the scheduler: join or start a refresh and wait for the whole of it (RSS and yfinance phases)."""
    task, _ = _ensure_refresh()
    await asyncio.shield(task)


def _usable_snapshot(now: float) -> tuple[bool, bool]:
    """(has_data, fresh). Data older than the max-stale limit is treated as absent."""
    snap = _snapshot
    if not snap["installed"]:
        return False, False
    age = now - snap["fetched_at"]
    if age >= _settings().live_news_max_stale_seconds:
        return False, False
    return True, age < CACHE_TTL


async def get_live_news(limit: int = 20) -> list[dict]:
    """Return live news. Never raises; [] when nothing could be obtained (live_news_status() says why: failed/timeout are infrastructure conditions, empty is a real empty result).
    Fresh snapshot: immediate. Stale (within max stale): immediate and one shared background refresh. Cold: a bounded wait for the RSS phase, within the request deadline when one is active."""
    now = time.time()
    has_data, fresh = _usable_snapshot(now)
    if has_data:
        if not fresh:
            try:
                _ensure_refresh()
            except Exception:
                pass
        items = _snapshot["items"]
        _last_status.set("ok" if fresh and items else ("empty" if fresh else "stale"))
        return [_served(a) for a in items[:limit]]

    from app.services import request_deadline
    cfg = _settings()
    budget = cfg.live_news_cold_rss_cap_seconds
    usable = request_deadline.usable()
    if usable is not None:
        budget = min(budget, usable)
    if budget <= 0:
        _last_status.set("timeout")
        return []
    _task, event = _ensure_refresh()
    try:
        await asyncio.wait_for(event.wait(), timeout=budget)      # waits on the event, not the task: a cancelled or timed-out waiter never cancels the shared refresh
    except asyncio.TimeoutError:
        _last_status.set("timeout")
        return []
    has_data, _fresh = _usable_snapshot(time.time())
    if not has_data:
        _last_status.set("failed")
        return []
    items = _snapshot["items"]
    _last_status.set("ok" if items else "empty")
    return [_served(a) for a in items[:limit]]
