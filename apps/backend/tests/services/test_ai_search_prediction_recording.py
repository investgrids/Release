"""
AI Search -> Prediction Memory / Calibration — shared module
(app/services/ai_search/prediction_recording.py).

Ported verbatim from V2's own _map_horizon/_store_search_predictions/
inline calibration block. These tests prove the shared behavior once;
V2 and V3 each get a live end-to-end proof separately (see
test_ai_search_v2_confidence.py's live test and the live V3 verification
run as part of this same change) that they actually call it.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest
from sqlalchemy import delete, select

from app.db.models.predictions import PredictionRecord
from app.db.session import AsyncSessionLocal
from app.services.ai_search.prediction_recording import (
    apply_calibration,
    map_horizon,
    store_search_predictions,
)


@dataclass
class _FakeConfResult:
    total_score: float
    level: str
    reasons: list[str] = field(default_factory=list)


def test_map_horizon_matches_v2_semantics():
    assert map_horizon("intraday") == 1
    assert map_horizon("1 day") == 1
    assert map_horizon("this week") == 3
    assert map_horizon("3 day") == 3
    assert map_horizon("1 month") == 7
    assert map_horizon("short term") == 7
    assert map_horizon("") == 30
    assert map_horizon("long term structural") == 30


def test_apply_calibration_noop_below_ten_verified_predictions():
    conf = _FakeConfResult(total_score=50.0, level="Medium")
    apply_calibration(conf, {"Medium": {"calibration_factor": 1.5, "total": 5, "accuracy_rate": 0.8}})
    assert conf.total_score == 50.0  # untouched -- below the >=10 guard
    assert conf.reasons == []


def test_apply_calibration_noop_when_factor_out_of_bounds():
    conf = _FakeConfResult(total_score=50.0, level="Medium")
    apply_calibration(conf, {"Medium": {"calibration_factor": 3.0, "total": 20, "accuracy_rate": 0.9}})
    assert conf.total_score == 50.0  # untouched -- factor exceeds the 0.4-1.8 sane bound


def test_apply_calibration_adjusts_score_and_level_when_qualified():
    conf = _FakeConfResult(total_score=50.0, level="Medium")
    apply_calibration(conf, {"Medium": {"calibration_factor": 1.5, "total": 15, "accuracy_rate": 0.75}})
    assert conf.total_score == 75.0
    assert conf.level != "Medium" or conf.total_score != 50.0  # something real changed
    assert any("Calibrated from 15 verified predictions" in r for r in conf.reasons)


def test_apply_calibration_noop_with_no_cal_data():
    conf = _FakeConfResult(total_score=50.0, level="Medium")
    apply_calibration(conf, {})
    assert conf.total_score == 50.0


async def _cleanup(queries: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(PredictionRecord).where(PredictionRecord.query.in_(queries)))
        await db.commit()


@pytest.mark.asyncio
async def test_store_search_predictions_creates_overall_and_company_records():
    query = f"pytest-shared-pred-{uuid.uuid4().hex[:8]}"
    result = {
        "query": query,
        "investment_verdict": {"direction": "bullish", "horizon": "1 month"},
        "answer": {"sentiment": "bullish", "immediate_impact": "Strong quarter"},
        "companies": [
            {"symbol": "RELIANCE", "name": "Reliance Industries", "impact_type": "beneficiary", "confidence": 80},
            {"symbol": "ONGC", "name": "ONGC", "impact_type": "at_risk", "confidence": 60},
        ],
    }
    try:
        await store_search_predictions(
            result=result, confidence_score=70.0, confidence_level="High", confidence_breakdown={"x": 1},
        )
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(PredictionRecord).where(PredictionRecord.query == query))).scalars().all()
        by_type = {r.prediction_type: r for r in rows}
        assert "overall" in by_type
        assert by_type["overall"].direction == "up"
        assert by_type["overall"].horizon_days == 7  # "1 month" maps to 7 per map_horizon
        assert "company" in by_type or len(rows) >= 2
        company_rows = [r for r in rows if r.prediction_type == "company"]
        directions = {r.target_entities[0]["symbol"]: r.direction for r in company_rows}
        assert directions.get("RELIANCE") == "up"
        assert directions.get("ONGC") == "down"
    finally:
        await _cleanup([query])


@pytest.mark.asyncio
async def test_store_search_predictions_never_raises_on_malformed_result():
    """Fire-and-forget contract: a malformed result must not raise --
    the caller creates this as an unawaited asyncio task."""
    await store_search_predictions(
        result={}, confidence_score=50.0, confidence_level="Medium", confidence_breakdown={},
    )  # must not raise
