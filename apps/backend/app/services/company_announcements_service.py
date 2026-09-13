"""
Company Announcements Ingestion Service
Persists NSE corporate announcements to the DB, and optionally
AI-enriches high-impact ones. BSE is not ingested here — see CR-2A note
on ingest_announcements() below.

Schedule (CR-2A, 2026-09-13): no longer has its own scheduler entry —
called directly from job_ingest_news's existing 15-minute NSE fetch (the
"every 30 minutes during market hours, every 2 hours otherwise" cadence
this docstring used to describe was never actually implemented as
market-hours-aware in the scheduler; it was a flat 30-minute interval
year-round, and no evidence tied that specific number to any downstream
consumer's freshness requirement).

Phase 5D fix (2026-08-17): this module used to import stdlib `logging`
and call it with structlog-style keyword arguments (`log.warning("...",
error=str(e))`). Stdlib `Logger.warning()` doesn't accept arbitrary
kwargs — that call raised `TypeError` INSIDE the except block itself,
uncaught, every time BSE's fetch failed (which it always does — BSE's
API sits behind a JS-execution-required Akamai bot wall, see
app/providers/bse_provider.py). Since `raw = _fetch_nse_announcements()
+ _fetch_bse_announcements()` evaluates both before concatenating, that
crash discarded NSE's already-successfully-fetched data too, every
single run. Confirmed against the real dev DB before this fix: the
company_announcements table had zero rows, ever — not "missing BSE
data", a completely dead pipeline, silently starving every real
consumer (AI Search's get_recent_announcements(), Weekend
Intelligence's evidence sources, the daily intelligence-observation-
snapshot job) of NSE data that was fetching successfully the entire
time. Fixed by switching to structlog (matching the rest of this
codebase) and making each source's failure genuinely independent — see
_fetch_nse_safe/_fetch_bse_safe below.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import structlog

from app.services import source_health

log = structlog.get_logger(__name__)

# ── Simple in-memory dedup cache (symbol+date+subject hash) ───────────────────
_seen: set[str] = set()
_last_run: float = 0.0
_MIN_INTERVAL = 900  # 15 minutes minimum between runs


def _hash(symbol: str, subject: str, date_str: str) -> str:
    return hashlib.sha1(f"{symbol}:{subject[:80]}:{date_str}".encode()).hexdigest()[:16]


# ── NSE corporate announcements ────────────────────────────────────────────────

def _raw_item_to_announcement_dict(raw_item) -> dict:
    """Shared mapping from an already-normalized NSE RawItem (announcement
    kind) to the dict shape ingest_announcements() persists. Pulled out as
    its own function (CR-2A) so both the pre-fetched path (job_ingest_news's
    shared fetch) and the standalone fallback path (_fetch_nse_announcements
    below) produce byte-identical output."""
    symbol = (raw_item.companies[0] if raw_item.companies else "").strip().upper()
    return {
        "symbol":            symbol,
        "company_name":      raw_item.extra.get("company_name", ""),
        "source":            "NSE",
        "category":          "",
        "subject":           raw_item.headline[:500],
        "description":       raw_item.summary[:1000] if raw_item.summary else None,
        "date_str":          f"{raw_item.published_at} 00:00:00" if raw_item.published_at else "",
        "attachment_url":    None,
        "source_record_id":  raw_item.id,  # e.g. "nse-<an_no>" -- shared with Event/NewsArticle
    }


async def _fetch_nse_announcements(limit: int = 50) -> list[dict]:
    """Fetch recent corporate announcements from NSE India.

    Phase 5E.2: this used to independently re-scrape NSE's own API with
    its own requests session — a second, unaware-of-the-first fetch of
    the exact same endpoint app/providers/nse_provider.py's NSEProvider
    already polls for the Event/NewsArticle pipeline. Two scrapers of
    one feed meant the same real filing got hashed into two unrelated
    ID namespaces (`nse-<hash>` for Event/NewsArticle vs `ann_<hash>_nse`
    here) — confirmed live in the dev DB: 9 of 20 CompanyAnnouncement
    rows had a same-day Event/NewsArticle duplicate for the literal same
    filing, invisible to any exact-ID dedup check because the IDs never
    matched by construction.

    Fixed by routing through NSEProvider.fetch_announcements_only() —
    the SAME fetch+normalize path — and carrying its RawItem.id through
    as `source_record_id`, so ingest_announcements() can derive a
    correlated CompanyAnnouncement id instead of an independent hash.
    Still never raises — any failure is caught here, recorded to
    source_health, and reported as an empty list, same contract
    _fetch_bse_announcements makes; one source's outage never takes the
    other's already-fetched data down with it.

    CR-2A (2026-09-13): this is now only the FALLBACK path, used when
    ingest_announcements() is called without pre-fetched items (the
    standalone/manual-trigger case, e.g. POST /api/announcements/ingest).
    The production scheduled path no longer calls this — job_ingest_news
    passes its own already-fetched items directly, eliminating the second
    network call to the same NSE endpoint this function used to make on
    its own independent 30-minute schedule. Left in place (not deleted)
    so the standalone call path keeps working and rollback stays easy."""
    start = time.monotonic()
    try:
        from app.providers.nse_provider import NSEProvider
        raw_items = await NSEProvider().fetch_announcements_only()
        results = [_raw_item_to_announcement_dict(r) for r in raw_items[:limit]]
        source_health.record_fetch(
            "NSE", success=True, event_count=len(results), latency_ms=(time.monotonic() - start) * 1000,
        )
        return results
    except Exception as e:
        log.warning("nse_announcements_fetch_failed", error=str(e)[:200])
        source_health.record_fetch(
            "NSE", success=False, failure_kind="parse",
            latency_ms=(time.monotonic() - start) * 1000, error=str(e)[:500],
        )
        return []


def _fetch_bse_announcements(limit: int = 50) -> list[dict]:
    """Fetch recent corporate announcements from BSE India. Currently
    always fails: BSE's announcement API sits behind an Akamai bot wall
    confirmed (2026-08-17) to require real JavaScript execution — a
    Chrome-TLS-fingerprint-impersonating client (curl_cffi) plus a real
    cookie warm-up still gets redirected to BSE's error page, and no
    cookies are set by the warm-up itself. Status: DEFERRED_BOT_PROTECTED
    (see app/providers/bse_provider.py's module docstring for the full
    investigation) — not fixed here; this function's contract is simply
    to fail safely and never take NSE's data down with it."""
    start = time.monotonic()
    try:
        import requests
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        r = requests.get(
            "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?strCat=-1&strPrevDate=&strScrip=&strSearch=&strToDate=&strType=C&subcategory=-1",
            headers={"User-Agent": ua, "Referer": "https://www.bseindia.com/"},
            timeout=10,
        )
        if not r.ok:
            source_health.record_fetch(
                "BSE", success=False, failure_kind="http",
                latency_ms=(time.monotonic() - start) * 1000, error=f"http {r.status_code}",
            )
            return []
        data = r.json()
        if not isinstance(data, dict):
            source_health.record_fetch(
                "BSE", success=False, failure_kind="parse",
                latency_ms=(time.monotonic() - start) * 1000, error="response was not a JSON object (bot-wall page)",
            )
            return []
        items = data.get("Table", [])
        results = []
        for item in items[:limit]:
            subject = item.get("HEADLINE", "") or item.get("NEWS_HDR", "") or ""
            if not subject:
                continue
            results.append({
                "symbol":       (item.get("SCRIP_CD", "") or "").strip(),
                "company_name": item.get("SLONGNAME", "") or item.get("CompanyName", ""),
                "source":       "BSE",
                "category":     item.get("CATEGORYNAME", "") or item.get("NEWSSUB", ""),
                "subject":      subject[:500],
                "description":  item.get("NEWS_BODY", "")[:1000] if item.get("NEWS_BODY") else None,
                "date_str":     item.get("NEWS_DT", "") or item.get("DissemDT", ""),
                "attachment_url": None,
            })
        source_health.record_fetch(
            "BSE", success=True, event_count=len(results), latency_ms=(time.monotonic() - start) * 1000,
        )
        return results
    except Exception as e:
        log.warning("bse_announcements_fetch_failed", error=str(e)[:200])
        source_health.record_fetch(
            "BSE", success=False, failure_kind="parse",
            latency_ms=(time.monotonic() - start) * 1000, error=str(e)[:500],
        )
        return []


