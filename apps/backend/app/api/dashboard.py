"""
Dashboard API — cache-first endpoint.

Flow:
  1. Read Redis (DASHBOARD_KEY)
  2. Hit  → return immediately (target: < 10 ms)
  3. Miss → load from PostgreSQL + compute on-the-fly
  4. Store result in Redis for subsequent requests
  5. Return response

The precompute job (7 AM IST daily) pre-warms the cache so nearly every
request hits step 2.
"""
from __future__ import annotations

import asyncio
import time

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import (
    get as cache_get,
    set as cache_set,
    DASHBOARD_KEY,
    TTL_DASHBOARD,
)
from app.db.session import get_db
from app.db.crud import get_trending_events
from app.services.market_data import get_index_quotes, get_top_movers
from app.services.ai_service import get_market_summary

router = APIRouter()
log = structlog.get_logger(__name__)


@router.get("/", response_model=dict)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    t0 = time.perf_counter()

    # ── 1. Try Redis cache first ──────────────────────────────────────────────
    cached = await cache_get(DASHBOARD_KEY)
    if cached is not None:
        elapsed = round((time.perf_counter() - t0) * 1000)
        log.info("dashboard.cache_hit", latency_ms=elapsed)
        return cached

    # ── 2. Cache miss — compute from DB + external data ───────────────────────
    log.info("dashboard.cache_miss")

    events_task      = get_trending_events(db, limit=5)
    index_task       = get_index_quotes()
    movers_task      = get_top_movers()

    events, index_quotes, movers = await asyncio.gather(
        events_task, index_task, movers_task,
        return_exceptions=True,
    )
    if isinstance(events,       Exception): events       = []
    if isinstance(index_quotes, Exception): index_quotes = []
    if isinstance(movers,       Exception): movers       = {}

    trending = [
        {
            "id":           e.id,
            "title":        e.title,
            "summary":      e.summary,
            "category":     e.category or "Macro",
            "impact_score": e.impact_score,
            "confidence":   e.confidence,
            "sectors":      e.sectors,
            "companies":    e.companies,
            "date":         e.published_at.isoformat() if e.published_at else None,
        }
        for e in (events or [])
    ]

    event_dicts = [{"title": e.title, "impact_score": e.impact_score} for e in (events or [])]
    ai_summary  = await get_market_summary(index_quotes or [], event_dicts)

    market_snapshot = {
        q["title"].lower().replace(" ", "_"): q["value"]
        for q in (index_quotes or [])
    }

    # Add 5-day chart data to each index quote
    index_tickers = {"NIFTY 50": "^NSEI", "SENSEX": "^BSESN", "BANKNIFTY": "^NSEBANK"}
    loop = asyncio.get_event_loop()
    if isinstance(index_quotes, list):
        for q in index_quotes:
            try:
                ticker = index_tickers.get(q.get("title", ""), "^NSEI")
                from app.services.market_data import _fetch_history
                hist = await loop.run_in_executor(None, _fetch_history, ticker, "5d", "1d")
                q["chartData"] = [{"label": h["label"], "value": h["value"]} for h in hist]
            except Exception:
                q["chartData"] = []

    payload = {
        "market_snapshot":  market_snapshot,
        "index_quotes":     index_quotes or [],
        "aiSummary":        ai_summary,
        "trending_events":  trending,
        "top_movers":       movers or {},
    }

    # ── 3. Warm cache for next request ────────────────────────────────────────
    await cache_set(DASHBOARD_KEY, payload, TTL_DASHBOARD)

    elapsed = round((time.perf_counter() - t0) * 1000)
    log.info("dashboard.computed", latency_ms=elapsed)
    return payload
