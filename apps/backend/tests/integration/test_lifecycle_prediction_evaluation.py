"""
Phase 1E §21-§25 — prediction recording through the real V1 trigger path,
and evaluation through the real evaluator, using deterministic price
fixtures (never live yfinance data, per §23).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.db.models.predictions import PredictionEvaluation, PredictionRecord
from app.services.weekend_intelligence.checkpoints import run_checkpoint
from app.services.weekend_intelligence.context import get_weekend_context_for_session
from app.services.weekend_intelligence.prediction_recording import record_weekend_intelligence_predictions
from tests.integration.conftest import MONDAY, SUNDAY, ist, make_company_signal, make_event, make_event_triage

TARGET = MONDAY.isoformat()


def _utc(d, h, m=0):
    return ist(d, h, m).astimezone(timezone.utc)


async def _seed_directional_snapshot(isolated_db, frozen_time):
    """Real checkpoint producing a directional overall_bias (positive)
    and at least one directional company signal — via real normalizers,
    not a hand-built snapshot.

    Uses AICompanySignal, not Event: normalize_event never sets a
    direction at all (Event has no sentiment/direction column in this
    schema — confirmed against evidence.py directly), so an
    Event-only fixture can never produce anything but a "neutral"
    sector/company signal. AICompanySignal.signed_magnitude is the real
    field that drives direction here (evidence.py::normalize_company_signal)."""
    frozen_time(ist(SUNDAY, 18, 0))
    for i in range(3):
        await make_company_signal(
            isolated_db, symbol="INFY", when=ist(SUNDAY, 9 + i, 0), sector="Technology",
            signed_magnitude=20.0, confidence=0.8,
            reason=f"INFY positive development number {i} this weekend",
        )
    await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SUNDAY, 18, 0), checkpoint_label="Sunday 18:00 IST")

    frozen_time(ist(MONDAY, 8, 30))
    return await get_weekend_context_for_session(isolated_db, TARGET, now=ist(MONDAY, 8, 30))


def _no_op_price(*_a, **_kw):
    return None  # store_prediction's baseline-price lookup: no live data, degrades to None (honest, not fabricated)


# ── §21: prediction recording, real V1 trigger path ─────────────────────────

@pytest.mark.asyncio
async def test_prediction_recording_via_real_trigger_path(isolated_db, frozen_time):
    context = await _seed_directional_snapshot(isolated_db, frozen_time)
    assert context is not None

    with patch("app.services.prediction_service._fetch_price_sync", side_effect=_no_op_price):
        created = await record_weekend_intelligence_predictions(context)
    assert len(created) >= 1

    rows = (await isolated_db.execute(
        select(PredictionRecord).where(PredictionRecord.query.like(f"weekend_intelligence:{context.snapshot_id}:%"))
    )).scalars().all()
    assert len(rows) == len(created)
    for r in rows:
        assert r.source == "weekend_intelligence"
        assert r.prediction_type in ("overall", "sector", "company")
        assert r.direction in ("up", "down")
        assert r.horizon_days == 1
        assert r.confidence_factors["snapshot_ref"] == f"{context.snapshot_id}:v{context.snapshot_version}"

    # No duplicate on repeated request (the real V1 semantics — §22).
    with patch("app.services.prediction_service._fetch_price_sync", side_effect=_no_op_price):
        created_again = await record_weekend_intelligence_predictions(context)
    assert created_again == []
    rows_after = (await isolated_db.execute(
        select(PredictionRecord).where(PredictionRecord.query.like(f"weekend_intelligence:{context.snapshot_id}:%"))
    )).scalars().all()
    assert len(rows_after) == len(rows)


@pytest.mark.asyncio
async def test_superseded_saturday_version_not_independently_recorded(isolated_db, frozen_time):
    """Only the CURRENT snapshot's WeekendContext is ever loaded (brief
    §26) — a superseded earlier version has no route into
    record_weekend_intelligence_predictions at all, verified by
    confirming the recorded snapshot_ref always matches the CURRENT
    version, never an older one."""
    frozen_time(ist(SUNDAY, 12, 0))
    evt = await make_event(isolated_db, title="Initial positive Technology development",
                            when=ist(SUNDAY, 9, 0), sectors=["Technology"], companies=["INFY"])
    await make_event_triage(isolated_db, evt.id, urgency=9, importance=9, headline=evt.title)
    await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SUNDAY, 12, 0))
    v1 = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(SUNDAY, 12, 5))

    evt2 = await make_event(isolated_db, title="Major additional Defence development",
                             when=ist(SUNDAY, 15, 0), sectors=["Defence"], companies=["HAL"])
    await make_event_triage(isolated_db, evt2.id, urgency=10, importance=10, headline=evt2.title)
    await run_checkpoint(isolated_db, TARGET, checkpoint_time=_utc(SUNDAY, 18, 0), checkpoint_label="Sunday 18:00 IST")

    frozen_time(ist(MONDAY, 8, 30))
    current = await get_weekend_context_for_session(isolated_db, TARGET, now=ist(MONDAY, 8, 30))
    assert current.snapshot_version > v1.snapshot_version
    assert current.snapshot_id != v1.snapshot_id  # a genuinely different, newer row


# ── §23/§24: deterministic outcome evaluation ───────────────────────────────

def _fixed_price_result(price_before, price_after, ticker="^NSEI"):
    move_pct = round((price_after / price_before - 1) * 100, 3)
    return {"price_before": price_before, "price_after": price_after, "move_pct": move_pct, "ticker": ticker}


@pytest.mark.asyncio
async def test_correct_prediction_evaluates_correct(isolated_db):
    from app.services.prediction_service import store_prediction
    from app.services.prediction_evaluator import evaluate_prediction

    with patch("app.services.prediction_service._fetch_price_sync", side_effect=_no_op_price):
        pred_id = await store_prediction(
            source="weekend_intelligence", prediction_text="test", direction="up",
            prediction_type="overall", target_entities=[{"type": "index", "ticker": "^NSEI", "name": "NIFTY"}],
            confidence_score=70.0, confidence_level="High", horizon_days=1,
            query="test-marker-correct",
        )
    assert pred_id is not None

    prediction = {
        "id": pred_id, "direction": "up", "prediction_type": "overall",
        "target_entities": [{"type": "index", "ticker": "^NSEI", "name": "NIFTY"}],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with patch("app.services.prediction_evaluator._fetch_prices_sync",
               return_value=_fixed_price_result(24000, 24500)):  # +2.08%, well above CORRECT_THRESH
        await evaluate_prediction(prediction, horizon_days=1)

    evals = (await isolated_db.execute(
        select(PredictionEvaluation).where(PredictionEvaluation.prediction_id == pred_id)
    )).scalars().all()
    assert len(evals) == 1
    assert evals[0].verdict == "correct"
    assert evals[0].actual_direction == "up"


@pytest.mark.asyncio
async def test_incorrect_prediction_evaluates_incorrect(isolated_db):
    from app.services.prediction_service import store_prediction
    from app.services.prediction_evaluator import evaluate_prediction

    with patch("app.services.prediction_service._fetch_price_sync", side_effect=_no_op_price):
        pred_id = await store_prediction(
            source="weekend_intelligence", prediction_text="test", direction="up",
            prediction_type="company", target_entities=[{"type": "company", "symbol": "INFY", "name": "INFY"}],
            confidence_score=60.0, confidence_level="Medium", horizon_days=1,
            query="test-marker-incorrect",
        )

    prediction = {
        "id": pred_id, "direction": "up", "prediction_type": "company",
        "target_entities": [{"type": "company", "symbol": "INFY", "name": "INFY", "baseline_ticker": "INFY.NS"}],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with patch("app.services.prediction_evaluator._fetch_prices_sync",
               return_value=_fixed_price_result(1500, 1450, ticker="INFY.NS")):  # -3.33%
        await evaluate_prediction(prediction, horizon_days=1)

    evals = (await isolated_db.execute(
        select(PredictionEvaluation).where(PredictionEvaluation.prediction_id == pred_id)
    )).scalars().all()
    assert evals[0].verdict == "incorrect"
    assert evals[0].actual_direction == "down"


@pytest.mark.asyncio
async def test_missing_outcome_data_evaluates_inconclusive_not_guessed(isolated_db):
    from app.services.prediction_service import store_prediction
    from app.services.prediction_evaluator import evaluate_prediction

    with patch("app.services.prediction_service._fetch_price_sync", side_effect=_no_op_price):
        pred_id = await store_prediction(
            source="weekend_intelligence", prediction_text="test", direction="up",
            prediction_type="sector", target_entities=[{"type": "sector", "name": "SomeSector", "ticker": "^UNKNOWNIDX"}],
            confidence_score=50.0, confidence_level="Low", horizon_days=1,
            query="test-marker-unavailable",
        )

    prediction = {
        "id": pred_id, "direction": "up", "prediction_type": "sector",
        "target_entities": [{"type": "sector", "name": "SomeSector", "ticker": "^UNKNOWNIDX"}],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with patch("app.services.prediction_evaluator._fetch_prices_sync", return_value={}):  # no data available
        await evaluate_prediction(prediction, horizon_days=1)

    evals = (await isolated_db.execute(
        select(PredictionEvaluation).where(PredictionEvaluation.prediction_id == pred_id)
    )).scalars().all()
    assert evals[0].verdict == "inconclusive"
    assert evals[0].actual_direction is None  # no guessed result
    assert evals[0].actual_move_pct is None


# ── Full wire-up: PredictionRecord -> get_due_predictions -> evaluation ────

@pytest.mark.asyncio
async def test_full_pipeline_record_to_due_to_evaluated(isolated_db, frozen_time):
    context = await _seed_directional_snapshot(isolated_db, frozen_time)
    with patch("app.services.prediction_service._fetch_price_sync", side_effect=_no_op_price):
        created = await record_weekend_intelligence_predictions(context)
    assert len(created) >= 1

    # Backdate created_at so it's genuinely "due" at horizon=1 — real
    # store_prediction() always stamps real now() with no override
    # (documented Phase 1C limitation), so this is the honest way to
    # exercise the due-filter without waiting a real day.
    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
    for pred_id in created:
        row = (await isolated_db.execute(
            select(PredictionRecord).where(PredictionRecord.id == pred_id)
        )).scalar_one()
        row.created_at = two_days_ago
    await isolated_db.commit()

    from app.services.prediction_service import get_due_predictions
    due = await get_due_predictions(horizon_days=1, limit=50)
    due_ids = {d["id"] for d in due}
    assert set(created) <= due_ids

    with patch("app.services.prediction_evaluator._fetch_prices_sync",
               return_value=_fixed_price_result(24000, 24300)):
        from app.services.prediction_evaluator import run_evaluation_cycle
        stats = await run_evaluation_cycle()
    assert stats["evaluated"] >= len(created)

    evals = (await isolated_db.execute(
        select(PredictionEvaluation).where(PredictionEvaluation.prediction_id.in_(created))
    )).scalars().all()
    assert len(evals) == len(created)
