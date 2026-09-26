"""
Provenance contract — 2026-09-26 audit follow-up. Two real gaps the audit
found: (1) a single pillar-wide "financial_data_as_of" can overstate
freshness for any one metric whose own latest valid period is actually
older than another metric's; (2) the yfinance-sourced metrics (ROE, NII
growth, Profit growth) carried no captured fiscal period at all. These
tests prove score_financial_strength() now reports each metric's own real
period/source/substitution reason individually, and honestly marks the
yfinance metrics' period as unknown rather than borrowing another metric's.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.financial_fact import EXTRACTION_POPULATED, QUALITY_ANOMALY, FinancialFact
from app.db.session import AsyncSessionLocal
from app.services.marketripple_score.financial_strength import FORMULA_VERSION, score_financial_strength


def _tag():
    return uuid.uuid4().hex[:8]


async def _cleanup(symbols: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FinancialFact).where(FinancialFact.symbol.in_(symbols)))
        await db.commit()


def _fact(symbol, metric_code, value, fy, fq, quality_status, published_at=None) -> FinancialFact:
    return FinancialFact(
        symbol=symbol, metric_code=metric_code, metric_name=metric_code, value=value, unit="pct",
        fiscal_year=fy, fiscal_quarter=fq, period_type="Quarterly",
        consolidation_scope="Non-Consolidated", source_provider="NSE",
        extraction_status=EXTRACTION_POPULATED, quality_status=quality_status,
        published_at=published_at,
    )


def _no_network_yfinance(monkeypatch):
    """These tests only exercise FinancialFact-sourced provenance — the
    real yfinance-sourced (ROE/NII/Profit growth) inputs are irrelevant to
    what's being asserted here, so stub them out rather than make real,
    slow, always-404 network calls for a fake test symbol."""
    from app.services.marketripple_score import financial_strength as fs_module

    monkeypatch.setattr(
        fs_module, "_fetch_financial_strength_inputs_sync",
        lambda sym: {"roe": None, "nii_growth": None, "profit_growth": None, "nim_proxy_not_scored": None},
    )


@pytest.mark.asyncio
async def test_substitution_is_reported_with_its_own_real_period(monkeypatch):
    """The real ICICIBANK shape this audit examined: a symbol's newest
    period is ANOMALY-flagged, so scoring falls back to its own next-most-
    recent valid period — that fallback, and which period it came FROM,
    must be visible in this metric's own provenance record."""
    _no_network_yfinance(monkeypatch)
    tag = _tag()
    symbol = f"TESTPROV{tag}"[:20].upper()
    peer = f"TESTPEER{tag}"[:20].upper()
    published = datetime(2025, 8, 1, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as db:
        # Own symbol: FY25Q3 anomalous, FY25Q2 valid -> must substitute to Q2.
        db.add(_fact(symbol, "gross_npa_pct", 2.5, 2025, 3, QUALITY_ANOMALY))
        db.add(_fact(symbol, "gross_npa_pct", 2.1, 2025, 2, "OK", published_at=published))
        # A real peer so percentile ranking has >=2 values.
        db.add(_fact(peer, "gross_npa_pct", 3.0, 2025, 3, "OK"))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            pillar = await score_financial_strength(db, symbol, "Banking", peer_group=[symbol, peer])
        rec = pillar.detail["metrics"]["gross_npa_pct"]
        assert rec["value"] == 2.1
        assert rec["period"] == "FY2025Q2"
        # SQLite's DateTime(timezone=True) round-trips as naive — compare
        # the wall-clock value, not tzinfo presence.
        assert rec["observation_as_of"].replace("+00:00", "") == published.isoformat().replace("+00:00", "")
        assert rec["substitution_reason"] == "anomaly_fallback_from_FY2025Q3"
        assert rec["source"] == "NSE_XBRL_FinancialFact"
        assert rec["formula_version"] == FORMULA_VERSION
    finally:
        await _cleanup([symbol, peer])


@pytest.mark.asyncio
async def test_no_substitution_when_newest_period_is_already_valid(monkeypatch):
    _no_network_yfinance(monkeypatch)
    tag = _tag()
    symbol = f"TESTNOSUB{tag}"[:20].upper()
    peer = f"TESTPEER2{tag}"[:20].upper()

    async with AsyncSessionLocal() as db:
        db.add(_fact(symbol, "cet1_ratio", 15.0, 2025, 3, "OK"))
        db.add(_fact(peer, "cet1_ratio", 14.0, 2025, 3, "OK"))
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            pillar = await score_financial_strength(db, symbol, "Banking", peer_group=[symbol, peer])
        rec = pillar.detail["metrics"]["cet1_ratio"]
        assert rec["period"] == "FY2025Q3"
        assert rec["substitution_reason"] is None
    finally:
        await _cleanup([symbol, peer])


@pytest.mark.asyncio
async def test_yfinance_sourced_metrics_report_period_as_explicitly_unknown(monkeypatch):
    """ROE/NII growth/Profit growth carry no captured fiscal period today —
    this must show up as an explicit None, never silently omitted or
    borrowed from a FinancialFact metric's own period."""
    from app.services.marketripple_score import financial_strength as fs_module

    tag = _tag()
    symbol = f"TESTYFPROV{tag}"[:20].upper()
    peer = f"TESTYFPEER{tag}"[:20].upper()

    def fake_fetch(sym: str) -> dict:
        return {"roe": 0.15, "nii_growth": 8.0, "profit_growth": 12.0, "nim_proxy_not_scored": None}

    monkeypatch.setattr(fs_module, "_fetch_financial_strength_inputs_sync", fake_fetch)

    try:
        async with AsyncSessionLocal() as db:
            pillar = await score_financial_strength(db, symbol, "Banking", peer_group=[symbol, peer])
        for code in ("roe", "nii_growth", "profit_growth"):
            rec = pillar.detail["metrics"][code]
            assert rec["period"] is None
            assert rec["observation_as_of"] is None
            assert rec["source"].startswith("yfinance")
    finally:
        await _cleanup([symbol, peer])
