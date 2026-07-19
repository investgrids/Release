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

async def read_story() -> Optional[dict]:
    """
    Redis-first read of the latest market story. This is the single source of
    truth for `market:story:latest` — other modules (intelligence_market.py's
    /story route, aipe/market_story_engine.py's get_mie_context()) call this
    instead of independently reading and re-parsing the same Redis key.
    """
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


# Backward-compatible private alias for any remaining internal callers.
_read_story = read_story


async def read_themes() -> list[dict]:
    """
    Redis-first read of ranked themes. Single source of truth for
    `market:themes:ranked` — see read_story() docstring for why.
    """
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


# Backward-compatible private alias for any remaining internal callers.
_read_themes = read_themes


async def read_top_events(limit: int = 12, min_urgency: int = 4, hours: int = 8) -> list[dict]:
    """
    Latest triaged events ranked by urgency — the real-time intelligence pulse.
    Every event is annotated with a priority_score (0-100) and priority_tier
    (Critical/High/Medium/Low) from the Intelligence Priority Queue — see
    _compute_priority(). Callers that only want homepage-grade signal should
    filter to priority_tier in ("Critical", "High"); this function itself
    returns the full urgency>=min_urgency set so Events-page search and the
    live feed are unaffected by the homepage-facing filter.
    """
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import EventTriage
        from sqlalchemy import select
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(EventTriage)
                .where(EventTriage.triaged_at >= cutoff)
                .where(EventTriage.urgency >= min_urgency)
                .order_by(EventTriage.urgency.desc(), EventTriage.triaged_at.desc())
                .limit(limit)
            )).scalars().all()
            events = []
            for r in rows:
                priority_score, priority_tier = _compute_priority(r.urgency, r.importance, None, r.headline)
                events.append({
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
                    "source":        r.source,
                    "triaged_at":    r.triaged_at.isoformat() if r.triaged_at else None,
                    "priority_score": priority_score,
                    "priority_tier":  priority_tier,
                })
            return events
    except Exception as e:
        log.warning("mie.events_read_error", error=str(e))
    return []


# Backward-compatible private alias — old call sites within this module used
# the underscore name before these readers became the shared public surface.
_read_top_events = read_top_events


def _compute_priority(urgency: int | None, importance: int | None, category: str | None, headline: str | None) -> tuple[int, str]:
    """
    Intelligence Priority Queue — every event gets a 0-100 priority score and a tier:
      Critical (95-100): RBI, Budget, War, Fed, major policy
      High     (80-94):  Earnings, Government, large deals
      Medium   (60-79):  Sector news, analyst changes
      Low      (<60):    Routine exchange filings, director changes, compliance filings

    Base score comes from the triage worker's own urgency/importance (1-10 each,
    already reflects the AI's read of event significance). A small keyword floor
    ensures the named always-critical/high categories land in the right tier even
    when the raw urgency score alone would place them lower.
    """
    base = round(((urgency or 0) + (importance or 0)) / 2 * 10)

    text = f"{category or ''} {headline or ''}".lower()
    if any(k in text for k in (
        "rbi", "repo rate", "monetary policy", "budget", "war", "fed ", "federal reserve",
    )):
        base = max(base, 95)
    elif any(k in text for k in (
        "earnings", "results", "government", "acquisition", "merger", "block deal", "bulk deal",
    )):
        base = max(base, 80)

    base = min(base, 100)
    if base >= 95:
        tier = "Critical"
    elif base >= 80:
        tier = "High"
    elif base >= 60:
        tier = "Medium"
    else:
        tier = "Low"
    return base, tier


# Public name — other modules (e.g. the AIPE publisher) that need to classify
# events by the same Critical/High/Medium/Low priority tiers should import
# this instead of re-implementing the cutoffs.
compute_priority = _compute_priority


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


async def read_opportunities(limit: int = 5) -> list[dict]:
    """
    Top-ranked opportunities from the real Opportunity Engine (the same
    OpportunityService that backs /api/radar) — not re-derived here, just
    read through, so "biggest opportunity" always matches what the
    Opportunity Radar page itself shows.
    """
    try:
        from app.db.session import AsyncSessionLocal
        from app.services.opportunity_service import OpportunityService
        async with AsyncSessionLocal() as db:
            result = await OpportunityService(db).list_opportunities(page=1, page_size=limit)
            return [
                {
                    "id":                o.id,
                    "slug":              o.slug,
                    "title":             o.title,
                    "summary":           o.summary,
                    "opportunity_score": o.opportunity_score,
                    "confidence":        o.confidence,
                    "trend":             o.trend,
                    "risk_level":        o.risk_level,
                    "sectors":           o.sectors or [],
                }
                for o in result.items
            ]
    except Exception as e:
        log.warning("mie.opportunities_read_error", error=str(e))
    return []


