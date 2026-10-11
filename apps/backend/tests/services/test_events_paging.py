"""get_events pages by offset and filters scored events in SQL, so events of any age are reachable (real temp SQLite)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.db.models_legacy  # noqa: F401
from app.db.base import Base
from app.db.crud import get_events
from app.db.models.event import Event

NOW = datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_offset_reaches_old_scored_events_beyond_the_newest_pool(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'p.db'}", connect_args={"check_same_thread": False})
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        for i in range(400):                      # 400 newest events, all unscored (routine filings)
            s.add(Event(id=f"u{i}", title=f"filing {i}", summary="x", source="NSE", published_at=NOW - timedelta(minutes=i), impact_score=None, companies=[], sectors=[]))
        for i in range(30):                       # 30 scored events, all OLDER than every unscored one
            s.add(Event(id=f"s{i}", title=f"scored {i}", summary="x", source="NSE", published_at=NOW - timedelta(days=30, minutes=i), impact_score=50.0, companies=[], sectors=[]))
        await s.commit()
    async with factory() as db:
        p1 = await get_events(db, limit=20, offset=0, scored_only=True)
        p2 = await get_events(db, limit=20, offset=20, scored_only=True)
        unscored = await get_events(db, limit=5, offset=395)
    await engine.dispose()
    assert [e.id for e in p1] == [f"s{i}" for i in range(20)]            # the old scored events are found at all
    assert [e.id for e in p2] == [f"s{i}" for i in range(20, 30)]        # and page 2 continues without overlap
    assert all(e.impact_score is not None for e in p1 + p2)
    assert len(unscored) == 5                                            # offset also works without the filter
