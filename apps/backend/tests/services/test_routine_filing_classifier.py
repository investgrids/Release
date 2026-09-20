"""
routine_filing_classifier.py -- pure-function unit tests. No DB, no LLM,
matches the module's own explicit "offline dry-run only" contract.
"""
from __future__ import annotations

from app.services.opportunity_v2.routine_filing_classifier import (
    classify_development,
    classify_opportunity,
)


def test_real_postal_ballot_with_no_material_content_is_routine():
    c = classify_development(
        "dev-1",
        "Zee Learn Limited has submitted the Exchange a copy Srutinizers report of Postal Ballot. "
        "Further, the company has informed the Exchange regarding voting results.",
        ["corporate"],
    )
    assert c.is_routine is True
    assert c.matched_escape_patterns == []


def test_real_smp_appointment_canary_case_is_routine():
    c = classify_development("dev-1", "Appointment of Senior Management Personnel (SMP)", ["regulatory"])
    assert c.is_routine is True


def test_postal_ballot_approving_a_merger_is_not_routine_material_escape_wins():
    c = classify_development(
        "dev-1",
        "Postal Ballot results: shareholders approve the Scheme of Amalgamation with XYZ Ltd",
        ["corporate"],
    )
    assert c.is_routine is False
    assert c.matched_escape_patterns  # a real escape keyword fired


def test_regulation_30_disclosure_of_an_acquisition_is_not_routine():
    c = classify_development(
        "dev-1",
        "Disclosure under Regulation 30 -- further acquisition of equity stake in a subsidiary",
        ["regulatory"],
    )
    assert c.is_routine is False


def test_ceo_resignation_is_never_routine_even_with_no_other_material_keyword():
    c = classify_development("dev-1", "Resignation of Managing Director", ["corporate"])
    assert c.is_routine is False


def test_gst_show_cause_notice_is_escaped_never_suppressed():
    c = classify_development(
        "dev-1",
        "Disclosure under Regulation 30 -- Receipt of Show Cause Notice from GST Authorities",
        ["regulatory"],
    )
    assert c.is_routine is False


def test_earnings_event_type_is_never_routine_regardless_of_title():
    c = classify_development("dev-1", "Postal Ballot voting results", ["earnings"])
    assert c.is_routine is False


def test_macro_event_type_is_never_routine():
    c = classify_development("dev-1", "Annual General Meeting", ["macro"])
    assert c.is_routine is False


def test_no_linked_event_at_all_can_still_be_routine_if_title_matches():
    c = classify_development("dev-1", "Re-appointment of Director", [])
    assert c.is_routine is True


def test_genuinely_material_real_news_is_never_flagged_routine():
    c = classify_development("dev-1", "Reliance announces $2B acquisition of renewable energy assets", ["corporate"])
    assert c.is_routine is False


def test_unrelated_real_news_with_no_routine_pattern_is_not_routine():
    c = classify_development("dev-1", "RBI cuts repo rate by 25bps", ["macro"])
    assert c.is_routine is False


def test_synthetic_exposure_title_is_inventoried_separately_not_classified_either_way():
    c = classify_development("dev-1", "Directly exposed to Energy opportunity through core operations.", ["corporate"])
    assert c.is_synthetic_exposure is True
    assert c.is_routine is False


# ── Opportunity-level: require EVERY linked Development to qualify ──────────

def test_opportunity_flagged_only_when_every_development_is_routine():
    a = classify_development("dev-a", "Postal Ballot voting results", ["corporate"])
    b = classify_development("dev-b", "Re-appointment of Director", ["corporate"])
    assert classify_opportunity([a, b]) is True


def test_one_material_development_keeps_the_whole_opportunity_out_of_scope():
    a = classify_development("dev-a", "Postal Ballot voting results", ["corporate"])
    b = classify_development("dev-b", "Reliance announces $2B acquisition", ["corporate"])
    assert classify_opportunity([a, b]) is False


def test_synthetic_exposure_developments_never_drive_the_opportunity_decision():
    a = classify_development("dev-a", "Postal Ballot voting results", ["corporate"])
    synthetic = classify_development("dev-b", "Directly exposed to Energy opportunity through core operations.", ["corporate"])
    assert classify_opportunity([a, synthetic]) is True  # the one real dev is routine; synthetic entry doesn't block it


def test_opportunity_with_only_synthetic_exposure_developments_is_never_flagged():
    synthetic = classify_development("dev-a", "Directly exposed to Energy opportunity through core operations.", ["corporate"])
    assert classify_opportunity([synthetic]) is False
