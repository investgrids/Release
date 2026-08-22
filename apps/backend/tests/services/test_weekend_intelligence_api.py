"""
Weekend Intelligence read API tests — brief §35. Calls the router
functions directly (same convention as other API test files in this
codebase — no live HTTP server needed for FastAPI route functions).
DB-backed: creates/cleans up real WeekendIntelligenceSnapshot rows.
"""
from __future__ import annotations

import time
import uuid

import pytest
from sqlalchemy import delete

from app.api import weekend_intelligence as api
from app.db.session import AsyncSessionLocal
from app.db.models.weekend_intelligence import WeekendIntelligenceSnapshot
from app.services.weekend_intelligence.versioning import create_next_version


def _target(bucket: str) -> str:
    return f"2098-{bucket}-0{(uuid.uuid4().int % 8) + 1}"


async def _cleanup(target: str):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(WeekendIntelligenceSnapshot).where(
            WeekendIntelligenceSnapshot.target_trading_date == target))
        await db.commit()


@pytest.mark.asyncio
async def test_current_returns_available_false_when_no_snapshot(monkeypatch):
    target = _target("01")
    monkeypatch.setattr(
        "app.services.weekend_intelligence.session_resolution.resolve_weekend_session",
        lambda *a, **kw: ("2098-01-01", target),
    )
    result = await api.get_current_weekend_intelligence()
    assert result["available"] is False
    assert result["target_trading_date"] == target


@pytest.mark.asyncio
async def test_current_returns_full_shape_when_snapshot_exists(monkeypatch):
    target = _target("02")
    try:
        async with AsyncSessionLocal() as db:
            await create_next_version(
                db, target_trading_date=target, last_trading_date="2098-02-01",
                status="ok", overall_bias="positive", production_confidence=65.0,
                confidence_components={"raw": {}, "weights": {}, "weighted_contributions": {}},
                top_sector_refs=[{"sector": "IT", "direction": "positive", "score": 0.6, "evidence_count": 3}],
                top_company_refs=[{"symbol": "INFY", "state": "positive_watch", "confidence": 0.5, "evidence_count": 2}],
                risk_refs=[{"description": "IT: conflicting evidence", "risk_type": "conflicting_evidence", "severity": "medium"}],
                confidence_warning_refs=[{"description": "Baseline missing", "risk_type": "stale_or_missing_baseline", "severity": "high"}],
                evidence_refs=[{"source_type": "event", "source_id": "e1"}, {"source_type": "news", "source_id": "n1"}],
                new_since_close_refs=[{"source_type": "event", "source_id": "e1", "title": "t", "direction": "positive"}],
                market_snapshot_id="ms1",
            )
            await db.commit()

        monkeypatch.setattr(
            "app.services.weekend_intelligence.session_resolution.resolve_weekend_session",
            lambda *a, **kw: ("2098-02-01", target),
        )
        result = await api.get_current_weekend_intelligence()

        assert result["available"] is True
        assert result["target_trading_date"] == target
        assert result["status"] == "ok"
        assert result["overall_bias"] == "positive"
        assert result["production_confidence"] == 65.0
        assert result["baseline_available"] is True
        assert result["top_sectors"][0]["sector"] == "IT"
        assert result["top_companies"][0]["symbol"] == "INFY"
        assert result["market_risks"][0]["risk_type"] == "conflicting_evidence"
        assert result["confidence_warnings"][0]["risk_type"] == "stale_or_missing_baseline"
        assert result["new_since_close_count"] == 1
        assert result["evidence_summary"]["total"] == 2
        assert result["evidence_summary"]["by_source_type"] == {"event": 1, "news": 1}
        assert "experimental_signals" not in result
        assert "confidence_components" in result
    finally:
        await _cleanup(target)


