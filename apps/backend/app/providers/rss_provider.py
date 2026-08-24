"""
RSS news provider — aggregates multiple India-finance RSS feeds.
Each feed config is a (url, source_name, impact_score) tuple.
"""
from __future__ import annotations

import hashlib
import time
from datetime import date
from email.utils import parsedate_to_datetime

import httpx
import structlog

from .base import BaseProvider, RawItem

log = structlog.get_logger(__name__)

# Third element is a per-feed source-credibility weight -- kept for now
# (feature_extraction.extract_source_quality already computes a real,
# independent per-source-name signal for the actual scoring engine, so this
# number isn't needed there), but no longer used as an article's
# impact_score (see RawItem's docstring and normalize() below): a per-feed
# constant was never a per-article score, and exposing it as one made every
# article from the same feed look independently AI-analyzed when none of
# them were.
_FEEDS: list[tuple[str, str, float]] = [
    ("https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "Economic Times", 8.0),
    ("https://www.moneycontrol.com/rss/latestnews.xml",                      "Moneycontrol",   7.5),
    ("https://feeds.feedburner.com/ndtvprofit-latest",                        "NDTV Profit",    7.5),
    ("https://www.business-standard.com/rss/markets-106.rss",                 "Business Standard", 7.5),
    ("https://www.livemint.com/rss/markets",                                  "Livemint",       7.0),
    ("https://news.google.com/rss/search?q=Indian+stock+market+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en",
     "Google News India", 6.5),
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; InvestGridsBot/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}

_INDIA_KEYWORDS = {
    "nifty", "sensex", "nse", "bse", "sebi", "rbi", "india", "rupee", "inr",
    "crore", "lakh", "ndtv", "moneycontrol", "zerodha", "reliance", "tata",
    "infosys", "hdfc", "icici", "bajaj", "adani", "wipro", "ipo", "budget",
}


def _is_india_relevant(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in _INDIA_KEYWORDS)


# _is_india_relevant is a geography filter, not a topic one — any Indian
# entertainment/sports story mentioning "India" or reporting collections in
# "crore" trivially passes it (confirmed live: NDTV Profit's general "latest"
# feed, not markets-scoped, produced two fully-indexed box-office pages —
# "The Odyssey Box Office Collection..." and "...Spider-Man... In India" —
# both pass _is_india_relevant purely because their summaries say "India").
# This second filter targets the actual off-topic content, independent of
# geography. Phrase-based rather than a bare "box office" ban so it doesn't
# catch a legitimate article like "PVR Inox profit jumps on strong box
# office, stock rallies" — real finance content about a listed cinema chain
# reacting to box-office numbers, which should still pass.
_OFF_TOPIC_PHRASES = (
    "box office collection",
    "movie review", "film review",
    "ott release", "web series review",
)

# A real finance story about a listed cinema chain (PVR/Inox) can
# legitimately say "box office collections boosted profit" — only exclude
# when no market-specific signal is also present, so the phrase filter
# above doesn't sweep up genuine stock coverage along with it.
_MARKET_CONTEXT_OVERRIDE = {"stock", "shares", "nse", "bse", "multiplex", "listed"}


def _is_off_topic(text: str) -> bool:
    low = text.lower()
    if not any(kw in low for kw in _OFF_TOPIC_PHRASES):
        return False
    return not any(kw in low for kw in _MARKET_CONTEXT_OVERRIDE)


def _parse_pub_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        return date_str[:10]


class RSSProvider(BaseProvider):
    source_name = "RSS"
    capture_raw_evidence = True   # Phase 1B Batch 2, 2026-08-23

    async def fetch_latest(self) -> list[dict]:
        # Each of the 6 feeds is independent — one going down shouldn't kill
        # the batch, so failures here are per-feed try/except rather than
        # one try around the whole loop. That used to mean a single feed
        # silently going dark (a bad status code or a raised exception)
        # produced literally zero signal: nothing distinguished "this feed
        # had nothing new" from "this feed has been broken for a week."
        # Logging each failure with the specific feed's source name fixes
        # that without changing the graceful-degradation behavior itself.
        # Per-feed health tracking (Phase 6, 2026-08-13 audit) — the shared
        # BaseProvider.fetch_and_normalize() wrapper only sees RSSProvider
        # as a single aggregate ("RSS"), since it calls fetch_latest() once
        # for the whole provider; the 6 real feeds inside it need their own
        # entries, tracked directly here instead.
        import time
        from app.services import source_health

        results: list[dict] = []
        async with httpx.AsyncClient(headers=_HEADERS, timeout=10, follow_redirects=True) as c:
            for url, source, score in _FEEDS:
                feed_id = f"RSS/{source}"
                start = time.monotonic()
                try:
                    r = await c.get(url)
                    elapsed_ms = (time.monotonic() - start) * 1000
                    if r.status_code != 200:
                        log.warning("rss_provider.feed_failed", source=source, status_code=r.status_code)
                        source_health.record_fetch(
                            feed_id, success=False, failure_kind="http", latency_ms=elapsed_ms,
                            error=f"HTTP {r.status_code}",
                        )
                        continue
                    items = _parse_rss_xml(r.content, source, score)
                    results.extend(items)
                    source_health.record_fetch(
                        feed_id, success=True, event_count=len(items), latency_ms=elapsed_ms,
                    )
                except Exception as exc:
                    elapsed_ms = (time.monotonic() - start) * 1000
                    log.warning("rss_provider.feed_failed", source=source, error=str(exc))
                    kind = "http" if isinstance(exc, httpx.HTTPError) else "parse"
                    source_health.record_fetch(
                        feed_id, success=False, failure_kind=kind, latency_ms=elapsed_ms, error=str(exc),
                    )
                    continue
        return results

    async def fetch_by_date(self, target: date) -> list[dict]:
        all_items = await self.fetch_latest()
        target_str = target.isoformat()
        return [i for i in all_items if i.get("published_at", "").startswith(target_str)]

    def normalize(self, raw: dict) -> RawItem | None:
        headline = (raw.get("headline") or "").strip()
        combined = headline + " " + raw.get("summary", "")
        if not headline or not _is_india_relevant(combined) or _is_off_topic(combined):
            return None
        uid = raw.get("id") or f"rss-{hashlib.md5(headline.encode()).hexdigest()[:10]}"
        return RawItem(
            id=uid,
            headline=headline[:512],
            summary=raw.get("summary", "")[:1000],
            source=raw.get("source", "RSS"),
            url=raw.get("url", ""),
            published_at=raw.get("published_at", ""),
            companies=[],
            impact_score=None,  # see RawItem's docstring -- the per-feed weight isn't a real per-article score
            event_type="news",
        )


def _parse_rss_xml(data: bytes, source: str, score: float) -> list[dict]:
    """Parse RSS XML without feedparser (stdlib only)."""
    from xml.etree import ElementTree as ET
    results: list[dict] = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        desc  = (item.findtext("description") or "").strip()
        pub   = (item.findtext("pubDate") or "").strip()
        link  = (item.findtext("link") or "").strip()
        uid   = f"rss-{hashlib.md5((source + title).encode()).hexdigest()[:12]}"
        results.append({
            "id":           uid,
            "headline":     title,
            "summary":      desc[:1000],
            "source":       source,
            "url":          link,
            "published_at": _parse_pub_date(pub),
            "impact_score": score,
        })
    return results[:25]
