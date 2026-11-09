"""
Workstream A (2026-10-24) — AIPE materiality gate.

A deterministic, no-LLM gate on the V1 publisher's CREATE path: routine /
non-substantive filings (publication_tier EVENT_ONLY/REJECT) should not create
new standalone articles, while material developments still publish. Two modes:
  - "shadow" (default): measure only, change nothing.
  - "enforce": suppress new-article creation for routine events, record them as
    coverage (SKIPPED_NOT_MATERIAL).

Covered here:
  1. The shared classifier core (classify_from_title) on both sides of the gate,
     including routine SEBI filings, procedural clarifications, material numeric
     RBI/earnings headlines, acquisitions, degenerate/empty subjects, and the
     conservative market_impact="high" -> analytical-context keep-signal.
  2. classify_publication_tier still delegates correctly (V2 compatibility; the
     authoritative V2 regression is test_article_v2_publication_tier.py).
  3. coverage_engine.mark_skipped_not_material terminal state.
  4. Publisher integration: shadow is a no-op; enforce suppresses + records +
     blocks fan-out; material events still publish; must-cover events are never
     suppressed; the market_impact keep-signal publishes a routine-looking but
     high-impact event.
No deployment, no production data.
"""
from __future__ import annotations

import uuid
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select

from app.db.models.event_coverage import EventCoverage
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services import coverage_engine
from app.services.aipe import publisher
from app.services.article_v2.publication_tier import (
    classify_from_title, classify_publication_tier, ARTICLE, EVENT_ONLY, REJECT,
)

# Confirmed empirically against the real classifier (see Workstream A notes).
ROUTINE_SEBI = "Disclosure under Regulation 30 of SEBI LODR"
ROUTINE_SEBI_33 = "Compliance Certificate under Regulation 33 of SEBI LODR"
ROUTINE_SEBI_36 = "Submission of notice under Regulation 36 of SEBI LODR"
CLARIFICATION = "The Exchange has sought clarification from ABC Ltd for the quarter ended"
MATERIAL_EARNINGS = "Reliance Industries Q2 net profit rises 12% to Rs 18,000 crore"
MATERIAL_RBI = "RBI cuts repo rate by 25 bps to 6.25%"
MATERIAL_ACQ = "Board approves acquisition of XYZ Technologies"
DEGENERATE = "Notice of undefined"


# ── 1. shared classifier core (classify_from_title) ──────────────────────────

@pytest.mark.parametrize("headline", [ROUTINE_SEBI, ROUTINE_SEBI_33, ROUTINE_SEBI_36])
def test_routine_sebi_filings_are_event_only(headline):
    assert classify_from_title(headline).tier == EVENT_ONLY


def test_procedural_clarification_is_event_only():
    r = classify_from_title(CLARIFICATION)
    assert r.tier == EVENT_ONLY and "PROCEDURAL_CLARIFICATION_REQUEST" in r.reason_codes


@pytest.mark.parametrize("headline", [MATERIAL_EARNINGS, MATERIAL_RBI, MATERIAL_ACQ])
def test_material_headlines_are_article(headline):
    assert classify_from_title(headline).tier == ARTICLE


def test_degenerate_and_empty_are_reject():
    assert classify_from_title(DEGENERATE).tier == REJECT
    assert classify_from_title("").tier == REJECT
    assert classify_from_title(None).tier == REJECT


def test_market_impact_high_keep_signal_escalates_routine_headline():
    # The conservative V1 mapping: market_impact == "high" -> has_analytical_context.
    assert classify_from_title(ROUTINE_SEBI, has_analytical_context=False).tier == EVENT_ONLY
    r = classify_from_title(ROUTINE_SEBI, has_analytical_context=True)
    assert r.tier == ARTICLE and "ANALYTICAL_CONTEXT_PRESENT" in r.reason_codes


def test_budget_without_numbers_relies_on_keep_signal():
    # Documents a real edge: a numberless budget headline is EVENT_ONLY on text
    # alone, and only an analytical-context (market_impact=high) keeps it.
    budget = "Union Budget 2026: FM announces new capex plan"
    assert classify_from_title(budget).tier == EVENT_ONLY
    assert classify_from_title(budget, has_analytical_context=True).tier == ARTICLE


