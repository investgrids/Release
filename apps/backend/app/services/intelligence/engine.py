"""
Market Intelligence Engine — the single source of truth for the entire application.

Reads from the four existing intelligence producers:
  • MarketStory  (StoryEngineWorker)   → narrative, mood, confidence
  • ThemeState   (ThemeWorker)         → active investment themes
  • EventTriage  (TriageWorker)        → real-time event scores
  • MarketSnapshot (PriceMonitor)      → price context

Synthesises them into ONE IntelligenceState object that every page, component,
and API can consume. No caller should compute intelligence on its own.

Cache key: mie:state:v1  (TTL 5 min during market hours, 30 min otherwise)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import structlog

from app.core.redis import cache_get, cache_set

log = structlog.get_logger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))

_STATE_KEY   = "mie:state:v1"
_CONTEXT_KEY = "mie:context:{symbol}"  # per-symbol context

# ── Market session helper ──────────────────────────────────────────────────────

def _market_session() -> str:
    now  = datetime.now(_IST)
    h, m = now.hour, now.minute
    mins = h * 60 + m
    dow  = now.weekday()        # 0=Monday … 6=Sunday
    if dow >= 5:
        return "weekend"
    if mins < 9 * 60 + 15:
        return "pre_market"
    if mins <= 15 * 60 + 30:
        return "live"
    return "post_market"


def _cache_ttl() -> int:
    """Short TTL during live session, longer otherwise."""
    s = _market_session()
    return 300 if s == "live" else 1800


# ── Intelligence readers ───────────────────────────────────────────────────────

async def _read_story() -> Optional[dict]:
    """Redis-first read of the latest market story."""
    raw = await cache_get("market:story:latest")
    if raw:
        return raw if isinstance(raw, dict) else None

    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import MarketStory
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(MarketStory).order_by(MarketStory.generated_at.desc()).limit(1)
            )).scalars().first()
            if row:
                return {
                    "text":           row.story,
                    "mood":           row.mood,
                    "pulse":          row.pulse,
                    "direction":      row.direction,
                    "opportunity":    row.opportunity,
                    "risk":           row.risk,
                    "trader_watch":   row.trader_watch,
                    "investor_watch": row.investor_watch,
                    "confidence":     row.confidence,
                    "sector_rotation": row.sector_rotation,
                    "generated_at":   row.generated_at.isoformat() if row.generated_at else None,
                }
    except Exception as e:
        log.warning("mie.story_read_error", error=str(e))
    return None


async def _read_themes() -> list[dict]:
    """Redis-first read of ranked themes."""
    raw = await cache_get("market:themes:ranked")
    if isinstance(raw, list):
        return raw[:8]

    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import ThemeState
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(ThemeState).order_by(ThemeState.score.desc()).limit(8)
            )).scalars().all()
            return [
                {
                    "theme":       r.theme,
                    "score":       r.score,
                    "momentum":    r.momentum,
                    "top_stocks":  r.top_stocks or [],
                    "price_signal": r.price_signal,
                    "news_signal":  r.news_signal,
                    "news_count":   r.news_count_24h,
                    "updated_at":  r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in rows
            ]
    except Exception as e:
        log.warning("mie.themes_read_error", error=str(e))
    return []


async def _read_top_events(limit: int = 12) -> list[dict]:
    """Latest triaged events ranked by urgency — the real-time intelligence pulse."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import EventTriage
        from sqlalchemy import select
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=8)
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(EventTriage)
                .where(EventTriage.triaged_at >= cutoff)
                .where(EventTriage.urgency >= 4)
                .order_by(EventTriage.urgency.desc(), EventTriage.triaged_at.desc())
                .limit(limit)
            )).scalars().all()
            return [
                {
                    "id":            r.event_id,
                    "headline":      r.headline,
                    "one_liner":     r.one_liner,
                    "urgency":       r.urgency,
                    "importance":    r.importance,
                    "confidence":    r.confidence,
                    "sentiment":     r.sentiment,
                    "horizon":       r.horizon,
                    "market_impact": r.market_impact,
                    "direction":     r.direction,
                    "is_structural": r.is_structural,
                    "sectors":       r.sectors or [],
                    "themes":        r.themes or [],
                    "tickers":       r.tickers or [],
                    "broadcast":     r.broadcast,
                    "triaged_at":    r.triaged_at.isoformat() if r.triaged_at else None,
                }
                for r in rows
            ]
    except Exception as e:
        log.warning("mie.events_read_error", error=str(e))
    return []


