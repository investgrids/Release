"""
Phase 6E.1 — Development Evidence Reconciliation
(app/services/development_memory/reconciliation.py).

Live tests against the real dev DB. Reuses _conflict_bucket() unmodified
-- these tests prove Development's real evidence rows feed it correctly,
not that the bucket function itself is correct (that's already covered
elsewhere for its existing callers).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.development import Development, DevelopmentEvidence
from app.db.session import AsyncSessionLocal
from app.services.development_memory.reconciliation import reconcile_development


async def _cleanup(db, development_ids: list[str]) -> None:
    await db.execute(delete(DevelopmentEvidence).where(DevelopmentEvidence.development_id.in_(development_ids)))
    await db.execute(delete(Development).where(Development.id.in_(development_ids)))
    await db.commit()


def _make_dev(current_direction: str | None) -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()), canonical_title="Test dev for 6E.1", status="open",
        companies=[], sectors=[], themes=[],
        first_observed_at=now, last_observed_at=now,
        current_direction=current_direction, evidence_count=0, schema_version="test",
    )


def _make_evidence(dev_id: str, direction: str | None, title: str, hours_ago: float) -> DevelopmentEvidence:
    observed_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return DevelopmentEvidence(
        id=str(uuid.uuid4()), development_id=dev_id, source_type="news",
        source_id=str(uuid.uuid4()), evidence_key=str(uuid.uuid4()),
        observed_at=observed_at, title=title, direction=direction, match_tier="seed",
    )


@pytest.mark.asyncio
async def test_all_positive_evidence_reconciles_cleanly():
    dev = _make_dev("positive")
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            db.add(_make_evidence(dev.id, "positive", "loan growth", hours_ago=1))
            db.add(_make_evidence(dev.id, "positive", "RBI liquidity support", hours_ago=2))
            await db.commit()

            result = await reconcile_development(db, dev)
            assert result.conflict_bucket == "all_positive"
            assert result.positive_count == 2
            assert result.negative_count == 0
            assert len(result.supporting_evidence) == 2
            assert result.conflicting_evidence == []
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_balanced_conflict_has_no_supporting_or_conflicting_side():
    """Matches the user's own worked example: 4 positive, 3 negative is
    NOT balanced (mostly_positive), but equal counts genuinely are -- and
    with no majority, there is no 'side' to label supporting/conflicting."""
    dev = _make_dev("mixed")
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            db.add(_make_evidence(dev.id, "positive", "loan growth", hours_ago=1))
            db.add(_make_evidence(dev.id, "negative", "margin pressure", hours_ago=2))
            await db.commit()

            result = await reconcile_development(db, dev)
            assert result.conflict_bucket == "balanced_conflict"
            assert len(result.positive_evidence) == 1
            assert len(result.negative_evidence) == 1
            assert result.supporting_evidence is None
            assert result.conflicting_evidence is None
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_mostly_positive_with_real_conflicting_minority():
    """The HDFC example shape: majority positive, real conflicting
    evidence still surfaced by name, not dropped."""
    dev = _make_dev("positive")
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            db.add(_make_evidence(dev.id, "positive", "loan growth update", hours_ago=1))
            db.add(_make_evidence(dev.id, "positive", "RBI liquidity support", hours_ago=2))
            db.add(_make_evidence(dev.id, "positive", "branch expansion", hours_ago=3))
            db.add(_make_evidence(dev.id, "negative", "margin compression", hours_ago=4))
            await db.commit()

            result = await reconcile_development(db, dev)
            assert result.conflict_bucket == "mostly_positive"
            assert result.positive_count == 3
            assert result.negative_count == 1
            assert [e.title for e in result.conflicting_evidence] == ["margin compression"]
            assert result.conflicting_evidence[0].observed_at is not None
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_no_directional_evidence_is_no_signal():
    dev = _make_dev("neutral")
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            db.add(_make_evidence(dev.id, "neutral", "routine filing", hours_ago=1))
            db.add(_make_evidence(dev.id, None, "record date notice", hours_ago=2))
            await db.commit()

            result = await reconcile_development(db, dev)
            assert result.conflict_bucket == "no_signal"
            assert result.neutral_count == 2
            assert result.supporting_evidence is None
            assert result.conflicting_evidence is None
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_observed_at_is_preserved_on_every_item():
    """Explicit ask: 6E.2 needs raw temporal data even though this phase
    doesn't use it for any horizon heuristic."""
    dev = _make_dev("negative")
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            db.add(_make_evidence(dev.id, "negative", "valuation concern", hours_ago=5))
            await db.commit()

            result = await reconcile_development(db, dev)
            assert result.positive_evidence == []  # no positive evidence at all this time
            assert len(result.negative_evidence) == 1
            item = result.negative_evidence[0]
            assert item.observed_at is not None
            assert item.title == "valuation concern"
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)
