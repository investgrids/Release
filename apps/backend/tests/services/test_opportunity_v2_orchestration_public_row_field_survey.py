"""
Full end-to-end field survey of run_shadow_pass() against a public row
(2026-09-26, widened after tracing read_service.py's real consumers). Runs
the REAL, complete run_shadow_pass() pipeline — never _process_cluster()
directly — through every step that can write to an OpportunityV2 row, AND
through the real public read path (get_opportunity_v2_detail) that renders
what a public page actually shows.

Original (narrower) freeze only protected current_score/score_breakdown/
contradictions/sectors/companies. That was not enough: read_service.py's
title/why_this_exists fall back to current_title/current_summary whenever
no editorial_title/editorial_summary is set (a real, valid public-row
state — promotion doesn't require an override), and evidence_count/
supporting_evidence/ripple/development_impacts are all built live from
CURRENT Development linkage, which kept growing unconditionally. Both are
real, user-visible content changes a promoted row was not actually
protected from.

The fix: once a matched row is public, the ENTIRE cluster outcome is
skipped — no score write, no new Development linkage, no narrative
regeneration, no slug touch. This test proves that through both layers:
the ORM row's own fields, AND the real public detail response built from it.
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
from app.services.opportunity_v2.read_service import get_opportunity_v2_detail


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


@pytest.mark.asyncio
async def test_full_field_survey_including_the_real_public_read_path_for_a_row_without_editorial_override(monkeypatch):
    """The harder, more exposed case: a public row that was promoted WITHOUT
    an editorial override (a real, valid state) — title/why_this_exists on
    such a row fall straight through to current_title/current_summary, so
    THIS is the case where the original narrower freeze would have let a
    public page's displayed title/summary/evidence silently change."""
    call_count = {"n": 0}

    async def _fake_narrative(evidence_text, sectors, companies) -> NarrativeResult:
        call_count["n"] += 1
        return NarrativeResult(
            title=f"Generated title, call {call_count['n']}", summary=f"Generated summary, call {call_count['n']}.",
            matters="Matters.", benefits="Benefits.", risks=["Risk one"],
            invalidate="Invalidate.", why_bullets=["Bullet one"],
        )
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative)

    since = _since()
    ticker = f"TSURVEY{uuid.uuid4().hex[:5].upper()}"
    dev_a = _make_dev("First development forming the public thesis", companies=[ticker], sectors=["Banking"])
    dev_b = None
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev_a))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp = await _opportunity_for(dev_a.id)
        assert opp is not None
        opp_ids = [opp.id]

        # Promote to public with NO editorial override — the exposed case.
        async with AsyncSessionLocal() as db:
            row = await db.get(OpportunityV2, opp.id)
            row.public_status = "public"
            await db.commit()

        async with AsyncSessionLocal() as db:
            before = await db.get(OpportunityV2, opp.id)
            before_state = {
                "current_score": before.current_score, "score_breakdown": before.score_breakdown,
                "contradictions": before.contradictions, "sectors": before.sectors, "companies": before.companies,
                "current_title": before.current_title, "current_summary": before.current_summary,
                "narrative_status": before.narrative_status, "narrative_input_hash": before.narrative_input_hash,
                "slug": before.slug,
            }
            linked_before = (await db.execute(
                select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opp.id)
            )).scalars().all()
            detail_before = await get_opportunity_v2_detail(db, opp.slug)
        assert detail_before is not None
        calls_before_reprocess = call_count["n"]

        # A real new signal and a real second Development — enough real new
        # evidence that, if this row were NOT frozen, both the score AND the
        # narrative AND the evidence surface would all genuinely change.
        async with AsyncSessionLocal() as db:
            db.add(AICompanySignal(
                source_type="article", source_id="test-survey-2", symbol=ticker,
                company_name="Survey Co", sector="Banking",
                signed_magnitude=90.0, confidence=0.95, quality=0.95,
                signal_at=datetime.now(timezone.utc),
            ))
            await db.commit()

        dev_b = _make_dev("Second development, real new evidence, would force a re-narration if not frozen", companies=[ticker], sectors=["Banking"])
        node_ids.append(await _link(dev_b))
        async with AsyncSessionLocal() as db:
            summary = await orch.run_shadow_pass(db, since=since, limit=50)

        assert summary.public_rows_frozen >= 1

        async with AsyncSessionLocal() as db:
            after = await db.get(OpportunityV2, opp.id)
            linked_after = (await db.execute(
                select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opp.id)
            )).scalars().all()
            detail_after = await get_opportunity_v2_detail(db, opp.slug)
        assert detail_after is not None

        # --- ORM-level: score/signal fields frozen (previously verified) ---
        assert after.current_score == before_state["current_score"]
        assert after.score_breakdown == before_state["score_breakdown"]
        assert after.contradictions == before_state["contradictions"]
        assert after.sectors == before_state["sectors"]
        assert after.companies == before_state["companies"]

        # --- ORM-level: NOW ALSO frozen — narrative content and linkage ---
        assert after.current_title == before_state["current_title"]
        assert after.current_summary == before_state["current_summary"]
        assert after.narrative_status == before_state["narrative_status"]
        assert after.narrative_input_hash == before_state["narrative_input_hash"]
        assert call_count["n"] == calls_before_reprocess, "generate_narrative must not be called at all for a frozen row"
        assert linked_after == linked_before, "no new Development may link to a public row via a routine shadow pass"
        assert dev_b.id not in linked_after
        assert after.slug == before_state["slug"]

        # --- Real public read path: what a public page ACTUALLY shows must
        # be byte-identical before and after, field by field ---
        assert detail_after.title == detail_before.title
        assert detail_after.why_this_exists == detail_before.why_this_exists
        assert detail_after.current_strength == detail_before.current_strength
        assert detail_after.evidence_count == detail_before.evidence_count
        assert [s.development_id for s in detail_after.supporting_evidence] == [s.development_id for s in detail_before.supporting_evidence]
        assert [n.id for n in detail_after.ripple.nodes] == [n.id for n in detail_before.ripple.nodes]
        assert [e.id for e in detail_after.ripple.edges] == [e.id for e in detail_before.ripple.edges]
        assert [d.development_id for d in detail_after.development_impacts] == [d.development_id for d in detail_before.development_impacts]
        assert detail_after.companies_connected == detail_before.companies_connected
        assert detail_after.sectors_themes == detail_before.sectors_themes
        assert detail_after.contradictions_risks == detail_before.contradictions_risks
        assert detail_after.updated_at == detail_before.updated_at
    finally:
        dev_ids = [dev_a.id] + ([dev_b.id] if dev_b is not None else [])
        await _cleanup(dev_ids, node_ids, opp_ids, [ticker])