# ── Impact scoring ────────────────────────────────────────────────────────────

_HIGH_IMPACT_KEYWORDS = {
    "results", "dividend", "buyback", "merger", "acquisition", "demerger",
    "board meeting", "qip", "rights issue", "ofs", "fpo", "ipo",
    "insolvency", "fraud", "rbi", "sebi", "order", "penalty",
    "ceo", "cfo", "md", "resignation", "appointment",
}

_SENTIMENT_MAP = {
    "dividend":     "bullish",
    "results":      "neutral",
    "buyback":      "bullish",
    "merger":       "bullish",
    "acquisition":  "bullish",
    "qip":          "bullish",
    "rights issue": "neutral",
    "penalty":      "bearish",
    "insolvency":   "bearish",
    "fraud":        "bearish",
    "resignation":  "bearish",
}


def _score_announcement(subject: str, category: str) -> tuple[int, str, bool]:
    """Returns (impact_score 0-10, sentiment, is_high_impact)."""
    combined = (subject + " " + category).lower()
    score = 3
    sentiment = "neutral"
    for kw in _HIGH_IMPACT_KEYWORDS:
        if kw in combined:
            score = max(score, 7)
            if kw in _SENTIMENT_MAP:
                sentiment = _SENTIMENT_MAP[kw]
    is_high = score >= 7
    return score, sentiment, is_high


# ── DB persistence ─────────────────────────────────────────────────────────────

