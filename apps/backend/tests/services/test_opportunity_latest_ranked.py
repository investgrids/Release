"""The Market Overview's opportunity list is the best of the NEWEST opportunities, not the all-time top scores (real temp SQLite)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.db.models_legacy  # noqa: F401
from app.db.base import Base
from app.db.models.opportunity import Opportunity
from app.repositories.opportunity_repository import OpportunityRepository

NOW = datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_old_high_scores_do_not_outrank_recent_opportunities(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'o.db'}", connect_args={"check_same_thread": False})
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        for i in range(10):                                   # months-old, top scores
            s.add(Opportunity(slug=f"old-{i}", title=f"old {i}", summary="x", opportunity_score=98.0 - i * 0.1, confidence=50, trend="up", risk_level="Low", time_horizon="Short", sectors=["IT"], created_at=NOW - timedelta(days=80 + i), updated_at=NOW - timedelta(days=80 + i)))
        for i in range(8):                                    # this week, lower scores
            s.add(Opportunity(slug=f"new-{i}", title=f"new {i}", summary="x", opportunity_score=70.0 + i, confidence=50, trend="up", risk_level="Low", time_horizon="Short", sectors=["IT"], created_at=NOW - timedelta(hours=i), updated_at=NOW - timedelta(hours=i)))
        await s.commit()
    async with factory() as db:
        top = await OpportunityRepository(db).list_latest_ranked(limit=6, pool=8)
    await engine.dispose()
    assert [o.slug for o in top] == [f"new-{i}" for i in range(7, 1, -1)]      # newest pool only, best score first
    assert all(o.slug.startswith("new-") for o in top)
