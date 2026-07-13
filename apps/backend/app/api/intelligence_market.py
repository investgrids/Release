"""
Intelligence Market API — /api/intelligence/market/*

Note: multi_horizon.router already occupies /api/intelligence.
These endpoints mount at /api/intelligence/market/* to avoid conflict.

Endpoints:
  GET /story   — latest AI market narrative
  GET /themes  — all 12 theme scores ranked
  GET /feed    — recent intelligence feed (triage results urgency >= 4)
  GET /explain — explain a symbol/sector move
"""
from __future__ import annotations

import structlog
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query

log = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/story")
async def get_market_story():
    """Latest AI-generated market narrative (5-min conditional refresh)."""
    try:
        from app.core.redis import cache_get
        cached = await cache_get("market:story:latest")
        if cached:
            return {"story": cached, "source": "cache"}
    except Exception:
        pass

    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import MarketStory
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(MarketStory).order_by(desc(MarketStory.generated_at)).limit(1)
            )).scalar_one_or_none()

        if row:
            return {
                "story": {
                    "text":           row.story,
                    "mood":           row.mood,
                    "pulse":          row.pulse,
                    "direction":      row.direction,
                    "opportunity":    row.opportunity,
                    "risk":           row.risk,
                    "trader_watch":   row.trader_watch,
                    "investor_watch": row.investor_watch,
                    "sector_rotation": row.sector_rotation,
                    "confidence":     row.confidence,
                    "generated_at":   row.generated_at.isoformat(),
                    "story_hash":     row.story_hash,
                },
                "source": "db",
            }
    except Exception as exc:
        log.warning("intelligence.story_error", error=str(exc))

    return {"story": None, "source": "none"}


@router.get("/themes")
async def get_theme_scores():
    """All 12 theme scores ranked by composite score."""
    try:
        from app.core.redis import cache_get
        cached = await cache_get("market:themes:ranked")
        if cached:
            return {"themes": cached, "source": "cache"}
    except Exception:
        pass

    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import ThemeState
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(ThemeState).order_by(ThemeState.score.desc())
            )).scalars().all()

        return {
            "themes": [
                {
                    "theme":         t.theme,
                    "score":         t.score,
                    "momentum":      t.momentum,
                    "top_stocks":    t.top_stocks,
                    "news_count_24h": t.news_count_24h,
                    "updated_at":    t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in rows
            ],
            "source": "db",
        }
    except Exception as exc:
        log.warning("intelligence.themes_error", error=str(exc))
        return {"themes": [], "source": "error"}


@router.get("/feed")
async def get_intelligence_feed(limit: int = Query(default=20, le=50)):
    """Recent intelligence feed — triage results for the alert panel."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import EventTriage
        from sqlalchemy import select, desc

        since = datetime.now(timezone.utc) - timedelta(hours=8)
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(EventTriage)
                .where(EventTriage.triaged_at >= since)
                .where(EventTriage.urgency >= 4)
                .order_by(desc(EventTriage.urgency), desc(EventTriage.triaged_at))
                .limit(limit)
            )).scalars().all()

        return {
            "feed": [
                {
                    "id":          r.id,
                    "headline":    r.headline,
                    "urgency":     r.urgency,
                    "importance":  r.importance,
                    "sentiment":   r.sentiment,
                    "direction":   r.direction,
                    "one_liner":   r.one_liner,
                    "themes":      r.themes,
                    "sectors":     r.sectors,
                    "tickers":     r.tickers,
                    "source":      r.source,
                    "triaged_at":  r.triaged_at.isoformat(),
                }
                for r in rows
            ]
        }
    except Exception as exc:
        log.warning("intelligence.feed_error", error=str(exc))
        return {"feed": []}


@router.get("/explain")
async def explain_change(symbol: str = Query(default="")):
    """
    AI explanation for why a symbol or sector moved.
    Uses recent triage data as evidence.
    """
    from app.services.ai_service import _call_with_fallback  # noqa: PLC2701
    from app.db.session import AsyncSessionLocal
    from app.db.models.intelligence import EventTriage
    from sqlalchemy import select, desc

    since = datetime.now(timezone.utc) - timedelta(hours=8)
    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(EventTriage)
                .where(EventTriage.triaged_at >= since)
                .where(EventTriage.urgency >= 3)
                .order_by(desc(EventTriage.urgency))
                .limit(15)
            )).scalars().all()

        sym_upper = symbol.upper()
        relevant = [
            r for r in rows
            if sym_upper in [t.upper() for t in (r.tickers or [])]
            or sym_upper in (r.headline or "").upper()
        ] or rows[:5]

        context = "\n".join(
            f"- [{r.urgency}/10] {r.one_liner or r.headline[:100]}"
            for r in relevant
        )

        explanation = await _call_with_fallback(
            f"Explain what caused {symbol or 'the market'} to move today:\n\n{context}\n\nGive a 2-3 sentence explanation for retail investors.",
            "You explain Indian stock market moves simply and clearly.",
            max_tokens=200,
        )

        return {
            "symbol":       symbol,
            "explanation":  (explanation or "Unable to generate explanation.").strip(),
            "events_used":  len(relevant),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        log.warning("intelligence.explain_error", error=str(exc))
        return {"symbol": symbol, "explanation": "Unable to generate explanation at this time.", "events_used": 0}


@router.get("/replay")
async def get_market_replay():
    """Today's market stories in chronological order — powers the Market Replay timeline."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models.intelligence import MarketStory
        from sqlalchemy import select, asc

        _IST = timezone(timedelta(hours=5, minutes=30))
        today_ist = datetime.now(_IST).date()
        # Start of today in UTC
        day_start_utc = datetime(today_ist.year, today_ist.month, today_ist.day, 0, 0, 0, tzinfo=timezone.utc) - timedelta(hours=5, minutes=30)

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(MarketStory)
                .where(MarketStory.generated_at >= day_start_utc)
                .order_by(asc(MarketStory.generated_at))
                .limit(100)
            )).scalars().all()

        return {
            "entries": [
                {
                    "generated_at": r.generated_at.isoformat(),
                    "mood":         r.mood,
                    "pulse":        r.pulse,
                    "direction":    r.direction,
                    "story":        r.story,
                    "nifty_at":     r.nifty_at,
                    "vix_at":       r.vix_at,
                    "confidence":   r.confidence,
                }
                for r in rows
            ]
        }
    except Exception as exc:
        log.warning("intelligence.replay_error", error=str(exc))
        return {"entries": []}