async def ingest_announcements(nse_items: Optional[list] = None) -> int:
    """Deduplicate and persist NSE corporate announcements to DB. Returns
    count saved.

    CR-2A (2026-09-13): BSE removed from this hot path entirely —
    DEFERRED_BOT_PROTECTED (see bse_provider.py), every call guaranteed to
    fail, contributing pure waste on this function's own schedule. BSE
    availability is now checked by one isolated daily health probe
    instead (see bse_health_check.py) — a real recovery would be a
    deliberate re-enablement decision, not automatically resumed here.

    `nse_items` lets a caller pass already-fetched RawItem objects (their
    `nse_feed_kind` extra pre-filtered to "announcement") instead of this
    function fetching NSE itself — job_ingest_news's shared 15-minute
    fetch does this, eliminating the second independent NSE network call
    this function used to make on its own 30-minute schedule. When
    `nse_items` is None (the standalone/manual-trigger call path, e.g.
    POST /api/announcements/ingest), this fetches on its own via
    _fetch_nse_announcements(), unchanged from before."""
    global _last_run
    now = time.time()
    if now - _last_run < _MIN_INTERVAL:
        return 0
    _last_run = now

    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.company_announcements import CompanyAnnouncement
        import uuid

        if nse_items is None:
            raw = await _fetch_nse_announcements()
        else:
            raw = [_raw_item_to_announcement_dict(i) for i in nse_items]
        if not raw:
            return 0

        saved = 0
        async with AsyncSessionLocal() as db:
            for item in raw:
                h = _hash(item["symbol"], item["subject"], item["date_str"])
                if h in _seen:
                    continue

                ann_date: Optional[datetime] = None
                if item["date_str"]:
                    for fmt in ("%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                        try:
                            ann_date = datetime.strptime(item["date_str"][:19], fmt).replace(tzinfo=timezone.utc)
                            break
                        except ValueError:
                            continue

                # Skip if older than 2 days
                if ann_date and (datetime.now(timezone.utc) - ann_date).days > 2:
                    _seen.add(h)
                    continue

                score, sentiment, is_high = _score_announcement(item["subject"], item.get("category", ""))

                # Phase 5E.2: when this item came through the shared
                # NSEProvider fetch, source_record_id IS the same id
                # Event/NewsArticle use for the identical filing (e.g.
                # "nse-<an_no>") — deriving ann_id from it (rather than an
                # independent content hash) makes this row's identity
                # deterministically correlated with its Event/NewsArticle
                # counterpart, closing that duplicate class exactly rather
                # than relying on fuzzy matching. BSE (not yet unified —
                # still broken/deferred, see bse_provider.py) keeps the
                # old hash-based scheme.
                source_record_id = item.get("source_record_id")
                ann_id = f"ann_{source_record_id}" if source_record_id else f"ann_{h}_{item['source'].lower()}"
                existing = await db.get(CompanyAnnouncement, ann_id)
                if existing:
                    _seen.add(h)
                    continue

                record = CompanyAnnouncement(
                    id=ann_id,
                    symbol=item["symbol"] or None,
                    company_name=item["company_name"] or None,
                    source=item["source"],
                    category=item.get("category") or None,
                    subject=item["subject"],
                    description=item.get("description"),
                    announcement_date=ann_date,
                    attachment_url=item.get("attachment_url"),
                    impact_score=score,
                    sentiment=sentiment,
                    is_high_impact=is_high,
                    sectors=[],
                    themes=[],
                    ai_summary=None,
                )
                db.add(record)
                _seen.add(h)
                saved += 1

            if saved:
                await db.commit()

        log.info("announcements_ingested", count=saved)
        return saved

    except Exception as e:
        log.error("announcements_ingest_error", error=str(e))
        return 0


async def get_recent_announcements(
    symbol: Optional[str] = None,
    limit: int = 20,
    high_impact_only: bool = False,
) -> list[dict]:
    """Query recent announcements from DB."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.company_announcements import CompanyAnnouncement
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            q = select(CompanyAnnouncement)
            if symbol:
                q = q.where(CompanyAnnouncement.symbol == symbol.upper())
            if high_impact_only:
                q = q.where(CompanyAnnouncement.is_high_impact == True)
            q = q.order_by(desc(CompanyAnnouncement.announcement_date)).limit(limit)
            result = await db.execute(q)
            rows = result.scalars().all()
            return [
                {
                    "id":                row.id,
                    "symbol":            row.symbol,
                    "company_name":      row.company_name,
                    "source":            row.source,
                    "category":          row.category,
                    "subject":           row.subject,
                    "description":       row.description,
                    "announcement_date": row.announcement_date.isoformat() if row.announcement_date else None,
                    "attachment_url":    row.attachment_url,
                    "impact_score":      row.impact_score,
                    "sentiment":         row.sentiment,
                    "is_high_impact":    row.is_high_impact,
                    "ai_summary":        row.ai_summary,
                    "ingested_at":       row.ingested_at.isoformat() if row.ingested_at else None,
                }
                for row in rows
            ]
    except Exception as e:
        log.error("announcements_query_error", error=str(e))
        return []
