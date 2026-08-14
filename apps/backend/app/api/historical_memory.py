"""
Historical Market Memory API — /api/historical/*

Endpoints:
  GET  /api/historical/similar   Search for similar past events (main query)
  GET  /api/historical/all       List all stored historical events
  GET  /api/historical/{id}      Get a single historical event by ID
  POST /api/historical/store     Store a new event (manual or auto)
  GET  /api/historical/stats     Memory stats (count, categories, date range)
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.core.security import require_admin_key

log = structlog.get_logger(__name__)
router = APIRouter()

_CACHE_KEY = "historical:similar:{hash}"
_CACHE_TTL = 300  # 5 minutes


@router.get("/similar")
async def get_similar_events(
    category:             Optional[str]  = Query(None),
    sectors:              Optional[str]  = Query(None, description="Comma-separated"),
    sentiment:            Optional[str]  = Query(None),
    market_regime:        Optional[str]  = Query(None),
    interest_rate_trend:  Optional[str]  = Query(None),
    crude_trend:          Optional[str]  = Query(None),
    limit:                int            = Query(default=10, ge=1, le=20),
    min_similarity:       float          = Query(default=20.0, ge=0.0, le=100.0),
):
    """
    Find the top similar historical market events.

    Use this to replace AI hallucinations with verified historical evidence.
    Pass the attributes of the current event — returns ranked past matches.
    """
    query = {
        "category":            category,
        "sectors":             [s.strip() for s in sectors.split(",")] if sectors else [],
        "sentiment":           sentiment,
        "market_regime":       market_regime,
        "interest_rate_trend": interest_rate_trend,
        "crude_trend":         crude_trend,
    }

    # Cache key from query fingerprint
    import hashlib, json
    cache_key = _CACHE_KEY.format(
        hash=hashlib.md5(json.dumps(query, sort_keys=True).encode()).hexdigest()[:12]
    )

    try:
        from app.core.redis import cache_get
        cached = await cache_get(cache_key)
        if cached:
            return {"events": cached, "source": "cache", "count": len(cached)}
    except Exception:
        pass

    try:
        from app.services.historical_memory_service import find_similar_events
        events = await find_similar_events(query, limit=limit, min_similarity=min_similarity)

        try:
            from app.core.redis import cache_set
            await cache_set(cache_key, events, ttl=_CACHE_TTL)
        except Exception:
            pass

        return {"events": events, "source": "db", "count": len(events), "query": query}
    except Exception as exc:
        log.warning("historical.similar_error", error=str(exc))
        raise HTTPException(status_code=503, detail=f"Historical memory unavailable: {exc}")


@router.get("/all")
async def list_all_events(
    limit:    int = Query(default=50, ge=1, le=200),
    category: Optional[str] = Query(None),
):
    """List all stored historical events, optionally filtered by category.

    Each event's `historical_score`/`stars` is computed from its full
    category group (not just the returned page) so filtering/pagination
    never skews the real per-category aggregate math behind it.
    """
    try:
        from datetime import datetime, timezone
        from app.services.historical_memory_service import (
            compute_category_pattern, compute_historical_score, compute_avg_similarity,
        )
        from app.db.session import AsyncSessionLocal
        from app.db.models.historical_memory import HistoricalMarketEvent
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            all_rows = (await db.execute(select(HistoricalMarketEvent))).scalars().all()

        by_category: dict[str, list] = {}
        for r in all_rows:
            by_category.setdefault(r.category, []).append(r)

        display = sorted(all_rows, key=lambda r: r.event_date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        if category:
            display = [r for r in display if r.category == category]
        display = display[:limit]

        pattern_cache: dict[str, dict] = {}

        def _score_for(r) -> dict:
            group = by_category[r.category]
            pat = pattern_cache.get(r.category)
            if pat is None:
                pat = compute_category_pattern(group, current_id="")
                pattern_cache[r.category] = pat
            similarity = compute_avg_similarity(r, group)
            return compute_historical_score(r, group, pat, similarity)

        return {
            "events": [
                {
                    "id":            r.id,
                    "event_title":   r.event_title,
                    "event_date":    r.event_date.strftime("%b %d, %Y") if r.event_date else None,
                    "category":      r.category,
                    "sentiment":     r.sentiment,
                    "sectors":       r.sectors,
                    "nifty_1w":      r.nifty_1w,
                    "nifty_1m":      r.nifty_1m,
                    "opportunity_score": r.opportunity_score,
                    "risk_score":    r.risk_score,
                    "historical_score": _score_for(r),
                }
                for r in display
            ],
            "count": len(display),
        }
    except Exception as exc:
        log.warning("historical.list_error", error=str(exc))
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/stats")
async def memory_stats():
    """Memory health — total count, categories covered, date range."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.historical_memory import HistoricalMarketEvent
        from sqlalchemy import select, func, distinct

        async with AsyncSessionLocal() as db:
            total = (await db.execute(
                select(func.count()).select_from(HistoricalMarketEvent)
            )).scalar_one()

            rows = (await db.execute(
                select(HistoricalMarketEvent.category,
                       func.count(HistoricalMarketEvent.id).label("cnt"))
                .group_by(HistoricalMarketEvent.category)
                .order_by(func.count(HistoricalMarketEvent.id).desc())
            )).all()

            dates = (await db.execute(
                select(func.min(HistoricalMarketEvent.event_date),
                       func.max(HistoricalMarketEvent.event_date))
            )).one()

        return {
            "total_events":   total,
            "categories":     [{"category": r[0], "count": r[1]} for r in rows],
            "date_range": {
                "earliest": dates[0].strftime("%b %d, %Y") if dates[0] else None,
                "latest":   dates[1].strftime("%b %d, %Y") if dates[1] else None,
            },
        }
    except Exception as exc:
        log.warning("historical.stats_error", error=str(exc))
        raise HTTPException(status_code=503, detail=str(exc))


