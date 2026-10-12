"""The 'active events' engine (homepage Other Major Events / Companies to Watch / hero) must not go empty just because the NEWEST events are unscored (real temp SQLite)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.db.models_legacy  # noqa: F401
from app.db.base import Base
from app.db.models.event import Event
from app.services.event_lifecycle import get_top_active_events

NOW = datetime.now(timezone.utc)


async def _db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'lc.db'}", connect_args={"check_same_thread": False})
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    return engine, sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_newest_unscored_events_do_not_hide_older_scored_ones(tmp_path):
    engine, factory = await _db(tmp_path)
    async with factory() as s:
        for i in range(400):                          # 400 NEWEST events, all unscored (enrichment is behind)
            s.add(Event(id=f"u{i}", title=f"routine filing {i}", summary="x", source="NSE", published_at=NOW - timedelta(minutes=i), event_date=NOW - timedelta(minutes=i),
                        impact_score=None, companies=["TCS"], sectors=[]))
        for i, score in enumerate((75.0, 70.0, 66.0, 58.0)):        # older but real scored events, still inside the 7-day window
            s.add(Event(id=f"s{i}", title=f"scored event {i}", summary="x", source="NDTV Profit", published_at=NOW - timedelta(hours=20 + i), event_date=NOW - timedelta(hours=20 + i),
                        impact_score=score, confidence=60.0, companies=[{"symbol": "RELIANCE", "name": "Reliance", "impact": "Positive"}], sectors=["Energy"]))
        await s.commit()
    async with factory() as db:
        top = await get_top_active_events(db, limit=5)
    await engine.dispose()
    assert [e.id for e in top][:3] and {e.id for e in top} == {"s0", "s1", "s2", "s3"}        # the 4 scored events surface; before the fix this was []
    assert all(e.impact_score for e in top)
    assert any(c.symbol == "RELIANCE" for e in top for c in e.companies)                       # so "Companies to Watch" has real companies to show


@pytest.mark.asyncio
async def test_unscored_events_are_still_never_ranked(tmp_path):
    engine, factory = await _db(tmp_path)
    async with factory() as s:
        for i in range(5):
            s.add(Event(id=f"u{i}", title=f"filing {i}", summary="x", source="NSE", published_at=NOW - timedelta(minutes=i), event_date=NOW - timedelta(minutes=i), impact_score=None, companies=[], sectors=[]))
        s.add(Event(id="zero", title="zero score", summary="x", source="NSE", published_at=NOW, event_date=NOW, impact_score=0, companies=[], sectors=[]))
        await s.commit()
    async with factory() as db:
        assert await get_top_active_events(db, limit=5) == []                                  # nothing scored: an honest empty list, no fabricated fallback
    await engine.dispose()
