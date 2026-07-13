"""
Market Intelligence Engine — unified API.

Single source of truth for every page and component in the application.
The UI must never calculate intelligence independently — it must consume from here.

Endpoints
---------
GET /api/mie/state              Full intelligence state (all producers aggregated)
GET /api/mie/state/refresh      Force-refresh the state (internal/admin use)
GET /api/mie/context/{symbol}   Intelligence context for a specific NSE symbol
GET /api/mie/feed               Real-time intelligence feed (events ranked by urgency)
GET /api/mie/status             Engine health — last refresh time + cache status
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.intelligence.engine import (
    get_intelligence_state,
    get_symbol_context,
    refresh_mie_state,
    _read_top_events,
    _market_session,
)

router = APIRouter()


# ── Full intelligence state ────────────────────────────────────────────────────

@router.get("/state")
async def mie_state():
    """
    Return the complete current intelligence state.

    This is the primary endpoint. Every page should call this instead of
    making isolated calls to /api/stories, /api/themes, or /api/events.

    Response shape:
      generated_at    — ISO timestamp of last computation
      market_session  — "pre_market" | "live" | "post_market" | "weekend"
      is_market_open  — bool
      story           — market narrative (mood, direction, confidence, etc.)
      themes          — top 8 active investment themes with scores
      top_events      — top 12 triaged events (urgency ≥ 4, last 8 hours)
      signals         — synthesised signals (risk_level, breadth, critical_alerts)
      sector_themes   — sectors ranked by composite theme score
      event_sectors   — sectors ranked by recent event frequency
    """
    try:
        state = await get_intelligence_state()
        return state
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Intelligence engine unavailable: {e}")


@router.post("/state/refresh")
async def mie_force_refresh():
    """Force-recompute and cache the intelligence state. Use after bulk ingest."""
    try:
        state = await refresh_mie_state()
        return {
            "refreshed": True,
            "generated_at": state["generated_at"],
            "market_session": state["market_session"],
            "events_loaded": len(state.get("top_events", [])),
            "themes_loaded": len(state.get("themes", [])),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Refresh failed: {e}")


# ── Symbol context ─────────────────────────────────────────────────────────────

@router.get("/context/{symbol}")
async def mie_symbol_context(symbol: str):
    """
    Return intelligence context for a specific NSE stock symbol.

    Filters the global state to events and themes relevant to this symbol.
    Use on company pages, stock research flows, and AI search company cards.

    Response shape:
      symbol           — normalised NSE symbol
      story            — full market narrative
      signals          — market-level signals (mood, direction, risk_level)
      related_events   — events that mention this ticker (up to 6)
      related_themes   — active themes that include this stock (up to 4)
      market_mood      — current market mood string
      market_direction — "up" | "down" | "sideways"
    """
    if not symbol or not symbol.strip():
        raise HTTPException(status_code=400, detail="Symbol required")
    try:
        return await get_symbol_context(symbol.strip().upper())
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Context unavailable: {e}")


# ── Live intelligence feed ─────────────────────────────────────────────────────

@router.get("/feed")
async def mie_feed(
    limit: int = Query(default=20, ge=1, le=50),
    min_urgency: int = Query(default=4, ge=1, le=10),
    hours: int = Query(default=8, ge=1, le=48),
):
    """
    Real-time intelligence feed — triaged events ranked by urgency.

    This is the live pulse of the market. High urgency (≥7) events are
    breaking alerts. Medium urgency (4-6) are informational.

    Use on:
      • Homepage live feed widget
      • Events page "Breaking" tab
      • AI Search live context injection
      • Breaking Market Alert banner
    """
    try:
        from datetime import datetime, timezone, timedelta
        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import EventTriage
        from sqlalchemy import select

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(EventTriage)
                .where(EventTriage.triaged_at >= cutoff)
                .where(EventTriage.urgency >= min_urgency)
                .order_by(EventTriage.urgency.desc(), EventTriage.triaged_at.desc())
                .limit(limit)
            )).scalars().all()

        return {
            "feed": [
                {
                    "id":            r.event_id,
                    "headline":      r.headline,
                    "one_liner":     r.one_liner,
                    "urgency":       r.urgency,
                    "sentiment":     r.sentiment,
                    "market_impact": r.market_impact,
                    "direction":     r.direction,
                    "sectors":       r.sectors or [],
                    "tickers":       r.tickers or [],
                    "is_structural": r.is_structural,
                    "broadcast":     r.broadcast,
                    "triaged_at":    r.triaged_at.isoformat() if r.triaged_at else None,
                }
                for r in rows
            ],
            "count":       len(rows),
            "min_urgency": min_urgency,
            "hours":       hours,
            "market_session": _market_session(),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Feed unavailable: {e}")


# ── Engine status ──────────────────────────────────────────────────────────────

@router.get("/status")
async def mie_status():
    """
    Engine health check — last refresh time, cache status, producer status.

    Use this to show staleness indicators in the UI and for monitoring.
    """
    from app.core.redis import get_redis, cache_get as _get

    redis_ok = False
    state_age_seconds: int | None = None
    state_session: str | None = None

    try:
        r = await get_redis()
        redis_ok = r is not None
    except Exception:
        pass

    try:
        cached = await _get("mie:state:v1")
        if cached and isinstance(cached, dict):
            from datetime import datetime, timezone
            gen = cached.get("generated_at")
            if gen:
                dt  = datetime.fromisoformat(gen.replace("Z", "+00:00"))
                state_age_seconds = int((datetime.now(timezone.utc) - dt).total_seconds())
            state_session = cached.get("market_session")
    except Exception:
        pass

    return {
        "engine":             "Market Intelligence Engine v1",
        "market_session":     _market_session(),
        "redis_connected":    redis_ok,
        "state_cached":       state_age_seconds is not None,
        "state_age_seconds":  state_age_seconds,
        "state_session":      state_session,
        "is_fresh":           (state_age_seconds or 9999) < 360,
    }
