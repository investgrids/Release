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
    _statement_scale, _fmt_large,
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


# Currency/unit correctness fix (2026-09-27, owner-directed re-audit).
# Confirmed live before this fix: INFY reports financialCurrency="USD"
# (real annual revenue $20.158B) while get_stock_detail unconditionally
# divided by 1e7 assuming INR — the exact bug already found and fixed once
# for the sibling get_stock_financials() (INFY, commit c844920), except
# THAT fix's own `(financial_currency or "INR")` default still silently
# assumed INR whenever financialCurrency was missing, which is the same
# defect moved rather than closed. _statement_scale now returns None for
# a missing/unrecognized currency, and _extract_statement_rows nulls every
# "currency"-unit field rather than guessing a scale, in that case.
class TestStatementScale:
    def test_known_inr_currency_returns_the_crore_scale(self):
        assert _statement_scale("INR") == (1e7, "₹", "Crore")

    def test_known_usd_currency_returns_the_million_scale(self):
        assert _statement_scale("USD") == (1e6, "$", "Million")

    def test_currency_matching_is_case_insensitive(self):
        assert _statement_scale("inr") == (1e7, "₹", "Crore")
        assert _statement_scale("usd") == (1e6, "$", "Million")

    def test_missing_currency_returns_none_never_the_inr_default(self):
        """The exact regression this fix closes: a missing financialCurrency
        must never be silently treated as INR."""
        assert _statement_scale(None) is None
        assert _statement_scale("") is None

    def test_unrecognized_currency_returns_none_never_the_inr_default(self):
        """A real currency yfinance could report that this app has no
        confirmed scale for (e.g. EUR, GBP, JPY) must also withhold rather
        than guess — not just a genuinely-missing value."""
        assert _statement_scale("EUR") is None
        assert _statement_scale("GBP") is None


class TestExtractStatementRowsCurrencyAware:
    """_extract_statement_rows(currency_scale=...) — the shared function
    both get_stock_financials and get_stock_detail rely on for currency-
    aware scaling."""

    def _income_df(self):
        cols = [pd.Timestamp("2026-03-31")]
        return pd.DataFrame({cols[0]: [
            1057219000000.0,  # Total Revenue
            204906000000.0,   # EBITDA
            121377000000.0,   # Operating Income
            123162000000.0,   # Pretax Income
            27552000000.0,    # Tax Provision
            0.224,             # Tax Rate For Calcs
            80775000000.0,     # Net Income
            59.69,              # Diluted EPS
        ]}, index=[
            "Total Revenue", "EBITDA", "Operating Income", "Pretax Income",
            "Tax Provision", "Tax Rate For Calcs", "Net Income", "Diluted EPS",
        ])

    def test_inr_scale_divides_currency_fields_by_1e7(self):
        rows = _extract_statement_rows(self._income_df(), _INCOME_STATEMENT_ROWS, _annual_label, currency_scale=1e7)
        assert len(rows) == 1
        assert rows[0]["revenue"] == 105721.9

    def test_usd_scale_divides_currency_fields_by_1e6_not_1e7(self):
        """The real fix: a USD-reporting company's real figures must scale
        to Million, not be mislabeled at the INR/Crore divisor."""
        rows = _extract_statement_rows(self._income_df(), _INCOME_STATEMENT_ROWS, _annual_label, currency_scale=1e6)
        assert len(rows) == 1
        assert rows[0]["revenue"] == 1057219.0  # 1,057,219,000,000 / 1e6
        assert rows[0]["revenue"] != 105721.9   # never the INR-scale number

    def test_unconfirmed_currency_nulls_every_currency_field_but_keeps_percent_and_raw_fields(self):
        """The honest response to a genuinely unknown reporting currency:
        withhold the numbers that would be wrong if mislabeled (revenue,
        ebitda, net_profit, etc.), while percent/raw fields that don't
        depend on currency (effective_tax_rate, eps) are unaffected — same
        "null over fabricated" rule as a missing line item."""
        rows = _extract_statement_rows(self._income_df(), _INCOME_STATEMENT_ROWS, _annual_label, currency_scale=None)
        assert len(rows) == 1  # the period survives because eps/tax_rate are still real
        r = rows[0]
        assert r["revenue"] is None
        assert r["ebitda"] is None
        assert r["net_profit"] is None
        assert r["effective_tax_rate"] == 22.4   # percent — unaffected by currency
        assert r["eps"] == 59.69                  # raw — unaffected by currency

    def test_unconfirmed_currency_drops_a_period_that_is_all_currency_fields(self):
        """Balance Sheet / Cash Flow rows are ALL "currency"-typed (no
        percent/raw fallback) — with an unconfirmed currency, a period with
        zero survivable fields must be dropped entirely, exactly like a
        period with no real data at all."""
        cols = [pd.Timestamp("2026-03-31")]
        df = pd.DataFrame({cols[0]: [500000000000.0]}, index=["Common Stock Equity"])
        rows = _extract_statement_rows(df, _BALANCE_SHEET_ROWS, _annual_label, currency_scale=None)
        assert rows == []


# Currency/unit correctness fix, second instance (2026-09-27): free_cashflow
# was the only real caller of _fmt_large and hardcoded "₹" regardless of
# the company's real financialCurrency — the identical mislabeling bug
# already fixed for annual_financials/quarterly_revenue in the same file,
# missed the first time because it lives in a separate formatting helper.
class TestFmtLargeCurrencyAware:
    def test_inr_uses_the_real_indian_numbering_convention(self):
        assert _fmt_large(5_000_000_000, "INR") == "₹5.0B"
        assert _fmt_large(50_000_000, "INR") == "₹5Cr"

    def test_usd_uses_the_standard_international_convention_never_crore_or_lakh(self):
        assert _fmt_large(5_000_000_000, "USD") == "$5.0B"
        assert "Cr" not in _fmt_large(5_000_000_000, "USD")
        assert "L" not in _fmt_large(5_000_000_000, "USD")

    def test_missing_currency_withholds_the_figure_never_defaults_to_inr(self):
        assert _fmt_large(5_000_000_000, None) == "—"

    def test_unrecognized_currency_withholds_rather_than_guess_a_convention(self):
        assert _fmt_large(5_000_000_000, "EUR") == "—"

    def test_currency_matching_is_case_insensitive(self):
        assert _fmt_large(5_000_000_000, "usd") == "$5.0B"
