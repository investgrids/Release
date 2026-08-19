"""
Development Memory generic read-path (2026-08 Pre-Market rebuild, Part
A2) — app/services/development_memory/read.py::list_active_developments.

Live tests against the real dev DB, following this codebase's established
convention (see test_development_graph_link.py) for proving DB-backed
behavior actually works. Every test cleans up the rows it creates.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.development import Development, DevelopmentEvidence
from app.db.session import AsyncSessionLocal
from app.services.development_memory.read import list_active_developments


async def _cleanup(db, ids: list[str]) -> None:
    if ids:
        await db.execute(delete(DevelopmentEvidence).where(DevelopmentEvidence.development_id.in_(ids)))
        await db.execute(delete(Development).where(Development.id.in_(ids)))
        await db.commit()


def _make_dev(
    title: str, *, status: str = "open", evidence_count: int = 2,
    impact_tier: str | None = None, confidence: float | None = None,
    sectors: list[str] | None = None, companies: list[str] | None = None,
    observed_minutes_ago: int = 10,
) -> Development:
    now = datetime.now(timezone.utc)
    observed = now - timedelta(minutes=observed_minutes_ago)
    return Development(
        id=str(uuid.uuid4()),
        canonical_title=title,
        status=status,
        primary_company=(companies or [None])[0],
        companies=companies or [],
        sectors=sectors or [],
        themes=[],
        first_observed_at=observed,
        last_observed_at=observed,
        current_direction="negative",
        current_impact_tier=impact_tier,
        current_confidence=confidence,
        evidence_count=evidence_count,
        schema_version="test",
    )


@pytest.mark.asyncio
async def test_importance_ranking_beats_plain_recency():
    """A newer but low-tier development must not outrank an older,
    higher-impact-tier one -- the exact scenario the plan's refinement
    called out (a low-importance filing shouldn't beat a major RBI/policy
    development just for being newer)."""
    major = _make_dev("Major RBI policy action", impact_tier="Critical",
                       confidence=0.9, observed_minutes_ago=120)
    minor = _make_dev("Routine compliance filing", impact_tier="Low",
                       confidence=0.3, observed_minutes_ago=5)
    ids = [major.id, minor.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([major, minor])
            await db.commit()
            # Generous limit: the dev DB has hundreds of real open
            # Developments (many genuinely low-tier), so a tight limit
            # could crowd our synthetic "minor" row out of the result
            # entirely -- this test checks RELATIVE order, which needs
            # both rows present, not top-ranked.
            rows = await list_active_developments(db, limit=2000)
        titles = [r["title"] for r in rows]
        assert titles.index("Major RBI policy action") < titles.index("Routine compliance filing")
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_recency_is_tiebreaker_within_same_tier():
    older = _make_dev("Older same-tier development", impact_tier="High",
                       confidence=0.7, observed_minutes_ago=200)
    newer = _make_dev("Newer same-tier development", impact_tier="High",
                       confidence=0.7, observed_minutes_ago=5)
    ids = [older.id, newer.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([older, newer])
            await db.commit()
            rows = await list_active_developments(db, limit=2000)
        titles = [r["title"] for r in rows]
        assert titles.index("Newer same-tier development") < titles.index("Older same-tier development")
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_order_recency_param_ignores_tier():
    high_tier_old = _make_dev("High tier but old", impact_tier="Critical",
                               observed_minutes_ago=500)
    low_tier_new = _make_dev("Low tier but new", impact_tier="Low",
                              observed_minutes_ago=1)
    ids = [high_tier_old.id, low_tier_new.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([high_tier_old, low_tier_new])
            await db.commit()
            rows = await list_active_developments(db, limit=2000, order="recency")
        titles = [r["title"] for r in rows]
        assert titles.index("Low tier but new") < titles.index("High tier but old")
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_excludes_closed_developments():
    closed = _make_dev("Closed development", status="closed", impact_tier="Critical")
    ids = [closed.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(closed)
            await db.commit()
            rows = await list_active_developments(db, limit=10)
        assert closed.id not in {r["id"] for r in rows}
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_excludes_non_graph_worthy_low_value_development():
    """evidence_count=1, no high impact tier -- fails is_graph_worthy's
    corroboration-or-materiality bar (no linked EventTriage row either),
    so it must not appear as a prominent "development that matters"."""
    weak = _make_dev("Weak single-source item", evidence_count=1, impact_tier=None)
    ids = [weak.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(weak)
            await db.commit()
            rows = await list_active_developments(db, limit=10)
        assert weak.id not in {r["id"] for r in rows}
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_sector_filter_matches_case_insensitively():
    banking = _make_dev("Banking development", sectors=["Banking"], impact_tier="High")
    it = _make_dev("IT development", sectors=["IT"], impact_tier="High")
    ids = [banking.id, it.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all([banking, it])
            await db.commit()
            rows = await list_active_developments(db, sectors=["banking"], limit=2000)
        result_ids = {r["id"] for r in rows}
        assert banking.id in result_ids
        assert it.id not in result_ids
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_limit_respected():
    devs = [_make_dev(f"Development {i}", impact_tier="High") for i in range(5)]
    ids = [d.id for d in devs]
    try:
        async with AsyncSessionLocal() as db:
            db.add_all(devs)
            await db.commit()
            rows = await list_active_developments(db, limit=2)
        assert len(rows) <= 2
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_row_shape_has_expected_fields():
    dev = _make_dev("Shape check development", impact_tier="High", confidence=0.65,
                     sectors=["Banking"], companies=["HDFCBANK"])
    ids = [dev.id]
    try:
        async with AsyncSessionLocal() as db:
            db.add(dev)
            await db.commit()
            rows = await list_active_developments(db, limit=2000)
        row = next(r for r in rows if r["id"] == dev.id)
        assert row["title"] == "Shape check development"
        assert row["sectors"] == ["Banking"]
        assert row["companies"] == ["HDFCBANK"]
        assert row["direction"] == "negative"
        assert row["confidence"] == 0.65
        assert row["impact_tier"] == "High"
        assert row["evidence_count"] == 2
        assert row["last_observed_at"] is not None
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)
