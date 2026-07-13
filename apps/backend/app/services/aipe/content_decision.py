"""
Content Decision Engine — evaluates every live event and decides whether
an intelligence article should be generated.

Scoring model (0-100):
  impact_score  × 8   → up to 80
  confidence    × 0.15 → up to 15
  sector_count  × 2   → up to ~20
  company_count × 1   → up to ~20
  urgency bonus       → +10 for breaking / RBI / SEBI / earnings
  recency bonus       → +10 if event < 6 h old

Minimum score to trigger generation: 60
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_article import IntelligenceArticle

log = structlog.get_logger(__name__)

_MIN_SCORE = 60

_URGENT_TYPES = {"breaking", "rbi", "sebi", "earnings", "ipo", "policy", "budget"}
_URGENT_KEYWORDS = [
    "rbi", "sebi", "repo rate", "rate cut", "rate hike", "budget",
    "earnings", "results", "quarterly", "q1", "q2", "q3", "q4",
    "ipo", "listing", "circuit breaker", "f&o ban", "ban", "ban list",
    "acquisition", "merger", "demerger", "buyback", "dividend",
]


def score_event(event: dict[str, Any]) -> float:
    """Return a 0–100 content decision score for an event dict."""
    impact = float(event.get("impact_score") or 0)
    confidence = float(event.get("confidence") or 0)
    sectors = event.get("sectors") or []
    companies = event.get("companies") or []
    event_type = (event.get("event_type") or "").lower()
    title = (event.get("title") or "").lower()
    summary = (event.get("summary") or "").lower()
    text = title + " " + summary

    score = (impact * 8) + (confidence * 0.15)
    score += min(len(sectors) * 2, 20)
    score += min(len(companies) * 1, 20)

    # Urgency bonus
    is_urgent = event_type in _URGENT_TYPES or any(kw in text for kw in _URGENT_KEYWORDS)
    if is_urgent:
        score += 10

    # Recency bonus (event_date within 6 h)
    raw_date = event.get("event_date") or event.get("published_at")
    if raw_date:
        if isinstance(raw_date, str):
            try:
                raw_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                raw_date = None
        if isinstance(raw_date, datetime):
            age = datetime.now(timezone.utc) - raw_date.astimezone(timezone.utc)
            if age < timedelta(hours=6):
                score += 10

    return round(min(score, 100), 2)


def decide_article_type(event: dict[str, Any]) -> str:
    """Choose the most appropriate article type for the event."""
    event_type = (event.get("event_type") or "").lower()
    title = (event.get("title") or "").lower()
    text = title + " " + (event.get("summary") or "").lower()
    sectors = event.get("sectors") or []
    companies = event.get("companies") or []

    if any(kw in text for kw in ["rbi", "sebi", "budget", "policy", "repo rate", "regulation"]):
        return "policy_brief"
    if any(kw in text for kw in ["earnings", "results", "q1", "q2", "q3", "q4", "quarterly"]):
        return "company_analysis"
    if any(kw in text for kw in ["oil", "crude", "gold", "silver", "commodity"]):
        return "ripple"
    if len(companies) >= 3:
        return "sector_report"
    if event_type in {"breaking", "flash"}:
        return "breaking"
    if sectors and not companies:
        return "sector_report"
    if companies and len(companies) <= 2:
        return "company_analysis"
    return "event_analysis"


async def get_publishable_events(
    db: AsyncSession,
    limit: int = 10,
) -> list[tuple[dict, float]]:
    """
    Return a list of (event_dict, score) for events that should get articles.
    Excludes events that already have a published or draft article.
    """
    from app.db.models.event import Event

    # Events from the last 48 h
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    result = await db.execute(
        select(Event)
        .where(Event.created_at >= cutoff)
        .order_by(Event.impact_score.desc())
        .limit(100)
    )
    events = result.scalars().all()

    # Already-covered event IDs
    covered = await db.execute(
        select(IntelligenceArticle.trigger_event_id)
        .where(IntelligenceArticle.status.in_(["published", "draft", "validating"]))
    )
    covered_ids = {row[0] for row in covered.all() if row[0]}

    candidates: list[tuple[dict, float]] = []
    for ev in events:
        if ev.id in covered_ids:
            continue
        ev_dict = {
            "id": ev.id,
            "title": ev.title,
            "summary": ev.summary or ev.description or "",
            "event_type": ev.event_type or "",
            "impact_score": ev.impact_score or 0,
            "confidence": ev.confidence or 0,
            "sectors": ev.sectors or [],
            "companies": ev.companies or [],
            "event_date": ev.event_date,
            "published_at": ev.published_at,
        }
        score = score_event(ev_dict)
        if score >= _MIN_SCORE:
            candidates.append((ev_dict, score))

    # Sort by score desc, return top N
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:limit]
