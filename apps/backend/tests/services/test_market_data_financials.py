"""
Financial statement extraction (Company redesign Financials sub-tabs) —
pure logic tests against real pandas DataFrame shapes matching yfinance's
own real row labels (confirmed live against RELIANCE.NS before writing
the extraction code — see market_data.py's own module comment). No
network calls: these test _extract_statement_rows/_is_real_number
directly against synthetic-but-realistically-shaped DataFrames, not the
live yfinance fetch itself (get_stock_financials is exercised live in
the completion notes instead, matching this session's established
pattern for yfinance-network-dependent code).
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from app.services.market_data import (
    _extract_statement_rows, _is_real_number, _annual_label, _quarterly_label,
    _INCOME_STATEMENT_ROWS, _BALANCE_SHEET_ROWS, _CASH_FLOW_ROWS,
)


def test_is_real_number_rejects_none_and_nan():
    assert _is_real_number(None) is False
    assert _is_real_number(float("nan")) is False
    assert _is_real_number(0.0) is True
    assert _is_real_number(123.45) is True


def test_extract_income_statement_real_values_and_unit_conversion():
    """A real yfinance-shaped income statement DataFrame: currency rows
    convert to Crore (÷1e7), the tax-rate row converts from a real 0-1
    fraction to a 0-100 percent, EPS is left as-is."""
    cols = [pd.Timestamp("2026-03-31")]
    df = pd.DataFrame({cols[0]: [
        1057219000000.0,  # Total Revenue (real, in raw rupees)
        204906000000.0,   # EBITDA
        121377000000.0,   # Operating Income
        123162000000.0,   # Pretax Income
        27552000000.0,    # Tax Provision
        0.224,             # Tax Rate For Calcs (real 0-1 fraction)
        80775000000.0,     # Net Income
        59.69,              # Diluted EPS
    ]}, index=[
        "Total Revenue", "EBITDA", "Operating Income", "Pretax Income",
        "Tax Provision", "Tax Rate For Calcs", "Net Income", "Diluted EPS",
    ])

    rows = _extract_statement_rows(df, _INCOME_STATEMENT_ROWS, _annual_label)
    assert len(rows) == 1
    r = rows[0]
    assert r["period"] == "FY26"
    assert r["revenue"] == 105721.9          # 1,057,219,000,000 / 1e7
    assert r["ebitda"] == 20490.6
    assert r["effective_tax_rate"] == 22.4    # 0.224 * 100
    assert r["eps"] == 59.69                  # raw, no conversion


def test_extract_statement_rows_never_fabricates_missing_fields():
    """A real DataFrame missing some real rows (e.g. no Tax Provision this
    period) must leave that specific field null, never 0 or interpolated
    — while still including the period since other real fields exist."""
    cols = [pd.Timestamp("2026-03-31")]
    df = pd.DataFrame({cols[0]: [1057219000000.0]}, index=["Total Revenue"])

    rows = _extract_statement_rows(df, _INCOME_STATEMENT_ROWS, _annual_label)
    assert len(rows) == 1
    r = rows[0]
    assert r["revenue"] == 105721.9
    assert r["ebitda"] is None
    assert r["tax_expense"] is None
    assert r["eps"] is None


def test_extract_statement_rows_drops_a_period_with_zero_real_data():
    """A column where every candidate row is NaN must not appear at all
    — an all-null period is the honest absence of data, not a real
    (empty) reporting period."""
    cols = [pd.Timestamp("2026-03-31")]
    df = pd.DataFrame({cols[0]: [float("nan")]}, index=["Total Revenue"])
    rows = _extract_statement_rows(df, _INCOME_STATEMENT_ROWS, _annual_label)
    assert rows == []


def test_extract_statement_rows_empty_dataframe_returns_empty_list():
    """The real, live-confirmed case (e.g. RELIANCE's own quarterly
    cashflow, and any smaller company's full statement set) — an empty
    or missing DataFrame must return [], never raise, never fabricate a
    period."""
    assert _extract_statement_rows(None, _CASH_FLOW_ROWS, _quarterly_label) == []
    assert _extract_statement_rows(pd.DataFrame(), _CASH_FLOW_ROWS, _quarterly_label) == []


def test_extract_balance_sheet_candidate_key_fallback():
    """Real row-label variance across companies/regions — Stockholders
    Equity may appear as "Common Stock Equity" instead. The candidate-key
    fallback (same real pattern _REV_KEYS/_NI_KEYS already used) must
    still find it."""
    cols = [pd.Timestamp("2026-03-31")]
    df = pd.DataFrame({cols[0]: [500000000000.0]}, index=["Common Stock Equity"])
    rows = _extract_statement_rows(df, _BALANCE_SHEET_ROWS, _annual_label)
    assert len(rows) == 1
    assert rows[0]["shareholders_equity"] == 50000.0


def test_quarterly_label_format():
    ts = pd.Timestamp("2026-06-30")
    assert _quarterly_label(ts) == "Jun '26"
