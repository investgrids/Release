"""
opportunity_v2/orchestration.py — real DB-backed end-to-end tests against
the real Intelligence Graph (via link_development_to_graph, not mocked).
generate_narrative is monkeypatched only where a test needs deterministic
AI success/failure (same precedent as test_ai_service_nvidia.py for
external-call tests) -- everything else (gate, coherence, identity,
scoring, DB writes) runs for real.

This is the module the user's own verification checklist targets
end-to-end: Aditya Birla/Goldman stay separate, repeated runs update
instead of duplicating, AI failure never blocks persistence.

Every run_shadow_pass() call below passes a `since` bound scoped to just
the fixtures each test creates (see _since()) — confirmed live,
2026-08-22: an unbounded call processes every real open Development in
the local dev DB (900+ rows, 10+ minutes), which is what made an earlier
run of this file look hung rather than merely slow.

Don't run this file while the local uvicorn dev server (or any other
process writing to the same sqlite dev DB) is running — confirmed live,
2026-08-22: a concurrent live server caused a real `database is locked`
error during a test's own cleanup teardown.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models.development import Development, DevelopmentEvidence
from app.db.models.intelligence_graph import IGEdge, IGNode
from app.db.models.opportunity_v2 import OpportunityV2, OpportunityV2Development
from app.db.session import AsyncSessionLocal
from app.services.development_memory.graph_link import link_development_to_graph
from app.services.opportunity_v2 import orchestration as orch
from app.services.opportunity_v2.generation import NarrativeResult
from app.services.opportunity_v2.orchestration import _narrative_input_hash


async def _cleanup(development_ids: list[str], node_ids: list[str], opportunity_ids: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        if opportunity_ids:
            await db.execute(delete(OpportunityV2Development).where(OpportunityV2Development.opportunity_id.in_(opportunity_ids)))
            await db.execute(delete(OpportunityV2).where(OpportunityV2.id.in_(opportunity_ids)))
        if development_ids:
            await db.execute(delete(DevelopmentEvidence).where(DevelopmentEvidence.development_id.in_(development_ids)))
            await db.execute(delete(Development).where(Development.id.in_(development_ids)))
        if node_ids:
            await db.execute(delete(IGEdge).where(IGEdge.source_id.in_(node_ids) | IGEdge.target_id.in_(node_ids)))
            await db.execute(delete(IGNode).where(IGNode.id.in_(node_ids)))
        await db.commit()


def _since() -> datetime:
    """A `since` bound scoped to just-created fixtures (owner instruction,
    2026-08-22: tests must not traverse the entire real Development
    history — run_shadow_pass(limit=1000) with no `since` bound processes
    every real open Development, which took 10+ minutes against the real
    local dev DB and is exactly what made the original test runs look
    hung rather than slow). A few seconds of slack absorbs clock skew
    between this call and _make_dev()'s own `datetime.now()`."""
    return datetime.now(timezone.utc) - timedelta(seconds=10)


def _make_dev(title: str, *, companies: list[str] | None = None, sectors: list[str] | None = None,
              confidence: float = 0.9) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()), canonical_title=title, status="open",
        primary_company=(companies or [None])[0], companies=companies or [], sectors=sectors or [],
        themes=[], first_observed_at=now, last_observed_at=now,
        formation_impact_tier="High", current_direction="positive", current_confidence=confidence,
        evidence_count=1, schema_version="test",
    )


async def _link(dev: Development) -> str:
    async with AsyncSessionLocal() as db:
        db.add(dev)
        await db.commit()
        node_id = await link_development_to_graph(db, dev)
        assert node_id
        dev.ig_node_id = node_id
        db.add(dev)
        await db.commit()
    return node_id


async def _all_opportunities_for(dev_ids: list[str]) -> list[OpportunityV2]:
    async with AsyncSessionLocal() as db:
        links = (await db.execute(
            select(OpportunityV2Development.opportunity_id).where(OpportunityV2Development.development_id.in_(dev_ids))
        )).scalars().all()
        if not links:
            return []
        return (await db.execute(select(OpportunityV2).where(OpportunityV2.id.in_(set(links))))).scalars().all()