async def read_upcoming_calendar(limit: int = 5) -> list[dict]:
    """Upcoming scheduled events (earnings, RBI, global, expiry) for Tomorrow Watch."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.db import crud
        async with AsyncSessionLocal() as db:
            rows = await crud.get_calendar(db)
        today = datetime.now(_IST).date()
        upcoming: list[tuple] = []
        for r in rows:
            try:
                d = datetime.strptime(r.date, "%b %d, %Y").date()
            except (ValueError, TypeError):
                continue
            if d >= today:
                upcoming.append((d, {
                    "id": r.id, "category": r.category, "title": r.title,
                    "date": r.date, "description": r.description,
                }))
        upcoming.sort(key=lambda x: x[0])
        return [item for _, item in upcoming[:limit]]
    except Exception as e:
        log.warning("mie.calendar_read_error", error=str(e))
    return []


def _compute_market_health(signals: dict) -> dict:
    """
    0-100 composite health score from mood, breadth, and confidence. This is
    the same set of inputs LiveMarketTab's frontend computeHealthScore() used
    to derive independently per-page — moved here so it's computed once and
    every consumer reads the same number.
    """
    score = 50.0
    mood = (signals.get("mood") or "").lower()
    if "bull" in mood:
        score += 15
    elif "bear" in mood:
        score -= 15

    breadth = signals.get("breadth")
    if breadth == "advancing":
        score += 15
    elif breadth == "declining":
        score -= 15

    confidence = signals.get("confidence")
    if confidence is not None:
        score += (confidence - 50) * 0.2

    score = max(0, min(100, round(score)))
    if score >= 70:
        label = "Healthy"
    elif score >= 50:
        label = "Mixed"
    elif score >= 30:
        label = "Weak"
    else:
        label = "Stressed"
    return {"score": score, "label": label}


def _derive_biggest_risk(story: Optional[dict], events: list[dict]) -> Optional[dict]:
    """
    The most urgent bearish event currently on the radar, or — if none —
    the AI market story's own risk narrative. Never fabricated: returns None
    if neither real source has anything to say.
    """
    bearish = sorted(
        (e for e in events if e.get("sentiment") == "bearish"),
        key=lambda e: -(e.get("urgency") or 0),
    )
    if bearish:
        top = bearish[0]
        return {
            "headline":   top.get("headline"),
            "reason":     top.get("one_liner") or top.get("headline"),
            "sectors":    top.get("sectors") or [],
            "tickers":    top.get("tickers") or [],
            "confidence": top.get("confidence"),
        }
    if story and story.get("risk"):
        return {
            "headline":   None,
            "reason":     story["risk"],
            "sectors":    [],
            "tickers":    [],
            "confidence": story.get("confidence"),
        }
    return None


def _derive_companies_to_watch(events: list[dict], limit: int = 8) -> list[dict]:
    """
    Companies to watch, derived once from the same homepage-grade (Critical/
    High priority) events every page already ranks — replaces the pattern of
    each page (homepage, Live Market, After Market) independently deriving
    its own "top companies from top events" list.
    """
    seen: set[str] = set()
    out: list[dict] = []
    for e in events:
        for t in (e.get("tickers") or []):
            if t in seen:
                continue
            seen.add(t)
            out.append({
                "ticker":     t,
                "why":        e.get("one_liner") or e.get("headline"),
                "impact":     e.get("priority_score"),
                "confidence": e.get("confidence"),
            })
            if len(out) >= limit:
                return out
    return out


# ── Core engine ───────────────────────────────────────────────────────────────

async def compute_intelligence_state() -> dict:
    """
    Build the full intelligence state from all producers.
    Called by refresh_mie_state() on a schedule and on cache miss.
    """
    import asyncio
    story, themes, events, opportunities, tomorrow_watch = await asyncio.gather(
        read_story(),
        read_themes(),
        read_top_events(),
        read_opportunities(),
        read_upcoming_calendar(),
    )

    session = _market_session()
    # Signals and sector roll-ups use the full urgency>=4 set — breadth,
    # critical-alert counts etc. should reflect everything happening, not
    # just what's homepage-worthy.
    signals = _synthesise_signals(story, themes, events)

    # Intelligence Priority Queue: only Critical/High events flow into the
    # homepage-facing top_events. Medium/Low stay fully queryable via
    # /api/events/ search — they just don't clutter the homepage.
    homepage_events = [e for e in events if e.get("priority_tier") in ("Critical", "High")]

    # Sector roll-up from themes (ranked)
    sectors_from_themes = [
        {"name": t["theme"], "score": t["score"], "momentum": t["momentum"]}
        for t in themes
    ]

    # Affected sectors from events (de-duped, ranked by frequency) — uses the
    # full event set so sector rollups aren't skewed by the homepage filter.
    sector_freq: dict[str, int] = {}
    for ev in events:
        for s in (ev.get("sectors") or []):
            sector_freq[s] = sector_freq.get(s, 0) + 1
    event_sectors = [
        {"name": k, "event_count": v}
        for k, v in sorted(sector_freq.items(), key=lambda x: -x[1])
    ][:8]

    return {
        "version":            "2.0",
        "generated_at":       datetime.now(timezone.utc).isoformat(),
        "market_session":     session,
        "is_market_open":     session == "live",
        "story":              story,
        "themes":             themes,
        "top_events":         homepage_events,
        "signals":            signals,
        "sector_themes":      sectors_from_themes,
        "event_sectors":      event_sectors,

        # Newsroom-style summary fields
        "market_bias":        signals.get("mood"),
        "market_health":      _compute_market_health(signals),
        "ai_summary":         story.get("text") if story else None,
        "biggest_opportunity": opportunities[0] if opportunities else None,
        "biggest_risk":       _derive_biggest_risk(story, events),
        "companies_to_watch": _derive_companies_to_watch(homepage_events),
        "market_drivers":     [
            {"headline": e.get("one_liner") or e.get("headline"), "urgency": e.get("urgency")}
            for e in homepage_events[:5]
        ],
        "strongest_themes":   themes[:5],
        "weakest_themes":     list(reversed(themes[-5:])) if themes else [],
        "tomorrow_watch":     tomorrow_watch,
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

    # Themes whose top_stocks include this ticker — top_stocks entries are
    # {sym, change_pct} dicts (theme_worker.py's real schema), not bare strings.
    def _stock_symbol(s: Any) -> str:
        return (s.get("sym", "") if isinstance(s, dict) else str(s)).upper()

    related_themes = [
        t for t in state.get("themes", [])
        if sym_upper in [_stock_symbol(s) for s in (t.get("top_stocks") or [])]
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
