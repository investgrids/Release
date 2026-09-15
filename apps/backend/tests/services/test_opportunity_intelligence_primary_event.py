"""
Opportunity PE-1 — Public Link Integrity (2026-09-15).

Real DB-backed (AsyncSessionLocal), matching this codebase's established
convention for DB-touching tests -- explicit insert, explicit cleanup.

The Opportunity `primary_event` Integrity Audit found OpportunityEvent.
event_id is a write-time snapshot with no DB-enforced FK to `events.id`
and no existence check -- 79.6% of real production opportunities had a
dangling top-ranked event. select_primary_event() is the read-time fix:
pick the highest-importance event among only the ones that actually
resolve to a real Event (by id OR slug, matching EventService.
get_event_detail's own id-then-slug resolution), never the dangling
top-ranked row just because it ranks highest.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.db.models.event import Event
from app.db.session import AsyncSessionLocal
from app.schemas.opportunity_detail import EventSchema
from app.services.opportunity_intelligence import select_primary_event


def _ev(event_id: str, importance: float, title: str = "t") -> EventSchema:
    return EventSchema(event_id=event_id, title=title, event_date="2026-09-01", tag="General", description="", importance=importance)


async def _create_event(event_id: str, slug: str | None = None) -> None:
    async with AsyncSessionLocal() as db:
        db.add(Event(id=event_id, title=f"Event {event_id}", slug=slug))
        await db.commit()


async def _cleanup(event_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Event).where(Event.id.in_(event_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_highest_ranked_event_wins_when_it_resolves():
    real_id = f"test-pe-{uuid.uuid4()}"
    await _create_event(real_id)
    try:
        events = [_ev(real_id, importance=5.0), _ev(f"news-{uuid.uuid4()}", importance=1.0)]
        async with AsyncSessionLocal() as db:
            result = await select_primary_event(db, events)
        assert result is not None
        assert result.event_id == real_id
    finally:
        await _cleanup([real_id])


@pytest.mark.asyncio
async def test_falls_back_to_a_lower_ranked_event_when_the_top_one_dangles():
    dangling_id = f"news-only-{uuid.uuid4()}"  # never inserted as an Event
    real_id = f"test-pe-{uuid.uuid4()}"
    await _create_event(real_id)
    try:
        events = [_ev(dangling_id, importance=9.0), _ev(real_id, importance=1.0)]
        async with AsyncSessionLocal() as db:
            result = await select_primary_event(db, events)
        assert result is not None
        assert result.event_id == real_id
    finally:
        await _cleanup([real_id])


@pytest.mark.asyncio
async def test_returns_none_when_every_linked_event_dangles():
    events = [_ev(f"news-only-{uuid.uuid4()}", importance=9.0), _ev(f"news-only-{uuid.uuid4()}", importance=1.0)]
    async with AsyncSessionLocal() as db:
        result = await select_primary_event(db, events)
    assert result is None


@pytest.mark.asyncio
async def test_seed_opportunity_identifiers_never_resolve_and_return_none():
    # Real seed data shape confirmed by the audit (opportunities.id 1-6,
    # source="seed") -- these deliberately reference no real table.
    events = [_ev("seed-ai-1", importance=1.0)]
    async with AsyncSessionLocal() as db:
        result = await select_primary_event(db, events)
    assert result is None


@pytest.mark.asyncio
async def test_resolves_via_slug_when_event_id_only_matches_a_slug():
    # EventService.get_event_detail accepts either the real id or the
    # real slug -- select_primary_event must offer the same compatibility,
    # not just an exact id match.
    real_id = f"test-pe-{uuid.uuid4()}"
    slug = f"test-pe-slug-{uuid.uuid4()}"
    await _create_event(real_id, slug=slug)
    try:
        events = [_ev(slug, importance=1.0)]
        async with AsyncSessionLocal() as db:
            result = await select_primary_event(db, events)
        assert result is not None
        assert result.event_id == slug
    finally:
        await _cleanup([real_id])


@pytest.mark.asyncio
async def test_empty_events_list_returns_none_without_a_query():
    async with AsyncSessionLocal() as db:
        result = await select_primary_event(db, [])
    assert result is None
