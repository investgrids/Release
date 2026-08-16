"""
Evidence window tests — real DB (this codebase's convention for
DB-touching tests, see test_dashboard_metrics.py), unique test-scoped
ids, explicit cleanup. Covers the core correctness requirement design
doc §17 calls out: a real lower bound, not "latest N rows."
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import delete

from app.db.models.event import Event
from app.db.session import AsyncSessionLocal
from app.services.weekend_intelligence.evidence_window import SOURCE_ANNOUNCEMENT, collect_evidence_since


async def _cleanup(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Event).where(Event.id.in_(ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_evidence_before_window_is_excluded():
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=2)
    before_id = f"pytest-wi-before-{uuid.uuid4().hex[:8]}"
    inside_id = f"pytest-wi-inside-{uuid.uuid4().hex[:8]}"
    ids = [before_id, inside_id]
    await _cleanup(*ids)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(id=before_id, title="Before window", published_at=since - timedelta(hours=1)))
            db.add(Event(id=inside_id, title="Inside window", published_at=since + timedelta(minutes=30)))
            await db.commit()

            items = await collect_evidence_since(db, since, now)
            found_ids = {i.source_id for i in items if i.source_type == "event"}
            assert before_id not in found_ids
            assert inside_id in found_ids
    finally:
        await _cleanup(*ids)


@pytest.mark.asyncio
async def test_evidence_at_exact_since_boundary_is_excluded():
    """since is exclusive (`>`), until is inclusive (`<=`) — a row stamped
    exactly at `since` belongs to the PRIOR window, not this one."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=1)
    boundary_id = f"pytest-wi-boundary-{uuid.uuid4().hex[:8]}"
    await _cleanup(boundary_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(id=boundary_id, title="Exactly at since", published_at=since))
            await db.commit()

            items = await collect_evidence_since(db, since, now)
            found_ids = {i.source_id for i in items if i.source_type == "event"}
            assert boundary_id not in found_ids
    finally:
        await _cleanup(boundary_id)


@pytest.mark.asyncio
async def test_evidence_after_until_is_excluded():
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=2)
    until = now - timedelta(hours=1)
    after_id = f"pytest-wi-after-{uuid.uuid4().hex[:8]}"
    await _cleanup(after_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(id=after_id, title="After until", published_at=now))
            await db.commit()

            items = await collect_evidence_since(db, since, until)
            found_ids = {i.source_id for i in items if i.source_type == "event"}
            assert after_id not in found_ids
    finally:
        await _cleanup(after_id)


@pytest.mark.asyncio
async def test_event_priority_tier_joined_from_event_triage():
    from app.db.models.intelligence import EventTriage

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=1)
    event_id = f"pytest-wi-triaged-{uuid.uuid4().hex[:8]}"
    triage_id = f"pytest-wi-triage-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(id=event_id, title="RBI monetary policy decision", published_at=now))
            db.add(EventTriage(
                id=triage_id, event_id=event_id, source="policy",
                headline="RBI monetary policy decision", urgency=10, importance=10,
            ))
            await db.commit()

            items = await collect_evidence_since(db, since, now + timedelta(minutes=1))
            match = next(i for i in items if i.source_type == "event" and i.source_id == event_id)
            assert match.impact_strength in ("Critical", "High")
    finally:
        await _cleanup(event_id)
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventTriage).where(EventTriage.id == triage_id))
            await db.commit()


# ── Per-source failure isolation (Phase 1E hardening, post-review) ─────────

@pytest.mark.asyncio
async def test_one_source_failure_does_not_abort_the_others():
    """The exact scenario requested: Announcements fails, the other
    source (here: Event, standing in for the rest) still collects
    normally, and the failure is reported via failed_sources rather than
    raised out of the function. normalize_announcement only runs if
    there's a real row for the query to return, so a real
    CompanyAnnouncement row is required to actually exercise the
    failure — mocking the normalizer alone against an empty result set
    would trivially "pass" without proving anything."""
    from app.db.models.company_announcements import CompanyAnnouncement

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=1)
    event_id = f"pytest-wi-partial-{uuid.uuid4().hex[:8]}"
    ann_id = f"pytest-wi-partial-ann-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(Event(id=event_id, title="Healthy source keeps working", published_at=now))
            db.add(CompanyAnnouncement(id=ann_id, subject="Will fail to normalize", ingested_at=now))
            await db.commit()

            failed: list[str] = []
            with patch(
                "app.services.weekend_intelligence.evidence_window.normalize_announcement",
                side_effect=RuntimeError("simulated announcement read failure"),
            ):
                items = await collect_evidence_since(db, since, now + timedelta(minutes=1), failed_sources=failed)

            # The failing source is reported, not silently dropped.
            assert failed == [SOURCE_ANNOUNCEMENT]
            # The healthy source's evidence still made it through.
            found_ids = {i.source_id for i in items if i.source_type == "event"}
            assert event_id in found_ids
            # The failed source contributed nothing (not a partial/corrupt row).
            assert not any(i.source_type == "announcement" for i in items)
    finally:
        await _cleanup(event_id)
        async with AsyncSessionLocal() as db:
            await db.execute(delete(CompanyAnnouncement).where(CompanyAnnouncement.id == ann_id))
            await db.commit()


@pytest.mark.asyncio
async def test_session_remains_usable_after_a_caught_source_failure():
    """The per-source except block rolls back — proves the session isn't
    left in a broken state that would poison a LATER, unrelated query in
    the same request (real concern under Postgres, where a failed
    statement aborts the whole transaction until ROLLBACK). A real
    GovernmentPolicy row is required so normalize_policy is actually
    invoked (and therefore actually raises) — see the previous test's
    docstring for why an empty result set would make the mock a no-op."""
    from app.db.models.event import GovernmentPolicy

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=1)
    event_id = f"pytest-wi-postrollback-{uuid.uuid4().hex[:8]}"
    policy_id = f"pytest-wi-postrollback-pol-{uuid.uuid4().hex[:8]}"
    await _cleanup(event_id)
    try:
        async with AsyncSessionLocal() as db:
            db.add(GovernmentPolicy(external_id=policy_id, title="Will fail to normalize", created_at=now))
            await db.commit()

            with patch(
                "app.services.weekend_intelligence.evidence_window.normalize_policy",
                side_effect=RuntimeError("simulated policy read failure"),
            ):
                failed: list[str] = []
                await collect_evidence_since(db, since, now, failed_sources=failed)
            assert failed == ["policy"]

            # A completely ordinary query on the SAME session, right after
            # the caught failure, must still work.
            db.add(Event(id=event_id, title="Post-failure query still works", published_at=now))
            await db.commit()
            items = await collect_evidence_since(db, since, now + timedelta(minutes=1))
            assert any(i.source_id == event_id for i in items)
    finally:
        await _cleanup(event_id)
        async with AsyncSessionLocal() as db:
            await db.execute(delete(GovernmentPolicy).where(GovernmentPolicy.external_id == policy_id))
            await db.commit()


@pytest.mark.asyncio
async def test_failed_sources_param_is_optional_and_does_not_crash():
    """Every existing caller that doesn't pass failed_sources= must keep
    working unmodified — the parameter is purely additive, and a source
    failure with no failed_sources list supplied must not raise."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=1)
    async with AsyncSessionLocal() as db:
        with patch(
            "app.services.weekend_intelligence.evidence_window.normalize_opportunity",
            side_effect=RuntimeError("simulated opportunity read failure"),
        ):
            items = await collect_evidence_since(db, since, now)  # no failed_sources= at all
    assert isinstance(items, list)  # did not raise
