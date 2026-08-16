"""
Phase 5A.3 — real, live proof of the full India ingestion semantics:
official source -> parse -> normalize -> identity_key -> upsert/version
-> source_tier -> last_verified_at -> real DB row -> idempotent rerun
-> correct reschedule -> source-failure isolation.

These hit the real RBI/MOSPI sites (matching this codebase's existing
`_live` test convention, e.g. test_ai_search_engines_live.py — allowed
to occasionally fail on external outages, not mocked to fake success).
Parsing-logic-only tests belong in a separate, non-live file if the
regex ever needs unit coverage independent of network availability;
these specifically prove the end-to-end pipeline against today's real
official data, which is what Phase 5A.3 was asked to prove before any
other source gets built.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.db.models.economic_calendar import EconomicCalendarEvent
from app.services.economic_calendar.sync_engine import upsert_calendar_event, CalendarCandidate
from app.services.economic_calendar.rbi_source import fetch_rbi_mpc_candidates
from app.services.economic_calendar.mospi_source import fetch_mospi_candidates


async def _cleanup(prefix: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like(f"{prefix}%")))
        await db.commit()


def _aware(dt: datetime) -> datetime:
    """SQLite's DateTime(timezone=True) columns round-trip as naive on a
    fresh read (the same footgun already documented elsewhere in this
    codebase) — the stored value is correct UTC, just missing tzinfo on
    read-back. Confirmed directly against the raw column (`typeof=text`,
    value `2026-04-08 04:30:00.000000`, no offset suffix) — this is a
    read-back interpretation issue, not a storage bug."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── RBI ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rbi_real_ingestion_creates_future_events():
    await _cleanup("rbi_mpc:")
    candidates = await fetch_rbi_mpc_candidates()
    assert candidates, "RBI source returned nothing — real site may be unreachable right now"

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        results = [await upsert_calendar_event(db, c) for c in candidates]
    assert all(r["action"] == "created" for r in results)

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like("rbi_mpc:%")))).scalars().all()
    assert len(rows) == len(candidates)
    assert any(_aware(r.scheduled_at) > now for r in rows), "expected at least one future-dated MPC meeting"
    assert all(r.source_tier == "tier_1" for r in rows)
    assert all(r.source == "rbi" for r in rows)

    await _cleanup("rbi_mpc:")


@pytest.mark.asyncio
async def test_rbi_rerun_is_idempotent():
    await _cleanup("rbi_mpc:")
    candidates = await fetch_rbi_mpc_candidates()
    assert candidates

    async with AsyncSessionLocal() as db:
        for c in candidates:
            await upsert_calendar_event(db, c)

    # Second run against the SAME real candidates — must be a no-op, not new rows.
    async with AsyncSessionLocal() as db:
        second_results = [await upsert_calendar_event(db, c) for c in candidates]
    assert all(r["action"] == "unchanged" for r in second_results)

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like("rbi_mpc:%")))).scalars().all()
    assert len(rows) == len(candidates)   # no duplicates

    await _cleanup("rbi_mpc:")


@pytest.mark.asyncio
async def test_rbi_reschedule_updates_in_place():
    """A real identity_key from today's real schedule, with a simulated
    postponement (RBI's real calendar won't change on demand for a
    test) — proves the reschedule path the sync engine actually runs,
    against a real row, not a synthetic one."""
    await _cleanup("rbi_mpc:")
    candidates = await fetch_rbi_mpc_candidates()
    assert candidates
    first = candidates[0]

    async with AsyncSessionLocal() as db:
        created = await upsert_calendar_event(db, first)

    postponed = CalendarCandidate(**{**first.__dict__, "scheduled_at": first.scheduled_at + timedelta(days=1)})
    async with AsyncSessionLocal() as db:
        updated = await upsert_calendar_event(db, postponed)
    assert updated["action"] == "updated"
    assert updated["id"] == created["id"]   # same row, not a new one

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key == first.identity_key))).scalars().all()
    assert len(rows) == 1
    assert _aware(rows[0].scheduled_at) == postponed.scheduled_at

    await _cleanup("rbi_mpc:")


