"""
In-memory SQLite fixtures for the AI pipeline smoke tests. Uses StaticPool
so the same connection (and therefore the same in-memory database) is
reused across the whole test — a fresh `sqlite+aiosqlite:///:memory:`
connection would otherwise hand back an empty, unseeded database on every
query.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.event import Event


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


async def _seed(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    session.add_all([
        Event(
            id="evt-rbi-rate-cut-test",
            title="RBI cuts repo rate by 25 bps to support growth",
            summary=(
                "The Reserve Bank of India cut the repo rate by 25 basis points, "
                "aiming to boost credit growth and support banking sector lending."
            ),
            description="RBI's Monetary Policy Committee voted to reduce the repo rate.",
            source="RBI",
            event_type="policy",
            category="monetary_policy",
            event_date=now,
            published_at=now,
            impact_score=8.0,
            confidence=0.8,
            sectors=["Banking", "NBFCs"],
            companies=[{
                "symbol": "HDFCBANK", "name": "HDFC Bank",
                "impact": "positive", "impact_score": 7.5,
                "reason": "Lower rates boost credit growth and NIM outlook",
            }],
            ai_summary={
                "summary": "RBI's rate cut is expected to boost bank lending and consumer credit demand.",
                "why_it_matters": "Lower borrowing costs typically support economic growth and bank margins.",
                "key_bullets": ["Repo rate cut by 25bps", "Expected to boost credit growth"],
                "immediate_impact": "positive",
                "long_term_impact": "positive",
                "risk_factors": ["Inflation risk if rates stay low too long"],
                "opportunities": ["Banking sector credit growth"],
            },
        ),
        Event(
            id="evt-defence-budget-test",
            title="Union Budget allocates record capex for defence indigenisation",
            summary=(
                "The government's latest budget significantly increases defence capital "
                "expenditure, favoring domestic manufacturers."
            ),
            description="Budget 2026 defence allocation raised sharply for indigenous procurement.",
            source="Budget",
            event_type="policy",
            category="defence",
            event_date=now,
            published_at=now,
            impact_score=8.5,
            confidence=0.75,
            sectors=["Defence", "Capital Goods"],
            companies=[{
                "symbol": "HAL", "name": "Hindustan Aeronautics",
                "impact": "positive", "impact_score": 8.0,
                "reason": "Direct beneficiary of higher defence capex and indigenisation push",
            }],
            ai_summary={
                "summary": "Budget allocates record defence capex favoring domestic manufacturers like HAL.",
                "why_it_matters": "Higher defence spending directly benefits domestic manufacturers via larger order books.",
                "key_bullets": ["Record defence capex", "Focus on indigenisation"],
                "immediate_impact": "positive",
                "long_term_impact": "positive",
                "risk_factors": ["Execution risk on large capex programs"],
                "opportunities": ["Defence manufacturing order book growth"],
            },
        ),
    ])
    await session.commit()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await _seed(session)
        yield session
