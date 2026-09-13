"""
P7 Candidate Ownership Arbitration (owner design, 2026-09-13) —
regression tests.

Locked policy under test: a High-tier (never Critical) candidate may be
withheld from V1 for exactly one AIPE cycle, so V2 can attempt real
ownership, only when the immediately preceding cycle's own shadow
execution for that exact event independently reached would_publish=True,
stage_reached=P4, c8_tier=ARTICLE, c5_publication_action=CREATE_NEW
(not UPDATE_EXISTING -- V2 must have wanted a NEW article, not agreed
this is an update), collision_gate_outcome=no_collision (post-gate
evidence only -- NULL/not_evaluated historical rows are ineligible),
evidence_count>=3 (the real P6-B median, not an invented number), a
resolved canonical entity, no existing real coverage, and no prior
withhold ever recorded for this event (a real, unique-indexed DB
invariant, not just an application-level check-then-insert).

Fixed test date: none needed -- all timestamps are relative to a
controlled cycle_start_time passed explicitly, matching how
publisher.py's run_aipe_cycle() calls this in production (one
wall-clock timestamp captured at cycle start, passed through).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.db.models.article_v2_canary_withhold import ArticleV2CanaryWithhold
from app.db.models.article_v2_shadow_execution import ArticleV2ShadowExecution
from app.db.models.event_coverage import EventCoverage
from app.db.session import AsyncSessionLocal
from app.services.article_v2.ownership_arbitration import (
    _FRESHNESS_WINDOW_SECONDS, _MIN_EVIDENCE_COUNT, should_withhold_for_v2_canary,
)


def _tag():
    return uuid.uuid4().hex[:10]


_QUALIFYING_DEFAULTS = dict(
    would_publish=True, stage_reached="P4", c8_tier="ARTICLE",
    c5_publication_action="CREATE_NEW", collision_gate_outcome="no_collision",
    evidence_count=5, pipeline_mode="shadow_v2",
)


async def _seed_shadow_execution(db, *, triage_event_id: str, created_at: datetime, canonical_entity_id="cmp_test", **overrides) -> str:
    fields = dict(_QUALIFYING_DEFAULTS)
    fields.update(overrides)
    shadow_id = f"shadow-{uuid.uuid4()}"
    db.add(ArticleV2ShadowExecution(
        id=shadow_id, triage_event_id=triage_event_id, symbol="TEST",
        canonical_entity_id=canonical_entity_id, created_at=created_at,
        evidence_ids=[], **fields,
    ))
    return shadow_id


async def _seed_coverage(db, *, event_id: str, coverage_status: str) -> None:
    db.add(EventCoverage(
        id=str(uuid.uuid4()), event_id=event_id, priority="High", priority_score=50,
        detected_at=datetime.now(timezone.utc), event_title="Test event",
        sectors=[], companies=[], article_required=True, coverage_status=coverage_status,
        last_checked_at=datetime.now(timezone.utc),
    ))


async def _cleanup(*event_ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id.in_(event_ids)))
        await db.execute(delete(ArticleV2ShadowExecution).where(ArticleV2ShadowExecution.triage_event_id.in_(event_ids)))
        await db.execute(delete(EventCoverage).where(EventCoverage.event_id.in_(event_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_eligible_candidate_is_withheld_and_row_recorded():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    prior_created = cycle_start - timedelta(minutes=5)
    async with AsyncSessionLocal() as db:
        shadow_id = await _seed_shadow_execution(db, triage_event_id=event_id, created_at=prior_created)
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start)
        assert result.should_withhold is True
        assert result.prior_shadow_execution_id == shadow_id
        assert result.reason_predicates["c5_publication_action"] == "CREATE_NEW"
        assert result.reason_predicates["collision_gate_outcome"] == "no_collision"

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            row = (await db.execute(select(ArticleV2CanaryWithhold).where(ArticleV2CanaryWithhold.triage_event_id == event_id))).scalar_one()
        assert row.prior_shadow_execution_id == shadow_id
        assert row.reason_predicates["evidence_count"] == 5
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_second_call_never_withholds_the_same_event_again():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await _seed_shadow_execution(db, triage_event_id=event_id, created_at=cycle_start - timedelta(minutes=5))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            first = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start)
        assert first.should_withhold is True

        # Simulate next cycle: even with a fresh, still-qualifying shadow row.
        async with AsyncSessionLocal() as db:
            await _seed_shadow_execution(db, triage_event_id=event_id, created_at=cycle_start + timedelta(minutes=4, seconds=55))
            await db.commit()
        async with AsyncSessionLocal() as db:
            second = await should_withhold_for_v2_canary(
                db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start + timedelta(minutes=5),
            )
        assert second.should_withhold is False
        assert "already withheld" in second.reason
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_critical_tier_is_never_withheld_regardless_of_evidence():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await _seed_shadow_execution(db, triage_event_id=event_id, created_at=cycle_start - timedelta(minutes=5))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="Critical", cycle_start_time=cycle_start)
        assert result.should_withhold is False
        assert "not eligible" in result.reason
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_medium_tier_is_not_eligible_either():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await _seed_shadow_execution(db, triage_event_id=event_id, created_at=cycle_start - timedelta(minutes=5))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="Medium", cycle_start_time=cycle_start)
        assert result.should_withhold is False
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_stale_prior_shadow_row_is_rejected():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    stale_created = cycle_start - timedelta(seconds=_FRESHNESS_WINDOW_SECONDS + 60)  # well outside the window
    async with AsyncSessionLocal() as db:
        await _seed_shadow_execution(db, triage_event_id=event_id, created_at=stale_created)
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start)
        assert result.should_withhold is False
        assert "freshness window" in result.reason
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_would_publish_false_is_rejected():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await _seed_shadow_execution(db, triage_event_id=event_id, created_at=cycle_start - timedelta(minutes=5), would_publish=False)
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start)
        assert result.should_withhold is False
        assert "would_publish" in result.reason
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_c8_tier_not_article_is_rejected():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await _seed_shadow_execution(db, triage_event_id=event_id, created_at=cycle_start - timedelta(minutes=5), c8_tier="EVENT_ONLY")
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start)
        assert result.should_withhold is False
        assert "c8_tier" in result.reason
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_production_observed_shape_update_existing_with_not_evaluated_must_not_withhold():
    """The test the owner specifically required, directly motivated by
    real production telemetry: a candidate that reached P4/ARTICLE/
    would_publish=True but which C5 itself resolved as UPDATE_EXISTING
    (so the collision gate correctly never evaluated it,
    collision_gate_outcome=not_evaluated) must NEVER be withheld -- V2
    didn't want a new canonical article for this event in the first
    place, so standing V1 aside would serve nothing."""
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await _seed_shadow_execution(
            db, triage_event_id=event_id, created_at=cycle_start - timedelta(minutes=5),
            c5_publication_action="UPDATE_EXISTING", collision_gate_outcome=None,
        )
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start)
        assert result.should_withhold is False
        assert "CREATE_NEW" in result.reason
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_collision_gate_outcome_resolved_existing_is_rejected_even_if_create_new():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await _seed_shadow_execution(
            db, triage_event_id=event_id, created_at=cycle_start - timedelta(minutes=5),
            c5_publication_action="CREATE_NEW", collision_gate_outcome="resolved_existing",
        )
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start)
        assert result.should_withhold is False
        assert "no_collision" in result.reason
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_unresolved_canonical_entity_is_rejected():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await _seed_shadow_execution(db, triage_event_id=event_id, created_at=cycle_start - timedelta(minutes=5), canonical_entity_id=None)
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start)
        assert result.should_withhold is False
        assert "canonical_entity_id" in result.reason
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_evidence_count_below_floor_is_rejected():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await _seed_shadow_execution(db, triage_event_id=event_id, created_at=cycle_start - timedelta(minutes=5), evidence_count=_MIN_EVIDENCE_COUNT - 1)
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start)
        assert result.should_withhold is False
        assert "evidence_count" in result.reason
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_existing_real_coverage_is_rejected():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await _seed_shadow_execution(db, triage_event_id=event_id, created_at=cycle_start - timedelta(minutes=5))
        await _seed_coverage(db, event_id=event_id, coverage_status="PUBLISHED")
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start)
        assert result.should_withhold is False
        assert "coverage" in result.reason
    finally:
        await _cleanup(event_id)


@pytest.mark.asyncio
async def test_no_prior_shadow_execution_at_all_is_rejected():
    event_id = f"evt-{_tag()}"
    cycle_start = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await should_withhold_for_v2_canary(db, triage_event_id=event_id, ev_tier="High", cycle_start_time=cycle_start)
    assert result.should_withhold is False
    assert "no prior shadow execution" in result.reason


@pytest.mark.asyncio
async def test_unique_constraint_fails_closed_on_duplicate_withhold_insert():
    """DB-level invariant proof: a second ArticleV2CanaryWithhold row for
    the same triage_event_id must be rejected by the unique index, not
    merely avoided by application-level convention. Directly proves the
    fail-closed contract (V1 retains ownership) rather than trusting
    should_withhold_for_v2_canary's own pre-check alone."""
    event_id = f"evt-{_tag()}"
    async with AsyncSessionLocal() as db:
        db.add(ArticleV2CanaryWithhold(
            id=f"withhold-{uuid.uuid4()}", triage_event_id=event_id,
            prior_shadow_execution_id="shadow-1", reason_predicates={},
            withheld_at=datetime.now(timezone.utc),
        ))
        await db.commit()
    try:
        with pytest.raises(IntegrityError):
            async with AsyncSessionLocal() as db:
                db.add(ArticleV2CanaryWithhold(
                    id=f"withhold-{uuid.uuid4()}", triage_event_id=event_id,
                    prior_shadow_execution_id="shadow-2", reason_predicates={},
                    withheld_at=datetime.now(timezone.utc),
                ))
                await db.commit()
    finally:
        await _cleanup(event_id)
