"""
Phase 5A.1 — real-DB proof that the identity/versioning design actually
works, not just that the table creates. Three things the owner's
correction specifically depends on:

  1. identity_key never includes scheduled_at — a reschedule of the
     same economic event must NOT be representable as two rows.
  2. The partial unique index actually enforces "at most one current
     row per identity" at the DB level, not just by convention.
  3. A genuine revision creates a new row and preserves the prior
     row's values — nothing is silently overwritten.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.db.session import AsyncSessionLocal
from app.db.models.economic_calendar import EconomicCalendarEvent


def _row(**overrides) -> dict:
    # category/country deliberately synthetic ("test_cpi"/"XX") — never a
    # real category:country pair a live source could produce (real ones
    # are rbi_mpc/india_cpi/india_iip/fomc/us_cpi/us_jobs x IN/US), so
    # these fixtures can never collide with genuine ingested rows sharing
    # this same dev DB (real, confirmed collision found and fixed: an
    # earlier manual run_full_sync() left real rows with the exact
    # identity_key "us_cpi:US:2026-07" this fixture used to default to).
    base = dict(
        id=str(uuid.uuid4()),
        identity_key="test_cpi:XX:2026-07",
        reference_period="2026-07",
        title="Test CPI (July 2026)",
        category="test_cpi",
        country="XX",
        scheduled_at=datetime(2026, 8, 12, 12, 30, tzinfo=timezone.utc),
        source_timezone="America/New_York",
        importance="critical",
        status="scheduled",
        source="bls",
        source_tier="tier_1",
    )
    base.update(overrides)
    return base


async def _cleanup(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EconomicCalendarEvent).where(EconomicCalendarEvent.id.in_(ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_reschedule_is_an_update_not_a_new_identity():
    """A postponement (same event, different scheduled_at) must reuse the
    SAME identity_key — this is the owner's core correction: the date is
    not part of the event's identity."""
    row_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(**_row(id=row_id)))
        await db.commit()

        row = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.id == row_id))).scalar_one()
        original_identity = row.identity_key
        row.scheduled_at = datetime(2026, 8, 13, 12, 30, tzinfo=timezone.utc)   # postponed by one day
        await db.commit()

        reloaded = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.id == row_id))).scalar_one()
        assert reloaded.identity_key == original_identity
        assert reloaded.scheduled_at.day == 13

    await _cleanup(row_id)


@pytest.mark.asyncio
async def test_partial_unique_index_rejects_two_current_rows_same_identity():
    """Real DB constraint, not just application-level convention."""
    id_a, id_b = str(uuid.uuid4()), str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(**_row(id=id_a, identity_key="test_cpi_2:XX:2026-07")))
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(**_row(id=id_b, identity_key="test_cpi_2:XX:2026-07")))
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    await _cleanup(id_a, id_b)


@pytest.mark.asyncio
async def test_revision_preserves_prior_row_and_links_back():
    """A genuine data revision (corrected actual value) creates a NEW
    current row and flips the prior one's is_current — the prior actual
    value must still be readable afterward, never overwritten in place."""
    original_id = str(uuid.uuid4())
    revision_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(**_row(
            id=original_id, identity_key="test_jobs:XX:2026-07", status="released",
            actual=3.1, released_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )))
        await db.commit()

        # Flip the original to non-current, then insert the revision —
        # exactly the sequence the sync engine (Phase 5A.6) will perform.
        original = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.id == original_id))).scalar_one()
        original.is_current = False
        db.add(EconomicCalendarEvent(**_row(
            id=revision_id, identity_key="test_jobs:XX:2026-07", status="revised",
            actual=3.2, version=2, revision_of=original_id,
            released_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )))
        await db.commit()

        prior = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.id == original_id))).scalar_one()
        current = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.id == revision_id))).scalar_one()

        assert prior.is_current is False
        assert prior.actual == 3.1   # never overwritten
        assert current.is_current is True
        assert current.actual == 3.2
        assert current.revision_of == original_id

    await _cleanup(original_id, revision_id)


@pytest.mark.asyncio
async def test_forecast_defaults_to_none_never_fabricated():
    row_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(**_row(id=row_id, identity_key="test_mpc:XX:2026-10")))
        await db.commit()
        row = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.id == row_id))).scalar_one()
        assert row.forecast is None

    await _cleanup(row_id)
