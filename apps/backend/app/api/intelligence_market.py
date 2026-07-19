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
    from app.services.intelligence.engine import read_story
    try:
        story = await read_story()
        return {"story": story, "source": "cache" if story else "none"}
    except Exception as exc:
        log.warning("intelligence.story_error", error=str(exc))
        return {"story": None, "source": "none"}


@router.get("/themes")
async def get_theme_scores():
    """All 12 theme scores ranked by composite score."""
    from app.services.intelligence.engine import read_themes
    try:
        themes = await read_themes()
        return {"themes": themes, "source": "cache" if themes else "error"}
    except Exception as exc:
        log.warning("intelligence.themes_error", error=str(exc))
        return {"themes": [], "source": "error"}


@router.get("/feed")
async def get_intelligence_feed(limit: int = Query(default=20, le=50)):
    """Recent intelligence feed — triage results for the alert panel."""
    from app.services.intelligence.engine import read_top_events
    try:
        feed = await read_top_events(limit=limit, min_urgency=4, hours=8)
        return {"feed": feed}
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