def _nearest_point(series: list[dict], target: "date", tolerance_days: int = 7):
    """Nearest real trading-day point to `target`, or None if the closest
    point available is further than `tolerance_days` away — e.g. a +90D
    window for an event that happened last week genuinely has no data yet,
    and should read as unavailable rather than silently reusing whatever
    the nearest (much closer) point happens to be."""
    from datetime import datetime as _dt
    best, best_diff = None, None
    for p in series:
        d = _dt.strptime(p["date"], "%Y-%m-%d").date()
        diff = abs((d - target).days)
        if best_diff is None or diff < best_diff:
            best_diff, best = diff, p
    if best is None or best_diff > tolerance_days:
        return None
    return best


def _compute_window_returns(series: list[dict], event_date: "date") -> dict:
    """Real, standardized before/after return windows computed from the
    actual fetched daily series — Before: 7D/30D/90D pre-event, After:
    1D/7D/30D/90D post-event. A window is omitted (None) rather than
    approximated when no real trading day exists close enough to it."""
    from datetime import timedelta as _td

    event_pt = _nearest_point(series, event_date, tolerance_days=5)
    if not event_pt or not event_pt["value"]:
        return {"before": {}, "after": {}}
    event_price = event_pt["value"]

    before = {}
    for label, days in [("7d", 7), ("30d", 30), ("90d", 90)]:
        p = _nearest_point(series, event_date - _td(days=days))
        before[label] = round((event_price - p["value"]) / p["value"] * 100, 2) if p and p["value"] else None

    after = {}
    for label, days in [("1d", 1), ("7d", 7), ("30d", 30), ("90d", 90)]:
        p = _nearest_point(series, event_date + _td(days=days))
        after[label] = round((p["value"] - event_price) / event_price * 100, 2) if p and p["value"] else None

    return {"before": before, "after": after}


_RANGE_AFTER_DAYS = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}


