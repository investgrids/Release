"""
Article V2 Phase C3 — Event-aware Context Builder tests. Real DB-backed
for FinancialFact scoping; ArticleEvidenceSet/LinkedEvidence constructed
directly (both are plain frozen dataclasses) to isolate C3's own logic
from C2's already-separately-tested evidence-selection behavior. Covers
the owner's required categories: results, order/contract, governance/
management, dividend/corporate-action, a development with no relevant
FinancialFact, and the MOLDTECH-motivated cross-company adversarial case.
"""
from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models.financial_fact import FinancialFact
from app.db.session import AsyncSessionLocal
from app.services.article_v2.context_builder import (
    AVAILABLE, NONE_STATUS, PARTIAL, build_context,
)
from app.services.article_v2.evidence_set_builder import ArticleEvidenceSet
from app.services.warehouse.read_service import LinkedEvidence


def _tag():
    return "".join(random.choices(string.ascii_uppercase, k=8))


def _evidence(title: str, days_ago: int = 0, source_type: str = "nse") -> LinkedEvidence:
    now = datetime.now(timezone.utc)
    return LinkedEvidence(
        raw_evidence_id=str(uuid.uuid4()), title=title, source_type=source_type,
        published_at=now - timedelta(days=days_ago), source_url=None,
        relationship_type="subject", resolution_method="source_symbol", link_confidence=None,
    )


def _evidence_set(symbol: str, primary_title: str, *, supporting: list[LinkedEvidence] | None = None, days_ago: int = 0) -> ArticleEvidenceSet:
    return ArticleEvidenceSet(
        entity_id=f"cmp_{symbol.lower()}", symbol=symbol, event_id=None, event_headline=primary_title,
        status="COHERENT", primary_evidence=_evidence(primary_title, days_ago=days_ago),
        supporting_evidence=supporting or [], raw_evidence_count=1 + len(supporting or []),
    )


async def _seed_fact(db, *, symbol: str, metric_code: str, metric_name: str, value: float, unit: str,
                      fiscal_year: int, fiscal_quarter: int | None, quality_status: str = "OK"):
    db.add(FinancialFact(
        symbol=symbol, metric_code=metric_code, metric_name=metric_name, value=value, unit=unit,
        fiscal_year=fiscal_year, fiscal_quarter=fiscal_quarter, period_type="Quarterly" if fiscal_quarter else "Annual",
        consolidation_scope="Non-Consolidated", source_provider="NSE",
        extraction_status="POPULATED", quality_status=quality_status,
    ))


async def _cleanup_facts(symbols: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(FinancialFact).where(FinancialFact.symbol.in_(symbols)))
        await db.commit()


@pytest.mark.asyncio
async def test_insufficient_c2_set_never_reaches_context():
    """Owner instruction: C3 must not run at all for an INSUFFICIENT C2
    evidence set -- must not rescue an evidence-insufficient development."""
    es = ArticleEvidenceSet(
        entity_id=None, symbol="ANYSYM", event_id=None, event_headline="Anything",
        status="INSUFFICIENT", primary_evidence=None,
    )
    async with AsyncSessionLocal() as db:
        result = await build_context(db, es)
    assert result.status == NONE_STATUS
    assert result.financial_context == []
    assert result.market_reaction is None


@pytest.mark.asyncio
async def test_results_event_selects_full_metric_family():
    symbol = f"T{_tag()}"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_fact(db, symbol=symbol, metric_code="cet1_ratio", metric_name="CET1 Ratio", value=0.14, unit="pct", fiscal_year=2025, fiscal_quarter=3)
            await _seed_fact(db, symbol=symbol, metric_code="gross_npa_pct", metric_name="Gross NPA %", value=0.02, unit="pct", fiscal_year=2025, fiscal_quarter=3)
            await db.commit()
        es = _evidence_set(symbol, f"{symbol} has informed the Exchange regarding financial results for the quarter", days_ago=30)
        async with AsyncSessionLocal() as db:
            result = await build_context(db, es)
        assert "RESULTS" in result.matched_event_families
        codes = {f.metric_code for f in result.financial_context}
        assert "cet1_ratio" in codes and "gross_npa_pct" in codes
    finally:
        await _cleanup_facts([symbol])