@pytest.mark.asyncio
async def test_aditya_birla_goldman_regression_stays_separate_end_to_end():
    """The literal reported bug, run through the full real pipeline."""
    since = _since()
    dev_a = _make_dev("Aditya Birla Capital enters gold loan market", sectors=["Banking"])
    dev_b = _make_dev("Goldman rates Indian banks", sectors=["Banking"])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev_a))
        node_ids.append(await _link(dev_b))
        node_ids.append("sector:banking")

        async with AsyncSessionLocal() as db:
            summary = await orch.run_shadow_pass(db, since=since, limit=50)

        opps_a = await _all_opportunities_for([dev_a.id])
        opps_b = await _all_opportunities_for([dev_b.id])
        opp_ids = [o.id for o in (opps_a + opps_b)]

        assert len(opps_a) == 1 and len(opps_b) == 1
        assert opps_a[0].id != opps_b[0].id, "shared sector alone must never merge these into one opportunity"
    finally:
        await _cleanup([dev_a.id, dev_b.id], node_ids, opp_ids)


@pytest.mark.asyncio
async def test_repeated_runs_update_the_same_thesis_not_duplicate(monkeypatch):
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    ticker = f"TREP{uuid.uuid4().hex[:6].upper()}"
    dev = _make_dev("Company announces real expansion", companies=[ticker], sectors=["Banking"])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev))

        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)  # rerun over the SAME data

        opps = await _all_opportunities_for([dev.id])
        opp_ids = [o.id for o in opps]
        assert len(opps) == 1, "a rerun over unchanged data must update, never duplicate"
    finally:
        await _cleanup([dev.id], node_ids, opp_ids)


@pytest.mark.asyncio
async def test_new_evidence_merges_into_existing_open_opportunity(monkeypatch):
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    ticker = f"TMRG{uuid.uuid4().hex[:6].upper()}"
    dev_a = _make_dev("First real development about the company", companies=[ticker])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev_a))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)
        opps_after_first = await _all_opportunities_for([dev_a.id])
        assert len(opps_after_first) == 1
        first_id = opps_after_first[0].id

        dev_b = _make_dev("Second real development, same company", companies=[ticker])
        node_ids.append(await _link(dev_b))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opps_after_second = await _all_opportunities_for([dev_a.id, dev_b.id])
        opp_ids = [o.id for o in opps_after_second]
        assert {o.id for o in opps_after_second} == {first_id}, "real new evidence for the same company must merge into the existing open thesis, not create a second one"

        async with AsyncSessionLocal() as db:
            links = (await db.execute(
                select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == first_id)
            )).scalars().all()
        assert set(links) == {dev_a.id, dev_b.id}
    finally:
        await _cleanup([dev_a.id, dev_b.id], node_ids, opp_ids)


@pytest.mark.asyncio
async def test_ai_generation_failure_does_not_block_the_deterministic_candidate(monkeypatch):
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_fail)
    since = _since()
    ticker = f"TFAIL{uuid.uuid4().hex[:5].upper()}"
    dev = _make_dev("Real development with no AI capacity available", companies=[ticker])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opps = await _all_opportunities_for([dev.id])
        opp_ids = [o.id for o in opps]
        assert len(opps) == 1
        opp = opps[0]
        assert opp.candidate_status == "formed"
        assert opp.narrative_status == "failed_capacity"
        assert opp.current_score is not None  # deterministic fields still real and persisted
        assert opp.current_title is None  # never a fabricated substitute title
    finally:
        await _cleanup([dev.id], node_ids, opp_ids)


@pytest.mark.asyncio
async def test_unrelated_companies_never_merge_even_when_processed_in_the_same_pass():
    since = _since()
    ticker_a = f"TX{uuid.uuid4().hex[:6].upper()}"
    ticker_b = f"TY{uuid.uuid4().hex[:6].upper()}"
    dev_a = _make_dev("Pharma company real news", companies=[ticker_a], sectors=["Pharma"])
    dev_b = _make_dev("Auto company real news", companies=[ticker_b], sectors=["Automotive"])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev_a))
        node_ids.append(await _link(dev_b))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opps_a = await _all_opportunities_for([dev_a.id])
        opps_b = await _all_opportunities_for([dev_b.id])
        opp_ids = [o.id for o in (opps_a + opps_b)]
        assert len(opps_a) == 1 and len(opps_b) == 1
        assert opps_a[0].id != opps_b[0].id
    finally:
        await _cleanup([dev_a.id, dev_b.id], node_ids, opp_ids)


