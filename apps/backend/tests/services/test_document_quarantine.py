"""
S4.5-B — real DB-backed tests for filing-level quarantine propagation.
Real, live-confirmed motivation: YESBANK's cet1_ratio was correctly
flagged IMPLAUSIBLE_SCALE, but its gross_npa_pct/net_npa_pct/roa from the
SAME real filing were not — and under the frozen percentile formula that
actually made YESBANK's own score RISE (52.8 -> 61.6) once CET1 alone was
excluded, since near-zero NPA ranks #1 of 27 under "lower is better." See
artifacts/marketripple_score_s4_5_publication_guardrails.md.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models.financial_fact import FinancialFact
from app.db.session import AsyncSessionLocal
from app.services.financial_facts import quality


def _tag():
    return uuid.uuid4().hex[:8]


def _row(symbol, metric_code, value, quality_status, doc_id, fy=2025, fq=3):
    return FinancialFact(
        symbol=symbol, metric_code=metric_code, metric_name=metric_code, value=value, unit="pct",
        fiscal_year=fy, fiscal_quarter=fq, period_type="Quarterly", consolidation_scope="Non-Consolidated",
        source_provider="NSE", source_document_id=doc_id, source_document_url=f"https://example/{doc_id}",
        extraction_status="POPULATED", quality_status=quality_status, quality_reason=None,
        observed_at=datetime.now(timezone.utc),
    )


async def _cleanup(symbol: str):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FinancialFact).where(FinancialFact.symbol == symbol))
        await db.commit()


@pytest.mark.asyncio
async def test_quarantine_propagates_from_implausible_scale_to_other_ok_metrics():
    symbol = f"TESTDOC{_tag()}"[:20].upper()
    doc_id = f"doc-{_tag()}"
    async with AsyncSessionLocal() as db:
        db.add_all([
            _row(symbol, "cet1_ratio", 0.0013, "IMPLAUSIBLE_SCALE", doc_id),
            _row(symbol, "gross_npa_pct", 0.0002, "OK", doc_id),
            _row(symbol, "net_npa_pct", 0.0, "OK", doc_id),
            _row(symbol, "roa", 0.0001, "OK", doc_id),
        ])
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            n = await quality.quarantine_document_if_needed(db, symbol, "NSE", doc_id, "Non-Consolidated")
            await db.commit()
        assert n == 3  # the 3 real OK rows, not the trigger row itself

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            rows = (await db.execute(
                select(FinancialFact.metric_code, FinancialFact.value, FinancialFact.quality_status)
                .where(FinancialFact.symbol == symbol)
            )).all()
        by_code = {code: (value, status) for code, value, status in rows}

        # Trigger row keeps its own, more specific status — never overwritten.
        assert by_code["cet1_ratio"] == (0.0013, "IMPLAUSIBLE_SCALE")
        # Other real metrics from the SAME document are quarantined, values untouched.
        assert by_code["gross_npa_pct"] == (0.0002, "SOURCE_DOCUMENT_QUARANTINED")
        assert by_code["net_npa_pct"] == (0.0, "SOURCE_DOCUMENT_QUARANTINED")
        assert by_code["roa"] == (0.0001, "SOURCE_DOCUMENT_QUARANTINED")
    finally:
        await _cleanup(symbol)


@pytest.mark.asyncio
async def test_quarantine_does_not_propagate_from_plain_anomaly():
    """The real ICICIBANK Q1 FY25 case: a genuine single-metric ANOMALY
    must never quarantine the rest of that filing's real, valid metrics —
    an anomaly is signal about ONE metric's own history, not proof the
    whole document's scale is wrong."""
    symbol = f"TESTDOC{_tag()}"[:20].upper()
    doc_id = f"doc-{_tag()}"
    async with AsyncSessionLocal() as db:
        db.add_all([
            _row(symbol, "gross_npa_pct", 0.0002, "ANOMALY", doc_id),
            _row(symbol, "net_npa_pct", 0.015, "OK", doc_id),
            _row(symbol, "roa", 0.018, "OK", doc_id),
        ])
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            n = await quality.quarantine_document_if_needed(db, symbol, "NSE", doc_id, "Non-Consolidated")
            await db.commit()
        assert n == 0

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            rows = (await db.execute(
                select(FinancialFact.metric_code, FinancialFact.quality_status)
                .where(FinancialFact.symbol == symbol)
            )).all()
        statuses = dict(rows)
        assert statuses["net_npa_pct"] == "OK"
        assert statuses["roa"] == "OK"
    finally:
        await _cleanup(symbol)


@pytest.mark.asyncio
async def test_quarantine_never_crosses_documents():
    """Two real, distinct filings for the same symbol/period (e.g. a
    Quarterly vs. Annual scope, or simply two different real documents) —
    a structural failure in one must never quarantine the other."""
    symbol = f"TESTDOC{_tag()}"[:20].upper()
    doc_a, doc_b = f"doc-a-{_tag()}", f"doc-b-{_tag()}"
    async with AsyncSessionLocal() as db:
        db.add_all([
            _row(symbol, "cet1_ratio", 0.0013, "IMPLAUSIBLE_SCALE", doc_a),
            _row(symbol, "gross_npa_pct", 0.0002, "OK", doc_a),
            _row(symbol, "cet1_ratio", 0.14, "OK", doc_b, fy=2024, fq=4),
            _row(symbol, "gross_npa_pct", 0.02, "OK", doc_b, fy=2024, fq=4),
        ])
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            await quality.quarantine_document_if_needed(db, symbol, "NSE", doc_a, "Non-Consolidated")
            await db.commit()

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            rows = (await db.execute(
                select(FinancialFact.source_document_id, FinancialFact.metric_code, FinancialFact.quality_status)
                .where(FinancialFact.symbol == symbol)
            )).all()
        for doc_id, code, status in rows:
            if doc_id == doc_b:
                assert status == "OK", f"doc_b's {code} was incorrectly touched by doc_a's quarantine"
    finally:
        await _cleanup(symbol)


@pytest.mark.asyncio
async def test_quarantine_returns_zero_without_a_real_document_id():
    symbol = f"TESTDOC{_tag()}"[:20].upper()
    async with AsyncSessionLocal() as db:
        n = await quality.quarantine_document_if_needed(db, symbol, "NSE", None, "Non-Consolidated")
    assert n == 0