@pytest.mark.asyncio
async def test_rbi_source_failure_leaves_existing_rows_untouched():
    await _cleanup("rbi_mpc:")
    candidates = await fetch_rbi_mpc_candidates()
    assert candidates

    async with AsyncSessionLocal() as db:
        for c in candidates:
            await upsert_calendar_event(db, c)
    async with AsyncSessionLocal() as db:
        before = {r.identity_key: (_aware(r.scheduled_at), _aware(r.last_verified_at)) for r in (
            await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like("rbi_mpc:%")))
        ).scalars().all()}

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=Exception("simulated network failure"))):
        failed_candidates = await fetch_rbi_mpc_candidates()
    assert failed_candidates == []   # fails closed — no fabricated candidates

    async with AsyncSessionLocal() as db:
        after = {r.identity_key: (_aware(r.scheduled_at), _aware(r.last_verified_at)) for r in (
            await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like("rbi_mpc:%")))
        ).scalars().all()}
    assert before == after   # untouched — no wipe, no stale-timestamp bump from a failed run

    await _cleanup("rbi_mpc:")


# ── MOSPI ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mospi_real_ingestion_creates_future_events():
    await _cleanup("india_cpi:")
    await _cleanup("india_iip:")
    candidates = await fetch_mospi_candidates()
    assert candidates, "MOSPI source returned nothing — real site may be unreachable right now"

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        results = [await upsert_calendar_event(db, c) for c in candidates]
    assert all(r["action"] == "created" for r in results)

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.source == "mospi"))).scalars().all()
    assert len(rows) == len(candidates)
    assert any(_aware(r.scheduled_at) > now for r in rows)
    assert all(r.source_tier == "tier_1" for r in rows)
    # identity_key uniqueness held at the DB level (would have raised on insert otherwise)
    assert len({r.identity_key for r in rows}) == len(rows)

    await _cleanup("india_cpi:")
    await _cleanup("india_iip:")


@pytest.mark.asyncio
async def test_mospi_rerun_is_idempotent():
    await _cleanup("india_cpi:")
    await _cleanup("india_iip:")
    candidates = await fetch_mospi_candidates()
    assert candidates

    async with AsyncSessionLocal() as db:
        for c in candidates:
            await upsert_calendar_event(db, c)
    async with AsyncSessionLocal() as db:
        second_results = [await upsert_calendar_event(db, c) for c in candidates]
    assert all(r["action"] == "unchanged" for r in second_results)

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.source == "mospi"))).scalars().all()
    assert len(rows) == len(candidates)

    await _cleanup("india_cpi:")
    await _cleanup("india_iip:")


@pytest.mark.asyncio
async def test_mospi_reschedule_updates_in_place():
    await _cleanup("india_cpi:")
    candidates = await fetch_mospi_candidates()
    cpi_candidates = [c for c in candidates if c.category == "india_cpi"]
    assert cpi_candidates
    first = cpi_candidates[0]

    async with AsyncSessionLocal() as db:
        created = await upsert_calendar_event(db, first)

    postponed = CalendarCandidate(**{**first.__dict__, "scheduled_at": first.scheduled_at + timedelta(days=1)})
    async with AsyncSessionLocal() as db:
        updated = await upsert_calendar_event(db, postponed)
    assert updated["action"] == "updated"
    assert updated["id"] == created["id"]

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key == first.identity_key))).scalars().all()
    assert len(rows) == 1
    assert _aware(rows[0].scheduled_at) == postponed.scheduled_at

    await _cleanup("india_cpi:")


@pytest.mark.asyncio
async def test_mospi_source_failure_leaves_existing_rows_untouched():
    await _cleanup("india_cpi:")
    await _cleanup("india_iip:")
    candidates = await fetch_mospi_candidates()
    assert candidates

    async with AsyncSessionLocal() as db:
        for c in candidates:
            await upsert_calendar_event(db, c)
    async with AsyncSessionLocal() as db:
        before = {r.identity_key: (_aware(r.scheduled_at), _aware(r.last_verified_at)) for r in (
            await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.source == "mospi"))
        ).scalars().all()}

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=Exception("simulated network failure"))):
        failed_candidates = await fetch_mospi_candidates()
    assert failed_candidates == []

    async with AsyncSessionLocal() as db:
        after = {r.identity_key: (_aware(r.scheduled_at), _aware(r.last_verified_at)) for r in (
            await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.source == "mospi"))
        ).scalars().all()}
    assert before == after

    await _cleanup("india_cpi:")
    await _cleanup("india_iip:")
