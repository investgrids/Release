"""
Company Announcements Ingestion Service
Fetches corporate announcements from NSE and BSE, stores them in the DB,
and optionally AI-enriches high-impact ones.

Schedule: every 30 minutes during market hours, every 2 hours otherwise.

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

def _fetch_nse_announcements(limit: int = 50) -> list[dict]:
    """Fetch recent corporate announcements from NSE India. Never raises —
    any failure is caught, recorded to source_health, and reported as an
    empty list, same contract _fetch_bse_announcements makes. Each
    function's failure is independent: a caller doing
    `_fetch_nse_announcements() + _fetch_bse_announcements()` never has
    one source's outage take down the other's already-fetched data."""
    start = time.monotonic()
    try:
        import requests
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        session = requests.Session()
        session.get("https://www.nseindia.com/", headers={"User-Agent": ua}, timeout=6)
        r = session.get(
            "https://www.nseindia.com/api/corporate-announcements?index=equities",
            headers={
                "User-Agent": ua,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
            },
            timeout=10,
        )
        if not r.ok:
            source_health.record_fetch(
                "NSE", success=False, failure_kind="http",
                latency_ms=(time.monotonic() - start) * 1000, error=f"http {r.status_code}",
            )
            return []
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", [])
        results = []
        for item in items[:limit]:
            subject = item.get("subject", "") or item.get("desc", "") or ""
            if not subject:
                continue
            results.append({
                "symbol":       (item.get("symbol", "") or "").strip().upper(),
                "company_name": item.get("comp", "") or item.get("companyName", ""),
                "source":       "NSE",
                "category":     item.get("attchmntText", "") or item.get("type", ""),
                "subject":      subject[:500],
                "description":  item.get("body", "")[:1000] if item.get("body") else None,
                "date_str":     item.get("exchdisstime", "") or item.get("an_dt", ""),
                "attachment_url": item.get("attchmntFile", "") or None,
            })
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

async def ingest_announcements() -> int:
    """Fetch announcements from NSE+BSE, deduplicate, persist to DB. Returns count saved."""
    global _last_run
    now = time.time()
    if now - _last_run < _MIN_INTERVAL:
        return 0
    _last_run = now

    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.company_announcements import CompanyAnnouncement
        import uuid

        raw = _fetch_nse_announcements() + _fetch_bse_announcements()
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

                ann_id = f"ann_{h}_{item['source'].lower()}"
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
