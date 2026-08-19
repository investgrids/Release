"""
"Since Previous Session -> why" (2026-08 homepage redesign) —
homepage_intelligence.py::_explain_change / get_yesterday_changes.

Real evidence per sector-delta from Development Memory, never an LLM
call, never invented — a development only counts as an explanation when
its own direction agrees with the delta's direction (a sector
"improving" is explained by positive-leaning developments, not any
development merely tagged to that sector). Live tests against the real
dev DB, following this codebase's established convention.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete

from app.db.models.development import Development, DevelopmentEvidence
from app.db.models.homepage_snapshot import HomepageDailySnapshot
from app.db.session import AsyncSessionLocal
import app.services.homepage_intelligence as hi_module
from app.services.homepage_intelligence import _explain_change, get_yesterday_changes

# get_yesterday_changes' own _today() reads the REAL current UTC date, and
# the real dev DB already has a genuine snapshot row for real "yesterday"
# (the homepage has actually been hit) — inserting another row for that
# same date would collide with homepage_daily_snapshots' UNIQUE(snapshot_date)
# constraint. Using fake, far-future-relative dates (monkeypatched _today())
# sidesteps that collision entirely rather than depending on real data state.
_FAKE_TODAY = "2099-01-02"
_FAKE_YESTERDAY = "2099-01-01"


async def _cleanup_devs(db, ids: list[str]) -> None:
    if ids:
        await db.execute(delete(DevelopmentEvidence).where(DevelopmentEvidence.development_id.in_(ids)))
        await db.execute(delete(Development).where(Development.id.in_(ids)))
        await db.commit()


async def _cleanup_snapshots(db, ids: list[str]) -> None:
    if ids:
        await db.execute(delete(HomepageDailySnapshot).where(HomepageDailySnapshot.id.in_(ids)))
        await db.commit()


def _make_dev(title: str, *, sectors: list[str], direction: str, evidence_count: int = 2, impact_tier: str | None = "High") -> Development:
    now = datetime.now(timezone.utc)
    return Development(
        id=str(uuid.uuid4()), canonical_title=title, status="open",
        primary_company=None, companies=[], sectors=sectors, themes=[],
        first_observed_at=now, last_observed_at=now,
        current_direction=direction, current_impact_tier=impact_tier,
        evidence_count=evidence_count, schema_version="test",
    )


@pytest.mark.asyncio
async def test_explain_change_returns_real_matching_reasons():
    positive = _make_dev("RBI liquidity action eases funding costs", sectors=["Banking"], direction="positive")
    negative = _make_dev("NBFC downgrade fears resurface", sectors=["Banking"], direction="negative")
    ids = [positive.id, negative.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([positive, negative])
            await db.commit()
            reasons = await _explain_change(db, "Banking", "up")
        assert "RBI liquidity action eases funding costs" in reasons
        assert "NBFC downgrade fears resurface" not in reasons
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup_devs(db, ids)


@pytest.mark.asyncio
async def test_explain_change_empty_when_nothing_matches_direction():
    negative = _make_dev("Only a negative development exists here", sectors=["Chemicals"], direction="negative")
    ids = [negative.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(negative)
            await db.commit()
            reasons = await _explain_change(db, "Chemicals", "up")
        assert reasons == []
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup_devs(db, ids)


@pytest.mark.asyncio
async def test_explain_change_empty_when_no_sector_match():
    async with AsyncSessionLocal() as db:
        result = await _explain_change(db, "NoSuchSectorAtAll12345", "up")
    assert result == []


@pytest.mark.asyncio
async def test_explain_change_caps_at_max_reasons():
    devs = [_make_dev(f"Positive development {i}", sectors=["Auto"], direction="positive") for i in range(5)]
    ids = [d.id for d in devs]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all(devs)
            await db.commit()
            reasons = await _explain_change(db, "Auto", "up", max_reasons=3)
        assert len(reasons) <= 3
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup_devs(db, ids)


@pytest.mark.asyncio
async def test_get_yesterday_changes_enriches_with_real_reasons(monkeypatch):
    monkeypatch.setattr(hi_module, "_today", lambda: _FAKE_TODAY)
    snapshot = HomepageDailySnapshot(
        id=str(uuid.uuid4()), snapshot_date=_FAKE_YESTERDAY, article_id="test-article",
        sectors=[{"name": "Banking", "impact": "neutral", "magnitude": "low", "score": 0}],
    )
    dev = _make_dev("RBI liquidity action explains today's move", sectors=["Banking"], direction="positive")
    article = SimpleNamespace(
        id="test-article-2",
        sectors_affected=[{"name": "Banking", "impact": "positive", "magnitude": "high"}],
    )
    snap_ids = [snapshot.id]
    dev_ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([snapshot, dev])
            await db.commit()
            changes = await get_yesterday_changes(db, article)
        banking = next((c for c in changes if c["name"] == "Banking"), None)
        assert banking is not None
        assert banking["direction"] == "up"
        assert "reasons" in banking
        assert "RBI liquidity action explains today's move" in banking["reasons"]
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup_snapshots(db, snap_ids)
            await _cleanup_devs(db, dev_ids)


@pytest.mark.asyncio
async def test_get_yesterday_changes_honest_empty_reasons_when_no_evidence(monkeypatch):
    monkeypatch.setattr(hi_module, "_today", lambda: _FAKE_TODAY)
    snapshot = HomepageDailySnapshot(
        id=str(uuid.uuid4()), snapshot_date=_FAKE_YESTERDAY, article_id="test-article-3",
        sectors=[{"name": "ZZZUnusualSectorForTest", "impact": "neutral", "magnitude": "low", "score": 0}],
    )
    article = SimpleNamespace(
        id="test-article-4",
        sectors_affected=[{"name": "ZZZUnusualSectorForTest", "impact": "positive", "magnitude": "high"}],
    )
    snap_ids = [snapshot.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(snapshot)
            await db.commit()
            changes = await get_yesterday_changes(db, article)
        row = next((c for c in changes if c["name"] == "ZZZUnusualSectorForTest"), None)
        assert row is not None
        assert row["reasons"] == []
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup_snapshots(db, snap_ids)
