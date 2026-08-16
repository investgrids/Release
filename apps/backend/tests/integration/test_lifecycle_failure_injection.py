"""
Phase 1E §33 — failure injection across the lifecycle. Several of these
scenarios are already covered elsewhere (cross-referenced below rather
than duplicated) — this file adds the ones with no existing direct
coverage.
"""
from __future__ import annotations

from datetime import timezone
from unittest.mock import patch

import pytest

from app.services.weekend_intelligence.checkpoints import run_checkpoint, run_weekend_checkpoint_cycle
from app.services.weekend_intelligence.context import get_weekend_context_for_session
from app.services.weekend_intelligence.risk_synthesis import SOURCE_UNAVAILABLE
from tests.integration.conftest import (
    MONDAY, SUNDAY, ist, make_announcement, make_company_signal, make_event,
    make_event_triage, make_news, make_opportunity, make_policy,
)

TARGET = MONDAY.isoformat()


def _utc(d, h, m=0):
    return ist(d, h, m).astimezone(timezone.utc)


# 1. Close baseline missing — already covered:
#    test_lifecycle_friday_close.py::test_missing_close_snapshot_makes_weekend_intelligence_honestly_degraded

# 2. Weekend evidence source unavailable — post-review refinement,
#    verified through the full REAL checkpoint path with 6 real evidence
#    rows (one per source) and one source (announcements) mocked to
#    fail: the checkpoint completes using the 5 healthy sources rather
#    than aborting entirely, forces status="degraded", and the
#    persisted confidence_warning_refs names exactly which source was
#    unavailable. See test_weekend_intelligence_aggregator.py /
#    test_weekend_intelligence_evidence_window.py for the matching
#    lower-level unit/integration coverage of the same refinement.

@pytest.mark.asyncio
async def test_owner_scenario_one_source_fails_five_continue_degraded_not_skipped(isolated_db, frozen_time):
    """The exact scenario from review: News/Events/Policy/CompanySignal/
    Opportunity healthy, Announcements fails. Real checkpoint outcome
    must be CREATED (not skipped/aborted), status degraded, and a
    plain-English warning naming the failed source — never a silently
    smaller evidence set with no explanation."""
    frozen_time(ist(SUNDAY, 18, 0))

    evt = await make_event(isolated_db, title="Healthy event evidence", when=ist(SUNDAY, 9, 0), sectors=["Banking"])
    await make_event_triage(isolated_db, evt.id, urgency=9, importance=9, headline=evt.title)
    await make_news(isolated_db, headline="Healthy news evidence", when=ist(SUNDAY, 9, 5))
    await make_policy(isolated_db, title="Healthy policy evidence", when=ist(SUNDAY, 9, 10))
    await make_company_signal(isolated_db, symbol="INFY", when=ist(SUNDAY, 9, 15), sector="Technology")
    await make_opportunity(isolated_db, title="Healthy opportunity evidence", when=ist(SUNDAY, 9, 20))
    await make_announcement(isolated_db, subject="Will fail to normalize", when=ist(SUNDAY, 9, 25))
    await isolated_db.commit()

    with patch(
        "app.services.weekend_intelligence.evidence_window.normalize_announcement",
        side_effect=RuntimeError("simulated announcement source failure"),
    ):
        result = await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SUNDAY, 18, 0),
                                       checkpoint_label="Sunday 18:00 IST")

    # Did not skip/abort — the 5 healthy sources produced a real snapshot.
    assert result.outcome == "created"
    assert result.evidence_count is not None and result.evidence_count >= 5
    assert result.status == "degraded"

    snap = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(SUNDAY, 18, 5))
    assert snap is not None
    assert snap.status == "degraded"
    # The exact warning wording is verified separately, at the persisted
    # WeekendIntelligenceSnapshot level (WeekendContext.major_risks is
    # market risks, not confidence warnings — see the next test).


