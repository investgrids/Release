"""
AI Article V2 Phase B — real tests for get_verified_financial_context(),
the one boundary the article pipeline is allowed to read financial facts
through (owner decision, 2026-08-30: "The article pipeline should never
query FinancialFact directly and decide quality for itself"). Real
DB-backed rows, no network calls.
"""
from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.financial_fact import (
    EXTRACTION_POPULATED,
    QUALITY_IMPLAUSIBLE_SCALE,
    QUALITY_OK,
    QUALITY_SOURCE_DOCUMENT_QUARANTINED,
    FinancialFact,
)
from app.db.session import AsyncSessionLocal
from app.services.warehouse.read_service import get_verified_financial_context


def _symbol():
    return "TF" + "".join(random.choices(string.ascii_uppercase, k=8))


async def _cleanup(symbol: str):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FinancialFact).where(FinancialFact.symbol == symbol))
        await db.commit()


def _fact(symbol, metric_code, metric_name, value, fiscal_year, fiscal_quarter, quality_status, unit="pct",
          source_document_id=None):
    return FinancialFact(
        symbol=symbol, metric_code=metric_code, metric_name=metric_name, value=value, unit=unit,
        fiscal_year=fiscal_year, fiscal_quarter=fiscal_quarter, period_type="Quarterly",
        consolidation_scope="Non-Consolidated", source_provider="NSE",
        source_document_id=source_document_id or str(uuid.uuid4()),
        extraction_status=EXTRACTION_POPULATED, quality_status=quality_status,
        observed_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_returns_real_quality_passed_facts_only():
    symbol = _symbol()
    try:
        async with AsyncSessionLocal() as db:
            db.add(_fact(symbol, "gross_npa_pct", "Gross NPA %", 1.2, 2025, 3, QUALITY_OK))
            # An older quarter for the same metric -- must lose to the newer one above.
            db.add(_fact(symbol, "gross_npa_pct", "Gross NPA %", 1.5, 2025, 2, QUALITY_OK))
            db.add(_fact(symbol, "cet1_ratio", "CET1 Ratio", 14.1, 2025, 3, QUALITY_OK))
            await db.commit()

        async with AsyncSessionLocal() as db:
            ctx = await get_verified_financial_context(db, symbol)

        assert ctx.has_real_facts is True
        assert ctx.as_of == "FY2025Q3"
        by_metric = {f.metric_code: f for f in ctx.facts}
        assert by_metric["gross_npa_pct"].value == 1.2  # latest period wins, not the stale one
        assert by_metric["cet1_ratio"].value == 14.1
        assert all(f.quality_status == QUALITY_OK for f in ctx.facts)
    finally:
        await _cleanup(symbol)


@pytest.mark.asyncio
async def test_excludes_quarantined_and_implausible_facts():
    symbol = _symbol()
    try:
        async with AsyncSessionLocal() as db:
            db.add(_fact(symbol, "gross_npa_pct", "Gross NPA %", 0.02, 2025, 3, QUALITY_IMPLAUSIBLE_SCALE))
            db.add(_fact(symbol, "net_npa_pct", "Net NPA %", 0.01, 2025, 3, QUALITY_SOURCE_DOCUMENT_QUARANTINED))
            await db.commit()

        async with AsyncSessionLocal() as db:
            ctx = await get_verified_financial_context(db, symbol)

        # A real company whose ONLY facts are bad-quality gets a real, honest
        # empty context -- never a fallback, never a fabricated value.
        assert ctx.has_real_facts is False
        assert ctx.facts == []
        assert ctx.as_of is None
    finally:
        await _cleanup(symbol)


@pytest.mark.asyncio
async def test_no_facts_at_all_returns_honest_empty_context():
    symbol = _symbol()
    async with AsyncSessionLocal() as db:
        ctx = await get_verified_financial_context(db, symbol)
    assert ctx.symbol == symbol.upper()
    assert ctx.has_real_facts is False
    assert ctx.facts == []
    assert ctx.as_of is None


@pytest.mark.asyncio
async def test_good_and_bad_quality_facts_coexist_only_good_one_surfaces():
    """A company with a mix of real, valid facts and one quarantined metric
    must still surface the good ones -- quarantine is per-metric-column
    here (S4.5-B document-wide propagation already happened upstream at
    write time), never an all-or-nothing gate on the whole symbol."""
    symbol = _symbol()
    try:
        async with AsyncSessionLocal() as db:
            db.add(_fact(symbol, "roa", "Return on Assets", 1.8, 2025, 3, QUALITY_OK, unit="pct"))
            db.add(_fact(symbol, "gross_npa_pct", "Gross NPA %", 45.0, 2025, 3, QUALITY_IMPLAUSIBLE_SCALE))
            await db.commit()

        async with AsyncSessionLocal() as db:
            ctx = await get_verified_financial_context(db, symbol)

        assert ctx.has_real_facts is True
        assert len(ctx.facts) == 1
        assert ctx.facts[0].metric_code == "roa"
    finally:
        await _cleanup(symbol)
