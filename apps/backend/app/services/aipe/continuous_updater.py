"""
Continuous Update Engine — articles are living documents.

Every cycle (5 min), the updater checks published articles that:
  1. Were published in the current trading day
  2. Have a significant MIE story change (new mie_story_hash)
  3. Have new high-urgency triage events related to their sectors/companies

When an update is warranted, it regenerates the key_takeaway, why_it_matters,
and what_to_watch_next sections using fresh context, then appends an entry
to update_history.

Update tracking on each article:
  update_count  — incremented each time
  last_updated  — datetime of most recent update
  update_history — [{at: ISO, version: n, reason: str, summary: str}]
  lifecycle_status → "updated"
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.intelligence_article import IntelligenceArticle
from app.services.aipe.market_story_engine import get_mie_context, _story_hash

log = structlog.get_logger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))

# Only update articles published within this window
_UPDATE_WINDOW_HOURS = 12

# Minimum time between updates for the same article (avoid thrashing)
_MIN_UPDATE_GAP_MINUTES = 45


async def find_updatable_articles(
    db: AsyncSession,
    current_mie_hash: str,
) -> list[IntelligenceArticle]:
    """Return published articles from today that should receive an update."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_UPDATE_WINDOW_HOURS)
    min_gap = datetime.now(timezone.utc) - timedelta(minutes=_MIN_UPDATE_GAP_MINUTES)

    result = await db.execute(
        select(IntelligenceArticle)
        .where(IntelligenceArticle.status == "published")
        .where(IntelligenceArticle.published_at >= cutoff)
        .where(IntelligenceArticle.lifecycle_status.notin_(["archived", "merged"]))
        # Only update articles not updated very recently
        .where(
            (IntelligenceArticle.last_updated == None) |  # noqa: E711
            (IntelligenceArticle.last_updated <= min_gap)
        )
        .order_by(IntelligenceArticle.published_at.asc())
    )
    articles = result.scalars().all()

    # Filter to those whose MIE hash has changed
    return [
        a for a in articles
        if a.mie_story_hash != current_mie_hash
    ]


async def update_article(
    db: AsyncSession,
    article: IntelligenceArticle,
    mie_context: dict[str, Any],
    new_triage_events: list[dict[str, Any]],
) -> bool:
    """
    Update an article's dynamic sections with fresh market context.
    Returns True if updated, False if skipped.
    """
    now = datetime.now(timezone.utc)
    new_version = article.story_version + 1

    # Build update reason
    reasons = []
    if mie_context.get("story"):
        reasons.append(f"Market narrative updated: {mie_context['mood']}")
    if new_triage_events:
        high = [e for e in new_triage_events if e.get("urgency", 0) >= 7]
        if high:
            reasons.append(f"{len(high)} high-urgency development(s)")
    if not reasons:
        return False

    update_reason = " | ".join(reasons)

    # Regenerate dynamic sections
    new_takeaway = _generate_updated_takeaway(article, mie_context, new_triage_events)
    new_watch_next = _generate_watch_next(mie_context, new_triage_events)

    # Update history entry
    history_entry = {
        "at":      now.isoformat(),
        "version": new_version,
        "reason":  update_reason,
        "summary": f"Updated: {mie_context.get('mood', 'market conditions changed')}",
    }

    current_history = article.update_history or []
    updated_history = current_history + [history_entry]

    # Apply updates
    article.key_takeaway     = new_takeaway or article.key_takeaway
    article.what_to_watch_next = new_watch_next or article.what_to_watch_next
    article.story_version    = new_version
    article.update_count     = (article.update_count or 0) + 1
    article.update_history   = updated_history
    article.last_updated     = now
    article.mie_story_hash   = mie_context.get("story_hash")
    article.lifecycle_status = "updated"

    # Append update note to why_it_matters
    if mie_context.get("story"):
        update_note = f"\n\n**Update {now.strftime('%I:%M %p IST')}:** {mie_context['story']}"
        current = article.why_it_matters or ""
        if update_note[:50] not in current:  # avoid duplicate appends
            article.why_it_matters = current + update_note

    db.add(article)
    await db.commit()

    log.info(
        "continuous_updater.updated",
        article_id=article.id,
        version=new_version,
        reason=update_reason,
    )
    return True


def _generate_updated_takeaway(
    article: IntelligenceArticle,
    mie_context: dict[str, Any],
    new_events: list[dict[str, Any]],
) -> str | None:
    """Generate a fresh key takeaway based on current market context."""
    mood = mie_context.get("mood", "")
    opportunity = mie_context.get("opportunity", "")
    risk = mie_context.get("risk", "")
    investor_watch = mie_context.get("investor_watch", "")

    if not any([mood, opportunity, risk]):
        return None

    parts = []
    if mood:
        parts.append(f"Market mood: {mood}.")
    if opportunity:
        parts.append(opportunity)
    if risk:
        parts.append(f"Key risk: {risk}")
    if investor_watch:
        parts.append(f"Watch: {investor_watch}")

    # Add breaking development if any
    if new_events:
        top = sorted(new_events, key=lambda e: e.get("urgency", 0), reverse=True)[0]
        if top.get("one_liner"):
            parts.insert(0, f"LATEST: {top['one_liner']}")

    return " | ".join(parts)[:400] if parts else None


def _generate_watch_next(
    mie_context: dict[str, Any],
    new_events: list[dict[str, Any]],
) -> list[str] | None:
    """Generate updated watch-next items."""
    items = []

    if mie_context.get("investor_watch"):
        items.append(mie_context["investor_watch"])
    if mie_context.get("trader_watch"):
        items.append(mie_context["trader_watch"])

    for ev in new_events[:2]:
        if ev.get("one_liner"):
            items.append(ev["one_liner"])

    return items[:5] if items else None


async def run_continuous_update_cycle(
    db: AsyncSession,
    mie_context: dict[str, Any],
    new_triage_events: list[dict[str, Any]],
) -> int:
    """
    Run the update cycle. Returns number of articles updated.
    """
    current_hash = mie_context.get("story_hash", "")
    if not current_hash:
        return 0

    articles = await find_updatable_articles(db, current_hash)
    if not articles:
        return 0

    updated = 0
    # Only update articles related to the new events' sectors/tickers
    relevant_sectors = set()
    relevant_tickers = set()
    for ev in new_triage_events:
        relevant_sectors.update(ev.get("sectors") or [])
        relevant_tickers.update(ev.get("tickers") or [])

    for article in articles[:3]:  # Cap at 3 updates per cycle
        # Check if this article is relevant to new events
        art_sectors = {s.get("name", s) if isinstance(s, dict) else s
                       for s in (article.sectors_affected or [])}
        art_companies = {c.get("symbol", c) if isinstance(c, dict) else c
                         for c in (article.companies_affected or [])}

        sector_overlap = relevant_sectors & art_sectors
        company_overlap = relevant_tickers & art_companies

        if sector_overlap or company_overlap or mie_context.get("story_hash") != article.mie_story_hash:
            ok = await update_article(db, article, mie_context, new_triage_events)
            if ok:
                updated += 1

    return updated