# ── 2. classify_publication_tier still delegates (V2 compatibility) ──────────

def test_v2_shim_delegates_to_shared_core():
    es = SimpleNamespace(primary_evidence=SimpleNamespace(title=ROUTINE_SEBI))
    assert classify_publication_tier(None, es, None).tier == EVENT_ONLY
    es2 = SimpleNamespace(primary_evidence=SimpleNamespace(title=MATERIAL_RBI))
    assert classify_publication_tier(None, es2, None).tier == ARTICLE


def test_v2_shim_derives_analytical_context_from_financial_context():
    es = SimpleNamespace(primary_evidence=SimpleNamespace(title=ROUTINE_SEBI))
    ctx = SimpleNamespace(financial_context=[object()], market_reaction=None)
    r = classify_publication_tier(None, es, ctx)
    assert r.tier == ARTICLE and "ANALYTICAL_CONTEXT_PRESENT" in r.reason_codes


# ── 3. coverage terminal state ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mark_skipped_not_material_sets_terminal_state_and_never_overwrites_published():
    eid = f"pytest-notmat-{uuid.uuid4().hex[:8]}"
    eid_pub = f"pytest-notmat-pub-{uuid.uuid4().hex[:8]}"
    try:
        async with AsyncSessionLocal() as db:
            await coverage_engine.register_event(db, event_id=eid, source="test",
                                                 headline="x", urgency=6, importance=5, sectors=[], companies=[])
            await coverage_engine.register_event(db, event_id=eid_pub, source="test",
                                                 headline="y", urgency=6, importance=5, sectors=[], companies=[])
        async with AsyncSessionLocal() as db:
            await coverage_engine.mark_skipped_not_material(db, event_id=eid)
        async with AsyncSessionLocal() as db:
            await coverage_engine.mark_published(db, event_id=eid_pub, article_id="art-x")
            await coverage_engine.mark_skipped_not_material(db, event_id=eid_pub)  # must NOT overwrite
        async with AsyncSessionLocal() as db:
            got = (await db.execute(select(EventCoverage).where(EventCoverage.event_id == eid))).scalar_one()
            got_pub = (await db.execute(select(EventCoverage).where(EventCoverage.event_id == eid_pub))).scalar_one()
        assert got.coverage_status == "SKIPPED_NOT_MATERIAL"
        assert got_pub.coverage_status == "PUBLISHED"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventCoverage).where(EventCoverage.event_id.in_([eid, eid_pub])))
            await db.commit()


# ── 4. publisher integration (mirrors test_publisher_cycle_skip_states) ──────

def _fake_published_article(article_id: str, headline: str) -> IntelligenceArticle:
    return IntelligenceArticle(
        id=article_id, slug=article_id, article_type="company_intelligence",
        story_id=article_id, story_version=1, lifecycle_status="published",
        status="published", update_count=0, update_history=[],
        angle="primary", angle_entity=None,
        headline=headline, executive_summary="", key_takeaway="",
        why_it_matters="", what_happened="",
        companies_affected=[], sectors_affected=[],
    )


def _triage_event(event_id: str, headline: str, urgency=6, importance=5, market_impact=None, origin="NSE") -> dict:
    # origin defaults to "NSE" so gate-exercising tests hit the scoped path;
    # pass origin=<news outlet> or None to test the bypass / fail-open paths.
    ev = {"event_id": event_id, "headline": headline, "urgency": urgency,
          "importance": importance, "sectors": [], "themes": [], "tickers": [], "origin": origin}
    if market_impact is not None:
        ev["market_impact"] = market_impact
    return ev


async def _register(events):
    async with AsyncSessionLocal() as db:
        for ev in events:
            await coverage_engine.register_event(
                db, event_id=ev["event_id"], source="test", headline=ev["headline"],
                urgency=ev["urgency"], importance=ev["importance"], sectors=[], companies=[],
            )


async def _status(event_id: str) -> str:
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(EventCoverage).where(EventCoverage.event_id == event_id))).scalar_one().coverage_status


