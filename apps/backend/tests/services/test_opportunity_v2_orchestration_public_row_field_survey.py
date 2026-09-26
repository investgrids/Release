"""
Full end-to-end field survey of run_shadow_pass() against a public row
(2026-09-26, release-review verification). Runs the REAL, complete
run_shadow_pass() pipeline — never _process_cluster() directly — through
every step that can write to an OpportunityV2 row: the score/breakdown
write in _process_cluster() itself, _link_developments(), narrative
generation, and slug assignment. Asserts explicitly, field by field, which
survive untouched and which are intentionally NOT frozen, so this is one
place a reviewer can see the complete, real answer rather than trusting
that _process_cluster()'s own freeze check is the only place that matters.

Field disposition asserted here (see orchestration.py's own `frozen` check
for the code):
  FROZEN (never changes on a public row via a routine shadow pass):
    public_status, editorial_title, editorial_summary, editorial_reason,
    editorial_updated_at, current_score, score_breakdown, contradictions,
    sectors, companies.
  NOT FROZEN (still update normally — intentionally out of this fix's
  scope, verified here so that's a documented fact, not an oversight):
    narrative_status, current_title, current_summary, narrative_input_hash,
    slug (a no-op in practice once first set — never reassigned).
  ADDITIVE, always happens regardless of public_status:
    OpportunityV2Development linkage (new evidence keeps accumulating for
    a future explicit refresh).
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


@pytest.mark.asyncio
async def test_full_field_survey_of_a_reprocessed_public_row(monkeypatch):
    call_count = {"n": 0}

    async def _fake_narrative_changes_each_call(evidence_text, sectors, companies) -> NarrativeResult:
        call_count["n"] += 1
        return NarrativeResult(
            title=f"Generated title, call {call_count['n']}", summary=f"Generated summary, call {call_count['n']}.",
            matters="Matters.", benefits="Benefits.", risks=["Risk one"],
            invalidate="Invalidate.", why_bullets=["Bullet one"],
        )
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_changes_each_call)

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

        # Promote to public with a real editorial override, capturing every
        # field's real "before" value.
        editorial_title, editorial_summary, editorial_reason = (
            "Human-edited title", "Human-edited summary.", "Generated narrative overclaimed.",
        )
        editorial_at = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            row = await db.get(OpportunityV2, opp.id)
            row.public_status = "public"
            row.editorial_title = editorial_title
            row.editorial_summary = editorial_summary
            row.editorial_reason = editorial_reason
            row.editorial_updated_at = editorial_at
            await db.commit()

        async with AsyncSessionLocal() as db:
            before = await db.get(OpportunityV2, opp.id)
            before_state = {
                "public_status": before.public_status,
                "editorial_title": before.editorial_title,
                "editorial_summary": before.editorial_summary,
                "editorial_reason": before.editorial_reason,
                "editorial_updated_at": before.editorial_updated_at,
                "current_score": before.current_score,
                "score_breakdown": before.score_breakdown,
                "contradictions": before.contradictions,
                "sectors": before.sectors,
                "companies": before.companies,
                "current_title": before.current_title,
                "current_summary": before.current_summary,
                "narrative_status": before.narrative_status,
                "narrative_input_hash": before.narrative_input_hash,
                "slug": before.slug,
            }
            linked_before = (await db.execute(
                select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opp.id)
            )).scalars().all()

        # A real new signal (would move company_confirmation if recomputed)
        # and a real second Development (same identity, new evidence, and
        # different canonical_title so the narrative hash genuinely changes).
        async with AsyncSessionLocal() as db:
            db.add(AICompanySignal(
                source_type="article", source_id="test-survey", symbol=ticker,
                company_name="Survey Co", sector="Banking",
                signed_magnitude=90.0, confidence=0.95, quality=0.95,
                signal_at=datetime.now(timezone.utc),
            ))
            await db.commit()

        dev_b = _make_dev("Second development, new real evidence, forces a re-narration", companies=[ticker], sectors=["Banking"])
        node_ids.append(await _link(dev_b))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        async with AsyncSessionLocal() as db:
            after = await db.get(OpportunityV2, opp.id)
            linked_after = (await db.execute(
                select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opp.id)
            )).scalars().all()

        # --- FROZEN: must be byte-identical to the pre-reprocess state ---
        assert after.public_status == before_state["public_status"] == "public"
        assert after.editorial_title == before_state["editorial_title"]
        assert after.editorial_summary == before_state["editorial_summary"]
        assert after.editorial_reason == before_state["editorial_reason"]
        assert after.editorial_updated_at == before_state["editorial_updated_at"]
        assert after.current_score == before_state["current_score"]
        assert after.score_breakdown == before_state["score_breakdown"]
        assert after.contradictions == before_state["contradictions"]
        assert after.sectors == before_state["sectors"]
        assert after.companies == before_state["companies"]
        # The new real signal must NOT appear in the frozen breakdown.
        frozen_signals = after.score_breakdown["company_signals"]
        assert next(s for s in frozen_signals if s["symbol"] == ticker)["score"] is None

        # --- NOT FROZEN: must have genuinely changed, proving this is a
        # deliberate scope boundary, not an accident where nothing in the
        # test actually exercised these paths ---
        assert after.narrative_status == "generated"
        assert after.current_title != before_state["current_title"]
        assert after.current_summary != before_state["current_summary"]
        assert after.narrative_input_hash != before_state["narrative_input_hash"]
        assert call_count["n"] >= 2, "narrative generation must still run on a public row"

        # --- ADDITIVE: linkage always grows, regardless of public_status ---
        assert dev_a.id in linked_before
        assert dev_a.id in linked_after
        assert dev_b.id in linked_after and dev_b.id not in linked_before

        # --- slug: set once, never reassigned (already non-None here) ---
        assert after.slug == before_state["slug"]
    finally:
        dev_ids = [dev_a.id] + ([dev_b.id] if dev_b is not None else [])
        await _cleanup(dev_ids, node_ids, opp_ids, [ticker])
