"""
Phase 6A — Development Memory identity/matching lifecycle
(app/services/development_memory/identity.py).

Gives app/services/evidence_clustering's EvidenceCluster a persistent
identity for the first time: the same real-world happening, evidenced
again on a later run/day, should attach to the SAME Development instead
of spawning a duplicate. These are live tests against the real dev DB
(AsyncSessionLocal), matching this codebase's established convention for
proving DB-backed behavior actually works, not just that a mock was
called correctly — every test cleans up the rows it creates.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models.development import Development, DevelopmentEvidence
from app.db.session import AsyncSessionLocal
from app.services.development_memory.identity import (
    compute_evidence_key,
    resolve_development,
    sweep_close_stale,
)
from app.services.evidence_clustering.evidence import DETERMINISTIC, HEURISTIC, EvidenceItem


async def _cleanup(db, development_ids: list[str]) -> None:
    if not development_ids:
        return
    await db.execute(delete(DevelopmentEvidence).where(DevelopmentEvidence.development_id.in_(development_ids)))
    await db.execute(delete(Development).where(Development.id.in_(development_ids)))
    await db.commit()


def _item(source_type: str, source_id: str, title: str, *, observed_at: datetime,
          companies: list[str] | None = None, category: str | None = None,
          direction: str | None = None, confidence: float | None = None) -> EvidenceItem:
    return EvidenceItem(
        source_type=source_type, source_id=source_id, observed_at=observed_at, title=title,
        companies=companies or [], category=category, direction=direction, confidence=confidence,
        score_kind=DETERMINISTIC,
    )


def test_compute_evidence_key_verbatim_for_non_signal_sources():
    item = _item("event", "evt-123", "Some title", observed_at=datetime.now(timezone.utc))
    assert compute_evidence_key(item) == "evt-123"


def test_compute_evidence_key_disambiguates_company_signal_by_company():
    now = datetime.now(timezone.utc)
    a = _item("company_signal", "article:art-1", "Signal", observed_at=now, companies=["HDFCBANK"])
    b = _item("company_signal", "article:art-1", "Signal", observed_at=now, companies=["ICICIBANK"])
    assert compute_evidence_key(a) != compute_evidence_key(b)
    assert compute_evidence_key(a) == "article:art-1:HDFCBANK"


@pytest.mark.asyncio
async def test_first_evidence_item_creates_a_new_development():
    now = datetime.now(timezone.utc)
    item = _item("event", f"evt-{uuid.uuid4()}", "HDFC Bank announces Q1 results", observed_at=now,
                 companies=["HDFCBANK"], category="results", direction="positive", confidence=0.8)
    ids: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            result = await resolve_development(db, item)
            await db.commit()
            ids.append(result.development.id)

            assert result.tier == "seed"
            assert result.created is True
            assert result.development.canonical_title == item.title
            assert result.development.formation_direction == "positive"
            assert result.development.formation_confidence == 0.8
            assert result.development.evidence_count == 1
            assert result.development.status == "open"
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_reprocessing_the_same_evidence_item_is_idempotent():
    """The sync job's overlapping windows must not create duplicate
    DevelopmentEvidence rows when the same evidence is seen twice."""
    now = datetime.now(timezone.utc)
    item = _item("event", f"evt-{uuid.uuid4()}", "RBI cuts repo rate by 25bps", observed_at=now)
    ids: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            first = await resolve_development(db, item)
            await db.commit()
            ids.append(first.development.id)

        async with AsyncSessionLocal() as db:
            second = await resolve_development(db, item)
            await db.commit()

            assert second.tier == "existing"
            assert second.created is False
            assert second.development.id == first.development.id

            count = (await db.execute(
                select(DevelopmentEvidence).where(DevelopmentEvidence.development_id == first.development.id)
            )).scalars().all()
            assert len(count) == 1
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_tier2a_merges_related_evidence_within_24h_same_company():
    now = datetime.now(timezone.utc)
    seed = _item("event", f"evt-{uuid.uuid4()}", "Kotak Mahindra Bank board approves Q1 results",
                 observed_at=now, companies=["KOTAKBANK"], direction="positive")
    followup = _item("news", f"news-{uuid.uuid4()}", "Kotak Mahindra Bank Q1 results approved by board",
                      observed_at=now + timedelta(hours=2), companies=["KOTAKBANK"], direction="positive")
    ids: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            r1 = await resolve_development(db, seed)
            await db.commit()
            ids.append(r1.development.id)

        async with AsyncSessionLocal() as db:
            r2 = await resolve_development(db, followup)
            await db.commit()

            assert r2.tier == "tier2a"
            assert r2.development.id == r1.development.id
            assert r2.development.evidence_count == 2
            assert r2.development.last_observed_at == followup.observed_at
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_company_incompatible_evidence_does_not_merge():
    now = datetime.now(timezone.utc)
    seed = _item("event", f"evt-{uuid.uuid4()}", "Reliance Industries refinery expansion approved",
                 observed_at=now, companies=["RELIANCE"])
    unrelated = _item("event", f"evt-{uuid.uuid4()}", "Reliance Retail expansion approved by board",
                       observed_at=now + timedelta(hours=1), companies=["TCS"])
    ids: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            r1 = await resolve_development(db, seed)
            await db.commit()
            ids.append(r1.development.id)

        async with AsyncSessionLocal() as db:
            r2 = await resolve_development(db, unrelated)
            await db.commit()
            ids.append(r2.development.id)

            assert r2.tier == "seed"
            assert r2.development.id != r1.development.id
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_tier2b_extended_window_requires_same_company_and_category_and_stronger_title():
    """Friday-afternoon filing -> Monday-morning follow-up: >24h apart,
    must still merge under tier2b's stronger bar."""
    friday = datetime.now(timezone.utc)
    monday = friday + timedelta(hours=64)  # >24h, <=72h
    seed = _item("announcement", f"ann-{uuid.uuid4()}",
                 "HDFC Bank quarterly results announcement management commentary margins",
                 observed_at=friday, companies=["HDFCBANK"], category="results")
    followup = _item("news", f"news-{uuid.uuid4()}",
                      "HDFC Bank quarterly results management commentary on margins",
                      observed_at=monday, companies=["HDFCBANK"], category="results")
    ids: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            r1 = await resolve_development(db, seed)
            await db.commit()
            ids.append(r1.development.id)

        async with AsyncSessionLocal() as db:
            r2 = await resolve_development(db, followup)
            await db.commit()

            assert r2.tier == "tier2b"
            assert r2.development.id == r1.development.id
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_tier2b_does_not_merge_weakly_similar_evidence_beyond_24h():
    """Same company, >24h apart, but title overlap only clears tier2a's
    bar (0.5) not tier2b's stronger one (0.65) -- must NOT merge, proving
    tier2b's higher bar is actually enforced, not just documented."""
    friday = datetime.now(timezone.utc)
    monday = friday + timedelta(hours=64)
    seed = _item("event", f"evt-{uuid.uuid4()}",
                 "HDFC Bank announces new branch expansion plan across five states",
                 observed_at=friday, companies=["HDFCBANK"], category="expansion")
    weakly_related = _item("news", f"news-{uuid.uuid4()}",
                            "HDFC Bank stock rallies on strong quarterly outlook",
                            observed_at=monday, companies=["HDFCBANK"], category="expansion")
    ids: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            r1 = await resolve_development(db, seed)
            await db.commit()
            ids.append(r1.development.id)

        async with AsyncSessionLocal() as db:
            r2 = await resolve_development(db, weakly_related)
            await db.commit()
            ids.append(r2.development.id)

            assert r2.tier == "seed"
            assert r2.development.id != r1.development.id
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_canonical_drift_guard_stops_a_chain_from_wandering():
    """A ~ B ~ C ~ D where each hop is locally similar to its predecessor
    but D has drifted from A's actual story must NOT all land in one
    Development -- the canonical-title check (against the frozen seed
    title, not just the most recent evidence) is what catches this."""
    now = datetime.now(timezone.utc)
    a = _item("event", f"evt-{uuid.uuid4()}", "Tata Motors launches new electric SUV model",
              observed_at=now, companies=["TATAMOTORS"])
    # Deliberately share zero significant tokens with `a`'s title so the
    # canonical check fails even though it's within the same company/window.
    d = _item("news", f"news-{uuid.uuid4()}", "Tata Motors CFO resigns amid boardroom reshuffle",
              observed_at=now + timedelta(hours=3), companies=["TATAMOTORS"])
    ids: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            r1 = await resolve_development(db, a)
            await db.commit()
            ids.append(r1.development.id)

        async with AsyncSessionLocal() as db:
            r2 = await resolve_development(db, d)
            await db.commit()
            ids.append(r2.development.id)

            assert r2.tier == "seed"
            assert r2.development.id != r1.development.id
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)


@pytest.mark.asyncio
async def test_closed_development_is_never_reopened():
    now = datetime.now(timezone.utc)
    seed = _item("event", f"evt-{uuid.uuid4()}", "Infosys wins large multi-year IT services contract",
                 observed_at=now - timedelta(hours=100), companies=["INFY"])
    followup = _item("news", f"news-{uuid.uuid4()}", "Infosys wins large multi-year IT services deal",
                      observed_at=now, companies=["INFY"])
    ids: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            r1 = await resolve_development(db, seed)
            await db.commit()
            ids.append(r1.development.id)

            closed_count = await sweep_close_stale(db)
            await db.commit()
            assert closed_count >= 1

            refreshed = await db.get(Development, r1.development.id)
            assert refreshed.status == "closed"

        async with AsyncSessionLocal() as db:
            r2 = await resolve_development(db, followup)
            await db.commit()
            ids.append(r2.development.id)

            assert r2.tier == "seed"
            assert r2.development.id != r1.development.id
            assert r2.development.status == "open"
    finally:
        async with AsyncSessionLocal() as db:
            await _cleanup(db, ids)
