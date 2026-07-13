"""
Market Story Engine — the heart of the AIPE.

Every few minutes it asks: "Has today's market understanding materially changed?"

If NO → do nothing.
If YES → update today's market story OR create a new section update.

This is ONE evolving story per day, not separate articles. The story
progresses through phases:

  pre_market   → Morning Intelligence (published at 8:30-9:15 AM IST)
  live_morning → Mid-morning update if major development (10-11 AM)
  live_midday  → Midday check (12:30 PM) — only if story changed meaningfully
  live_pm      → Afternoon update if needed (2-3 PM)
  post_market  → Market Wrap (4:00-4:30 PM IST)
  archived     → Next morning at 9:00 AM

Story change detection uses the existing MIE mie_story_hash mechanism.
Only republish when the hash has changed significantly.

Taps into:
  - market:story:latest (Redis) — current MIE narrative
  - market:themes:ranked (Redis) — active themes
  - EventTriage DB — high-urgency events
  - MarketSnapshot DB — market state change detection
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))


def _ist_now() -> datetime:
    return datetime.now(_IST)


def _today_ist() -> str:
    return _ist_now().strftime("%Y-%m-%d")


def _session() -> str:
    now = _ist_now()
    h, m = now.hour, now.minute
    mins = h * 60 + m
    if mins < 8 * 60 + 30:
        return "pre_open"
    if mins < 9 * 60 + 15:
        return "pre_market"
    if mins <= 15 * 60 + 30:
        return "live"
    if mins <= 16 * 60 + 30:
        return "post_market"
    return "closed"


def _story_hash(story_text: str) -> str:
    return hashlib.sha1(story_text.encode()).hexdigest()[:16]


async def get_mie_context() -> dict[str, Any]:
    """Fetch current MIE state: story, themes, top triage events."""
    from app.core.redis import cache_get

    story_raw = await cache_get("market:story:latest")
    themes_raw = await cache_get("market:themes:ranked")

    story: dict = story_raw if isinstance(story_raw, dict) else {}
    themes: list = themes_raw if isinstance(themes_raw, list) else []

    return {
        "story":     story.get("text", ""),
        "mood":      story.get("mood", "Uncertain"),
        "pulse":     story.get("pulse", "="),
        "direction": story.get("direction", "sideways"),
        "opportunity": story.get("opportunity", ""),
        "risk":      story.get("risk", ""),
        "investor_watch": story.get("investor_watch", ""),
        "trader_watch":   story.get("trader_watch", ""),
        "confidence": story.get("confidence", 0),
        "sector_rotation": story.get("sector_rotation", ""),
        "themes":    [t.get("theme", "") for t in themes[:6]],
        "story_hash": _story_hash(story.get("text", "")),
        "generated_at": story.get("generated_at"),
        "session":   _session(),
    }


async def get_high_urgency_triage(
    db: AsyncSession,
    min_urgency: int = 6,
    hours: int = 3,
) -> list[dict[str, Any]]:
    """Fetch recent high-urgency triage events from the DB."""
    from app.db.models.intelligence import EventTriage

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(EventTriage)
        .where(EventTriage.triaged_at >= cutoff)
        .where(EventTriage.urgency >= min_urgency)
        .order_by(EventTriage.urgency.desc(), EventTriage.triaged_at.desc())
        .limit(20)
    )
    rows = result.scalars().all()
    return [
        {
            "event_id":     r.event_id,
            "headline":     r.headline,
            "urgency":      r.urgency,
            "importance":   r.importance,
            "confidence":   r.confidence,
            "sentiment":    r.sentiment,
            "market_impact": r.market_impact,
            "is_structural": r.is_structural,
            "one_liner":    r.one_liner,
            "sectors":      r.sectors or [],
            "tickers":      r.tickers or [],
            "themes":       r.themes or [],
            "triaged_at":   r.triaged_at.isoformat() if r.triaged_at else None,
        }
        for r in rows
    ]


async def has_mie_changed(db: AsyncSession, current_hash: str) -> bool:
    """
    Returns True if the MIE story has changed since the last published article.
    Uses the mie_story_hash stored on the most recent article.
    """
    from app.db.models.intelligence_article import IntelligenceArticle

    result = await db.execute(
        select(IntelligenceArticle.mie_story_hash)
        .where(IntelligenceArticle.status == "published")
        .where(IntelligenceArticle.mie_story_hash.isnot(None))
        .order_by(IntelligenceArticle.published_at.desc())
        .limit(1)
    )
    last_hash = result.scalar_one_or_none()
    if last_hash is None:
        return True  # No published articles yet — always run
    return last_hash != current_hash


async def fetch_historical_context(
    db: AsyncSession,
    sectors: list[str],
    keywords: list[str],
    limit: int = 3,
) -> list[dict[str, Any]]:
    """
    Fetch verified historical market events for grounding the AI.
    Uses stored evidence only — never hallucinate history.
    """
    from app.db.models.historical_memory import HistoricalMarketEvent
    from sqlalchemy import or_, func

    if not sectors and not keywords:
        return []

    try:
        # Build flexible filter: any sector overlap or keyword match in tags
        filters = []
        for s in sectors[:3]:
            filters.append(HistoricalMarketEvent.sectors.contains([s]))
        for kw in keywords[:3]:
            filters.append(HistoricalMarketEvent.tags.contains([kw]))

        if not filters:
            return []

        result = await db.execute(
            select(HistoricalMarketEvent)
            .where(or_(*filters))
            .order_by(HistoricalMarketEvent.event_date.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "event":    r.event_title,
                "date":     r.event_date.strftime("%b %Y") if r.event_date else "—",
                "category": r.category,
                "outcome":  getattr(r, "nifty_1d_change_pct", None),
                "sentiment": r.sentiment,
                "sectors":  r.sectors,
            }
            for r in rows
        ]
    except Exception as exc:
        log.warning("market_story.historical_fetch_error", error=str(exc))
        return []


async def get_latest_market_snapshot(db: AsyncSession) -> dict[str, Any]:
    """Get the most recent market snapshot for context."""
    from app.db.models.intelligence import MarketSnapshot

    try:
        result = await db.execute(
            select(MarketSnapshot)
            .order_by(MarketSnapshot.ts.desc())
            .limit(1)
        )
        snap = result.scalar_one_or_none()
        if snap:
            return {
                "nifty":       snap.nifty_level,
                "nifty_chg":   snap.nifty_change_pct,
                "banknifty":   snap.banknifty_level,
                "vix":         snap.vix,
                "advances":    snap.advances,
                "declines":    snap.declines,
                "fii_net":     snap.fii_net,
                "mood":        snap.mood,
            }
    except Exception as exc:
        log.warning("market_story.snapshot_fetch_error", error=str(exc))
    return {}