@pytest.mark.asyncio
async def test_shadow_row_still_updates_everything_normally(monkeypatch):
    """Control case: the freeze must be specific to public_status=="public"
    -- an ordinary shadow row must keep updating score, narrative, AND
    linkage exactly as before this fix."""
    call_count = {"n": 0}

    async def _fake_narrative(evidence_text, sectors, companies) -> NarrativeResult:
        call_count["n"] += 1
        return NarrativeResult(
            title=f"Generated title, call {call_count['n']}", summary="Summary.", matters="Matters.",
            benefits="Benefits.", risks=["Risk one"], invalidate="Invalidate.", why_bullets=["Bullet one"],
        )
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative)

    since = _since()
    ticker = f"TSHADOW2{uuid.uuid4().hex[:5].upper()}"
    dev_a = _make_dev("First development, stays shadow", companies=[ticker], sectors=["Banking"])
    dev_b = None
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev_a))
        async with AsyncSessionLocal() as db:
            summary1 = await orch.run_shadow_pass(db, since=since, limit=50)
        assert summary1.public_rows_frozen == 0

        opp = await _opportunity_for(dev_a.id)
        assert opp is not None
        opp_ids = [opp.id]
        assert opp.public_status == "shadow"
        score_before = opp.current_score
        calls_before = call_count["n"]

        dev_b = _make_dev("Second development, same company, reprocesses the shadow row", companies=[ticker], sectors=["Banking"])
        node_ids.append(await _link(dev_b))
        async with AsyncSessionLocal() as db:
            summary2 = await orch.run_shadow_pass(db, since=since, limit=50)
        assert summary2.public_rows_frozen == 0

        async with AsyncSessionLocal() as db:
            reprocessed = await db.get(OpportunityV2, opp.id)
            linked = (await db.execute(
                select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opp.id)
            )).scalars().all()

        assert reprocessed.current_score != score_before
        assert call_count["n"] > calls_before, "narrative generation must still run for a shadow row"
        assert dev_b.id in linked, "new evidence must still link normally for a shadow row"
    finally:
        dev_ids = [dev_a.id] + ([dev_b.id] if dev_b is not None else [])
        await _cleanup(dev_ids, node_ids, opp_ids, [ticker])
