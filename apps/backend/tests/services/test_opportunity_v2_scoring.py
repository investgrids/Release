"""
opportunity_v2/scoring.py — bounded/capped components (pure, no DB) plus
real DB-backed end-to-end tests exercising the direction-agreement-gated
company confirmation and contradiction penalty (owner correction,
2026-08-22: a real company score must only count as confirmation when its
own direction agrees with the thesis — disagreement is a real
contradiction, never silently averaged away).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.company_signal import AICompanySignal
from app.db.models.development import Development
from app.db.session import AsyncSessionLocal
from app.services.opportunity_v2.scoring import (
    _MAX_COMPANY_CONFIRMATION,
    _MAX_DEVELOPMENT_COUNT,
    _MAX_EVIDENCE_QUALITY,
    _MAX_FRESHNESS,
    _development_count_bonus,
    _evidence_quality,
    _freshness,
    score_cluster,
)


def _dev(*, confidence: float = 0.9, tier: str = "Critical", days_ago: float = 0.0) -> Development:
    now = datetime.now(timezone.utc)
    observed = now - timedelta(days=days_ago)
    return Development(
        id=str(uuid.uuid4()), canonical_title="Test", status="open",
        primary_company=None, companies=[], sectors=[], themes=[],
        first_observed_at=observed, last_observed_at=observed,
        current_confidence=confidence, current_impact_tier=tier,
        evidence_count=1, schema_version="test",
    )


# ── Pure component boundedness ──────────────────────────────────────────

def test_evidence_quality_never_exceeds_its_cap_even_at_max_real_inputs():
    devs = [_dev(confidence=1.0, tier="Critical") for _ in range(20)]
    assert _evidence_quality(devs) <= _MAX_EVIDENCE_QUALITY


def test_development_count_bonus_saturates_not_unbounded():
    few = _development_count_bonus([_dev() for _ in range(2)])
    many = _development_count_bonus([_dev() for _ in range(50)])
    assert many == _MAX_DEVELOPMENT_COUNT
    assert few < many


def test_ten_mediocre_developments_do_not_outscore_two_strong_ones():
    """The literal owner correction: raw summing would let 10 mediocre
    developments overpower 2 extremely strong ones just by count."""
    mediocre = [_dev(confidence=0.3, tier="Low") for _ in range(10)]
    strong = [_dev(confidence=1.0, tier="Critical") for _ in range(2)]
    assert _evidence_quality(mediocre) < _evidence_quality(strong)


def test_freshness_decays_with_age_and_stays_bounded():
    now = datetime.now(timezone.utc)
    fresh = _freshness([_dev(days_ago=0)], now)
    old = _freshness([_dev(days_ago=30)], now)
    assert fresh <= _MAX_FRESHNESS
    assert old < fresh


# ── End-to-end, real DB (honest degradation + agreement gating) ─────────

@pytest.mark.asyncio
async def test_unknown_company_contributes_no_confirmation_and_no_fabricated_score():
    dev = _dev()
    async with AsyncSessionLocal() as db:
        breakdown = await score_cluster(
            db, [dev], thesis_direction="positive",
            companies=[f"NOSUCHCO{uuid.uuid4().hex[:6].upper()}"], sectors=[],
            now=datetime.now(timezone.utc),
        )
    assert breakdown.company_confirmation == 0.0
    assert breakdown.contradiction_penalty == 0.0
    assert 0.0 <= breakdown.total <= 100.0


@pytest.mark.asyncio
async def test_real_company_signal_agreeing_with_thesis_adds_confirmation():
    symbol = f"TAGREE{uuid.uuid4().hex[:5].upper()}"
    signal = AICompanySignal(
        source_type="article", source_id="test", symbol=symbol, company_name="Test Co",
        sector="Banking", signed_magnitude=30.0, confidence=0.95, quality=0.95,
        signal_at=datetime.now(timezone.utc),
    )
    try:
        async with AsyncSessionLocal() as db:
            db.add(signal)
            await db.commit()
            breakdown = await score_cluster(
                db, [_dev()], thesis_direction="positive", companies=[symbol], sectors=[],
                now=datetime.now(timezone.utc),
            )
        assert breakdown.company_confirmation > 0.0
        assert breakdown.contradiction_penalty == 0.0
        assert breakdown.contradictions == []
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(AICompanySignal).where(AICompanySignal.symbol == symbol))
            await db.commit()


@pytest.mark.asyncio
async def test_real_company_signal_disagreeing_with_thesis_becomes_a_contradiction_not_a_bonus():
    symbol = f"TDISAG{uuid.uuid4().hex[:5].upper()}"
    signal = AICompanySignal(
        source_type="article", source_id="test", symbol=symbol, company_name="Test Co",
        sector="Banking", signed_magnitude=-30.0, confidence=0.95, quality=0.95,
        signal_at=datetime.now(timezone.utc),
    )
    try:
        async with AsyncSessionLocal() as db:
            db.add(signal)
            await db.commit()
            # thesis says positive, real company signal is strongly negative
            breakdown = await score_cluster(
                db, [_dev()], thesis_direction="positive", companies=[symbol], sectors=[],
                now=datetime.now(timezone.utc),
            )
        assert breakdown.company_confirmation == 0.0
        assert breakdown.contradiction_penalty > 0.0
        assert len(breakdown.contradictions) == 1
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(AICompanySignal).where(AICompanySignal.symbol == symbol))
            await db.commit()


@pytest.mark.asyncio
async def test_total_is_always_bounded_0_to_100():
    devs = [_dev(confidence=1.0, tier="Critical") for _ in range(30)]
    async with AsyncSessionLocal() as db:
        breakdown = await score_cluster(
            db, devs, thesis_direction="positive", companies=[], sectors=[],
            now=datetime.now(timezone.utc),
        )
    assert 0.0 <= breakdown.total <= 100.0