@router.get("/{event_id}/chart")
async def get_event_nifty_chart(event_id: str, range: str = Query("1Y", pattern="^(1M|3M|6M|1Y)$")):
    """Real daily NIFTY 50 closes around the event, plus standardized
    before/after window returns computed from that same real series — the
    seed events only store 4 discrete aggregate returns (nifty_1d/3d/1w/1m),
    not a daily series or a 90-day-before figure, so both the chart line
    and the window stats need their own live yfinance query.

    Always fetches a fixed wide window (95 days before, 380 days after —
    enough to cover a 1Y display range and every standardized window) in a
    single call; `range` only controls how much of that same real series is
    returned for charting, so switching ranges client-side needs no extra
    backend round-trip.
    """
    import math
    from datetime import timedelta
    import yfinance as yf
    from app.db.session import AsyncSessionLocal
    from app.db.models.historical_memory import HistoricalMarketEvent
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(HistoricalMarketEvent).where(HistoricalMarketEvent.id == event_id)
        )).scalar_one_or_none()

    if not row or not row.event_date:
        raise HTTPException(status_code=404, detail="Historical event not found")

    event_date = row.event_date.date() if hasattr(row.event_date, "date") else row.event_date
    fetch_start = row.event_date - timedelta(days=95)
    fetch_end = row.event_date + timedelta(days=380)

    def _fetch() -> list[dict]:
        try:
            hist = yf.download("^NSEI", start=fetch_start, end=fetch_end, interval="1d",
                                progress=False, auto_adjust=True, timeout=15)
            if hist.empty:
                return []
            out = []
            for idx, r in hist.iterrows():
                try:
                    close = r["Close"]
                    if hasattr(close, "iloc"):
                        close = close.iloc[0]
                    v = float(close)
                    if math.isnan(v) or math.isinf(v):
                        continue
                    out.append({"date": str(idx.date()), "value": round(v, 2)})
                except Exception:
                    continue
            return out
        except Exception as exc:
            log.warning("historical.chart_fetch_failed", event_id=event_id, error=str(exc))
            return []

    # yfinance's own `timeout=` param only bounds the final data-download
    # call — its internal session/cookie/crumb requests have historically
    # not always honored it, which can hang the executor thread with no
    # outer bound. wait_for() can't force-kill that OS thread (a Python
    # ThreadPoolExecutor limitation), but it does stop THIS request from
    # blocking on it forever, which is what actually matters here.
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        full_series = await asyncio.wait_for(loop.run_in_executor(None, _fetch), timeout=20)
    except asyncio.TimeoutError:
        log.warning("historical.chart_fetch_timeout", event_id=event_id)
        full_series = []

    windows = _compute_window_returns(full_series, event_date)

    from datetime import datetime as _dt
    after_days = _RANGE_AFTER_DAYS[range]
    display_start = (row.event_date - timedelta(days=30)).date()
    display_end = (row.event_date + timedelta(days=after_days)).date()
    display_series = [
        p for p in full_series
        if display_start <= _dt.strptime(p["date"], "%Y-%m-%d").date() <= display_end
    ]

    return {
        "event_id": event_id,
        "event_date": row.event_date.strftime("%Y-%m-%d"),
        "range": range,
        "series": display_series,
        "full_series": full_series,
        "windows": windows,
    }


