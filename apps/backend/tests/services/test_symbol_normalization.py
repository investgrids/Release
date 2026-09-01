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


# ── P0-CD2 Generation Containment (2026-09-01): symbol<->name cross-check ────
# Real, confirmed production bug: "Bajaj Finance" (a real company) stored
# under BAJAJFINSV -- the real, valid symbol for Bajaj Finserv, a DIFFERENT
# real, listed company. The old normalize_symbol trusted any symbol found in
# the universe unconditionally, never checking it actually matched the given
# name.

def test_valid_symbol_for_wrong_company_is_corrected_via_name():
    assert normalize_symbol("BAJAJFINSV", "Bajaj Finance") == "BAJFINANCE"


def test_valid_symbol_for_wrong_company_with_no_correct_match_returns_none():
    # The name doesn't resolve to anything real either -- must not fall
    # back to the wrong-but-valid symbol just because it exists somewhere
    # in the universe.
    assert normalize_symbol("BAJAJFINSV", "Totally Fictional Finance Ltd") is None


def test_matching_symbol_and_name_still_resolves():
    assert normalize_symbol("BAJAJFINSV", "Bajaj Finserv") == "BAJAJFINSV"


def test_symbol_with_no_name_given_still_trusted():
    # Unchanged behavior when there's nothing to cross-check against.
    assert normalize_symbol("BAJAJFINSV") == "BAJAJFINSV"


# ── P0-CD2: ambiguous-word false positives ───────────────────────────────────
# Real, confirmed bug: "apollo" is a substring of THREE different real
# companies' names (Apollo Hospitals, APL Apollo Tubes, Apollo Tyres) in the
# universe. A short/generic alias match must not confidently resolve a
# DIFFERENT real company (Apollo Micro Systems, not in this universe at all)
# to Apollo Hospitals just because they share a common leading word.

def test_ambiguous_leading_word_does_not_resolve_unrelated_company():
    assert normalize_symbol(None, "Apollo Micro Systems") is None


def test_ambiguous_word_still_resolves_its_own_exact_company():
    assert normalize_symbol(None, "Apollo Hospitals") == "APOLLOHOSP"
    # APOLLOTYRE's only registered alias is the squashed "apollotyre" (no
    # space), so a spaced "Apollo Tyres" doesn't substring-match it either
    # way (a pre-existing data gap, unrelated to this fix) — its own full
    # registered name always matches, which is what this test is for.
    assert normalize_symbol(None, "Apollo Tyres Ltd") == "APOLLOTYRE"


def test_generic_english_word_alias_does_not_resolve_unrelated_company():
    # Real shadow-corpus finding: "Reliance Home Finance" (a real company
    # not in this curated universe) incorrectly resolved to Home First
    # Finance purely via its bare "home" alias -- too generic a word to
    # trust against a name it doesn't actually belong to, even though
    # "home" doesn't collide with any OTHER company in this universe (so
    # the ambiguity check alone didn't catch it).
    assert normalize_symbol(None, "Reliance Home Finance") is None
    # The company's own full name must still resolve correctly.
    assert normalize_symbol(None, "Home First Finance Company India Ltd") == "HOMEFIRST"


def test_wrong_real_symbol_for_unlisted_company_returns_none_not_a_different_guess():
    # The exact real bug shape: the LLM stored RHIM (a real but entirely
    # unrelated company, RHI Magnesita India) for "Reliance Home Finance".
    # Must be corrected to None, not silently swapped for a different wrong
    # guess.
    assert normalize_symbol("RHIM", "Reliance Home Finance") is None


def test_short_unambiguous_alias_still_resolves():
    # The fix must not become so conservative that legitimate short
    # aliases stop working -- "tcs"/"infosys" don't collide with any other
    # real company in the universe.
    assert normalize_symbol(None, "TCS") == "TCS"
    assert normalize_symbol(None, "Infosys") == "INFY"
    assert normalize_symbol("tcs") == "TCS"


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
