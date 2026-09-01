"""
Regression suite — continuous_updater.py's P0-CD2 fix for global takeaway
contamination (2026-09-01).

Real, confirmed production bug: a company/event article's key_takeaway used
to be overwritten with the CURRENT GLOBAL market mood/opportunity/risk
narrative -- identical text for every article touched in the same cycle,
with no connection to that specific article's own subject. Confirmed live:
an Ambuja article acquired an unrelated global "Nifty swing-buy" opportunity
string as its own takeaway; a related, already-partially-fixed case showed
an ITC-vs-HUL comparison with a Cholamandalam Finance takeaway.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_article import IntelligenceArticle
from app.services.aipe.continuous_updater import _generate_updated_takeaway, update_article


# ── Pure function: _generate_updated_takeaway ────────────────────────────────

def test_global_mood_opportunity_risk_never_leak_into_takeaway():
    mie_context = {
        "mood": "Bullish",
        "opportunity": "Nifty swing-buy setup forming near support",
        "risk": "Global rate uncertainty",
        "investor_watch": "FOMC minutes due Thursday",
    }
    result = _generate_updated_takeaway(article=None, mie_context=mie_context, new_events=[])
    assert result is None
    assert "swing-buy" not in (result or "")


def test_no_article_relevant_events_returns_none_not_manufactured_text():
    # The honest "no article-specific development this cycle" answer, per
    # the CD2 authorization's "if no grounded takeaway can be produced:
    # omit it" instruction.
    mie_context = {"mood": "Bearish", "opportunity": "Some global opportunity", "risk": "Some global risk"}
    assert _generate_updated_takeaway(article=None, mie_context=mie_context, new_events=[]) is None


def test_article_relevant_event_produces_a_scoped_takeaway():
    mie_context = {"mood": "Bullish", "opportunity": "irrelevant global text"}
    new_events = [{"urgency": 8, "one_liner": "Ambuja Cements reports record quarterly volumes"}]
    result = _generate_updated_takeaway(article=None, mie_context=mie_context, new_events=new_events)
    assert result == "LATEST: Ambuja Cements reports record quarterly volumes"
    assert "irrelevant global text" not in result


def test_multiple_events_picks_highest_urgency_one():
    new_events = [
        {"urgency": 3, "one_liner": "Minor development"},
        {"urgency": 9, "one_liner": "Major development"},
    ]
    result = _generate_updated_takeaway(article=None, mie_context={}, new_events=new_events)
    assert result == "LATEST: Major development"


# ── DB-backed: update_article() ──────────────────────────────────────────────

def _row(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    base = dict(
        id=str(uuid.uuid4()), slug=f"test-takeaway-{uuid.uuid4().hex[:8]}", article_type="company_intelligence",
        angle="primary", is_evergreen=False, lifecycle_status="published", status="published",
        headline="Ambuja Cements Q2 Results", executive_summary="s",
        key_takeaway="Ambuja Cements posted a real, grounded quarterly result.",
        why_it_matters="Real cement-sector-specific analysis about Ambuja.",
        companies_affected=[{"name": "Ambuja Cements", "symbol": "AMBUJACEM"}],
        sectors_affected=[], sources=["NSE"],
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
async def test_update_article_does_not_stamp_global_opportunity_onto_unrelated_article():
    """The exact real bug: an Ambuja article must never acquire an unrelated
    global 'Nifty swing-buy' takeaway just because the MIE story hash moved
    on with zero real Ambuja-relevant news this cycle."""
    aid = await _seed()
    try:
        mie_context = {
            "story": "Broad market narrative unrelated to Ambuja",
            "mood": "Bullish",
            "opportunity": "Nifty swing-buy setup forming near key support",
            "risk": "Global rate uncertainty",
            "story_hash": "hash-v2",
        }
        async with AsyncSessionLocal() as db:
            article = await _fetch(aid)
            db.add(article)
            # market_move_reason=None, new_triage_events=[] -- the exact
            # shape of a story-hash-only trigger with zero real overlap,
            # per run_continuous_update_cycle's own filtering.
            ok = await update_article(db, article, mie_context, new_triage_events=[], market_move_reason=None)

        row = await _fetch(aid)
        if ok:
            assert "swing-buy" not in (row.key_takeaway or "")
            assert row.key_takeaway == "Ambuja Cements posted a real, grounded quarterly result."
            assert "swing-buy" not in (row.why_it_matters or "")
    finally:
        await _cleanup(aid)


@pytest.mark.asyncio
async def test_update_article_uses_article_relevant_event_when_present():
    aid = await _seed()
    try:
        mie_context = {"story": "irrelevant global narrative", "mood": "Bullish", "story_hash": "hash-v3"}
        relevant_events = [{"urgency": 8, "sectors": [], "tickers": ["AMBUJACEM"], "one_liner": "Ambuja Cements announces capacity expansion"}]
        async with AsyncSessionLocal() as db:
            article = await _fetch(aid)
            db.add(article)
            ok = await update_article(db, article, mie_context, new_triage_events=relevant_events, market_move_reason=None)
        assert ok is True

        row = await _fetch(aid)
        assert row.key_takeaway == "LATEST: Ambuja Cements announces capacity expansion"
        assert "irrelevant global narrative" not in (row.key_takeaway or "")
    finally:
        await _cleanup(aid)