@router.get("/{event_id}")
async def get_event(event_id: str):
    """Get full detail of a single historical event."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.historical_memory import HistoricalMarketEvent
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(HistoricalMarketEvent).where(HistoricalMarketEvent.id == event_id)
            )).scalar_one_or_none()

            if not row:
                raise HTTPException(status_code=404, detail="Historical event not found")

            # Cross-event pattern stats — every other stored event sharing
            # this category, aggregated honestly (see compute_category_
            # pattern's docstring on how n=1 degrades).
            from app.services.historical_memory_service import (
                compute_category_pattern, compute_pattern_snapshot,
                compute_historical_score, compute_avg_similarity,
            )
            cat_rows = (await db.execute(
                select(HistoricalMarketEvent).where(HistoricalMarketEvent.category == row.category)
            )).scalars().all()
            pattern = compute_category_pattern(cat_rows, current_id=row.id)
            pattern_snapshot = compute_pattern_snapshot(row, cat_rows, pattern)
            similarity = compute_avg_similarity(row, cat_rows)
            historical_score = compute_historical_score(row, cat_rows, pattern, similarity)

            # Attach each timeline entry's own real historical_score too —
            # "Similar Historical Patterns" renders these as star ratings,
            # which should be the same disclosed formula, not opportunity_score.
            rows_by_id = {r.id: r for r in cat_rows}
            for item in pattern["timeline"]:
                r = rows_by_id.get(item["id"])
                if r is not None:
                    r_sim = compute_avg_similarity(r, cat_rows)
                    item["historical_score"] = compute_historical_score(r, cat_rows, pattern, r_sim)

        # Real, deterministic verdict — same engine Opportunity Radar uses
        # (opportunity_score/confidence/risk/trend all real fields on this
        # row already), not a separate invented rating for this page.
        verdict = None
        if row.opportunity_score is not None and row.confidence is not None:
            from app.services.opportunity_intelligence import compute_investment_verdict
            risk_level = "High" if (row.risk_score or 0) >= 60 else "Medium" if (row.risk_score or 0) >= 30 else "Low"
            trend = "up" if row.sentiment == "bullish" else "down" if row.sentiment == "bearish" else "neutral"
            verdict = compute_investment_verdict(
                opportunity_score=row.opportunity_score, confidence=row.confidence,
                risk_level=risk_level, trend=trend,
            )

        return {
            "id":                  row.id,
            "event_title":         row.event_title,
            "event_date":          row.event_date.strftime("%b %d, %Y") if row.event_date else None,
            "category":            row.category,
            "sentiment":           row.sentiment,
            "sectors":             row.sectors,
            "companies":           row.companies,
            "tags":                row.tags,
            "market_regime":       row.market_regime,
            "interest_rate_trend": row.interest_rate_trend,
            "crude_trend":         row.crude_trend,
            "interest_rate_level": row.interest_rate_level,
            "vix_level":           row.vix_level,
            "nifty_1d":            row.nifty_1d,
            "nifty_3d":            row.nifty_3d,
            "nifty_1w":            row.nifty_1w,
            "nifty_1m":            row.nifty_1m,
            "sector_reactions":    row.sector_reactions,
            "historical_winners":  row.historical_winners,
            "historical_losers":   row.historical_losers,
            "opportunity_score":   row.opportunity_score,
            "risk_score":          row.risk_score,
            "confidence":          row.confidence,
            "what_happened":       row.what_happened,
            "key_lesson":          row.key_lesson,
            "source":              row.source,
            "verdict":             verdict,
            "pattern":             pattern,
            "pattern_snapshot":    pattern_snapshot,
            "historical_score":    historical_score,
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("historical.get_error", error=str(exc))
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/store", dependencies=[Depends(require_admin_key)])
async def store_event(body: dict):
    """
    Store a new historical market event.
    Called automatically by TriageWorker for high-urgency events (via a
    direct function call, not this HTTP route) — this endpoint itself is
    only for manual/ops use, hence admin-gated: anything unauthenticated
    could write bogus rows into data the AI treats as verified ground truth.
    """
    required = ["event_title", "event_date", "category"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=422, detail=f"Missing required field: {field}")

    try:
        # Parse date string if necessary
        from datetime import datetime, timezone
        if isinstance(body.get("event_date"), str):
            body["event_date"] = datetime.fromisoformat(
                body["event_date"].replace("Z", "+00:00")
            )

        from app.services.historical_memory_service import store_event as _store
        event_id = await _store(body)

        # Invalidate similarity caches
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            if r:
                keys = await r.keys("historical:similar:*")
                if keys:
                    await r.delete(*keys)
        except Exception:
            pass

        return {"stored": True, "id": event_id}
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("historical.store_api_error", error=str(exc))
        raise HTTPException(status_code=503, detail=str(exc))
