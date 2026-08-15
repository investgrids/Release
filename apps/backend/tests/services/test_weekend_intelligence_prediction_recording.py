"""
Weekend Intelligence prediction recording tests — brief §39. DB-backed:
writes real PredictionRecord rows via the existing store_prediction(),
cleaned up in finally. Uses fixed fake tickers/symbols wherever possible
to avoid live yfinance calls (store_prediction only fetches baseline
prices for entities missing one — company/index entries here trigger a
real yfinance lookup unless network is unavailable, in which case
baseline_price simply stays None; either way no test assertion depends
on the fetched price, only on record creation/dedup/direction/type).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.db.models.predictions import PredictionRecord
from app.services.weekend_intelligence.context import SignalRef, WeekendContext
from app.services.weekend_intelligence.prediction_recording import record_weekend_intelligence_predictions


def _context(**overrides) -> WeekendContext:
    defaults = dict(
        target_trading_date="2098-10-05", generated_at=datetime.now(timezone.utc), status="ok",
        overall_bias="positive", production_confidence=70.0,
        top_sector_signals=[], top_company_signals=[],
        snapshot_id=f"snap-{uuid.uuid4().hex[:8]}", snapshot_version=1,
    )
    defaults.update(overrides)
    return WeekendContext(**defaults)


async def _cleanup(snapshot_id: str):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(PredictionRecord).where(PredictionRecord.query.like(f"weekend_intelligence:{snapshot_id}:%")))
        await db.commit()


async def _fetch(snapshot_id: str) -> list[PredictionRecord]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(PredictionRecord).where(PredictionRecord.query.like(f"weekend_intelligence:{snapshot_id}:%"))
        )).scalars().all()
        return list(rows)


@pytest.mark.asyncio
async def test_market_prediction_recorded_for_directional_bias():
    ctx = _context(overall_bias="positive", production_confidence=75.0)
    try:
        created = await record_weekend_intelligence_predictions(ctx)
        assert len(created) == 1
        rows = await _fetch(ctx.snapshot_id)
        assert len(rows) == 1
        assert rows[0].source == "weekend_intelligence"
        assert rows[0].prediction_type == "overall"
        assert rows[0].direction == "up"
        assert rows[0].horizon_days == 1
        assert rows[0].confidence_score == 75.0
    finally:
        await _cleanup(ctx.snapshot_id)


@pytest.mark.asyncio
async def test_no_market_prediction_for_neutral_or_mixed_bias():
    ctx = _context(overall_bias="neutral")
    try:
        created = await record_weekend_intelligence_predictions(ctx)
        assert created == []
    finally:
        await _cleanup(ctx.snapshot_id)


@pytest.mark.asyncio
async def test_insufficient_evidence_records_nothing():
    ctx = _context(status="insufficient_evidence", overall_bias="neutral", production_confidence=0.0,
                    top_sector_signals=[SignalRef(id="IT", direction="positive", confidence=0.8, evidence_count=3)],
                    top_company_signals=[SignalRef(id="INFY", direction="positive_watch", confidence=0.7, evidence_count=3)])
    try:
        created = await record_weekend_intelligence_predictions(ctx)
        assert created == []
    finally:
        await _cleanup(ctx.snapshot_id)


@pytest.mark.asyncio
async def test_sector_prediction_recorded_only_with_resolvable_ticker():
    ctx = _context(
        overall_bias="neutral",  # isolate to sector-level only
        top_sector_signals=[
            SignalRef(id="Banking", direction="positive", confidence=0.8, evidence_count=5),
            SignalRef(id="ThisIsNotARealSectorName", direction="negative", confidence=0.5, evidence_count=2),
        ],
    )
    try:
        created = await record_weekend_intelligence_predictions(ctx)
        rows = await _fetch(ctx.snapshot_id)
        sector_rows = [r for r in rows if r.prediction_type == "sector"]
        assert len(sector_rows) == 1  # only Banking, which resolves via SECTOR_TICKERS
        assert sector_rows[0].direction == "up"
        assert sector_rows[0].target_entities[0]["ticker"] == "^NSEBANK"
    finally:
        await _cleanup(ctx.snapshot_id)


@pytest.mark.asyncio
async def test_mixed_sector_signal_not_recorded():
    ctx = _context(
        overall_bias="neutral",
        top_sector_signals=[SignalRef(id="Banking", direction="mixed", confidence=0.4, evidence_count=5)],
    )
    try:
        created = await record_weekend_intelligence_predictions(ctx)
        assert created == []
    finally:
        await _cleanup(ctx.snapshot_id)


@pytest.mark.asyncio
async def test_company_prediction_recorded_for_directional_states():
    ctx = _context(
        overall_bias="neutral",
        top_company_signals=[
            SignalRef(id="INFY", direction="high_conviction_watch", confidence=0.8, evidence_count=4),
            SignalRef(id="TCS", direction="risk_watch", confidence=0.6, evidence_count=3),
            SignalRef(id="SBIN", direction="mixed", confidence=0.5, evidence_count=3),
            SignalRef(id="ITC", direction="monitor", confidence=0.3, evidence_count=1),
        ],
    )
    try:
        created = await record_weekend_intelligence_predictions(ctx)
        rows = await _fetch(ctx.snapshot_id)
        company_rows = {r.target_entities[0]["symbol"]: r for r in rows if r.prediction_type == "company"}
        assert set(company_rows) == {"INFY", "TCS"}  # SBIN (mixed) and ITC (monitor) skipped
        assert company_rows["INFY"].direction == "up"
        assert company_rows["TCS"].direction == "down"
    finally:
        await _cleanup(ctx.snapshot_id)


@pytest.mark.asyncio
async def test_confidence_warnings_and_risks_never_produce_predictions():
    """Only overall_bias / sector / company signals are recordable
    (brief §24) — record_weekend_intelligence_predictions never reads
    major_risks/major_opportunities at all, verified here by populating
    them with real ItemRefs and confirming zero predictions result from
    a neutral-bias, signal-free context."""
    from app.services.weekend_intelligence.context import ItemRef
    ctx = _context(
        overall_bias="neutral",
        major_risks=[ItemRef(description="Something risky", severity="high")],
        major_opportunities=[ItemRef(description="Something promising", severity=None)],
    )
    try:
        created = await record_weekend_intelligence_predictions(ctx)
        assert created == []
        rows = await _fetch(ctx.snapshot_id)
        assert rows == []
    finally:
        await _cleanup(ctx.snapshot_id)


@pytest.mark.asyncio
async def test_rerunning_is_idempotent():
    ctx = _context(overall_bias="positive", production_confidence=80.0,
                    top_sector_signals=[SignalRef(id="IT", direction="positive", confidence=0.7, evidence_count=4)])
    try:
        first = await record_weekend_intelligence_predictions(ctx)
        second = await record_weekend_intelligence_predictions(ctx)
        assert len(first) == 2  # market + IT sector
        assert second == []    # nothing new — already recorded
        rows = await _fetch(ctx.snapshot_id)
        assert len(rows) == 2  # not duplicated
    finally:
        await _cleanup(ctx.snapshot_id)


@pytest.mark.asyncio
async def test_source_snapshot_and_version_preserved_in_confidence_factors():
    ctx = _context(overall_bias="positive", production_confidence=60.0, snapshot_version=3)
    try:
        await record_weekend_intelligence_predictions(ctx)
        rows = await _fetch(ctx.snapshot_id)
        assert rows[0].confidence_factors["snapshot_ref"] == f"{ctx.snapshot_id}:v3"
        assert rows[0].confidence_factors["source"] == "weekend_intelligence"
    finally:
        await _cleanup(ctx.snapshot_id)