def _run_with_mocks(triage_events, publish_side_effect, plan_angles=None):
    stack = ExitStack()
    stack.enter_context(patch("app.services.aipe.publisher.get_mie_context", new_callable=AsyncMock, return_value={"session": "closed", "themes": [], "mood": "neutral", "story": "", "story_hash": "x"}))
    stack.enter_context(patch("app.services.aipe.publisher.get_high_urgency_triage", new_callable=AsyncMock, return_value=triage_events))
    stack.enter_context(patch("app.services.aipe.publisher.filter_triage_batch", side_effect=lambda events, max_per_cycle: [(e, "approved") for e in events]))
    stack.enter_context(patch("app.services.aipe.publisher.count_today_articles", new_callable=AsyncMock, return_value=0))
    stack.enter_context(patch("app.services.aipe.publisher.get_today_story_ids", new_callable=AsyncMock, return_value=set()))
    stack.enter_context(patch("app.services.aipe.publisher.select_article_type", side_effect=lambda ev, mie: ("company_intelligence", f"story-{ev['event_id']}", "normal")))
    stack.enter_context(patch("app.services.aipe.publisher.find_duplicate", new_callable=AsyncMock, return_value=None))
    publish_mock = stack.enter_context(patch("app.services.aipe.publisher._publish_new_article", new_callable=AsyncMock, side_effect=publish_side_effect))
    stack.enter_context(patch("app.services.aipe.publisher.plan_extra_angles", return_value=plan_angles or []))
    stack.enter_context(patch("app.services.aipe.publisher.run_continuous_update_cycle", new_callable=AsyncMock, return_value=0))
    stack.enter_context(patch("app.services.aipe.publisher._scheduled_article_due", new_callable=AsyncMock, return_value=False))
    stack.enter_context(patch("app.services.aipe.publisher.get_latest_market_snapshot", new_callable=AsyncMock, return_value={}))
    return stack, publish_mock


@pytest.mark.asyncio
async def test_shadow_mode_is_a_noop_routine_event_still_publishes():
    eid = f"pytest-mat-shadow-{uuid.uuid4().hex[:8]}"
    events = [_triage_event(eid, ROUTINE_SEBI)]
    await _register(events)
    try:
        article = _fake_published_article(f"art-{eid}", ROUTINE_SEBI)
        stack, publish_mock = _run_with_mocks(events, publish_side_effect=[article])
        with stack, patch.object(publisher.settings, "aipe_materiality_gate_mode", "shadow"):
            await publisher.run_aipe_cycle()
        publish_mock.assert_called_once()                      # behavior unchanged
        assert await _status(eid) == "PUBLISHED"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventCoverage).where(EventCoverage.event_id == eid))
            await db.commit()


@pytest.mark.asyncio
async def test_enforce_suppresses_routine_event_records_coverage_and_blocks_fanout():
    eid = f"pytest-mat-enforce-{uuid.uuid4().hex[:8]}"
    events = [_triage_event(eid, ROUTINE_SEBI)]
    await _register(events)
    try:
        # plan_extra_angles returns a non-empty list; if the gate failed to
        # `continue`, _publish_new_article would be called for the angles too.
        angles = [("per_company", "ang-story", "per_company", "RELIANCE", "")]
        stack, publish_mock = _run_with_mocks(events, publish_side_effect=[], plan_angles=angles)
        with stack, patch.object(publisher.settings, "aipe_materiality_gate_mode", "enforce"):
            await publisher.run_aipe_cycle()
        publish_mock.assert_not_called()                      # primary AND fan-out suppressed
        assert await _status(eid) == "SKIPPED_NOT_MATERIAL"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventCoverage).where(EventCoverage.event_id == eid))
            await db.commit()


@pytest.mark.asyncio
async def test_enforce_still_publishes_material_event():
    eid = f"pytest-mat-material-{uuid.uuid4().hex[:8]}"
    events = [_triage_event(eid, MATERIAL_EARNINGS)]
    await _register(events)
    try:
        article = _fake_published_article(f"art-{eid}", MATERIAL_EARNINGS)
        stack, publish_mock = _run_with_mocks(events, publish_side_effect=[article])
        with stack, patch.object(publisher.settings, "aipe_materiality_gate_mode", "enforce"):
            await publisher.run_aipe_cycle()
        publish_mock.assert_called_once()
        assert await _status(eid) == "PUBLISHED"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventCoverage).where(EventCoverage.event_id == eid))
            await db.commit()


