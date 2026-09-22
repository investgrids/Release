"""
Regression test for the leaked seed-fixture repair (2026-09-22).

evt-rbi-june-2026/evt-defence-budget-2026/evt-solar-capacity-2026 leaked
into production because app/db/seed.py's write functions had no
production guard of their own — main.py's lifespan gated its OWN call
site, but any other caller (a test, a script, a future refactor) could
call seed()/seed_missing_events() directly and insert this hand-written
placeholder content straight into a production database. The fix added
`if settings.is_production: return` to the top of all 4 write functions
in seed.py itself — this test proves that guard holds regardless of who
calls it, not just main.py's own lifespan.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.models.event import Event

_LEAKED_FIXTURE_IDS = ("evt-rbi-june-2026", "evt-defence-budget-2026", "evt-solar-capacity-2026")


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
def _restore_json_logs():
    original = settings.json_logs
    yield
    settings.json_logs = original


async def test_seed_inserts_nothing_when_is_production_true(db_session):
    from app.db.seed import seed

    settings.json_logs = True  # is_production reads this directly
    assert settings.is_production is True

    await seed(db_session)

    result = await db_session.execute(select(Event))
    assert result.scalars().all() == [], "seed() must insert zero rows when is_production is True"


async def test_seed_missing_events_inserts_none_of_the_leaked_fixture_ids_when_is_production_true(db_session):
    from app.db.seed import seed_missing_events

    settings.json_logs = True
    assert settings.is_production is True

    await seed_missing_events(db_session)

    result = await db_session.execute(select(Event.id))
    ids = set(result.scalars().all())
    assert ids == set(), "seed_missing_events() must insert zero rows when is_production is True"
    for leaked_id in _LEAKED_FIXTURE_IDS:
        assert leaked_id not in ids


async def test_seed_missing_events_still_seeds_normally_when_not_production(db_session):
    """Confirms the new guard doesn't disable the function outright —
    only production is blocked; dev/staging keeps working exactly as
    before this fix."""
    from app.db.seed import seed_missing_events

    settings.json_logs = False
    assert settings.is_production is False

    await seed_missing_events(db_session)

    result = await db_session.execute(select(Event.id))
    ids = set(result.scalars().all())
    assert set(_LEAKED_FIXTURE_IDS).issubset(ids)


async def test_seed_missing_stories_and_calendar_also_guarded_in_production(db_session):
    from app.db.models_legacy import CalendarEvent, Story
    from app.db.seed import seed_missing_calendar, seed_missing_stories

    settings.json_logs = True
    assert settings.is_production is True

    await seed_missing_stories(db_session)
    await seed_missing_calendar(db_session)

    stories = (await db_session.execute(select(Story))).scalars().all()
    calendar = (await db_session.execute(select(CalendarEvent))).scalars().all()
    assert stories == []
    assert calendar == []
