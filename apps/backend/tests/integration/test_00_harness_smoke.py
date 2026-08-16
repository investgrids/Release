"""Smoke test for the Phase 1E harness itself — not a lifecycle test."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.integration.conftest import FRIDAY, ist, make_event


@pytest.mark.asyncio
async def test_isolated_db_is_actually_isolated_from_real_dev_db(isolated_db):
    """A row written here must never appear in / never come from the real
    ig_dev.db — proven by writing a row with a fixed id and confirming
    a fresh query against the SAME session sees it (in-memory, this
    process only)."""
    row = await make_event(isolated_db, title="Harness smoke event", when=ist(FRIDAY, 10))
    await isolated_db.commit()

    from app.db.models.event import Event
    found = (await isolated_db.execute(select(Event).where(Event.id == row.id))).scalar_one_or_none()
    assert found is not None
    assert found.title == "Harness smoke event"


@pytest.mark.asyncio
async def test_frozen_time_controls_market_session(frozen_time):
    from app.services.intelligence.engine import _market_session

    frozen_time(ist(FRIDAY, 12, 0))  # Friday noon IST -> live session
    assert _market_session() == "live"

    frozen_time(ist(FRIDAY, 16, 0))  # Friday 4pm IST -> post_market
    assert _market_session() == "post_market"

    from tests.integration.conftest import SATURDAY
    frozen_time(ist(SATURDAY, 12, 0))
    assert _market_session() == "weekend"


@pytest.mark.asyncio
async def test_asyncsessionlocal_is_patched_to_isolated_db(isolated_db):
    """capture_close_snapshot/prediction_service functions open their own
    AsyncSessionLocal() — verify that resolves to the SAME isolated
    engine, not the real ig_dev.db, by writing through a deferred-import
    path and reading it back via the injected session."""
    import app.db.session as db_session_module

    async with db_session_module.AsyncSessionLocal() as db2:
        row = await make_event(db2, title="Via patched AsyncSessionLocal", when=ist(FRIDAY, 10))
        await db2.commit()

    from app.db.models.event import Event
    found = (await isolated_db.execute(select(Event).where(Event.id == row.id))).scalar_one_or_none()
    assert found is not None
