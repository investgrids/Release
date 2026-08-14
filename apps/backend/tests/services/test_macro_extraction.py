"""
Regression suite — app.services.macro_extraction (Phase 7, 2026-08 audit).
Pure unit tests, no DB, no network — real-shaped PIB/RBI-style headlines
in, either a confidently-extracted structured value or None out, never a
guessed/partial value.
"""
from __future__ import annotations

from app.services.macro_extraction import extract_macro_release


def test_extracts_gst_collection_in_crore():
    result = extract_macro_release(
        "GST revenue collection for July 2026 stands at ₹1,87,000 crore, up 8% YoY",
        "Gross GST collections rose against ₹1,73,000 crore in June 2026",
    )
    assert result is not None
    assert result["metric"] == "GST"
    assert result["release_value"] == 187000.0
    assert result["unit"] == "₹ crore"
    assert result["previous_value"] == 173000.0
    assert result["expected_value"] is None
    assert result["period"] == "July 2026"


def test_extracts_cpi_inflation_percent():
    result = extract_macro_release(
        "CPI inflation eases to 4.2% in July 2026", "against 4.8% in June 2026",
    )
    assert result is not None
    assert result["metric"] == "CPI"
    assert result["release_value"] == 4.2
    assert result["unit"] == "%"
    assert result["previous_value"] == 4.8


def test_extracts_wpi_percent():
    result = extract_macro_release("WPI inflation stands at 2.1% in July 2026")
    assert result is not None
    assert result["metric"] == "WPI"
    assert result["release_value"] == 2.1


def test_extracts_iip_growth_percent():
    result = extract_macro_release("IIP grows by 5.3% in June 2026")
    assert result is not None
    assert result["metric"] == "IIP"
    assert result["release_value"] == 5.3


def test_extracts_gdp_growth_percent():
    result = extract_macro_release("GDP growth estimated at 7.2% for Q1 FY27")
    assert result is not None
    assert result["metric"] == "GDP"
    assert result["release_value"] == 7.2
    assert result["period"] == "Q1 FY27"


def test_extracts_trade_deficit_billion():
    result = extract_macro_release(
        "India's trade deficit narrows to $19.8 billion in July 2026",
        "against $21.3 billion in the previous month",
    )
    assert result is not None
    assert result["metric"] == "TRADE_BALANCE"
    assert result["release_value"] == 19.8
    assert result["previous_value"] == 21.3
    assert result["unit"] == "$ billion"


def test_extracts_fiscal_deficit_percent():
    result = extract_macro_release("Fiscal deficit at 32.5% of full year target in Q1 FY27")
    assert result is not None
    assert result["metric"] == "FISCAL_DEFICIT"
    assert result["release_value"] == 32.5


def test_never_fabricates_expected_value():
    result = extract_macro_release("CPI inflation eases to 4.2% in July 2026")
    assert result is not None
    assert result["expected_value"] is None


def test_returns_none_for_generic_press_release_with_no_number():
    result = extract_macro_release(
        "Finance Minister to hold pre-budget consultations with industry stakeholders",
        "Meeting scheduled for next week in New Delhi",
    )
    assert result is None


def test_returns_none_for_unrelated_headline_even_with_numbers_present():
    # A number is present, but no known metric keyword is anywhere near
    # it — must not guess a metric from an unrelated number.
    result = extract_macro_release(
        "Minister inaugurates 25 new railway stations across 5 states",
    )
    assert result is None


def test_returns_none_for_metric_keyword_with_no_number():
    # The metric word is present but with no parseable value attached —
    # must not default to any number.
    result = extract_macro_release("RBI to release CPI data next Monday")
    assert result is None


def test_sector_sensitivity_attached_deterministically():
    result = extract_macro_release("CPI inflation eases to 4.2% in July 2026")
    assert result is not None
    assert "Banking" in result["affected_sectors"]
    assert result["affected_companies"] == []  # never guessed


def test_importance_assigned_per_metric_not_ai_derived():
    gdp = extract_macro_release("GDP growth estimated at 7.2% for Q1 FY27")
    gst = extract_macro_release("GST revenue collection for July 2026 stands at ₹1,87,000 crore")
    assert gdp is not None and gdp["importance"] == "Critical"
    assert gst is not None and gst["importance"] == "Medium"


def test_release_date_parsed_from_published_at():
    result = extract_macro_release(
        "CPI inflation eases to 4.2% in July 2026", published_at="2026-08-12",
    )
    assert result is not None
    assert result["release_date"] is not None
    assert result["release_date"].year == 2026
    assert result["release_date"].month == 8
    assert result["release_date"].day == 12


def test_missing_published_at_leaves_release_date_none():
    result = extract_macro_release("CPI inflation eases to 4.2% in July 2026", published_at="")
    assert result is not None
    assert result["release_date"] is None