def _synthesise_signals(
    story: Optional[dict],
    themes: list[dict],
    events: list[dict],
) -> dict:
    """Derive a set of simple market signals from the aggregated data."""
    mood = story.get("mood", "Neutral") if story else "Neutral"
    confidence = story.get("confidence", 50) if story else 50
    direction = (story.get("direction", "sideways") if story else "sideways").lower()

    # Risk level from mood and direction
    if "bear" in mood.lower() or "panic" in mood.lower():
        risk_level = "HIGH"
    elif "bull" in mood.lower():
        risk_level = "LOW"
    else:
        risk_level = "MODERATE"

    # Top theme
    top_theme = themes[0] if themes else None

    # Event count by sentiment
    bullish_count  = sum(1 for e in events if e.get("sentiment") == "bullish")
    bearish_count  = sum(1 for e in events if e.get("sentiment") == "bearish")
    total_events   = len(events)
    breadth = (
        "advancing" if bullish_count > bearish_count
        else "declining" if bearish_count > bullish_count
        else "mixed"
    )

    # High-urgency event count
    critical_events = [e for e in events if e.get("urgency", 0) >= 7]

    # Structural count (long-term implications)
    structural_count = sum(1 for e in events if e.get("is_structural"))

    return {
        "mood":              mood,
        "direction":         direction,
        "risk_level":        risk_level,
        "confidence":        confidence,
        "top_theme":         top_theme["theme"] if top_theme else None,
        "top_theme_score":   top_theme["score"] if top_theme else 0,
        "breadth":           breadth,
        "bullish_events":    bullish_count,
        "bearish_events":    bearish_count,
        "total_events":      total_events,
        "critical_alerts":   len(critical_events),
        "structural_shifts": structural_count,
    }


# ── Core engine ───────────────────────────────────────────────────────────────

async def compute_intelligence_state() -> dict:
    """
    Build the full intelligence state from all producers.
    Called by refresh_mie_state() on a schedule and on cache miss.
    """
    import asyncio
    story, themes, events = await asyncio.gather(
        _read_story(),
        _read_themes(),
        _read_top_events(),
    )

    session = _market_session()
    signals = _synthesise_signals(story, themes, events)

    # Sector roll-up from themes (ranked)
    sectors_from_themes = [
        {"name": t["theme"], "score": t["score"], "momentum": t["momentum"]}
        for t in themes
    ]

    # Affected sectors from events (de-duped, ranked by frequency)
    sector_freq: dict[str, int] = {}
    for ev in events:
        for s in (ev.get("sectors") or []):
            sector_freq[s] = sector_freq.get(s, 0) + 1
    event_sectors = [
        {"name": k, "event_count": v}
        for k, v in sorted(sector_freq.items(), key=lambda x: -x[1])
    ][:8]

    return {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "market_session": session,
        "is_market_open": session == "live",
        "story":          story,
        "themes":         themes,
        "top_events":     events,
        "signals":        signals,
        "sector_themes":  sectors_from_themes,
        "event_sectors":  event_sectors,
    }


async def refresh_mie_state() -> dict:
    """Compute a fresh state and write it to the cache. Called by the scheduler."""
    try:
        state = await compute_intelligence_state()
        ttl   = _cache_ttl()
        await cache_set(_STATE_KEY, state, ttl=ttl)
        log.info("mie.state_refreshed",
                 session=state["market_session"],
                 themes=len(state["themes"]),
                 events=len(state["top_events"]),
                 ttl=ttl)
        return state
    except Exception as e:
        log.error("mie.refresh_error", error=str(e))
        raise


async def get_intelligence_state(force_refresh: bool = False) -> dict:
    """
    Return the current intelligence state.
    Serves from cache when available; computes on miss.
    """
    if not force_refresh:
        cached = await cache_get(_STATE_KEY)
        if cached and isinstance(cached, dict):
            return cached
    return await refresh_mie_state()


async def get_symbol_context(symbol: str) -> dict:
    """
    Derive intelligence context for a specific NSE symbol.
    Filters the global state to events and themes relevant to that symbol.
    """
    cache_key = _CONTEXT_KEY.format(symbol=symbol.upper())
    cached = await cache_get(cache_key)
    if cached and isinstance(cached, dict):
        return cached

    sym_upper = symbol.upper()
    state     = await get_intelligence_state()

    # Events that mention this ticker
    related_events = [
        e for e in state.get("top_events", [])
        if sym_upper in [t.upper() for t in (e.get("tickers") or [])]
        or sym_upper in (e.get("headline", "") + " " + (e.get("one_liner") or "")).upper()
    ]

    # Themes whose top_stocks include this ticker
    related_themes = [
        t for t in state.get("themes", [])
        if sym_upper in [s.upper() for s in (t.get("top_stocks") or [])]
    ]

    context = {
        "symbol":          sym_upper,
        "generated_at":    state["generated_at"],
        "market_session":  state["market_session"],
        "story":           state.get("story"),
        "signals":         state.get("signals"),
        "related_events":  related_events[:6],
        "related_themes":  related_themes[:4],
        "market_mood":     state.get("signals", {}).get("mood", "Neutral"),
        "market_direction": state.get("signals", {}).get("direction", "sideways"),
    }

    await cache_set(cache_key, context, ttl=300)
    return context
