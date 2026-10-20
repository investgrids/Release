"""
Provenance contract, Stage D (2026-10-19) -- continuous_updater.py's
takeaway/watch-next/update-note generators must never present a
rule_based_fallback/unknown event's one_liner as something MarketRipple
synthesized or verified. AI-sourced events keep today's exact behavior.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_article import IntelligenceArticle
from app.services.aipe.continuous_updater import (
    _generate_updated_takeaway,
    _generate_watch_next,
    update_article,
)


# ── _generate_updated_takeaway ───────────────────────────────────────────────

def test_fallback_sourced_event_is_skipped_for_takeaway():
    new_events = [{"urgency": 9, "one_liner": "Raw unverified headline", "triage_source": "rule_based_fallback"}]
    assert _generate_updated_takeaway(article=None, mie_context={}, new_events=new_events) is None


def test_unknown_provenance_event_is_skipped_for_takeaway():
    new_events = [{"urgency": 9, "one_liner": "Pre-migration headline", "triage_source": "unknown"}]
    assert _generate_updated_takeaway(article=None, mie_context={}, new_events=new_events) is None


def test_falls_through_to_the_next_best_ai_sourced_candidate():
    new_events = [
        {"urgency": 9, "one_liner": "Raw fallback headline", "triage_source": "rule_based_fallback"},
        {"urgency": 3, "one_liner": "Lower-urgency AI takeaway", "triage_source": "ai"},
    ]
    result = _generate_updated_takeaway(article=None, mie_context={}, new_events=new_events)
    assert result == "LATEST: Lower-urgency AI takeaway"


def test_ai_sourced_event_is_unaffected():
    new_events = [{"urgency": 8, "one_liner": "Genuine AI takeaway", "triage_source": "ai"}]
    result = _generate_updated_takeaway(article=None, mie_context={}, new_events=new_events)
    assert result == "LATEST: Genuine AI takeaway"


def test_missing_triage_source_key_is_treated_as_eligible():
    """Real production events always carry this key (EventTriage.triage_source
    is NOT NULL); a dict without it at all -- e.g. an older test fixture or
    a different producer -- must not be silently suppressed."""
    new_events = [{"urgency": 8, "one_liner": "No provenance key at all"}]
    result = _generate_updated_takeaway(article=None, mie_context={}, new_events=new_events)
    assert result == "LATEST: No provenance key at all"


# ── _generate_watch_next ─────────────────────────────────────────────────────

def test_watch_next_skips_fallback_and_unknown_events():
    new_events = [
        {"one_liner": "Raw fallback headline", "triage_source": "rule_based_fallback"},
        {"one_liner": "Pre-migration headline", "triage_source": "unknown"},
        {"one_liner": "Genuine AI item", "triage_source": "ai"},
    ]
    result = _generate_watch_next(mie_context={}, new_events=new_events)
    assert result == ["Genuine AI item"]


def test_watch_next_returns_none_when_everything_is_fallback():
    new_events = [{"one_liner": "Raw fallback headline", "triage_source": "rule_based_fallback"}]
    assert _generate_watch_next(mie_context={}, new_events=new_events) is None


# ── update_article()'s inline "**Update HH:MM:**" note (DB-backed) ─────────

def _row(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    base = dict(
        id=str(uuid.uuid4()), slug=f"test-provenance-{uuid.uuid4().hex[:8]}", article_type="company_intelligence",
        angle="primary", is_evergreen=False, lifecycle_status="published", status="published",
        headline="Test Headline", executive_summary="s",
        key_takeaway="Original takeaway.", why_it_matters="Original why-it-matters text.",
        companies_affected=[], sectors_affected=[], sources=["NSE"],
        story_version=1, update_count=0, update_history=[],
        market_context={"session": "post_market", "mood": "neutral"},
        published_at=now, last_updated=now,
    )
    base.update(overrides)
    return base


async def _seed(**overrides) -> str:
    data = _row(**overrides)
    async with AsyncSessionLocal() as db:
        db.add(IntelligenceArticle(**data))
        await db.commit()
    return data["id"]


async def _cleanup(article_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id == article_id))
        await db.commit()


async def _fetch(article_id: str) -> IntelligenceArticle:
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(IntelligenceArticle).where(IntelligenceArticle.id == article_id))).scalar_one()


@pytest.mark.asyncio
async def test_update_note_skips_fallback_event_and_falls_back_to_story():
    aid = await _seed()
    try:
        mie_context = {"story": "Global story fallback text", "story_hash": "hash-v2", "mood": "Neutral"}
        new_triage_events = [{"urgency": 9, "sectors": [], "tickers": [], "one_liner": "Raw fallback headline", "triage_source": "rule_based_fallback"}]
        async with AsyncSessionLocal() as db:
            article = await _fetch(aid)
            db.add(article)
            await update_article(db, article, mie_context, new_triage_events=new_triage_events, market_move_reason=None)
        row = await _fetch(aid)
        assert "Raw fallback headline" not in (row.why_it_matters or "")
        assert "Global story fallback text" in (row.why_it_matters or "")
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_update_note_uses_ai_sourced_event_normally():
    aid = await _seed()
    try:
        mie_context = {"story": "Global story fallback text", "story_hash": "hash-v3", "mood": "Neutral"}
        new_triage_events = [{"urgency": 9, "sectors": [], "tickers": [], "one_liner": "Genuine AI development", "triage_source": "ai"}]
        async with AsyncSessionLocal() as db:
            article = await _fetch(aid)
            db.add(article)
            await update_article(db, article, mie_context, new_triage_events=new_triage_events, market_move_reason=None)
        row = await _fetch(aid)
        assert "Genuine AI development" in (row.why_it_matters or "")
    finally:
        await _cleanup(aid)
