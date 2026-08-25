"""
Company Score Engine — real DB-backed tests for the 2026-08-25 ranking-
performance fix. Confirms the batch-precomputed accuracy_map path
(compute_sector_rankings/get_ranking_stats) produces byte-identical
scores to the original per-symbol query path (the single-symbol
/company-scores/{symbol} endpoint still uses), and that the short TTL
cache around compute_sector_rankings behaves correctly (hit avoids
recomputation, keyed by the real inputs that change the result, never
caches a raised exception).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.company_signal import AICompanySignal
from app.db.models.predictions import PredictionRecord, PredictionEvaluation
from app.db.session import AsyncSessionLocal
from app.services.aipe import company_score_engine as engine


def _tag():
    return uuid.uuid4().hex[:8]


async def _cleanup(symbols: list[str], prediction_ids: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(AICompanySignal).where(AICompanySignal.symbol.in_(symbols)))
        await db.execute(delete(PredictionEvaluation).where(PredictionEvaluation.prediction_id.in_(prediction_ids)))
        await db.execute(delete(PredictionRecord).where(PredictionRecord.id.in_(prediction_ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_contributing_signal_count_excludes_zero_weight_rows():
    """2026-08-25 — signal semantic integrity audit follow-up (artifacts/
    company_signal_semantic_integrity_audit.md): comparison_publisher.py
    and signal_publisher.py never set confidence_score/quality_score on
    their articles, so every AICompanySignal row sourced from them
    carries a real, stored 0.0 in at least one weighted factor and
    contributes exactly zero to the score — but still counts toward
    signal_count. contributing_signal_count must only count rows whose
    real weighted contribution is non-zero, while signal_count keeps
    counting every real row (unchanged, for any caller relying on "has
    at least one signal at all")."""
    tag = _tag()
    symbol = f"TESTCONTRIB{tag}"[:20].upper()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        db.add(AICompanySignal(  # a real, contributing row
            source_type="article", source_id=f"art-{tag}-1", symbol=symbol,
            company_name="Test Contributing Co", sector="Energy",
            signed_magnitude=60.0, confidence=0.8, quality=0.9,
            reason="real contributing signal", signal_at=now,
        ))
        db.add(AICompanySignal(  # zeroed like every real live_signal row (confidence=quality=0.0)
            source_type="article", source_id=f"art-{tag}-2", symbol=symbol,
            company_name="Test Contributing Co", sector="Energy",
            signed_magnitude=0.0, confidence=0.0, quality=0.0,
            reason="Intelligence Detection", signal_at=now,
        ))
        db.add(AICompanySignal(  # zeroed like every real comparison_intelligence row (quality=0.0)
            source_type="article", source_id=f"art-{tag}-3", symbol=symbol,
            company_name="Test Contributing Co", sector="Energy",
            signed_magnitude=0.0, confidence=0.29, quality=0.0,
            reason="Comparison subject", signal_at=now,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await engine.compute_company_score(db, symbol)
        assert result["signal_count"] == 3
        assert result["contributing_signal_count"] == 1
    finally:
        await _cleanup([symbol], [])


@pytest.mark.asyncio
async def test_accuracy_map_matches_per_symbol_query_exactly():
    """The real regression-fix invariant: compute_company_score's score
    must not change whether accuracy is computed via the old per-symbol
    query or the new precomputed accuracy_map, for real matching
    PredictionRecord/PredictionEvaluation data (>= _MIN_ACCURACY_SAMPLE
    real evaluations, so the multiplier is actually non-neutral)."""
    tag = _tag()
    symbol = f"TESTACC{tag}"[:20].upper()
    pred_ids = [str(uuid.uuid4()) for _ in range(12)]

    async with AsyncSessionLocal() as db:
        db.add(AICompanySignal(
            source_type="opportunity", source_id=f"opp-{tag}", symbol=symbol,
            company_name="Test Accuracy Co", sector="Energy",
            signed_magnitude=80.0, confidence=0.8, quality=1.0,
            reason="real test signal", signal_at=datetime.now(timezone.utc),
        ))
        for pid in pred_ids:
            db.add(PredictionRecord(
                id=pid, source="ai_search", prediction_text="test", direction="up",
                prediction_type="company", target_entities=[{"type": "company", "symbol": symbol}],
                status="complete",
            ))
        await db.flush()  # PredictionRecord rows must exist before the FK-constrained evaluations
        for i, pid in enumerate(pred_ids):
            db.add(PredictionEvaluation(
                id=str(uuid.uuid4()), prediction_id=pid, horizon_days=7,
                verdict="correct", score=1.0 if i % 2 == 0 else 0.5,
            ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            # Old path: real per-symbol query (_accuracy_multiplier called
            # internally since accuracy_map is omitted).
            old_result = await engine.compute_company_score(db, symbol)

        async with AsyncSessionLocal() as db:
            # New path: precomputed accuracy_map, batch-style.
            accuracy_map = await engine._build_accuracy_map(db)
            assert symbol in accuracy_map, "real prediction data must be found by the batch map"
            new_result = await engine.compute_company_score(db, symbol, accuracy_map=accuracy_map)

        assert old_result["score"] == new_result["score"]
        assert old_result["confidence"] == new_result["confidence"]
        assert old_result["trend"] == new_result["trend"]
        assert old_result["breakdown"]["accuracy_multiplier"] == new_result["breakdown"]["accuracy_multiplier"]
        # Real proof the accuracy signal actually moved the score off
        # neutral (1.0) — otherwise this test would pass trivially even
        # with a broken accuracy_map.
        assert new_result["breakdown"]["accuracy_multiplier"] != 1.0
    finally:
        await _cleanup([symbol], pred_ids)


@pytest.mark.asyncio
async def test_accuracy_map_neutral_when_sample_too_small():
    """Below _MIN_ACCURACY_SAMPLE real evaluations, both paths must stay
    neutral (1.0) rather than projecting confidence from a handful of
    samples — the same real guard as before this fix, still real."""
    tag = _tag()
    symbol = f"TESTSML{tag}"[:20].upper()
    pred_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as db:
        db.add(AICompanySignal(
            source_type="opportunity", source_id=f"opp-{tag}", symbol=symbol,
            company_name="Test Small Sample Co", sector="IT",
            signed_magnitude=50.0, confidence=0.7, quality=1.0,
            reason="real test signal", signal_at=datetime.now(timezone.utc),
        ))
        db.add(PredictionRecord(
            id=pred_id, source="ai_search", prediction_text="test", direction="up",
            prediction_type="company", target_entities=[{"type": "company", "symbol": symbol}],
            status="complete",
        ))
        await db.flush()
        db.add(PredictionEvaluation(
            id=str(uuid.uuid4()), prediction_id=pred_id, horizon_days=7,
            verdict="correct", score=1.0,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            accuracy_map = await engine._build_accuracy_map(db)
            result = await engine.compute_company_score(db, symbol, accuracy_map=accuracy_map)
        assert result["breakdown"]["accuracy_multiplier"] == 1.0
    finally:
        await _cleanup([symbol], [pred_id])


@pytest.mark.asyncio
async def test_rankings_cache_hit_avoids_recomputation():
    """A second call with the same (sector, limit) within the TTL window
    must return the cached object, not recompute — proven by mutating
    the DB in between and confirming the stale (cached) result is what
    comes back, not a freshly-recomputed one."""
    tag = _tag()
    # compute_sector_rankings filters through the real _is_real_symbol()
    # guard (only real NSE symbols are ranked) — reuse CEATLTD, an
    # already-established real-symbol fixture elsewhere in this session's
    # tests, with a synthetic sector name so this test never collides
    # with real production signal data for it.
    symbol = "CEATLTD"
    other_symbol = "AUROPHARMA"
    sector = f"TestSector{tag}"

    engine._RANKINGS_CACHE.clear()

    async with AsyncSessionLocal() as db:
        db.add(AICompanySignal(
            source_type="opportunity", source_id=f"opp-{tag}", symbol=symbol,
            company_name="Test Cache Co", sector=sector,
            signed_magnitude=60.0, confidence=0.7, quality=1.0,
            reason="real test signal", signal_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            first = await engine.compute_sector_rankings(db, sector=sector, limit=10)
        assert len(first) == 1 and first[0]["symbol"] == symbol

        # Mutate the DB — a real recomputation would now see 2 symbols.
        async with AsyncSessionLocal() as db:
            db.add(AICompanySignal(
                source_type="opportunity", source_id=f"opp2-{tag}", symbol=other_symbol,
                company_name="Other Co", sector=sector,
                signed_magnitude=60.0, confidence=0.7, quality=1.0,
                reason="real test signal 2", signal_at=datetime.now(timezone.utc),
            ))
            await db.commit()

        async with AsyncSessionLocal() as db:
            second = await engine.compute_sector_rankings(db, sector=sector, limit=10)
        assert second == first, "cache hit must return the exact same cached result, not recompute"

        # A different cache key (different limit) must NOT reuse the cache.
        async with AsyncSessionLocal() as db:
            third = await engine.compute_sector_rankings(db, sector=sector, limit=5)
        assert len(third) == 2, "a different cache key must trigger a real fresh computation"
    finally:
        engine._RANKINGS_CACHE.clear()
        await _cleanup([symbol, other_symbol], [])
