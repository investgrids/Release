"""
AI Article V2 Phase B — real, pure unit tests for numeric_validation.py.
No network, no DB: every case is built from real dataclass shapes
(VerifiedFinancialFact/LinkedEvidence) with hand-picked values matching
what this app's real data actually looks like (fraction-stored percents,
absolute-rupee INR facts).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.warehouse.numeric_validation import (
    build_allowed_values, extract_numeric_claims, extract_period_claims,
    validate_numeric_claims, validate_period_claims,
)
from app.services.warehouse.read_service import LinkedEvidence, VerifiedFinancialContext, VerifiedFinancialFact


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


class _FakeBundle:
    def __init__(self, price_move_pct=None, financial_context=None):
        self.price_move_pct = price_move_pct
        self.financial_context = financial_context


# ── extract_numeric_claims ───────────────────────────────────────────────

def test_extracts_percent_currency_inr_usd_and_ratio():
    text = "ROA was 2.38%, borrowings rose ₹1,410 crore, and TCS raised $1 billion at 1.4x coverage."
    nums = extract_numeric_claims(text)
    kinds = {(n.value, n.kind) for n in nums}
    assert (2.38, "percent") in kinds
    assert (1410 * 1e7, "currency_inr") in kinds
    assert (1 * 1e9, "currency_usd") in kinds
    assert (1.4, "ratio") in kinds


def test_bare_numbers_without_currency_word_are_not_extracted():
    text = "The filing was dated 2025 and referenced clause 30."
    nums = extract_numeric_claims(text)
    assert nums == []


def test_no_symbol_crore_is_treated_as_inr():
    nums = extract_numeric_claims("Advances grew to 1,410 crore this quarter.")
    assert len(nums) == 1
    assert nums[0].kind == "currency_inr"
    assert nums[0].value == 1410 * 1e7


# ── build_allowed_values + validate_numeric_claims ───────────────────────

def test_supported_percent_from_financial_fact_passes():
    fc = VerifiedFinancialContext(symbol="ICICIBANK", facts=[_fact("roa", "Return on Assets", 0.0238, "pct")], as_of="FY2025Q3")
    bundle = _FakeBundle(financial_context=fc)
    allowed = build_allowed_values(bundle, [])
    passed, errors = validate_numeric_claims("ICICI Bank's ROA stood at 2.38% this quarter.", allowed)
    assert passed is True
    assert errors == []


def test_unsupported_percent_fails_with_real_error_detail():
    fc = VerifiedFinancialContext(symbol="ICICIBANK", facts=[_fact("roa", "Return on Assets", 0.0238, "pct")], as_of="FY2025Q3")
    bundle = _FakeBundle(financial_context=fc)
    allowed = build_allowed_values(bundle, [])
    passed, errors = validate_numeric_claims("ICICI Bank's ROA stood at 9.9% this quarter.", allowed)
    assert passed is False
    assert len(errors) == 1
    assert errors[0]["raw_text"].strip() == "9.9%"


def test_inr_fact_matches_crore_phrasing():
    fc = VerifiedFinancialContext(
        symbol="ICICIBANK",
        facts=[_fact("deposits", "Deposits", 14128249500000.0, "inr", fiscal_year=2024, fiscal_quarter=None)],
        as_of="FY2024",
    )
    bundle = _FakeBundle(financial_context=fc)
    allowed = build_allowed_values(bundle, [])

    passed_crore, _ = validate_numeric_claims("Deposits reached ₹14,12,825 crore.", allowed)
    assert passed_crore is True
    passed_wrong, errors = validate_numeric_claims("Deposits reached ₹20,00,000 crore.", allowed)
    assert passed_wrong is False
    assert len(errors) == 1


def test_number_verbatim_in_evidence_title_is_allowed():
    evidence = [_evidence("ICICI Bank priced USD 1 billion Senior Unsecured Notes at a fixed rate.")]
    bundle = _FakeBundle()
    allowed = build_allowed_values(bundle, evidence)
    passed, errors = validate_numeric_claims("The bank raised $1 billion through this note issuance.", allowed)
    assert passed is True
    assert errors == []


def test_currency_conversion_not_in_evidence_is_rejected():
    """A model 'helpfully' converting $1 billion to a guessed INR figure
    introduces a genuinely new number the bundle never supplied -- this
    must fail, not pass as a formatting equivalent."""
    evidence = [_evidence("ICICI Bank priced USD 1 billion Senior Unsecured Notes at a fixed rate.")]
    bundle = _FakeBundle()
    allowed = build_allowed_values(bundle, evidence)
    passed, errors = validate_numeric_claims("The bank raised roughly ₹8,300 crore through this note issuance.", allowed)
    assert passed is False
    assert any("8,300" in e["raw_text"] or "8300" in e["raw_text"] for e in errors)


def test_price_move_pct_supported_in_both_signed_and_unsigned_form():
    bundle = _FakeBundle(price_move_pct=-1.4)
    allowed = build_allowed_values(bundle, [])
    passed_unsigned, _ = validate_numeric_claims("ICICIBANK shares declined 1.4% on the day.", allowed)
    passed_signed, _ = validate_numeric_claims("ICICIBANK shares moved -1.4% on the day.", allowed)
    assert passed_unsigned is True
    assert passed_signed is True


def test_no_facts_or_evidence_means_any_number_is_unsupported():
    bundle = _FakeBundle()
    allowed = build_allowed_values(bundle, [])
    passed, errors = validate_numeric_claims("Revenue grew 12% year over year.", allowed)
    assert passed is False
    assert len(errors) == 1


# ── period validation ─────────────────────────────────────────────────────

def test_period_matching_a_real_fact_year_passes():
    fc = VerifiedFinancialContext(symbol="ICICIBANK", facts=[_fact("roa", "Return on Assets", 0.0238, "pct", fiscal_year=2025, fiscal_quarter=3)], as_of="FY2025Q3")
    passed, errors = validate_period_claims("As of FY2025 Q3, ROA was 2.38%.", fc, [])
    assert passed is True
    assert errors == []


def test_period_not_matching_any_real_fact_or_evidence_fails():
    fc = VerifiedFinancialContext(symbol="ICICIBANK", facts=[_fact("roa", "Return on Assets", 0.0238, "pct", fiscal_year=2025, fiscal_quarter=3)], as_of="FY2025Q3")
    passed, errors = validate_period_claims("As of FY2022, ROA was 2.38%.", fc, [])
    assert passed is False
    assert errors == [{"fiscal_year": 2022, "fiscal_quarter": None}]


def test_period_extraction_handles_two_digit_fiscal_year():
    assert extract_period_claims("Results for FY25 were strong.") == [(2025, None)]
