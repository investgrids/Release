"""
Opportunity V2 orchestration vs. a PUBLIC row — real end-to-end proof
(2026-09-26, Current Intelligence dedup verification follow-up).

Original finding (now fixed, see orchestration.py's own comment on the
`frozen` check in _process_cluster): find_matching_open_opportunity()
(identity.py) matches purely on (thesis_anchor, thesis_direction,
status=="open") with no public_status check, so a normal shadow pass used
to silently overwrite current_score/score_breakdown/contradictions/
sectors/companies on an ALREADY-PUBLIC row exactly like any shadow row —
confirmed empirically by an earlier version of this test. public_status
and the 4 editorial_* fields were already safe (no code in orchestration.py
ever wrote them); the score/signal fields were not.

The fix: _process_cluster() now checks whether the matched existing row is
public and, if so, skips writing current_score/score_breakdown/
contradictions/sectors/companies entirely — logging what the recompute
WOULD have been (opportunity_v2.orchestration.public_row_score_frozen)
rather than silently applying it. Development linkage still happens (new
evidence keeps accumulating for a future EXPLICIT refresh, not implemented
here), and narrative regeneration is untouched (out of this fix's scope —
editorial override already protects narrative display regardless of what
the generated narrative does).

This test proves the fix through the real run_shadow_pass() pipeline
(never a direct call to the private _process_cluster), using the same
real-graph/real-DB/monkeypatched-narrative-only pattern as
test_opportunity_v2_orchestration_persistence.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models.company_signal import AICompanySignal
from app.db.models.development import Development, DevelopmentEvidence
from app.db.models.intelligence_graph import IGEdge, IGNode
from app.db.models.opportunity_v2 import OpportunityV2, OpportunityV2Development
from app.db.session import AsyncSessionLocal
from app.services.development_memory.graph_link import link_development_to_graph
from app.services.opportunity_v2 import orchestration as orch
from app.services.opportunity_v2.generation import NarrativeResult


def _since() -> datetime:
    return datetime.now(timezone.utc) - timedelta(seconds=10)


def _make_dev(title: str, *, companies: list[str] | None = None, sectors: list[str] | None = None) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()), canonical_title=title, status="open",
        primary_company=(companies or [None])[0], companies=companies or [], sectors=sectors or [],
        themes=[], first_observed_at=now, last_observed_at=now,
        formation_impact_tier="High", current_direction="positive", current_confidence=0.9,
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


async def _cleanup(development_ids, node_ids, opportunity_ids, signal_symbols=None):
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
        if signal_symbols:
            await db.execute(delete(AICompanySignal).where(AICompanySignal.symbol.in_(signal_symbols)))
        await db.commit()


async def _opportunity_for(dev_id: str) -> OpportunityV2 | None:
    async with AsyncSessionLocal() as db:
        link = (await db.execute(
            select(OpportunityV2Development.opportunity_id).where(OpportunityV2Development.development_id == dev_id)
        )).scalars().first()
        if not link:
            return None
        return await db.get(OpportunityV2, link)


async def _fake_narrative_ok(evidence_text, sectors, companies) -> NarrativeResult:
    return NarrativeResult(
        title="Real-shaped generated title", summary="Generated summary.", matters="Matters.",
        benefits="Benefits.", risks=["Risk one"], invalidate="Invalidate.", why_bullets=["Bullet one"],
    )


@pytest.mark.asyncio
async def test_public_row_score_and_signals_are_frozen_when_a_cluster_reprocesses(monkeypatch):
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    ticker = f"TPUB{uuid.uuid4().hex[:6].upper()}"

    dev_a = _make_dev("First real development forming the public thesis", companies=[ticker], sectors=["Banking"])
    dev_b = None
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev_a))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp = await _opportunity_for(dev_a.id)
        assert opp is not None
        opp_ids = [opp.id]
        score_before = opp.current_score
        breakdown_before = opp.score_breakdown
        companies_before = opp.companies
        assert score_before is not None

        # Simulate the real canary state: promoted to public with an
        # editorial override applied — exactly the Adani row's real shape
        # (real admin action, never done by orchestration.py itself).
        editorial_title = "The real, human-edited public title"
        editorial_summary = "The real, human-edited public summary."
        editorial_reason = "Generated narrative overclaimed beyond its evidence."
        editorial_at = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            row = await db.get(OpportunityV2, opp.id)
            row.public_status = "public"
            row.editorial_title = editorial_title
            row.editorial_summary = editorial_summary
            row.editorial_reason = editorial_reason
            row.editorial_updated_at = editorial_at
            await db.commit()

        # A real new signal for the same company, strong enough to move
        # company_confirmation and therefore current_score IF it were
        # recomputed — proves the freeze is real, not just "nothing new
        # to compute anyway".
        async with AsyncSessionLocal() as db:
            db.add(AICompanySignal(
                source_type="article", source_id="test-public-row", symbol=ticker,
                company_name="Test Public Co", sector="Banking",
                signed_magnitude=90.0, confidence=0.95, quality=0.95,
                signal_at=datetime.now(timezone.utc),
            ))
            await db.commit()

        # A second real Development, same company -> same (thesis_anchor,
        # thesis_direction) identity -> find_matching_open_opportunity()
        # matches the SAME row we just made public, purely on identity.
        dev_b = _make_dev("Second real development, same company, reprocesses the public row", companies=[ticker], sectors=["Banking"])
        node_ids.append(await _link(dev_b))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        async with AsyncSessionLocal() as db:
            reprocessed = await db.get(OpportunityV2, opp.id)

        # Editorial content and public_status — protected before and after this fix.
        assert reprocessed.public_status == "public"
        assert reprocessed.editorial_title == editorial_title
        assert reprocessed.editorial_summary == editorial_summary
        assert reprocessed.editorial_reason == editorial_reason
        assert reprocessed.editorial_updated_at.replace(tzinfo=timezone.utc) == editorial_at

        # Score/signal fields — the real fix: frozen, not silently recomputed.
        assert reprocessed.current_score == score_before, "a public row's score must never change from a routine shadow pass"
        assert reprocessed.score_breakdown == breakdown_before, "a public row's persisted breakdown must not be silently replaced"
        assert reprocessed.companies == companies_before

        # The new real signal was NOT folded in — proves this isn't an
        # accidental no-op (e.g. the cluster failing to match) but a
        # deliberate skip of a real, available update.
        signals = reprocessed.score_breakdown["company_signals"]
        matching = [s for s in signals if s.get("symbol") == ticker]
        assert len(matching) == 1
        assert matching[0]["score"] is None, "the frozen breakdown must still be the pre-promotion one, which had no real signal for this company yet"

        # Development linkage still happens even while frozen — evidence
        # keeps accumulating for a future explicit refresh.
        async with AsyncSessionLocal() as db:
            linked = (await db.execute(
                select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opp.id)
            )).scalars().all()
        assert dev_b.id in linked, "new evidence must still be linked even while the score itself is frozen"
    finally:
        dev_ids = [dev_a.id] + ([dev_b.id] if dev_b is not None else [])
        await _cleanup(dev_ids, node_ids, opp_ids, [ticker])


@pytest.mark.asyncio
async def test_shadow_row_still_updates_normally(monkeypatch):
    """Control case: the freeze must be specific to public_status=="public"
    -- an ordinary shadow row must keep updating exactly as before."""
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    ticker = f"TSHADOW{uuid.uuid4().hex[:6].upper()}"

    dev_a = _make_dev("First real development, stays shadow", companies=[ticker], sectors=["Banking"])
    dev_b = None
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev_a))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp = await _opportunity_for(dev_a.id)
        assert opp is not None
        opp_ids = [opp.id]
        assert opp.public_status == "shadow"
        score_before = opp.current_score

        async with AsyncSessionLocal() as db:
            db.add(AICompanySignal(
                source_type="article", source_id="test-shadow-row", symbol=ticker,
                company_name="Test Shadow Co", sector="Banking",
                signed_magnitude=90.0, confidence=0.95, quality=0.95,
                signal_at=datetime.now(timezone.utc),
            ))
            await db.commit()

        dev_b = _make_dev("Second real development, same company, reprocesses the shadow row", companies=[ticker], sectors=["Banking"])
        node_ids.append(await _link(dev_b))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        async with AsyncSessionLocal() as db:
            reprocessed = await db.get(OpportunityV2, opp.id)

        assert reprocessed.current_score != score_before, "a real shadow row must keep updating normally — the freeze is public-status-specific"
        signals = reprocessed.score_breakdown["company_signals"]
        matching = [s for s in signals if s.get("symbol") == ticker]
        assert matching[0]["score"] is not None, "the new real signal must be folded in for a shadow row"
    finally:
        dev_ids = [dev_a.id] + ([dev_b.id] if dev_b is not None else [])
        await _cleanup(dev_ids, node_ids, opp_ids, [ticker])
