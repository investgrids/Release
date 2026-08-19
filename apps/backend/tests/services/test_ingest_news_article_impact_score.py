"""
Confirms _persist_articles' NOT-NULL accommodation for NewsArticle.impact_score
(a separate, legacy schema constraint from the Event.impact_score provenance
fix -- see ingest_tasks.py's own comment at the call site). A RawItem with
impact_score=None (the new honest default) must still insert cleanly, falling
back to a neutral constant only for this one legacy NOT-NULL column, while the
provider-level fix (RawItem.impact_score=None) itself is unaffected.

Runs against the real configured dev DB, same convention as test_event_bridge.py
-- unique id, cleaned up in a finally block.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.db.models.event import Event
from app.db.models_legacy import NewsArticle
from app.providers.base import RawItem
from app.tasks.ingest_tasks import _create_events, _persist_articles


async def _cleanup(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(NewsArticle).where(NewsArticle.id.in_(ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_none_impact_score_falls_back_for_newsarticle_not_null_column():
    test_id = "pytest-newsarticle-impact-none-001"
    await _cleanup(test_id)
    try:
        item = RawItem(id=test_id, headline="Test headline for impact-score fallback",
                        summary="x", source="Test", impact_score=None)
        async with AsyncSessionLocal() as db:
            new_ids = await _persist_articles(db, [item])
            assert test_id in new_ids

            row = (await db.execute(select(NewsArticle).where(NewsArticle.id == test_id))).scalar_one()
            assert row.impact_score == 5.0  # the documented legacy-column fallback, not None (NOT NULL column)
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_real_impact_score_still_passes_through_unchanged():
    """Negative control: when a RawItem DOES carry a real (non-None) score,
    _persist_articles must not overwrite it with the fallback."""
    test_id = "pytest-newsarticle-impact-real-002"
    await _cleanup(test_id)
    try:
        item = RawItem(id=test_id, headline="Test headline with a real score",
                        summary="x", source="Test", impact_score=42.5)
        async with AsyncSessionLocal() as db:
            await _persist_articles(db, [item])
            row = (await db.execute(select(NewsArticle).where(NewsArticle.id == test_id))).scalar_one()
            assert row.impact_score == 42.5
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_event_impact_score_none_survives_insert_not_coerced_to_zero():
    """Regression test for a real SQLAlchemy footgun found live while
    fixing this: Column(Float, nullable=True, default=0.0) silently
    substitutes 0.0 for an explicitly-passed None at INSERT time -- the
    ORM can't distinguish "explicitly None" from "attribute never set."
    Verified directly against raw SQL (not the ORM identity map, which can
    mask this by returning a Python None from a Python-side default having
    never round-tripped through a fresh query). A "0.0 impact" reads as
    "AI analyzed this and found zero impact" -- a materially false claim
    for an event that was never analyzed at all. Event.impact_score/
    confidence no longer declare a column-level default for exactly this
    reason; this test exists so a future "helpful" default=0.0 doesn't
    quietly reintroduce the bug."""
    test_id = "pytest-event-impact-none-003"
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Event).where(Event.id == test_id))
        await db.execute(delete(NewsArticle).where(NewsArticle.id == test_id))
        await db.commit()
    try:
        item = RawItem(id=test_id, headline="Test event with no real score yet",
                        summary="x", source="Test", impact_score=None)
        async with AsyncSessionLocal() as db:
            new_ids = await _persist_articles(db, [item])
            await _create_events(db, [item], set(new_ids), "corporate")

        async with AsyncSessionLocal() as db2:
            row = (await db2.execute(text("SELECT impact_score FROM events WHERE id = :id"), {"id": test_id})).fetchone()
            assert row is not None
            assert row[0] is None, f"expected NULL, got {row[0]!r} -- the ORM default-substitution footgun is back"
    finally:
        async with AsyncSessionLocal() as db3:
            await db3.execute(delete(Event).where(Event.id == test_id))
            await db3.execute(delete(NewsArticle).where(NewsArticle.id == test_id))
            await db3.commit()
