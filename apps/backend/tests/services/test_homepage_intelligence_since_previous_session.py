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
async def test_get_yesterday_changes_gathered_calls_use_isolated_sessions(monkeypatch):
    """2026-08-31 concurrency fix -- the exact real production bug: the old
    code passed the SAME request-scoped `db` into every concurrently
    gathered _explain_change() call, and AsyncSession isn't safe for
    concurrent use across coroutines (is_graph_worthy()'s per-read commit
    discipline in graph_link.py raced, producing a real, recurring
    sqlalchemy.exc.IllegalStateChangeError in production). This asserts
    the actual fix mechanism deterministically -- each gathered call must
    receive its OWN session object, never the request's own `db` -- rather
    than depending on timing luck to reproduce the race itself."""
    monkeypatch.setattr(hi_module, "_today", lambda: _FAKE_TODAY)
    snapshot = HomepageDailySnapshot(
        id=str(uuid.uuid4()), snapshot_date=_FAKE_YESTERDAY, article_id="test-article-iso",
        sectors=[
            {"name": "Banking", "impact": "neutral", "magnitude": "low", "score": 0},
            {"name": "Auto", "impact": "neutral", "magnitude": "low", "score": 0},
        ],
    )
    article = SimpleNamespace(
        id="test-article-iso-2",
        sectors_affected=[
            {"name": "Banking", "impact": "positive", "magnitude": "high"},
            {"name": "Auto", "impact": "positive", "magnitude": "high"},
        ],
    )
    snap_ids = [snapshot.id]

    seen_session_ids: list[int] = []
    real_explain_change = hi_module._explain_change

    async def _spy_explain_change(db, sector_name, direction, max_reasons=3):
        seen_session_ids.append(id(db))
        return await real_explain_change(db, sector_name, direction, max_reasons)

    monkeypatch.setattr(hi_module, "_explain_change", _spy_explain_change)

    try:
        async with AsyncSessionLocal() as db:
            db.add(snapshot)
            await db.commit()
            request_session_id = id(db)
            await get_yesterday_changes(db, article)
        assert len(seen_session_ids) == 2
        # Neither gathered call reused the request's own session...
        assert request_session_id not in seen_session_ids
        # ...and the two concurrent calls didn't share a session with each other.
        assert len(set(seen_session_ids)) == 2
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup_snapshots(db, snap_ids)


@pytest.mark.asyncio
async def test_get_yesterday_changes_survives_concurrent_graph_worthy_commits(monkeypatch):
    """End-to-end regression for the real trigger condition: 2 sectors
    whose developments have evidence_count<2 and no High/Critical impact
    tier, forcing is_graph_worthy() down its SELECT+commit path
    (graph_link.py:67-81) for both, concurrently. Before the fix, this
    shape reliably raced on the shared session; this just needs to
    complete without raising."""
    monkeypatch.setattr(hi_module, "_today", lambda: _FAKE_TODAY)
    snapshot = HomepageDailySnapshot(
        id=str(uuid.uuid4()), snapshot_date=_FAKE_YESTERDAY, article_id="test-article-race",
        sectors=[
            {"name": "Banking", "impact": "neutral", "magnitude": "low", "score": 0},
            {"name": "Auto", "impact": "neutral", "magnitude": "low", "score": 0},
        ],
    )
    dev_banking = _make_dev(
        "Low-key banking development", sectors=["Banking"], direction="positive",
        evidence_count=1, impact_tier="Low",
    )
    dev_auto = _make_dev(
        "Low-key auto development", sectors=["Auto"], direction="positive",
        evidence_count=1, impact_tier="Low",
    )
    article = SimpleNamespace(
        id="test-article-race-2",
        sectors_affected=[
            {"name": "Banking", "impact": "positive", "magnitude": "high"},
            {"name": "Auto", "impact": "positive", "magnitude": "high"},
        ],
    )
    snap_ids = [snapshot.id]
    dev_ids = [dev_banking.id, dev_auto.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([snapshot, dev_banking, dev_auto])
            await db.commit()
            changes = await get_yesterday_changes(db, article)  # must not raise IllegalStateChangeError
        assert {c["name"] for c in changes} == {"Banking", "Auto"}
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
