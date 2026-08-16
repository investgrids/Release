"""
Phase 5A.6 — shared sync hardening: real-DB proof of the invariants
that must hold regardless of which source is running.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.db.models.economic_calendar import EconomicCalendarEvent
from app.services.economic_calendar.sync_engine import CalendarCandidate, upsert_calendar_event
from app.services.economic_calendar.sync_orchestrator import (
    REAL_SOURCES, is_stale, run_source_sync, get_source_health,
)
from app.services.economic_calendar.rbi_source import fetch_rbi_mpc_candidates


def _candidate(**overrides) -> CalendarCandidate:
    base = dict(
        identity_key="test_cat:XX:2026-01", reference_period="2026-01",
        title="Test Event", category="test_cat", country="XX",
        scheduled_at=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        source_timezone="UTC", importance="medium", source="rbi", source_tier="tier_1",
    )
    base.update(overrides)
    return CalendarCandidate(**base)


async def _cleanup(prefix: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key.like(f"{prefix}%")))
        await db.commit()


# ── Tier precedence ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lower_tier_never_overwrites_higher_tier_schedule():
    key = "tier_test:XX:2026-01"
    await _cleanup(key)

    tier1 = _candidate(identity_key=key, source="rbi", source_tier="tier_1",
                        scheduled_at=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc))
    async with AsyncSessionLocal() as db:
        created = await upsert_calendar_event(db, tier1)
    assert created["action"] == "created"

    # A tier_3 source disagrees with the schedule — must be rejected, not applied.
    tier3_conflicting = _candidate(identity_key=key, source="news_wire", source_tier="tier_3",
                                    scheduled_at=datetime(2026, 1, 20, 10, 0, tzinfo=timezone.utc))
    async with AsyncSessionLocal() as db:
        result = await upsert_calendar_event(db, tier3_conflicting)
    assert result["action"] == "skipped_lower_tier"

    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(EconomicCalendarEvent).where(EconomicCalendarEvent.identity_key == key))).scalar_one()
    assert row.scheduled_at.day == 15   # tier_1's original schedule, untouched
    assert row.source == "rbi"

    await _cleanup(key)


@pytest.mark.asyncio
async def test_same_tier_source_can_update_its_own_schedule():
    """Sanity check on the other side of the same rule — a same-tier
    (or more authoritative) source updating its own prior value must
    still work; only a LESS authoritative source is blocked."""
    key = "tier_test_same:XX:2026-01"
    await _cleanup(key)

    first = _candidate(identity_key=key, source="rbi", source_tier="tier_1")
    async with AsyncSessionLocal() as db:
        await upsert_calendar_event(db, first)

    updated = _candidate(identity_key=key, source="rbi", source_tier="tier_1",
                          scheduled_at=datetime(2026, 1, 16, 10, 0, tzinfo=timezone.utc))
    async with AsyncSessionLocal() as db:
        result = await upsert_calendar_event(db, updated)
    assert result["action"] == "updated"

    await _cleanup(key)


# ── Staleness ────────────────────────────────────────────────────────────

def test_is_stale_pure_function():
    now = datetime(2026, 8, 16, tzinfo=timezone.utc)
    fresh = now - timedelta(days=1)
    stale = now - timedelta(days=10)
    assert is_stale(fresh, now=now) is False
    assert is_stale(stale, now=now) is True
    # naive datetime (SQLite read-back) must still be handled, not raise
    assert is_stale(fresh.replace(tzinfo=None), now=now) is False


@pytest.mark.asyncio
async def test_get_source_health_flags_stale_and_fresh_sources():
    key_fresh, key_stale = "health_fresh:XX:2026-01", "health_stale:XX:2026-01"
    await _cleanup(key_fresh)
    await _cleanup(key_stale)

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(
            id=str(uuid.uuid4()), identity_key=key_fresh, reference_period="2026-01",
            title="Fresh", category="test_cat", country="XX",
            scheduled_at=now + timedelta(days=30), source_timezone="UTC", importance="medium",
            status="scheduled", source="rbi", source_tier="tier_1", last_verified_at=now,
        ))
        db.add(EconomicCalendarEvent(
            id=str(uuid.uuid4()), identity_key=key_stale, reference_period="2026-01",
            title="Stale", category="test_cat", country="XX",
            scheduled_at=now + timedelta(days=30), source_timezone="UTC", importance="medium",
            status="scheduled", source="mospi", source_tier="tier_1",
            last_verified_at=now - timedelta(days=30),
        ))
        await db.commit()

    async with AsyncSessionLocal() as db:
        health = await get_source_health(db)
    by_source = {h["source"]: h for h in health}

    assert by_source["rbi"]["is_stale"] is False
    assert by_source["mospi"]["is_stale"] is True
    assert by_source["rbi"]["is_real_source"] is True

    await _cleanup(key_fresh)
    await _cleanup(key_stale)


# ── Run orchestration ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_source_sync_counts_outcomes_correctly():
    key = "orchestrator_test:XX:2026-01"
    await _cleanup(key)

    calls = {"n": 0}

    async def fetch_fn():
        calls["n"] += 1
        return [_candidate(identity_key=key)]

    first = await run_source_sync("test_source", fetch_fn)
    assert first == {"source": "test_source", "fetched": 1, "ok": True, "elapsed_ms": first["elapsed_ms"],
                      "created": 1, "updated": 0, "unchanged": 0, "skipped_lower_tier": 0}

    second = await run_source_sync("test_source", fetch_fn)
    assert second["created"] == 0
    assert second["unchanged"] == 1

    await _cleanup(key)


@pytest.mark.asyncio
async def test_run_source_sync_reports_failure_without_touching_rows():
    async def failing_fetch():
        return []

    result = await run_source_sync("test_source_down", failing_fetch)
    assert result["ok"] is False
    assert result["fetched"] == 0


@pytest.mark.asyncio
async def test_run_source_sync_against_real_rbi_source():
    """One real end-to-end smoke test through the shared orchestrator,
    not just synthetic candidates — confirms the orchestration path
    itself works against a live source, matching this package's
    established real-data discipline."""
    await _cleanup("rbi_mpc:")
    result = await run_source_sync("rbi", fetch_rbi_mpc_candidates)
    assert result["ok"] is True
    assert result["fetched"] > 0
    assert result["created"] == result["fetched"]
    await _cleanup("rbi_mpc:")


# ── Seed/test isolation ──────────────────────────────────────────────────

def test_real_sources_allowlist_matches_actual_ingestion_tags():
    assert REAL_SOURCES == {"rbi", "mospi", "fed", "bls"}


@pytest.mark.asyncio
async def test_non_allowlisted_source_tag_is_flagged_not_real():
    key = "seed_isolation_test:XX:2026-01"
    await _cleanup(key)
    async with AsyncSessionLocal() as db:
        db.add(EconomicCalendarEvent(
            id=str(uuid.uuid4()), identity_key=key, reference_period="2026-01",
            title="Seed row", category="test_cat", country="XX",
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=1), source_timezone="UTC",
            importance="medium", status="scheduled", source="seed", source_tier="tier_3",
            last_verified_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    async with AsyncSessionLocal() as db:
        health = await get_source_health(db)
    seed_entry = next(h for h in health if h["source"] == "seed")
    assert seed_entry["is_real_source"] is False

    await _cleanup(key)
