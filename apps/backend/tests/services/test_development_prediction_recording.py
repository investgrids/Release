"""
Phase 6C V1 — Development -> Prediction Memory
(app/services/development_memory/prediction_recording.py).

Reuses the existing prediction_service/prediction_evaluator pipeline
entirely -- no new table, no new evaluator. Live tests against the real
dev DB, cleaning up every row they create.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models.development import Development
from app.db.models.predictions import PredictionRecord
from app.db.session import AsyncSessionLocal
from app.services.development_memory.prediction_recording import (
    HORIZON_DAYS,
    is_prediction_worthy,
    record_development_prediction,
)


async def _cleanup(db, *, development_ids: list[str] = (), queries: list[str] = ()) -> None:
    if development_ids:
        await db.execute(delete(Development).where(Development.id.in_(development_ids)))
    if queries:
        await db.execute(delete(PredictionRecord).where(PredictionRecord.query.in_(queries)))
    await db.commit()


def _make_dev(*, evidence_count: int = 2, formation_impact_tier: str | None = None,
              companies: list[str] | None = None, current_direction: str | None = "positive",
              current_confidence: float | None = 0.8) -> Development:
    now = datetime.now(timezone.utc)
    companies = companies if companies is not None else [f"T6C{uuid.uuid4().hex[:6].upper()}"]
    return Development(
        id=str(uuid.uuid4()),
        canonical_title="Test development for 6C prediction recording",
        status="open",
        primary_company=companies[0] if companies else None,
        companies=companies,
        sectors=[],
        themes=[],
        first_observed_at=now,
        last_observed_at=now,
        formation_impact_tier=formation_impact_tier,
        current_direction=current_direction,
        current_confidence=current_confidence,
        evidence_count=evidence_count,
        schema_version="test",
    )


@pytest.mark.asyncio
async def test_is_prediction_worthy_true_for_qualifying_single_company_development():
    dev = _make_dev(evidence_count=2, current_direction="positive", current_confidence=0.8)
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            assert await is_prediction_worthy(db, dev) is True
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=ids)


@pytest.mark.asyncio
async def test_is_prediction_worthy_false_for_multi_company_development():
    """The hard rule: never spray one direction across multiple targets
    -- V1 handles this by simply not predicting for multi-company
    Developments at all."""
    dev = _make_dev(evidence_count=3, companies=["AAA", "BBB"], current_direction="positive", current_confidence=0.8)
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            assert await is_prediction_worthy(db, dev) is False
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=ids)


@pytest.mark.asyncio
async def test_is_prediction_worthy_false_for_mixed_direction():
    dev = _make_dev(evidence_count=2, current_direction="mixed", current_confidence=0.8)
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            assert await is_prediction_worthy(db, dev) is False
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=ids)


@pytest.mark.asyncio
async def test_is_prediction_worthy_false_for_low_confidence():
    dev = _make_dev(evidence_count=2, current_direction="positive", current_confidence=0.1)
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            assert await is_prediction_worthy(db, dev) is False
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=ids)


@pytest.mark.asyncio
async def test_is_prediction_worthy_false_when_not_graph_worthy():
    """Prediction-worthiness requires graph-worthiness as its floor."""
    dev = _make_dev(evidence_count=1, formation_impact_tier=None, current_direction="positive", current_confidence=0.8)
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            assert await is_prediction_worthy(db, dev) is False
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=ids)


@pytest.mark.asyncio
async def test_record_development_prediction_creates_shadow_prediction():
    dev = _make_dev(evidence_count=2, current_direction="positive", current_confidence=0.8)
    ticker = dev.companies[0]
    marker = f"development:{dev.id}:7d:v1:{ticker}"
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            pred_id = await record_development_prediction(db, dev)
            assert pred_id is not None

            record = await db.get(PredictionRecord, pred_id)
            assert record.source == "development_memory"
            assert record.direction == "up"
            assert record.horizon_days == HORIZON_DAYS
            assert record.experimental is True  # shadow mode
            assert record.query == marker
            assert record.target_entities[0]["symbol"] == ticker
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=ids, queries=[marker])


@pytest.mark.asyncio
async def test_record_development_prediction_is_idempotent():
    dev = _make_dev(evidence_count=2, current_direction="positive", current_confidence=0.8)
    ticker = dev.companies[0]
    marker = f"development:{dev.id}:7d:v1:{ticker}"
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            first = await record_development_prediction(db, dev)
            second = await record_development_prediction(db, dev)
            assert first is not None
            assert second is None  # already recorded — no duplicate

            count = (await db.execute(
                select(PredictionRecord).where(PredictionRecord.query == marker)
            )).scalars().all()
            assert len(count) == 1
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=ids, queries=[marker])


@pytest.mark.asyncio
async def test_direction_flip_does_not_create_a_second_overlapping_prediction():
    """The idempotency key deliberately excludes direction -- the FIRST
    qualified prediction is preserved as what Market Ripple believed when
    this Development became prediction-worthy, even if direction later
    flips."""
    dev = _make_dev(evidence_count=2, current_direction="positive", current_confidence=0.8)
    ticker = dev.companies[0]
    marker = f"development:{dev.id}:7d:v1:{ticker}"
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            first = await record_development_prediction(db, dev)
            assert first is not None

            dev.current_direction = "negative"
            await db.commit()

            second = await record_development_prediction(db, dev)
            assert second is None

            records = (await db.execute(
                select(PredictionRecord).where(PredictionRecord.query == marker)
            )).scalars().all()
            assert len(records) == 1
            assert records[0].direction == "up"  # the original call, preserved
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, development_ids=ids, queries=[marker])
