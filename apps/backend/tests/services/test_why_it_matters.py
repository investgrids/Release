"""
AI Article V2 Phase B — real tests for why_it_matters.py. The LLM call
itself (_call_with_fallback) is mocked (no network, deterministic) --
exactly the established pattern in test_comparison_multi_compare_
resilience.py and test_ai_service_nvidia.py. What's real: the bundle
shapes, the numeric-validation gate it runs against, and the bounded
retry / omission behavior.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services.warehouse.article_evidence_bundle import ArticleEvidenceBundle
from app.services.warehouse.read_service import LinkedEvidence, VerifiedFinancialContext, VerifiedFinancialFact
from app.services.warehouse.why_it_matters import build_why_it_matters


def _fact(metric_code, metric_name, value, unit, fiscal_year=2025, fiscal_quarter=3):
    return VerifiedFinancialFact(
        metric_code=metric_code, metric_name=metric_name, value=value, unit=unit,
        fiscal_year=fiscal_year, fiscal_quarter=fiscal_quarter, period_type="Quarterly",
        source_document_url=None, quality_status="OK",
    )


def _evidence(title, raw_evidence_id="e1234567890abcdef"):
    return LinkedEvidence(
        raw_evidence_id=raw_evidence_id, title=title, source_type="nse",
        published_at=datetime(2026, 8, 24, tzinfo=timezone.utc), source_url=None,
        relationship_type="subject", resolution_method="test", link_confidence=1.0,
    )


def _bundle(evidence=(), financial_context=None, price_move_pct=None):
    return ArticleEvidenceBundle(
        resolved=True, entity_id="cmp_test", symbol="TESTBANK", company_name="Test Bank Limited",
        evidence=list(evidence), price_move_pct=price_move_pct, financial_context=financial_context,
    )


def _llm_json(why_it_matters: str, claims=None) -> str:
    return json.dumps({"why_it_matters": why_it_matters, "claims": claims or []})


@pytest.mark.asyncio
async def test_no_evidence_and_no_financial_context_never_calls_the_llm():
    bundle = _bundle()
    with patch("app.services.warehouse.why_it_matters._call_with_fallback", new_callable=AsyncMock) as mock_llm:
        result = await build_why_it_matters(bundle)
    assert result.status == "omitted_no_evidence"
    assert result.text is None
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_grounded_output_within_allowed_numbers_passes_first_try():
    fc = VerifiedFinancialContext(symbol="TESTBANK", facts=[_fact("roa", "Return on Assets", 0.0238, "pct")], as_of="FY2025Q3")
    bundle = _bundle(evidence=[_evidence("Test Bank has informed the Exchange about Q3 results")], financial_context=fc)
    raw = _llm_json(
        "Test Bank's ROA of 2.38% reflects steady underlying profitability.",
        claims=[{"text": "Test Bank's ROA was 2.38%", "type": "FACT", "evidence_refs": ["FACT:roa"]}],
    )
    with patch("app.services.warehouse.why_it_matters._call_with_fallback", new_callable=AsyncMock, return_value=raw) as mock_llm:
        result = await build_why_it_matters(bundle)

    assert result.status == "ok"
    assert result.attempts == 1
    assert "2.38%" in result.text
    assert mock_llm.call_count == 1
    assert len(result.claims) == 1
    assert result.claims[0].claim_type == "FACT"
    assert result.claims[0].financial_fact_ids == ["roa"]


@pytest.mark.asyncio
async def test_hallucinated_number_triggers_retry_then_succeeds():
    fc = VerifiedFinancialContext(symbol="TESTBANK", facts=[_fact("roa", "Return on Assets", 0.0238, "pct")], as_of="FY2025Q3")
    bundle = _bundle(evidence=[_evidence("Test Bank has informed the Exchange about Q3 results")], financial_context=fc)
    bad = _llm_json("Test Bank's ROA of 9.9% is exceptionally strong.")
    good = _llm_json("Test Bank's ROA of 2.38% is steady.")
    with patch(
        "app.services.warehouse.why_it_matters._call_with_fallback",
        new_callable=AsyncMock, side_effect=[bad, good],
    ) as mock_llm:
        result = await build_why_it_matters(bundle)

    assert result.status == "ok"
    assert result.attempts == 2
    assert mock_llm.call_count == 2
    # The retry prompt must actually mention the rejected number, not just retry blindly.
    retry_prompt = mock_llm.call_args_list[1].args[0]
    assert "9.9%" in retry_prompt


@pytest.mark.asyncio
async def test_persistent_hallucination_exhausts_retries_and_is_omitted_never_published():
    fc = VerifiedFinancialContext(symbol="TESTBANK", facts=[_fact("roa", "Return on Assets", 0.0238, "pct")], as_of="FY2025Q3")
    bundle = _bundle(evidence=[_evidence("Test Bank has informed the Exchange about Q3 results")], financial_context=fc)
    always_bad = _llm_json("Test Bank's ROA of 9.9% is exceptionally strong.")
    with patch(
        "app.services.warehouse.why_it_matters._call_with_fallback",
        new_callable=AsyncMock, return_value=always_bad,
    ) as mock_llm:
        result = await build_why_it_matters(bundle)

    assert result.status == "omitted_validation_failed"
    assert result.text is None  # never published despite having a generated string
    assert mock_llm.call_count == 2  # bounded retry, not unbounded
    assert len(result.validation_errors) == 1


@pytest.mark.asyncio
async def test_evidence_only_bundle_with_zero_financial_facts_still_generates():
    """TCS having no FinancialFact rows shouldn't block a grounded,
    evidence-only Why It Matters (owner's explicit requirement)."""
    bundle = _bundle(
        evidence=[_evidence('Test Bank has informed the Exchange regarding a press release: "Partnership announced"')],
        financial_context=None, price_move_pct=4.163,
    )
    raw = _llm_json("Shares gained 4.2% following the newly announced partnership.")
    with patch("app.services.warehouse.why_it_matters._call_with_fallback", new_callable=AsyncMock, return_value=raw) as mock_llm:
        result = await build_why_it_matters(bundle)

    assert result.status == "ok"
    mock_llm.assert_called_once()


@pytest.mark.asyncio
async def test_unparseable_llm_response_retries_then_omits():
    bundle = _bundle(evidence=[_evidence("Test Bank has informed the Exchange about Q3 results")])
    with patch(
        "app.services.warehouse.why_it_matters._call_with_fallback",
        new_callable=AsyncMock, return_value="not json at all",
    ) as mock_llm:
        result = await build_why_it_matters(bundle)

    assert result.status == "omitted_validation_failed"
    assert result.text is None
    assert mock_llm.call_count == 2