@pytest.mark.asyncio
async def test_owner_scenario_warning_text_matches_reviewed_wording(isolated_db, frozen_time):
    """Same scenario, checked at the persisted-snapshot level (not just
    the in-memory WeekendContext, which deliberately doesn't carry
    per-item warning text) — confirms the exact wording reaches the DB
    row an API consumer would read."""
    from sqlalchemy import select
    from app.db.models.weekend_intelligence import WeekendIntelligenceSnapshot

    frozen_time(ist(SUNDAY, 18, 0))
    await make_event(isolated_db, title="Healthy event evidence", when=ist(SUNDAY, 9, 0), sectors=["Banking"])
    await make_announcement(isolated_db, subject="Will fail to normalize", when=ist(SUNDAY, 9, 25))
    await isolated_db.commit()

    with patch(
        "app.services.weekend_intelligence.evidence_window.normalize_announcement",
        side_effect=RuntimeError("simulated announcement source failure"),
    ):
        await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SUNDAY, 18, 0))

    row = (await isolated_db.execute(
        select(WeekendIntelligenceSnapshot).where(
            WeekendIntelligenceSnapshot.target_trading_date == TARGET,
            WeekendIntelligenceSnapshot.is_current.is_(True),
        )
    )).scalar_one()
    assert row.status == "degraded"
    matches = [w for w in row.confidence_warning_refs if w["risk_type"] == SOURCE_UNAVAILABLE]
    assert len(matches) == 1
    assert matches[0]["description"] == "Company announcement data was unavailable during this update."


@pytest.mark.asyncio
async def test_scheduler_entry_point_never_propagates_a_deeper_failure():
    """The scheduler-level safety net (brief §33: "not crash") still
    holds for whatever CAN'T be isolated per-source (e.g. a failure in
    run_checkpoint's own orchestration, outside evidence collection)."""
    with patch(
        "app.services.weekend_intelligence.checkpoints.run_checkpoint",
        side_effect=RuntimeError("simulated deep failure outside evidence collection"),
    ):
        await run_weekend_checkpoint_cycle()  # must not raise


# 3. Historical matcher returns none — already covered:
#    test_lifecycle_weekend.py::test_sunday_final_state_integrity
#    (asserts historical_analogue_refs is a valid, possibly-empty list)
#    and Phase 1B's own historical_integration tests.

# 4. Weekend API unavailable — already covered:
#    apps/web/components/weekend/WeekendHomePage.test.tsx
#    ("API failure (network error)" / "non-ok HTTP status" tests)

# 5. Session API unavailable — already covered:
#    apps/web/lib/weekendSession.test.ts
#    ("null session response -> normal homepage")

# 6. Monday WeekendContext unavailable — already covered:
#    test_opening_prediction_weekend_integration.py::test_weekend_adjustment_not_applied_when_context_is_none
#    and the real "no snapshot / stale / wrong session -> None" behavior
#    in test_lifecycle_weekend.py and Phase 1C's own context tests.

@pytest.mark.asyncio
async def test_weekend_context_unavailable_still_produces_a_normal_opening_prediction(isolated_db, frozen_time):
    """Integrated version: no snapshot exists at all for the target
    session -> get_weekend_context_for_session returns None -> the
    deterministic triple degrades to "not applied", never raises."""
    from app.services import opening_prediction_service as ops

    frozen_time(ist(MONDAY, 8, 30))
    context = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(MONDAY, 8, 30))
    assert context is None

    signals = {
        "gift_nifty": {"value": "24500", "change": "+0.5%", "positive": True},
        "india_vix": {"value": "13.2", "float": 13.2, "level": "LOW", "interpretation": "calm"},
        "global_sentiment": {"positive_count": 3, "total": 4, "pct_positive": 75, "label": "Bullish"},
    }
    adj = ops._weekend_adjusted_score(signals, context)
    assert adj["applied"] is False
    assert adj["reason"] == "no_weekend_context"


# 7. Prediction outcome unavailable — already covered:
#    test_lifecycle_prediction_evaluation.py::test_missing_outcome_data_evaluates_inconclusive_not_guessed
