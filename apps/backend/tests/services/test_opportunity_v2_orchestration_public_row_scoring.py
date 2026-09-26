"""
Opportunity V2 orchestration vs. a PUBLIC row — real end-to-end proof
(2026-09-26, Current Intelligence dedup verification follow-up).

The question this answers precisely: when run_shadow_pass() reprocesses a
cluster that matches an ALREADY-PUBLIC opportunity's (thesis_anchor,
thesis_direction) identity, what actually survives unchanged and what
doesn't?

find_matching_open_opportunity() (identity.py) matches on
(thesis_anchor, thesis_direction, status=="open") only -- it has no
public_status filter at all. _process_cluster() (orchestration.py) never
references public_status or any editorial_* field. So the real, correct
expectation is NOT "the public row is frozen" -- it's narrower:

  - public_status itself is never written by orchestration.py (the only
    real write path is the admin-gated canary-promote/revert endpoints,
    confirmed by a full-repo grep in an earlier engagement audit).
  - editorial_title/editorial_summary/editorial_reason/editorial_updated_at
    are never written by orchestration.py either (no such field name
    appears in that module) -- so read_service.py's editorial-takes-
    precedence display stays stable regardless of what else changes.
  - current_score/score_breakdown/contradictions/sectors/companies ARE
    NOT frozen -- a normal shadow pass recomputes and overwrites them on
    a public row exactly like any other "open" row, if that row's cluster
    reforms. This is by design (the promotion flag is a display gate, not
    a freeze), not something the Current Intelligence dedup fix changed.

This test proves all of that empirically through the real run_shadow_pass()
pipeline (never a direct call to the private _process_cluster), using the
same real-graph/real-DB/monkeypatched-narrative-only pattern as
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
async def test_public_status_and_editorial_fields_survive_a_reprocessed_cluster_but_score_does_not(monkeypatch):
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
        # company_confirmation and therefore current_score if recomputed.
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
        # matches the SAME row we just made public, purely on identity,
        # with no public_status check anywhere in that lookup.
        dev_b = _make_dev("Second real development, same company, reprocesses the public row", companies=[ticker], sectors=["Banking"])
        node_ids.append(await _link(dev_b))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        async with AsyncSessionLocal() as db:
            reprocessed = await db.get(OpportunityV2, opp.id)

        # What IS protected, empirically confirmed:
        assert reprocessed.public_status == "public", "orchestration.py must never touch public_status"
        assert reprocessed.editorial_title == editorial_title
        assert reprocessed.editorial_summary == editorial_summary
        assert reprocessed.editorial_reason == editorial_reason
        # SQLite's DateTime(timezone=True) round-trips as naive — compare
        # the wall-clock value, not tzinfo presence.
        assert reprocessed.editorial_updated_at.replace(tzinfo=timezone.utc) == editorial_at, \
            "editorial fields must never be silently touched by a shadow pass"

        # What is NOT protected — the real, by-design behavior this test
        # exists to make explicit rather than assumed: a public row's
        # underlying score/breakdown DOES get recomputed like any other
        # open row when its cluster reforms.
        assert reprocessed.current_score != score_before, (
            "current_score is NOT frozen on a public row — it is recomputed "
            "by any shadow pass whose cluster matches its thesis identity, "
            "public_status notwithstanding. This is pre-existing orchestration "
            "behavior, not something the Current Intelligence dedup fix changed."
        )
        signals = reprocessed.score_breakdown["company_signals"]
        matching = [s for s in signals if s.get("symbol") == ticker]
        assert len(matching) == 1
        assert matching[0]["score"] is not None, "the new real signal DID get folded into the public row's persisted breakdown"
    finally:
        dev_ids = [dev_a.id] + ([dev_b.id] if dev_b is not None else [])
        await _cleanup(dev_ids, node_ids, opp_ids, [ticker])
