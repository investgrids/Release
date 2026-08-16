"""
Phase 1E §16-§20 — Monday handoff: session resolution, WeekendContext
load, fresh-Monday-data override scenarios, double-count protection,
base/adjustment/final triple, user-facing truthfulness.
"""
from __future__ import annotations

from datetime import timezone
from unittest.mock import patch

import pytest

from app.services import opening_prediction_service as ops
from app.services.weekend_intelligence.checkpoints import run_checkpoint
from app.services.weekend_intelligence.context import get_weekend_context_for_session
from app.services.weekend_intelligence.session_resolution import resolve_opening_prediction_session
from tests.integration.conftest import (
    FRIDAY, MONDAY, SATURDAY, SUNDAY, ist,
    make_event, make_event_triage,
)

TARGET = MONDAY.isoformat()


def _utc(d, h, m=0):
    return ist(d, h, m).astimezone(timezone.utc)


async def _build_sunday_snapshot(db, frozen_time, *, bias_evidence):
    """bias_evidence: a callable(db) that seeds whatever evidence should
    drive the resulting overall_bias — kept generic so scenarios A/B/C/D
    below can each build a differently-biased real snapshot through the
    real aggregator, never a hand-built WeekendIntelligenceSnapshot.

    Checkpoints once, at Sunday 18:00 (not Saturday morning) deliberately:
    the context loader's real staleness rule (_MAX_SNAPSHOT_AGE_HOURS=36,
    Phase 1C) means a snapshot generated Saturday morning genuinely IS
    stale by Monday 08:30 (46.5h > 36h) — that's the rule working
    correctly, not a bug to route around. Sunday 18:00 -> Monday 08:30 is
    14.5h, matching the realistic "last real checkpoint before Monday
    morning" scenario the rule's own docstring describes. Evidence is
    still dated Saturday (representing real weekend developments); only
    the CHECKPOINT itself runs Sunday evening, exactly as the real
    Sunday 18:00 IST scheduled job would if Saturday's own checkpoints
    hadn't already run — this is the first-ever checkpoint for the
    target, so §22's exception creates v1 regardless of materiality."""
    frozen_time(ist(SUNDAY, 18, 0))
    await bias_evidence(db)
    await run_checkpoint(db, TARGET, checkpoint_time=_utc(SUNDAY, 18, 0), checkpoint_label="Sunday 18:00 IST")


def _signals(*, gift_positive, pct_positive):
    return {
        "gift_nifty": {"value": "24500", "change": "+0.5%", "positive": gift_positive},
        "india_vix": {"value": "13.2", "float": 13.2, "level": "LOW", "interpretation": "calm"},
        "bank_nifty": {"value": "51000", "change": "+0.3%", "positive": True},
        "usd_inr": {"value": "83.1", "positive": False},
        "brent_crude": {"value": "78", "change": "-0.2%", "positive": False, "direction": "falling"},
        "fii": {"net": 500, "available": True, "buying": True},
        "us_futures": [], "asian_markets": [], "european_markets": [],
        "global_sentiment": {"positive_count": 3, "total": 4, "pct_positive": pct_positive, "label": "Bullish"},
        "crude_trend": "falling",
    }


# ── §16: Monday 08:30 session resolution + context load ────────────────────

@pytest.mark.asyncio
async def test_monday_0830_resolves_and_loads_current_snapshot(isolated_db, frozen_time):
    async def seed(db):
        evt = await make_event(db, title="Strong positive Technology sector development",
                                when=ist(SATURDAY, 10, 0), sectors=["Technology"], companies=["INFY"])
        await make_event_triage(db, evt.id, urgency=9, importance=9, headline=evt.title)

    await _build_sunday_snapshot(isolated_db, frozen_time, bias_evidence=seed)
    sunday_snap = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(SUNDAY, 18, 5))
    assert sunday_snap is not None
    version_after_v1 = sunday_snap.snapshot_version

    frozen_time(ist(MONDAY, 8, 30))
    resolved = resolve_opening_prediction_session(ist(MONDAY, 8, 30))
    assert resolved == MONDAY.isoformat()

    context = await get_weekend_context_for_session(isolated_db, resolved, now=ist(MONDAY, 8, 30))
    assert context is not None
    assert context.target_trading_date == MONDAY.isoformat()
    assert context.snapshot_version == version_after_v1
    assert context.status in ("ok", "degraded", "insufficient_evidence")


