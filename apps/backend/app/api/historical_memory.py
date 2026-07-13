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
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

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
    """List all stored historical events, optionally filtered by category."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.historical_memory import HistoricalMarketEvent
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            q = select(HistoricalMarketEvent).order_by(desc(HistoricalMarketEvent.event_date))
            if category:
                q = q.where(HistoricalMarketEvent.category == category)
            rows = (await db.execute(q.limit(limit))).scalars().all()

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
                }
                for r in rows
            ],
            "count": len(rows),
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
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("historical.get_error", error=str(exc))
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/store")
async def store_event(body: dict):
    """
    Store a new historical market event.
    Called automatically by TriageWorker for high-urgency events,
    or manually via the admin panel.
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
