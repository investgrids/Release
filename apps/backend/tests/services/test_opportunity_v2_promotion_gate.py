"""
promotion_gate.py::evaluate_promotion_eligibility -- real DB-backed
tests. No database write happens inside the gate itself; these tests
prove that (a) a rejection returns the exact machine-readable reason
and full evaluated detail, (b) the row is provably untouched by the
gate call alone, and (c) mixed/material/ordinary opportunities remain
eligible.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.development import Development, DevelopmentEvidence
from app.db.models.event import Event
from app.db.models.opportunity_v2 import OpportunityV2, OpportunityV2Development
from app.db.session import AsyncSessionLocal
from app.services.opportunity_v2.promotion_gate import (
    REASON_ROUTINE_FILING_ONLY,
    REASON_SYNTHETIC_EXPOSURE,
    evaluate_promotion_eligibility,
)


def _make_opp(*, public_status: str = "shadow") -> OpportunityV2:
    now = datetime.now(timezone.utc)
    return OpportunityV2(
        id=str(uuid.uuid4()), thesis_anchor="company:gatetest", thesis_direction="positive",
        status="open", source="test",
        candidate_status="formed", narrative_status="generated", public_status=public_status,
        formation_title="Real Gate Test Opportunity", formation_score=50.0, formation_at=now,
        current_title="Real Gate Test Opportunity", current_summary="Real summary.", current_score=50.0,
        sectors=[], companies=[], contradictions=[],
        slug=f"real-gate-test-{uuid.uuid4().hex[:8]}",
        created_at=now, updated_at=now,
    )


def _make_dev(title: str) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()), canonical_title=title, status="open",
        primary_company=None, companies=[], sectors=[], themes=[],
        first_observed_at=now, last_observed_at=now,
        formation_impact_tier="High", current_direction="positive", current_confidence=0.8,
        evidence_count=1, schema_version="test",
    )


def _make_event(event_type: str) -> Event:
    now = datetime.now(timezone.utc)
    return Event(
        id=f"test-event-{uuid.uuid4().hex[:10]}", title="Real test event", event_type=event_type,
        event_date=now, source="test",
    )


async def _link(opp: OpportunityV2, devs: list[Development], event_types: dict[str, str]) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        db.add(opp)
        for d in devs:
            db.add(d)
        await db.commit()
        for d in devs:
            db.add(OpportunityV2Development(opportunity_id=opp.id, development_id=d.id, added_at=now))
            et = event_types.get(d.id)
            if et is not None:
                ev = _make_event(et)
                db.add(ev)
                await db.flush()
                db.add(DevelopmentEvidence(
                    id=str(uuid.uuid4()), development_id=d.id, source_type="event", source_id=ev.id,
                    evidence_key=ev.id, observed_at=now, match_tier="seed", membership_confidence=1.0,
                    added_at=now,
                ))
        await db.commit()


async def _cleanup(opp_ids: list[str], dev_ids: list[str], event_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        if opp_ids:
            await db.execute(delete(OpportunityV2Development).where(OpportunityV2Development.opportunity_id.in_(opp_ids)))
            await db.execute(delete(OpportunityV2).where(OpportunityV2.id.in_(opp_ids)))
        if dev_ids:
            await db.execute(delete(DevelopmentEvidence).where(DevelopmentEvidence.development_id.in_(dev_ids)))
            await db.execute(delete(Development).where(Development.id.in_(dev_ids)))
        if event_ids:
            await db.execute(delete(Event).where(Event.id.in_(event_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_routine_only_rejected_and_row_provably_untouched():
    opp = _make_opp()
    dev = _make_dev("Real Co Ltd has submitted the Exchange a copy Srutinizers report of Postal Ballot.")
    await _link(opp, [dev], {})
    try:
        async with AsyncSessionLocal() as db:
            result = await evaluate_promotion_eligibility(db, opp.id)
        assert result.allowed is False
        assert result.reason == REASON_ROUTINE_FILING_ONLY
        assert len(result.evaluated) == 1
        assert result.evaluated[0]["is_routine"] is True

        async with AsyncSessionLocal() as db:
            refreshed = await db.get(OpportunityV2, opp.id)
        assert refreshed.public_status == "shadow"  # provably untouched
        assert refreshed.current_summary == "Real summary."
        assert refreshed.current_score == 50.0
        assert refreshed.candidate_status == "formed"
        assert refreshed.narrative_status == "generated"
    finally:
        await _cleanup([opp.id], [dev.id], [])


@pytest.mark.asyncio
async def test_material_development_alone_is_accepted():
    opp = _make_opp()
    dev = _make_dev("Reliance announces $2B acquisition of renewable energy assets")
    await _link(opp, [dev], {})
    try:
        async with AsyncSessionLocal() as db:
            result = await evaluate_promotion_eligibility(db, opp.id)
        assert result.allowed is True
        assert result.reason is None
    finally:
        await _cleanup([opp.id], [dev.id], [])


@pytest.mark.asyncio
async def test_mixed_routine_and_material_cluster_is_accepted():
    opp = _make_opp()
    routine_dev = _make_dev("Real Co Ltd has informed the Exchange regarding Proceedings of Annual General Meeting")
    material_dev = _make_dev("Real Co Ltd announces resignation of Managing Director")
    await _link(opp, [routine_dev, material_dev], {})
    try:
        async with AsyncSessionLocal() as db:
            result = await evaluate_promotion_eligibility(db, opp.id)
        assert result.allowed is True
        assert len(result.evaluated) == 2
    finally:
        await _cleanup([opp.id], [routine_dev.id, material_dev.id], [])


@pytest.mark.asyncio
async def test_synthetic_exposure_development_is_rejected_even_with_a_material_sibling():
    """The stricter, presence-based veto -- unlike routine-only, a SINGLE
    synthetic-exposure Development rejects the whole opportunity even if
    another linked Development is genuinely material."""
    opp = _make_opp()
    synthetic_dev = _make_dev("Directly exposed to Energy opportunity through core operations.")
    material_dev = _make_dev("Reliance announces $2B acquisition of renewable energy assets")
    await _link(opp, [synthetic_dev, material_dev], {})
    try:
        async with AsyncSessionLocal() as db:
            result = await evaluate_promotion_eligibility(db, opp.id)
        assert result.allowed is False
        assert result.reason == REASON_SYNTHETIC_EXPOSURE
    finally:
        await _cleanup([opp.id], [synthetic_dev.id, material_dev.id], [])


@pytest.mark.asyncio
async def test_ordinary_opportunity_with_no_linked_developments_is_accepted():
    opp = _make_opp()
    async with AsyncSessionLocal() as db:
        db.add(opp)
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            result = await evaluate_promotion_eligibility(db, opp.id)
        assert result.allowed is True
        assert result.evaluated == []
    finally:
        await _cleanup([opp.id], [], [])


@pytest.mark.asyncio
async def test_earnings_event_type_prevents_a_routine_looking_title_from_being_classified_routine():
    opp = _make_opp()
    dev = _make_dev("Annual General Meeting proceedings")
    await _link(opp, [dev], {dev.id: "earnings"})
    try:
        async with AsyncSessionLocal() as db:
            result = await evaluate_promotion_eligibility(db, opp.id)
        # An earnings-tagged event makes this dev NOT routine (real
        # structured pre-filter) -- so with only 1 dev and it's not
        # routine, the opportunity is accepted (not routine-only).
        assert result.allowed is True
        assert result.evaluated[0]["is_routine"] is False
    finally:
        await _cleanup([opp.id], [dev.id], [])