@pytest.mark.asyncio
async def test_order_contract_event_gets_scale_metrics_only():
    symbol = f"T{_tag()}"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_fact(db, symbol=symbol, metric_code="advances", metric_name="Advances", value=1e12, unit="inr", fiscal_year=2024, fiscal_quarter=None)
            await _seed_fact(db, symbol=symbol, metric_code="cet1_ratio", metric_name="CET1 Ratio", value=0.14, unit="pct", fiscal_year=2025, fiscal_quarter=3)
            await _seed_fact(db, symbol=symbol, metric_code="roa", metric_name="Return on Assets", value=0.02, unit="pct", fiscal_year=2025, fiscal_quarter=3)
            await db.commit()
        es = _evidence_set(symbol, f"{symbol} wins a real order worth Rs 800 crore from a real client", days_ago=30)
        async with AsyncSessionLocal() as db:
            result = await build_context(db, es)
        assert "ORDER_CONTRACT" in result.matched_event_families
        codes = {f.metric_code for f in result.financial_context}
        assert codes == {"advances"}  # only the ORDER_CONTRACT-allowed metric, not CET1/ROA
    finally:
        await _cleanup_facts([symbol])


@pytest.mark.asyncio
async def test_generic_in_order_to_phrasing_does_not_false_match_order_contract():
    """Real regression found via the C3 shadow run: NEWGEN's real
    evidence text '...in order to ensure that investors...' contains
    "order" as a bare substring but describes nothing about a real
    order/contract win. The family phrase list must not fire on this."""
    symbol = f"T{_tag()}"
    es = _evidence_set(
        symbol,
        f"{symbol} significant increase in volume observed. The Exchange, in order to ensure that "
        f"investors have latest relevant information, had written to the company.",
        days_ago=30,
    )
    async with AsyncSessionLocal() as db:
        result = await build_context(db, es)
    assert "ORDER_CONTRACT" not in result.matched_event_families
    assert result.matched_event_families == []


@pytest.mark.asyncio
async def test_governance_event_gets_zero_financial_context_even_with_real_facts_available():
    """The owner's own explicit example: a management resignation must
    not receive P/E or NII context just because the company has real
    FinancialFact data on file."""
    symbol = f"T{_tag()}"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_fact(db, symbol=symbol, metric_code="cet1_ratio", metric_name="CET1 Ratio", value=0.14, unit="pct", fiscal_year=2025, fiscal_quarter=3)
            await _seed_fact(db, symbol=symbol, metric_code="roa", metric_name="Return on Assets", value=0.02, unit="pct", fiscal_year=2025, fiscal_quarter=3)
            await db.commit()
        es = _evidence_set(symbol, f"{symbol} has informed the Exchange regarding resignation of an Independent Director", days_ago=30)
        async with AsyncSessionLocal() as db:
            result = await build_context(db, es)
        assert result.matched_event_families == []
        assert result.financial_context == []
        assert any("no recognized event family" in r for r in result.omitted_reasons)
    finally:
        await _cleanup_facts([symbol])


@pytest.mark.asyncio
async def test_dividend_record_date_gets_zero_financial_context():
    symbol = f"T{_tag()}"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_fact(db, symbol=symbol, metric_code="roa", metric_name="Return on Assets", value=0.02, unit="pct", fiscal_year=2025, fiscal_quarter=3)
            await db.commit()
        es = _evidence_set(symbol, f"{symbol} has informed the Exchange that Record date for dividend has been fixed", days_ago=30)
        async with AsyncSessionLocal() as db:
            result = await build_context(db, es)
        assert result.financial_context == []
    finally:
        await _cleanup_facts([symbol])


