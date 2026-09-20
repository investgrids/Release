"""
opportunity_v2/orchestration.py::_process_cluster -- real DB-backed
persistence contract tests for score_breakdown/company_signals/
contradictions/Development-linkage, run through the real
run_shadow_pass() pipeline (never a direct internal call to
_process_cluster, which is a private module function). Same real-graph,
real-DB, monkeypatched-narrative-only precedent as
test_opportunity_v2_orchestration.py.

The 2026-09-19 Opportunity V2 audit found zero direct test coverage of
this exact persistence path (score_breakdown/contradictions/
company_signals were tested at the scoring.py computation layer and the
read_service.py serialization layer, but never proven to actually survive
a real orchestration.py write).
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


async def _cleanup(development_ids: list[str], node_ids: list[str], opportunity_ids: list[str],
                    signal_symbols: list[str] | None = None) -> None:
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
        title="A real-shaped persistence test title", summary="Summary.", matters="Matters.",
        benefits="Benefits.", risks=["Risk one"], invalidate="Invalidate.", why_bullets=["Bullet one"],
    )


# ── score_breakdown persistence ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_score_breakdown_persists_with_real_component_fields(monkeypatch):
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    dev = _make_dev("Real development for score_breakdown persistence check", sectors=["Banking"])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp = await _opportunity_for(dev.id)
        assert opp is not None
        opp_ids = [opp.id]

        assert opp.score_breakdown is not None
        for key in (
            "evidence_quality", "development_count", "company_confirmation",
            "sector_confirmation", "freshness", "contradiction_penalty", "company_signals",
        ):
            assert key in opp.score_breakdown, f"score_breakdown missing real field {key!r}"
        # Never a live recomputation at read time -- current_score and the
        # persisted breakdown must come from the exact same write.
        assert opp.current_score is not None
    finally:
        await _cleanup([dev.id], node_ids, opp_ids)


# ── honest company_signals (never imputed) ───────────────────────────────

@pytest.mark.asyncio
async def test_company_signal_persists_honest_null_score_when_no_real_signal_exists(monkeypatch):
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    ticker = f"TPERSIST{uuid.uuid4().hex[:5].upper()}"
    dev = _make_dev("Real development, no matching real company signal", companies=[ticker])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp = await _opportunity_for(dev.id)
        assert opp is not None
        opp_ids = [opp.id]

        signals = opp.score_breakdown["company_signals"]
        matching = [s for s in signals if s.get("symbol") == ticker]
        assert len(matching) == 1
        # Never fabricated -- a company with no real AICompanySignal row
        # must persist a null score, not an invented number.
        assert matching[0]["score"] is None
        assert matching[0]["real_direction"] is None
        assert matching[0]["confirms_thesis"] is False
        assert matching[0]["contradicts_thesis"] is False
    finally:
        await _cleanup([dev.id], node_ids, opp_ids, [ticker])


@pytest.mark.asyncio
async def test_company_signal_agreeing_with_thesis_persists_real_confirmation(monkeypatch):
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    ticker = f"TCONF{uuid.uuid4().hex[:5].upper()}"
    signal = AICompanySignal(
        source_type="article", source_id="test", symbol=ticker, company_name="Test Co",
        sector="Banking", signed_magnitude=30.0, confidence=0.95, quality=0.95,
        signal_at=datetime.now(timezone.utc),
    )
    dev = _make_dev("Real development with a real agreeing company signal", companies=[ticker], sectors=["Banking"])
    node_ids, opp_ids = [], []
    try:
        async with AsyncSessionLocal() as db:
            db.add(signal)
            await db.commit()
        node_ids.append(await _link(dev))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp = await _opportunity_for(dev.id)
        assert opp is not None
        opp_ids = [opp.id]

        assert opp.score_breakdown["company_confirmation"] > 0.0
        signals = opp.score_breakdown["company_signals"]
        matching = [s for s in signals if s.get("symbol") == ticker]
        assert len(matching) == 1
        assert matching[0]["confirms_thesis"] is True
    finally:
        await _cleanup([dev.id], node_ids, opp_ids, [ticker])


# ── contradictions persistence ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_contradictions_persist_when_a_real_signal_disagrees_with_the_thesis(monkeypatch):
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    ticker = f"TCONTRA{uuid.uuid4().hex[:5].upper()}"
    signal = AICompanySignal(
        source_type="article", source_id="test", symbol=ticker, company_name="Test Co",
        sector="Banking", signed_magnitude=-30.0, confidence=0.95, quality=0.95,
        signal_at=datetime.now(timezone.utc),
    )
    # current_direction="positive" on the Development (see _make_dev) drives
    # a positive thesis direction; a strongly negative real company signal
    # on the same company must persist as a real contradiction, not be
    # silently averaged away.
    dev = _make_dev("Real development with a real disagreeing company signal", companies=[ticker], sectors=["Banking"])
    node_ids, opp_ids = [], []
    try:
        async with AsyncSessionLocal() as db:
            db.add(signal)
            await db.commit()
        node_ids.append(await _link(dev))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp = await _opportunity_for(dev.id)
        assert opp is not None
        opp_ids = [opp.id]

        assert opp.contradictions, "a real disagreeing signal must produce a real persisted contradiction"
        assert opp.score_breakdown["contradiction_penalty"] > 0.0
    finally:
        await _cleanup([dev.id], node_ids, opp_ids, [ticker])


@pytest.mark.asyncio
async def test_contradictions_default_to_empty_list_never_null_when_none_fire(monkeypatch):
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    dev = _make_dev("Real development with no disagreeing signal at all", sectors=["Banking"])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp = await _opportunity_for(dev.id)
        assert opp is not None
        opp_ids = [opp.id]
        assert opp.contradictions == []
    finally:
        await _cleanup([dev.id], node_ids, opp_ids)


# ── Development linkage ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_supporting_development_is_really_linked_via_the_join_table(monkeypatch):
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    dev = _make_dev("Real development that must appear as real supporting evidence", sectors=["Banking"])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp = await _opportunity_for(dev.id)
        assert opp is not None
        opp_ids = [opp.id]

        async with AsyncSessionLocal() as db:
            linked_dev_ids = (await db.execute(
                select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opp.id)
            )).scalars().all()
        assert dev.id in linked_dev_ids
    finally:
        await _cleanup([dev.id], node_ids, opp_ids)


# ── Never invent missing values ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_capacity_failure_persists_real_deterministic_fields_without_a_fabricated_title(monkeypatch):
    """Restates test_opportunity_v2_orchestration.py's own equivalent check
    from the persistence-contract angle: score_breakdown/contradictions/
    Development-linkage must all persist for real even when the narrative
    generation step fails closed -- capacity failures must never block or
    corrupt the deterministic write."""
    async def _fake_narrative_fail(evidence_text, sectors, companies):
        return None
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_fail)
    since = _since()
    dev = _make_dev("Real development, AI capacity unavailable this pass", sectors=["Banking"])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp = await _opportunity_for(dev.id)
        assert opp is not None
        opp_ids = [opp.id]

        assert opp.narrative_status == "failed_capacity"
        assert opp.current_title is None, "never a fabricated substitute title on capacity failure"
        assert opp.score_breakdown is not None, "deterministic score_breakdown must persist regardless of narrative outcome"
        assert opp.contradictions == []

        async with AsyncSessionLocal() as db:
            linked = (await db.execute(
                select(OpportunityV2Development.development_id).where(OpportunityV2Development.opportunity_id == opp.id)
            )).scalars().all()
        assert dev.id in linked, "Development linkage must persist even when narrative generation fails"
    finally:
        await _cleanup([dev.id], node_ids, opp_ids)


# ── Slug stability on update ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_slug_stays_stable_when_current_title_changes_on_a_later_merge(monkeypatch):
    monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_ok)
    since = _since()
    ticker = f"TSLUGSTB{uuid.uuid4().hex[:4].upper()}"
    dev_a = _make_dev("First real development establishing the thesis", companies=[ticker])
    node_ids, opp_ids = [], []
    try:
        node_ids.append(await _link(dev_a))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp_after_first = await _opportunity_for(dev_a.id)
        assert opp_after_first is not None
        opp_ids = [opp_after_first.id]
        slug_after_first = opp_after_first.slug
        assert slug_after_first is not None

        async def _fake_narrative_retitled(evidence_text, sectors, companies) -> NarrativeResult:
            return NarrativeResult(
                title="A completely different real-shaped retitled thesis",
                summary="Updated summary.", matters="Matters.", benefits="Benefits.",
                risks=["Risk one"], invalidate="Invalidate.", why_bullets=["Bullet one"],
            )
        monkeypatch.setattr(orch, "generate_narrative", _fake_narrative_retitled)

        dev_b = _make_dev("Second real development, same company, forces a re-narration", companies=[ticker])
        node_ids.append(await _link(dev_b))
        async with AsyncSessionLocal() as db:
            await orch.run_shadow_pass(db, since=since, limit=50)

        opp_after_second = await _opportunity_for(dev_b.id)
        assert opp_after_second is not None
        assert opp_after_second.id == opp_after_first.id, "must be the same merged opportunity"
        assert opp_after_second.current_title == "A completely different real-shaped retitled thesis", "the title itself must genuinely have changed"
        assert opp_after_second.slug == slug_after_first, "a permalink must never change under a reader just because the narrative regenerates later"
    finally:
        await _cleanup([dev_a.id, dev_b.id], node_ids, opp_ids)
