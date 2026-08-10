"""
Regression suite — symbol_normalization.normalize_symbol, offline.

Built for the AI Newsroom redesign (2026-08-10) after confirming that
`isRealSymbol()` on the frontend only blocklists placeholder strings and
never validates format, so malformed BSE-exchange codes like "BOM:500400"
were passing straight through into broken /companies/BOM:500400 links.
"""
from __future__ import annotations

import pytest

from app.services.symbol_normalization import normalize_symbol


def test_exact_nse_symbol_passes_through():
    assert normalize_symbol("TCS") == "TCS"


def test_lowercase_symbol_is_canonicalized():
    assert normalize_symbol("infy") == "INFY"


def test_bom_numeric_code_resolves_via_company_name():
    # The real production bug: a BSE scrip code with no NSE ticker
    # embedded in it at all, paired with a real company name.
    assert normalize_symbol("BOM:500400", "Tata Power Company Ltd") == "TATAPOWER"


def test_bom_prefixed_real_ticker_resolves():
    assert normalize_symbol("BSE:INFY") == "INFY"


def test_unresolved_malformed_symbol_with_no_name_returns_none():
    assert normalize_symbol("BOM:999999") is None


def test_unresolved_malformed_symbol_with_unrecognized_name_returns_none():
    assert normalize_symbol("BOM:999999", "Totally Fictional Company Ltd") is None


def test_empty_symbol_and_name_returns_none():
    assert normalize_symbol("", "") is None
    assert normalize_symbol(None, None) is None


def test_name_only_resolution_without_symbol():
    assert normalize_symbol("", "Infosys Ltd") == "INFY"


def test_alias_based_name_resolution():
    assert normalize_symbol("", "HCL Technologies Ltd") == "HCLTECH"


@pytest.mark.parametrize("raw_symbol,name", [
    ("BOM:500325", "Reliance Industries Ltd"),
    ("bom:532540", "Tata Consultancy Services Ltd"),
])
def test_known_bse_scrip_codes_resolve_via_name(raw_symbol, name):
    result = normalize_symbol(raw_symbol, name)
    assert result is not None
    assert ":" not in result
