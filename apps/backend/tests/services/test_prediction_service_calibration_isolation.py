"""
Phase 2B §6 — production calibration isolation, real DB.

This is the single gap the Phase 2A audit flagged as the one that
actually matters: without an `experimental` filter, a shadow/quant
prediction reaching status="complete" would silently blend into
get_stats()/CalibrationStat, the app's own reported "how good are we"
number. These tests prove the isolation holds against the real
prediction_service functions, not a mock.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.db.models.predictions import PredictionRecord, PredictionEvaluation
from app.services.prediction_service import store_prediction, record_evaluation, get_stats


async def _cleanup(*pred_ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(PredictionEvaluation).where(PredictionEvaluation.prediction_id.in_(pred_ids)))
        await db.execute(delete(PredictionRecord).where(PredictionRecord.id.in_(pred_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_experimental_prediction_defaults_to_false_for_ordinary_callers():
    """Every existing caller of store_prediction() (ai_search, triage,
    aipe, weekend_intelligence) doesn't pass `experimental` — must default
    to False, or every production prediction ever made would silently
    become invisible to its own accuracy dashboard."""
    pred_id = await store_prediction(
        source="ai_search", prediction_text="test prediction", direction="up",
        prediction_type="overall", target_entities=[], confidence_score=60.0,
        confidence_level="Medium", horizon_days=1,
    )
    assert pred_id is not None
    try:
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(PredictionRecord).where(PredictionRecord.id == pred_id))).scalar_one()
            assert row.experimental is False
    finally:
        await _cleanup(pred_id)


@pytest.mark.asyncio
async def test_experimental_prediction_excluded_from_get_stats_total():
    """The core regression: a completed experimental prediction must not
    move get_stats()'s total_predictions/complete_predictions counters —
    those are quoted verbatim as this app's own accuracy claim."""
    before = await get_stats()

    pred_id = await store_prediction(
        source="quant_baseline", prediction_text="pytest experimental prediction", direction="up",
        prediction_type="company",
        target_entities=[{"type": "company", "symbol": "PYTESTSYM", "baseline_price": 100.0, "baseline_ticker": "PYTESTSYM.NS"}],
        confidence_score=50.0, confidence_level="Medium", horizon_days=1,
        experimental=True, model_version="baseline-pytest-v1",
        created_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    assert pred_id is not None
    try:
        await record_evaluation(
            prediction_id=pred_id, horizon_days=1, verdict="correct",
            actual_direction="up", actual_move_pct=1.5, score=1.0,
            evidence={}, notes="pytest",
        )
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(PredictionRecord).where(PredictionRecord.id == pred_id))).scalar_one()
            assert row.status == "complete"  # really did complete — proves this isn't excluded by accident

        after = await get_stats()
        assert after["total_predictions"] == before["total_predictions"], \
            "an experimental prediction must not change the production total"
        assert after["complete_predictions"] == before["complete_predictions"], \
            "an experimental prediction reaching status=complete must still not count as a production completion"
    finally:
        await _cleanup(pred_id)


@pytest.mark.asyncio
async def test_non_experimental_prediction_is_counted_by_get_stats():
    """Sanity check the isolation isn't a blanket bug that hides
    everything — a real (non-experimental) completed prediction must
    still show up, or the fix would just be silently breaking the
    dashboard instead of correctly scoping it."""
    before = await get_stats()

    pred_id = await store_prediction(
        source="triage", prediction_text="pytest production prediction", direction="down",
        prediction_type="overall", target_entities=[], confidence_score=55.0,
        confidence_level="Medium", horizon_days=1,
        created_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    assert pred_id is not None
    try:
        await record_evaluation(
            prediction_id=pred_id, horizon_days=1, verdict="correct",
            actual_direction="down", actual_move_pct=-1.2, score=1.0,
            evidence={}, notes="pytest",
        )
        after = await get_stats()
        assert after["total_predictions"] == before["total_predictions"] + 1
        assert after["complete_predictions"] == before["complete_predictions"] + 1
    finally:
        await _cleanup(pred_id)
