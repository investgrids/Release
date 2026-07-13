"""
Duplicate Detector — prevents the AIPE from publishing the same intelligence
twice. Instead of creating a new article, it returns the existing one to be
updated.

Strategy (in priority order):
  1. Exact story_id match → definitive duplicate → update
  2. Same trigger_event_id + same article_type → duplicate → update
  3. Headline token overlap > 50% (Jaccard) → probable duplicate → update
  4. No match → create new article

This ensures "Oil rises 3% → article" followed by "Oil rises 5%" updates
the existing article rather than creating a second one.
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

_LOOKBACK_HOURS = 24  # Only check articles from the last 24 hours


def _tokenize(text: str) -> set[str]:
    """Lowercase, strip punctuation, split into tokens. Remove stop words."""
    _STOP = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "as", "by", "from", "up", "about", "into", "through", "after",
        "what", "how", "why", "when", "who", "which", "will", "can", "should",
        "its", "it", "this", "that", "these", "those",
    }
    tokens = re.findall(r"\b[a-z0-9₹%]+\b", text.lower())
    return {t for t in tokens if t not in _STOP and len(t) > 1}


def _jaccard(s1: set[str], s2: set[str]) -> float:
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


async def find_duplicate(
    db: AsyncSession,
    story_id: str,
    article_type: str,
    headline: str,
    trigger_event_id: str | None,
) -> IntelligenceArticle | None:
    """
    Returns the existing article if a duplicate is found, otherwise None.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_LOOKBACK_HOURS)

    # 1. Exact story_id match (same story, same day)
    if story_id:
        result = await db.execute(
            select(IntelligenceArticle)
            .where(IntelligenceArticle.story_id == story_id)
            .where(IntelligenceArticle.created_at >= cutoff)
            .where(IntelligenceArticle.lifecycle_status.notin_(["archived", "merged"]))
            .order_by(IntelligenceArticle.created_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            log.info("duplicate.story_id_match", story_id=story_id, existing_id=existing.id)
            return existing

    # 2. Same trigger event + same type
    if trigger_event_id:
        result = await db.execute(
            select(IntelligenceArticle)
            .where(IntelligenceArticle.trigger_event_id == trigger_event_id)
            .where(IntelligenceArticle.article_type == article_type)
            .where(IntelligenceArticle.created_at >= cutoff)
            .where(IntelligenceArticle.lifecycle_status.notin_(["archived", "merged"]))
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            log.info("duplicate.event_type_match", event_id=trigger_event_id, type=article_type)
            return existing

    # 3. Headline similarity
    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.article_type == article_type)
        .where(IntelligenceArticle.created_at >= cutoff)
        .where(IntelligenceArticle.lifecycle_status.notin_(["archived", "merged"]))
        .order_by(IntelligenceArticle.created_at.desc())
        .limit(20)
    )
    candidates = result.scalars().all()

    candidate_tokens = _tokenize(headline)
    for c in candidates:
        if not c.headline:
            continue
        existing_tokens = _tokenize(c.headline)
        similarity = _jaccard(candidate_tokens, existing_tokens)
        if similarity >= 0.50:
            log.info(
                "duplicate.headline_similarity",
                similarity=round(similarity, 3),
                existing_headline=c.headline[:80],
                new_headline=headline[:80],
            )
            return c

    return None


async def count_today_articles(db: AsyncSession) -> int:
    """Count articles published today (IST)."""
    from datetime import timedelta
    from sqlalchemy import func

    _IST = timezone(timedelta(hours=5, minutes=30))
    today_ist = datetime.now(_IST).replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = today_ist.astimezone(timezone.utc)

    result = await db.execute(
        select(func.count()).select_from(IntelligenceArticle)
        .where(IntelligenceArticle.published_at >= today_utc)
        .where(IntelligenceArticle.status == "published")
    )
    return result.scalar() or 0


async def get_today_story_ids(db: AsyncSession) -> set[str]:
    """Return story_ids already published today."""
    from datetime import timedelta

    _IST = timezone(timedelta(hours=5, minutes=30))
    today_ist = datetime.now(_IST).replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = today_ist.astimezone(timezone.utc)

    result = await db.execute(
        select(IntelligenceArticle.story_id)
        .where(IntelligenceArticle.created_at >= today_utc)
        .where(IntelligenceArticle.story_id.isnot(None))
    )
    return {row[0] for row in result.all() if row[0]}