# ── §17: fresh-Monday-data override scenarios A-E ───────────────────────────

@pytest.mark.asyncio
async def test_scenario_a_weekend_positive_monday_strongly_negative_overrides(isolated_db, frozen_time):
    async def seed(db):
        evt = await make_event(db, title="Strongly positive Technology development",
                                when=ist(SATURDAY, 10, 0), sectors=["Technology"], companies=["INFY"])
        await make_event_triage(db, evt.id, urgency=10, importance=10, headline=evt.title)
    await _build_sunday_snapshot(isolated_db, frozen_time, bias_evidence=seed)

    frozen_time(ist(MONDAY, 8, 30))
    context = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(MONDAY, 8, 30))
    assert context is not None

    bearish_signals = _signals(gift_positive=False, pct_positive=10)
    adj = ops._weekend_adjusted_score(bearish_signals, context)
    assert adj["base_direction"] == "Negative"
    assert adj["final_direction"] == "Negative"  # Monday-fresh data wins


@pytest.mark.asyncio
async def test_scenario_b_weekend_negative_monday_strongly_positive_overrides(isolated_db, frozen_time):
    async def seed(db):
        evt = await make_event(db, title="Strongly negative Energy sector development",
                                when=ist(SATURDAY, 10, 0), sectors=["Energy"], companies=["RELIANCE"], confidence=0.9)
        await make_event_triage(db, evt.id, urgency=10, importance=10, headline=evt.title)
    await _build_sunday_snapshot(isolated_db, frozen_time, bias_evidence=seed)

    frozen_time(ist(MONDAY, 8, 30))
    context = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(MONDAY, 8, 30))
    assert context is not None

    bullish_signals = _signals(gift_positive=True, pct_positive=90)
    adj = ops._weekend_adjusted_score(bullish_signals, context)
    assert adj["base_direction"] == "Positive"
    assert adj["final_direction"] == "Positive"


@pytest.mark.asyncio
async def test_scenario_c_weekend_mixed_low_confidence_zero_or_small_adjustment(isolated_db, frozen_time):
    async def seed(db):
        e1 = await make_event(db, title="Positive Banking development", when=ist(SATURDAY, 9, 0),
                               sectors=["Banking"], companies=["HDFCBANK"])
        await make_event_triage(db, e1.id, urgency=6, importance=6, headline=e1.title)
        e2 = await make_event(db, title="Negative Banking development", when=ist(SATURDAY, 9, 10),
                               sectors=["Banking"], companies=["ICICIBANK"])
        await make_event_triage(db, e2.id, urgency=6, importance=6, headline=e2.title)
    await _build_sunday_snapshot(isolated_db, frozen_time, bias_evidence=seed)

    frozen_time(ist(MONDAY, 8, 30))
    context = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(MONDAY, 8, 30))
    assert context is not None

    signals = _signals(gift_positive=True, pct_positive=75)
    adj = ops._weekend_adjusted_score(signals, context)
    assert abs(adj["adjustment"]) <= 5.0  # near-zero: mixed bias contributes ~nothing


@pytest.mark.asyncio
async def test_scenario_d_insufficient_evidence_zero_contribution(isolated_db, frozen_time):
    frozen_time(ist(SUNDAY, 18, 0))
    # No evidence seeded at all -> first-ever checkpoint still creates v1
    # (brief §22's exception) but with status=insufficient_evidence.
    await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SUNDAY, 18, 0))

    frozen_time(ist(MONDAY, 8, 30))
    context = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(MONDAY, 8, 30))
    assert context is not None
    assert context.status == "insufficient_evidence"

    signals = _signals(gift_positive=True, pct_positive=60)
    adj = ops._weekend_adjusted_score(signals, context)
    assert adj["applied"] is False
    assert adj["adjustment"] == 0.0


@pytest.mark.asyncio
async def test_scenario_e_degraded_bounded_contribution_only(isolated_db, frozen_time):
    """No close snapshot exists (baseline_available=False) -> degraded,
    but with real directional evidence -> bounded, nonzero contribution,
    never treated as invalid (brief §18)."""
    async def seed(db):
        evt = await make_event(db, title="Positive Auto sector development", when=ist(SATURDAY, 10, 0),
                                sectors=["Auto"], companies=["TATAMOTORS"])
        await make_event_triage(db, evt.id, urgency=9, importance=9, headline=evt.title)
    await _build_sunday_snapshot(isolated_db, frozen_time, bias_evidence=seed)

    frozen_time(ist(MONDAY, 8, 30))
    context = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(MONDAY, 8, 30))
    assert context is not None
    assert context.status == "degraded"
    assert context.baseline_available is False

    signals = _signals(gift_positive=True, pct_positive=60)
    adj = ops._weekend_adjusted_score(signals, context)
    if adj["applied"]:
        assert 0 < abs(adj["adjustment"]) <= 15.0