@pytest.mark.asyncio
async def test_reused_narrative_makes_zero_generation_calls_on_unchanged_evidence(monkeypatch):
    """Regression guard (owner instruction, 2026-08-22): confirmed live
    that a worker running repeatedly in production would re-spend a paid
    LLM call every single pass with zero evidence change — narrative_
    input_hash exists specifically to make the second call here a no-op."""
    call_count = {"n": 0}

    async def _counting_ok(evidence_text, sectors, companies) -> NarrativeResult:
        call_count["n"] += 1
        return NarrativeResult(
            title="A stable real-shaped test title for reuse", summary="Summary.", matters="Matters.",
            benefits="Benefits.", risks=["Risk one"], invalidate="Invalidate.", why_bullets=["Bullet one"],
        )

    monkeypatch.setattr(orch, "generate_narrative", _counting_ok)
    since = _since()
    ticker = f"THASH{uuid.uuid4().hex[:5].upper()}"
    dev = _make_dev("Real development for narrative reuse check", companies=[ticker])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)
        assert call_count["n"] == 1

        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)  # identical input again
        assert call_count["n"] == 1, "unchanged evidence must not trigger a second generation call"

        opps = await _all_opportunities_for([dev.id])
        opp_ids = [o.id for o in opps]
        assert len(opps) == 1
        assert opps[0].narrative_input_hash is not None
    finally:
        await _cleanup([dev.id], node_ids, opp_ids)


@pytest.mark.asyncio
async def test_narrative_evidence_stays_cumulative_even_if_a_linked_development_closes(monkeypatch):
    """Regression guard (owner instruction, 2026-08-22): confirmed live
    that a Development which merged into an opportunity in an earlier
    pass, then later closed, silently vanished from BOTH the narrative
    evidence text and its hash on the next pass — because they were being
    computed from that pass's transient cluster instead of the
    opportunity's full cumulative linked-Development set."""
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    ticker = f"TCUM{uuid.uuid4().hex[:5].upper()}"
    dev_a = _make_dev("First real development before it closes", companies=[ticker])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev_a))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)
        opps = await _all_opportunities_for([dev_a.id])
        assert len(opps) == 1
        opp_id = opps[0].id

        dev_b = _make_dev("Second real development, same company", companies=[ticker])
        node_ids.append(await _link(dev_b))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        # dev_a "ages out" — closes, so _fetch_open_developments no longer
        # returns it as a candidate on the next pass.
        async with AsyncSessionLocal() as db:
            dev_a_row = await db.get(Development, dev_a.id)
            dev_a_row.status = "closed"
            await db.commit()

        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        async with AsyncSessionLocal() as db:
            opp = await db.get(OpportunityV2, opp_id)
            links = (await db.execute(
                select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opp_id)
            )).scalars().all()
            both_devs = (await db.execute(select(Development).where(Development.id.in_([dev_a.id, dev_b.id])))).scalars().all()
        opp_ids = [opp_id]
        assert set(links) == {dev_a.id, dev_b.id}, "dev_a must stay linked even after closing"

        expected_hash = _narrative_input_hash(both_devs, opp.companies or [], opp.sectors or [], opp.thesis_anchor, opp.thesis_direction)
        assert opp.narrative_input_hash == expected_hash, "hash must reflect BOTH linked developments, not just whichever are still open this pass"
    finally:
        await _cleanup([dev_a.id, dev_b.id], node_ids, opp_ids)


async def _fake_narrative_ok(evidence_text, sectors, companies) -> NarrativeResult:
    return NarrativeResult(
        title="A real-shaped test title for this thesis", summary="Summary.", matters="Matters.",
        benefits="Benefits.", risks=["Risk one"], invalidate="Invalidate.", why_bullets=["Bullet one"],
    )


async def _fake_narrative_fail(evidence_text, sectors, companies) -> None:
    return None