@pytest.mark.asyncio
async def test_degraded_snapshot_still_returns_available_true():
    target = _target("03")
    try:
        async with AsyncSessionLocal() as db:
            await create_next_version(
                db, target_trading_date=target, last_trading_date="2098-03-01",
                status="degraded", overall_bias="mixed", production_confidence=30.0,
            )
            await db.commit()
        async with AsyncSessionLocal() as db:
            from app.services.weekend_intelligence.versioning import get_current_snapshot
            snap = await get_current_snapshot(db, target)
            response = api._snapshot_response(snap)
        assert response["available"] is True
        assert response["status"] == "degraded"
    finally:
        await _cleanup(target)


@pytest.mark.asyncio
async def test_insufficient_evidence_snapshot_still_returns_available_true():
    target = _target("04")
    try:
        async with AsyncSessionLocal() as db:
            await create_next_version(
                db, target_trading_date=target, last_trading_date="2098-04-01",
                status="insufficient_evidence", overall_bias="neutral", production_confidence=0.0,
            )
            await db.commit()
        async with AsyncSessionLocal() as db:
            from app.services.weekend_intelligence.versioning import get_current_snapshot
            snap = await get_current_snapshot(db, target)
            response = api._snapshot_response(snap)
        assert response["available"] is True
        assert response["status"] == "insufficient_evidence"
    finally:
        await _cleanup(target)


@pytest.mark.asyncio
async def test_missing_referenced_opportunity_omitted_not_erroring():
    """opportunity_refs pointing at a nonexistent Opportunity id must not
    fail the response — omitted honestly (brief §6)."""
    async with AsyncSessionLocal() as db:
        resolved = await api._resolve_opportunities(db, ["99999999"])
    assert resolved == []


@pytest.mark.asyncio
async def test_resolved_opportunity_carries_real_reason_and_top_companies():
    """2026-08-22 homepage card redesign — the reason must come from the
    real, already-persisted ai_summary.matters field (never a truncation
    of title), and companies must be the real OpportunityCompany rows,
    capped at 3 and ranked by their own real impact_score, never
    invented tickers."""
    from app.db.models.opportunity import Opportunity, OpportunityCompany

    async with AsyncSessionLocal() as db:
        opp = Opportunity(
            slug=f"test-opp-{uuid.uuid4().hex[:8]}", title="Test opportunity title",
            sectors=["Banking"], risk_level="Medium", opportunity_score=78.0, confidence=0.8,
            ai_summary={"matters": "Real concise reason from the backend."},
        )
        db.add(opp)
        await db.flush()
        db.add_all([
            OpportunityCompany(opportunity_id=opp.id, company_id="LOWSCORE", impact_score=10.0),
            OpportunityCompany(opportunity_id=opp.id, company_id="HIGHSCORE", impact_score=90.0),
            OpportunityCompany(opportunity_id=opp.id, company_id="MIDSCORE", impact_score=50.0),
            OpportunityCompany(opportunity_id=opp.id, company_id="FOURTH", impact_score=40.0),
        ])
        await db.commit()
        opp_id = opp.id
        try:
            resolved = await api._resolve_opportunities(db, [str(opp_id)])
            assert len(resolved) == 1
            r = resolved[0]
            assert r["reason"] == "Real concise reason from the backend."
            assert r["companies"] == ["HIGHSCORE", "MIDSCORE", "FOURTH"]  # top 3 by impact_score, "LOWSCORE" excluded
        finally:
            await db.delete(opp)
            await db.commit()


@pytest.mark.asyncio
async def test_resolved_opportunity_without_ai_summary_has_no_fabricated_reason():
    """A row that predates AI summary generation must report reason=None,
    never a fallback string invented here — the frontend is what decides
    to fall back to title, this layer just tells the truth about what's
    actually stored."""
    from app.db.models.opportunity import Opportunity

    async with AsyncSessionLocal() as db:
        opp = Opportunity(
            slug=f"test-opp-{uuid.uuid4().hex[:8]}", title="No AI summary yet",
            sectors=[], risk_level="Medium", opportunity_score=50.0, confidence=0.5,
            ai_summary=None,
        )
        db.add(opp)
        await db.commit()
        opp_id = opp.id
        try:
            resolved = await api._resolve_opportunities(db, [str(opp_id)])
            assert resolved[0]["reason"] is None
            assert resolved[0]["companies"] == []
        finally:
            await db.delete(opp)
            await db.commit()


