"""
S5-A — real DB-backed tests for the snapshot read/derivation path. The
full compute_and_persist_snapshot() itself is network-dependent (it calls
the real, frozen compute_marketripple_score()) — verified via a real
manual backfill run instead (artifacts/marketripple_score_s5_snapshot_backfill.md),
matching this whole initiative's established pattern of proving live-network
paths with a real run rather than a slow/flaky live pytest. These tests
cover the two pieces that are pure DB logic: which fiscal period counts as
"financial_data_as_of" (must respect the same S4.5/S4.5-B exclusions
scoring itself uses) and which snapshot counts as "latest" for a symbol.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.financial_fact import FinancialFact
from app.db.models.marketripple_score_snapshot import MarketRippleScoreSnapshot
from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.snapshot import _real_financial_data_as_of, get_latest_snapshot


def _tag():
    return uuid.uuid4().hex[:8]


def _fact_row(symbol, metric_code, value, quality_status, fy, fq, doc_id):
    return FinancialFact(
        symbol=symbol, metric_code=metric_code, metric_name=metric_code, value=value, unit="pct",
        fiscal_year=fy, fiscal_quarter=fq, period_type="Quarterly", consolidation_scope="Non-Consolidated",
        source_provider="NSE", source_document_id=doc_id, source_document_url=f"https://example/{doc_id}",
        extraction_status="POPULATED", quality_status=quality_status, quality_reason=None,
        observed_at=datetime.now(timezone.utc),
    )


async def _cleanup_facts(symbol: str):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FinancialFact).where(FinancialFact.symbol == symbol))
        await db.commit()


async def _cleanup_snapshots(symbol: str):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketRippleScoreSnapshot).where(MarketRippleScoreSnapshot.symbol == symbol))
        await db.commit()


@pytest.mark.asyncio
async def test_financial_data_as_of_picks_newest_eligible_period():
    symbol = f"TESTSNAP{_tag()}"[:20].upper()
    async with AsyncSessionLocal() as db:
        db.add_all([
            _fact_row(symbol, "gross_npa_pct", 0.02, "OK", 2024, 4, "doc-a"),
            _fact_row(symbol, "cet1_ratio", 0.15, "OK", 2025, 2, "doc-b"),
            # Newest real period, but ALL its facts are quarantined -- must
            # be skipped, the same way scoring itself would skip it.
            _fact_row(symbol, "roa", 0.02, "SOURCE_DOCUMENT_QUARANTINED", 2025, 3, "doc-c"),
        ])
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await _real_financial_data_as_of(db, symbol)
        assert result == "FY2025Q2"  # newest ELIGIBLE period, not the newest period overall
    finally:
        await _cleanup_facts(symbol)


@pytest.mark.asyncio
async def test_financial_data_as_of_none_when_nothing_eligible():
    symbol = f"TESTSNAP{_tag()}"[:20].upper()
    async with AsyncSessionLocal() as db:
        db.add(_fact_row(symbol, "roa", 0.0001, "IMPLAUSIBLE_SCALE", 2025, 3, "doc-x"))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await _real_financial_data_as_of(db, symbol)
        assert result is None
    finally:
        await _cleanup_facts(symbol)


@pytest.mark.asyncio
async def test_get_latest_snapshot_picks_most_recent_by_calculated_at():
    symbol = f"TESTSNAP{_tag()}"[:20].upper()
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        db.add(MarketRippleScoreSnapshot(
            symbol=symbol, score=50.0, coverage_pct=80.0, methodology_version="MARKETRIPPLE_SCORE_V1",
            peer_universe=[], peer_universe_count=0, calculated_at=now - timedelta(days=1),
            publishable=False,
        ))
        db.add(MarketRippleScoreSnapshot(
            symbol=symbol, score=55.5, coverage_pct=83.3, methodology_version="MARKETRIPPLE_SCORE_V1",
            peer_universe=[], peer_universe_count=0, calculated_at=now,
            publishable=False,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            latest = await get_latest_snapshot(db, symbol)
        assert latest is not None
        assert latest.score == 55.5  # the newer row, not the older one
    finally:
        await _cleanup_snapshots(symbol)


@pytest.mark.asyncio
async def test_get_latest_snapshot_none_when_no_snapshot_exists():
    symbol = f"TESTSNAP{_tag()}"[:20].upper()
    async with AsyncSessionLocal() as db:
        result = await get_latest_snapshot(db, symbol)
    assert result is None


@pytest.mark.asyncio
async def test_get_latest_snapshot_never_selects_a_superseded_methodology_even_with_a_newer_timestamp():
    """The real coordination guarantee owner instruction 2026-09-27 asked
    for: "select only snapshots from the current methodology... old and
    new calculations cannot be mistaken for each other." A stale-tagged
    row (e.g. the real, retired NONBANK_INDUSTRIAL_V2, superseded the same
    day by the "one score calculation" unification's MARKETRIPPLE_SCORE_V1)
    must never be selected as "latest," even in the adversarial case where
    it happens to carry a NEWER calculated_at than the real
    current-methodology row -- exactly the scenario a delayed batch or
    clock skew could produce. "Latest by timestamp" alone was not a safe
    proxy for "current methodology" before this fix."""
    symbol = f"TESTSNAP{_tag()}"[:20].upper()
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        db.add(MarketRippleScoreSnapshot(
            symbol=symbol, score=60.0, coverage_pct=90.0, methodology_version="MARKETRIPPLE_SCORE_V1",
            peer_universe=[], peer_universe_count=33, calculated_at=now - timedelta(hours=1),
            publishable=False,
        ))
        # Adversarial case: a real, superseded methodology tag with a
        # LATER timestamp than the current-methodology row above.
        db.add(MarketRippleScoreSnapshot(
            symbol=symbol, score=45.0, coverage_pct=70.0, methodology_version="NONBANK_INDUSTRIAL_V2",
            peer_universe=[], peer_universe_count=33, calculated_at=now,
            publishable=False,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            latest = await get_latest_snapshot(db, symbol)
        assert latest is not None
        assert latest.methodology_version == "MARKETRIPPLE_SCORE_V1"
        assert latest.score == 60.0  # the current-methodology row, despite being older
    finally:
        await _cleanup_snapshots(symbol)


@pytest.mark.asyncio
async def test_get_latest_snapshot_returns_none_when_only_superseded_methodology_rows_exist():
    symbol = f"TESTSNAP{_tag()}"[:20].upper()
    async with AsyncSessionLocal() as db:
        db.add(MarketRippleScoreSnapshot(
            symbol=symbol, score=45.0, coverage_pct=70.0, methodology_version="NONBANK_INDUSTRIAL_V1",
            peer_universe=[], peer_universe_count=33, calculated_at=datetime.now(timezone.utc),
            publishable=False,
        ))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            result = await get_latest_snapshot(db, symbol)
        assert result is None
    finally:
        await _cleanup_snapshots(symbol)


# ── Publication rule (owner decision 2026-09-28) ─────────────────────────────
def _headline_result(publishable: bool):
    from app.services.marketripple_score.contracts import MarketRippleScore, PillarScore, PillarStatus

    def p(score):
        return PillarScore(name="t", score=score, coverage_pct=100.0, status=PillarStatus.COMPLETE,
                           metrics_used=["a", "b", "c", "d", "e", "f"], metrics_missing=[], sources=["t"],
                           as_of=datetime.now(timezone.utc))
    return MarketRippleScore(
        symbol="X", score=62.0 if publishable else None, label="Positive" if publishable else None,
        publishable=publishable, publish_reason=None if publishable else "missing pillar",
        pillars={"financial_strength": p(70.0), "valuation": p(55.0), "market_behaviour": p(50.0), "current_intelligence": p(40.0)},
        weights={}, overall_coverage_pct=100.0,
    )


async def _persist_with(monkeypatch, symbol, *, sector, publishable, reasons):
    import app.services.aipe.company_score_engine as cse
    import app.services.company_identity.qualification as qual
    import app.services.marketripple_score.eligibility as elig
    from app.services.marketripple_score import snapshot as snap_mod

    async def _compute(*a, **k): return _headline_result(publishable)
    async def _entity(*a, **k): return None

    class _Verdict:
        def __init__(self, r): self.reasons = r

    monkeypatch.setattr(snap_mod, "compute_marketripple_score", _compute)
    monkeypatch.setattr(qual, "resolve_entity_by_any_symbol", _entity)
    monkeypatch.setattr(cse, "_sector_for", lambda s: sector)
    monkeypatch.setattr(elig, "evaluate_eligibility", lambda **k: _Verdict(reasons))
    async with AsyncSessionLocal() as db:
        return await snap_mod.compute_and_persist_snapshot(db, symbol)


@pytest.mark.asyncio
async def test_eligible_headline_score_is_persisted_publishable(monkeypatch):
    from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS
    symbol = f"PUB{_tag()}".upper()
    try:
        snap = await _persist_with(monkeypatch, symbol, sector=NONBANK_INDUSTRIAL_SECTORS[0], publishable=True, reasons=[])
        assert snap.publishable is True
        assert snap.publication_block_reason is None
    finally:
        await _cleanup_snapshots(symbol)


@pytest.mark.asyncio
async def test_ineligible_headline_score_is_withheld(monkeypatch):
    from app.services.marketripple_score.sector_universe import NONBANK_INDUSTRIAL_SECTORS
    symbol = f"INE{_tag()}".upper()
    try:
        snap = await _persist_with(monkeypatch, symbol, sector=NONBANK_INDUSTRIAL_SECTORS[0], publishable=True,
                                   reasons=["INSUFFICIENT_FINANCIAL_METRICS"])
        assert snap.publishable is False
        assert "INSUFFICIENT_FINANCIAL_METRICS" in snap.publication_block_reason
    finally:
        await _cleanup_snapshots(symbol)


@pytest.mark.asyncio
async def test_sector_without_eligibility_policy_is_never_publishable(monkeypatch):
    symbol = f"NOP{_tag()}".upper()
    try:
        # Even if the engine said publishable, no policy ran -> fail closed.
        snap = await _persist_with(monkeypatch, symbol, sector="Insurance", publishable=True, reasons=[])
        assert snap.publishable is False
    finally:
        await _cleanup_snapshots(symbol)