@pytest.mark.asyncio
async def test_enforce_high_market_impact_keeps_routine_looking_event():
    eid = f"pytest-mat-keep-{uuid.uuid4().hex[:8]}"
    events = [_triage_event(eid, ROUTINE_SEBI, market_impact="high")]
    await _register(events)
    try:
        article = _fake_published_article(f"art-{eid}", ROUTINE_SEBI)
        stack, publish_mock = _run_with_mocks(events, publish_side_effect=[article])
        with stack, patch.object(publisher.settings, "aipe_materiality_gate_mode", "enforce"):
            await publisher.run_aipe_cycle()
        publish_mock.assert_called_once()                      # keep-signal -> ARTICLE
        assert await _status(eid) == "PUBLISHED"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventCoverage).where(EventCoverage.event_id == eid))
            await db.commit()


@pytest.mark.asyncio
async def test_non_nse_macro_news_bypasses_gate_even_in_enforce():
    # A material macro/policy NEWS headline from a news outlet classifies
    # EVENT_ONLY on text alone, but origin != "NSE" means the filing-scoped gate
    # must NOT touch it -- published even in enforce mode (closes the offline-
    # estimate FP cluster: RBI/rupee/crude news from ET/Livemint/NDTV).
    eid = f"pytest-mat-macro-{uuid.uuid4().hex[:8]}"
    macro = "RBI tightens forex derivative rules: what changes for hedging"
    events = [_triage_event(eid, macro, urgency=9, importance=8, market_impact="medium", origin="Economic Times")]
    await _register(events)
    try:
        article = _fake_published_article(f"art-{eid}", macro)
        stack, publish_mock = _run_with_mocks(events, publish_side_effect=[article])
        with stack, patch.object(publisher.settings, "aipe_materiality_gate_mode", "enforce"):
            await publisher.run_aipe_cycle()
        publish_mock.assert_called_once()
        assert await _status(eid) == "PUBLISHED"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventCoverage).where(EventCoverage.event_id == eid))
            await db.commit()


@pytest.mark.asyncio
async def test_unknown_origin_fails_open_and_is_not_suppressed():
    # Fail-open: missing/unknown provenance must never become a suppression
    # decision, even for a routine-looking headline in enforce mode.
    eid = f"pytest-mat-unknown-{uuid.uuid4().hex[:8]}"
    events = [_triage_event(eid, ROUTINE_SEBI, origin=None)]
    await _register(events)
    try:
        article = _fake_published_article(f"art-{eid}", ROUTINE_SEBI)
        stack, publish_mock = _run_with_mocks(events, publish_side_effect=[article])
        with stack, patch.object(publisher.settings, "aipe_materiality_gate_mode", "enforce"):
            await publisher.run_aipe_cycle()
        publish_mock.assert_called_once()
        assert await _status(eid) == "PUBLISHED"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventCoverage).where(EventCoverage.event_id == eid))
            await db.commit()


@pytest.mark.asyncio
async def test_enforce_suppresses_routine_filing_even_at_must_cover_priority():
    # KEY behavior: coverage_classify's keyword floor elevates routine
    # "SEBI"/"Regulation" filings to Critical/High (is_must_cover), but that is
    # priority, not materiality. Even a 9/9 routine SEBI filing is suppressed in
    # enforce mode -- there is intentionally NO must-cover carve-out, because
    # such a carve-out would exempt exactly the routine filings this gate exists
    # to suppress. (A genuinely material high-tier event classifies ARTICLE via
    # its numbers/phrases and is never suppressed -- see the material test above.)
    eid = f"pytest-mat-mustcover-{uuid.uuid4().hex[:8]}"
    events = [_triage_event(eid, ROUTINE_SEBI, urgency=9, importance=9)]
    await _register(events)
    try:
        stack, publish_mock = _run_with_mocks(events, publish_side_effect=[])
        with stack, patch.object(publisher.settings, "aipe_materiality_gate_mode", "enforce"):
            await publisher.run_aipe_cycle()
        publish_mock.assert_not_called()
        assert await _status(eid) == "SKIPPED_NOT_MATERIAL"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(EventCoverage).where(EventCoverage.event_id == eid))
            await db.commit()