@pytest.mark.asyncio
async def test_company_ranking_only_contains_valid_tradable_symbols_end_to_end():
    """Structural check reusing Phase 1B's own canonical-symbol test
    fixtures — the API never re-introduces a pseudo-symbol since it only
    ever reads what company_synthesis.py already filtered at write time."""
    target = _target("05")
    try:
        async with AsyncSessionLocal() as db:
            await create_next_version(
                db, target_trading_date=target, last_trading_date="2098-05-01",
                status="ok", overall_bias="positive", production_confidence=50.0,
                top_company_refs=[{"symbol": "INFY", "state": "positive_watch", "confidence": 0.5, "evidence_count": 2}],
            )
            await db.commit()
            from app.services.aipe.company_score_engine import _is_real_symbol
            from app.services.weekend_intelligence.versioning import get_current_snapshot
            snap = await get_current_snapshot(db, target)
            response = api._snapshot_response(snap)
            assert all(_is_real_symbol(c["symbol"]) for c in response["top_companies"])
    finally:
        await _cleanup(target)


@pytest.mark.asyncio
async def test_history_endpoint_returns_newest_first_and_capped(monkeypatch):
    target = _target("06")
    try:
        async with AsyncSessionLocal() as db:
            await create_next_version(
                db, target_trading_date=target, last_trading_date="2098-06-01",
                status="ok", overall_bias="positive", production_confidence=40.0,
                checkpoint_label="Saturday 09:00 IST",
            )
            await db.commit()
            await create_next_version(
                db, target_trading_date=target, last_trading_date="2098-06-01",
                status="ok", overall_bias="mixed", production_confidence=55.0,
                checkpoint_label="Sunday 18:00 IST",
            )
            await db.commit()

        result = await api.get_weekend_intelligence_history(target_trading_date=target)
        assert result["target_trading_date"] == target
        assert len(result["versions"]) == 2
        assert result["versions"][0]["version"] > result["versions"][1]["version"]  # newest first
        assert result["versions"][0]["is_current"] is True
    finally:
        await _cleanup(target)


@pytest.mark.asyncio
async def test_history_empty_when_no_snapshots():
    target = _target("07")
    result = await api.get_weekend_intelligence_history(target_trading_date=target)
    assert result["versions"] == []


@pytest.mark.asyncio
async def test_current_response_does_not_trigger_aggregator(monkeypatch):
    """GET must never call build_weekend_intelligence — asserting the
    aggregator entry point is simply never imported/called during a
    normal current-snapshot read."""
    called = {"hit": False}

    async def _boom(*a, **kw):
        called["hit"] = True
        raise AssertionError("build_weekend_intelligence must not be called by the read API")

    monkeypatch.setattr(
        "app.services.weekend_intelligence.aggregator.build_weekend_intelligence", _boom,
    )
    target = _target("08")
    monkeypatch.setattr(
        "app.services.weekend_intelligence.session_resolution.resolve_weekend_session",
        lambda *a, **kw: ("2098-08-01", target),
    )
    await api.get_current_weekend_intelligence()
    assert called["hit"] is False


@pytest.mark.asyncio
async def test_current_response_time_is_cheap_for_no_snapshot(monkeypatch):
    target = _target("09")
    monkeypatch.setattr(
        "app.services.weekend_intelligence.session_resolution.resolve_weekend_session",
        lambda *a, **kw: ("2098-09-01", target),
    )
    started = time.monotonic()
    await api.get_current_weekend_intelligence()
    elapsed = time.monotonic() - started
    assert elapsed < 1.0  # generous local-DB bound; real assertion is "no aggregator run"