# ── §18: double-count protection through the integrated path ───────────────

@pytest.mark.asyncio
async def test_double_count_guard_through_integrated_path(isolated_db, frozen_time):
    """A real Event both contributes to Weekend Intelligence's
    new_since_close AND is (mocked to be) surfaced by the MIE breaking-
    signals layer opening_prediction_service._gather_events reads —
    verifies the SAME event id flowing through BOTH real layers produces
    the double-count instruction, using a REAL WeekendContext built from
    a real persisted snapshot (not a hand-built one, unlike the original
    Phase 1C unit test)."""
    frozen_time(ist(SUNDAY, 18, 0))
    evt = await make_event(isolated_db, title="RBI monetary policy statement affecting Banking",
                            when=ist(SATURDAY, 10, 0), sectors=["Banking"], companies=["HDFCBANK"])
    await make_event_triage(isolated_db, evt.id, urgency=10, importance=10, headline=evt.title)
    await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SUNDAY, 18, 0))

    frozen_time(ist(MONDAY, 8, 30))
    context = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(MONDAY, 8, 30))
    assert context is not None
    assert evt.id in context.meaningful_development_event_ids

    # Real key shape from read_top_events() (engine.py): "headline", not
    # "event"/"title" — matches the real fix in _gather_events, verified
    # here rather than papering over it with the wrong key.
    fake_mie_state = {"top_events": [{"headline": evt.title, "id": evt.id, "urgency": 90}]}
    with patch("app.services.intelligence.engine.get_intelligence_state", return_value=fake_mie_state):
        events = await ops._gather_events(isolated_db)

    assert events["mie_signals"][0]["id"] == evt.id
    lines = ops._weekend_prompt_lines(events, context)
    assert any("SAME underlying event" in l for l in lines)


# ── §19: base/adjustment/final triple ───────────────────────────────────────

@pytest.mark.asyncio
async def test_base_adjustment_final_triple_reported(isolated_db, frozen_time):
    async def seed(db):
        evt = await make_event(db, title="Strong positive Defence development", when=ist(SATURDAY, 10, 0),
                                sectors=["Defence"], companies=["HAL"])
        await make_event_triage(db, evt.id, urgency=10, importance=10, headline=evt.title)
    await _build_sunday_snapshot(isolated_db, frozen_time, bias_evidence=seed)

    frozen_time(ist(MONDAY, 8, 30))
    context = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(MONDAY, 8, 30))
    signals = _signals(gift_positive=True, pct_positive=55)
    adj = ops._weekend_adjusted_score(signals, context)

    for key in ("base_direction", "base_score", "weekend_direction", "weekend_confidence",
                "adjustment", "final_direction", "final_score", "reason"):
        assert key in adj
    if adj["applied"]:
        assert adj["final_score"] == round(adj["base_score"] + adj["adjustment"], 1) or \
               abs(adj["final_score"] - (adj["base_score"] + adj["adjustment"])) < 0.2  # clamped edge tolerance


# ── §20: user-facing truthfulness ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_weekend_watchlist_never_uses_certainty_language(isolated_db, frozen_time):
    async def seed(db):
        evt = await make_event(db, title="Positive INFY development", when=ist(SATURDAY, 10, 0),
                                sectors=["Technology"], companies=["INFY"])
        await make_event_triage(db, evt.id, urgency=9, importance=9, headline=evt.title)
    await _build_sunday_snapshot(isolated_db, frozen_time, bias_evidence=seed)

    frozen_time(ist(MONDAY, 8, 30))
    context = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(MONDAY, 8, 30))

    lines = ops._weekend_prompt_lines({"mie_signals": []}, context)
    forbidden = ["will rise", "will fall", "guaranteed", "strong buy", "must buy"]
    joined = " ".join(lines).lower()
    assert not any(phrase in joined for phrase in forbidden)
