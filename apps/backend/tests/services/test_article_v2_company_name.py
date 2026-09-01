"""
Article V2 — shared company-name resolution tests (C6.1 hardening,
owner review 2026-09-01). Regression coverage for the two real bugs
found via the C6 shadow run's manual inspection: SUPREMEENG (a garbled
real filing header wrongly captured as the "company name") and NAZARA
(present-tense "informs the Exchange" not recognized, silently falling
back to the bare symbol while the LLM got the real name right).
"""
from __future__ import annotations

from app.services.article_v2.company_name import resolve_company_name


def test_verified_company_name_is_always_preferred_over_prose_extraction():
    """A real, resolver-verified name must win even when the prose would
    have extracted something different -- never re-derived when already
    known."""
    name = resolve_company_name(
        verified_company_name="Canara Bank",
        primary_evidence_title="CANARA BANK has informed the Exchange about Board Meeting",
        symbol="CANBK",
    )
    assert name == "Canara Bank"


def test_supremeeng_garbled_filing_header_is_rejected_falls_back_to_symbol():
    """The real SUPREMEENG shape: the filing's own text has a garbled
    colon-separated header before "has informed the Exchange" -- must
    NOT be accepted as a company name."""
    title = (
        "SUPREMEENG : 31-Aug-2026 :  The Company has informed the Exchange that the Board Meeting "
        "scheduled for August 29, 2026, has been re-scheduled to August 31, 2026."
    )
    name = resolve_company_name(verified_company_name=None, primary_evidence_title=title, symbol="SUPREMEENG")
    assert name == "SUPREMEENG"
    assert ":" not in name
    assert "The Company" not in name


def test_nazara_present_tense_informs_the_exchange_is_recognized():
    """The real NAZARA shape: present-tense "informs the Exchange" (no
    "has") -- must resolve the real company name, not silently fall
    back to the bare symbol."""
    title = "Nazara Technologies Limited informs the Exchange regarding Proceedings of Extraordinary General Meeting held on August 30, 2026"
    name = resolve_company_name(verified_company_name=None, primary_evidence_title=title, symbol="NAZARA")
    assert name == "Nazara Technologies Limited"


def test_normal_has_informed_phrasing_still_works():
    title = "Atal Realtech Limited has informed the Exchange about Board Meeting to be held on 02-Sep-2026"
    name = resolve_company_name(verified_company_name=None, primary_evidence_title=title, symbol="ATALREAL")
    assert name == "Atal Realtech Limited"


def test_no_title_and_no_verified_name_falls_back_to_symbol():
    name = resolve_company_name(verified_company_name=None, primary_evidence_title=None, symbol="XYZ")
    assert name == "XYZ"


def test_no_verified_name_no_symbol_no_title_returns_generic_label():
    name = resolve_company_name(verified_company_name=None, primary_evidence_title=None, symbol=None)
    assert name == "The company"


def test_overly_long_candidate_is_rejected_as_implausible():
    title = ("X " * 50) + "has informed the Exchange about something"
    name = resolve_company_name(verified_company_name=None, primary_evidence_title=title, symbol="LONGCO")
    assert name == "LONGCO"