@pytest.mark.asyncio
async def test_matched_family_but_zero_real_facts_reports_the_honest_reason():
    """A recognized event family with a real relevance signal, but this
    company (non-Banking, real production constraint) has zero
    FinancialFact rows at all -- must be distinguished from 'facts exist
    but weren't relevant', not just silently empty."""
    symbol = f"T{_tag()}NOFACTS"
    es = _evidence_set(symbol, f"{symbol} has informed the Exchange regarding financial results for the quarter", days_ago=30)
    async with AsyncSessionLocal() as db:
        result = await build_context(db, es)
    assert result.financial_context == []
    assert any("zero quality-passed FinancialFact rows" in r for r in result.omitted_reasons)


@pytest.mark.asyncio
async def test_cross_company_contamination_never_occurs_despite_similar_names():
    """MOLDTECH-motivated adversarial case: two distinct real symbols
    with lexically similar/confusable text must never cross-contaminate
    context. Canonical scoping (the exact `symbol` on the C2 evidence
    set) is the only real boundary -- not company-name similarity."""
    sym_a, sym_b = f"MOLDTEKPACK{_tag()}", f"MOLDTEKTECH{_tag()}"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_fact(db, symbol=sym_a, metric_code="cet1_ratio", metric_name="CET1 Ratio", value=0.11, unit="pct", fiscal_year=2025, fiscal_quarter=3)
            await _seed_fact(db, symbol=sym_b, metric_code="cet1_ratio", metric_name="CET1 Ratio", value=0.99, unit="pct", fiscal_year=2025, fiscal_quarter=3)
            await db.commit()
        es = _evidence_set(sym_a, f"{sym_a} has informed the Exchange regarding financial results", days_ago=30)
        async with AsyncSessionLocal() as db:
            result = await build_context(db, es)
        assert result.symbol == sym_a
        values = {f.value for f in result.financial_context if f.metric_code == "cet1_ratio"}
        assert values == {0.11}  # never sym_b's 0.99, despite near-identical symbol text
    finally:
        await _cleanup_facts([sym_a, sym_b])


@pytest.mark.asyncio
async def test_market_reaction_included_within_window_omitted_outside_it():
    symbol_recent, symbol_old = f"T{_tag()}", f"T{_tag()}"
    es_recent = _evidence_set(symbol_recent, f"{symbol_recent} has informed the Exchange regarding a real event", days_ago=0)
    es_old = _evidence_set(symbol_old, f"{symbol_old} has informed the Exchange regarding a real event", days_ago=10)
    async with AsyncSessionLocal() as db:
        result_old = await build_context(db, es_old)
    assert result_old.market_reaction is None
    assert any("day(s) old" in r for r in result_old.omitted_reasons)


@pytest.mark.asyncio
async def test_prior_period_trend_is_attached_when_a_real_prior_value_exists():
    symbol = f"T{_tag()}"
    try:
        async with AsyncSessionLocal() as db:
            await _seed_fact(db, symbol=symbol, metric_code="cet1_ratio", metric_name="CET1 Ratio", value=0.14, unit="pct", fiscal_year=2025, fiscal_quarter=3)
            await _seed_fact(db, symbol=symbol, metric_code="cet1_ratio", metric_name="CET1 Ratio", value=0.15, unit="pct", fiscal_year=2025, fiscal_quarter=2)
            await db.commit()
        es = _evidence_set(symbol, f"{symbol} has informed the Exchange regarding financial results", days_ago=30)
        async with AsyncSessionLocal() as db:
            result = await build_context(db, es)
        cet1 = next(f for f in result.financial_context if f.metric_code == "cet1_ratio")
        assert cet1.value == 0.14
        assert cet1.prior_period_value == 0.15
        assert cet1.prior_period_label == "FY2025Q2"
    finally:
        await _cleanup_facts([symbol])
