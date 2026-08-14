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
    from app.services.intelligence.engine import read_story, read_themes

    story = await read_story() or {}
    themes = await read_themes()

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
    """
    Fetch recent Critical/High-tier triage events for AIPE to consider.

    Audit fix (2026-08-12): this used to filter candidates in SQL via
    `EventTriage.urgency >= min_urgency` and order/cap by raw urgency
    BEFORE compute_priority's keyword floor ever ran — so a genuinely
    Critical event (headline containing "war", "rbi", "budget", etc., per
    engine.py's _CRITICAL_KEYWORDS) with a low AI-assigned raw urgency
    could be excluded from AIPE's candidate pool entirely, only ever
    surfacing after the fact via coverage_engine's separate gap-detection
    query — a different code path than the one that actually generates
    articles. Confirmed live: a real triaged event (urgency=1, keyword-
    floor priority=Critical) was excluded by the old `urgency >= 6` WHERE
    clause.

    Now: fetch a broad, recency-ordered candidate pool (no raw-urgency
    filter), compute the real priority tier for every candidate in Python
    (cheap — no I/O, same compute_priority the homepage's live pulse and
    coverage_engine already use), keep only Critical/High, and sort/limit
    by the computed priority_score — not raw urgency — so a keyword-
    elevated event is considered on equal footing with a high-raw-urgency
    one. min_urgency is unused now that tier membership (which already
    incorporates urgency/importance as its base score) is the real gate;
    kept as a parameter for call-site compatibility.
    """
    from app.db.models.intelligence import EventTriage
    from app.services.intelligence.engine import compute_priority

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    # Candidate pool: recency-ordered, no raw-urgency filter — the filter
    # that matters (Critical/High tier) is computed below in Python, after
    # the keyword floor has had a chance to run. 300 is a generous cap on
    # a 3-hour window given real observed volume (roughly 1,000+ triage
    # rows/day across all tiers) without loading an unbounded result set.
    result = await db.execute(
        select(EventTriage)
        .where(EventTriage.triaged_at >= cutoff)
        .order_by(EventTriage.triaged_at.desc())
        .limit(300)
    )
    rows = result.scalars().all()
    events = []
    for r in rows:
        priority_score, priority_tier = compute_priority(r.urgency, r.importance, None, r.headline)
        if priority_tier not in ("Critical", "High"):
            continue
        events.append({
            "event_id":     r.event_id,
            "headline":     r.headline,
            "urgency":      r.urgency,
            "importance":   r.importance,
            "confidence":   r.confidence,
            "sentiment":    r.sentiment,
            "market_impact": r.market_impact,
            "is_structural": r.is_structural,
            "one_liner":    r.one_liner,
            "source":       r.source,
            "origin":       r.origin,
            "sectors":      r.sectors or [],
            "tickers":      r.tickers or [],
            "themes":       r.themes or [],
            "triaged_at":   r.triaged_at.isoformat() if r.triaged_at else None,
            "priority_tier": priority_tier,
            "priority_score": priority_score,
        })
    # Sort by the real computed priority (keyword-floor-aware), not raw
    # urgency — a keyword-elevated Critical event now ranks correctly
    # against a high-raw-urgency-but-non-critical one.
    events.sort(key=lambda e: e["priority_score"], reverse=True)
    return events[:30]


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
    from app.services.historical_memory_service import get_verified_historical_events
    from app.db.json_utils import json_array_contains
    from sqlalchemy import or_

    if not sectors and not keywords:
        return []

    try:
        # Build flexible filter: any sector overlap or keyword match in tags.
        # Was .contains([s])/.contains([kw]) — silently broken on this
        # deployment's SQLite database (see json_utils.py's module
        # docstring): confirmed live, always returned 0 rows against real
        # multi-element array matches.
        filters = []
        for s in sectors[:3]:
            filters.append(json_array_contains(HistoricalMarketEvent.sectors, s))
        for kw in keywords[:3]:
            filters.append(json_array_contains(HistoricalMarketEvent.tags, kw))

        if not filters:
            return []

        # P3.5: routed through the shared verified-outcome filter — this
        # used to query HistoricalMarketEvent directly with no outcome-data
        # check, directly contradicting this function's own docstring
        # ("Uses stored evidence only — never hallucinate history": a
        # same-day auto-harvested preview of the current story IS a form
        # of that, just via contaminated data rather than an LLM guess).
        rows = await get_verified_historical_events(db, extra_filters=[or_(*filters)], limit=limit)
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
