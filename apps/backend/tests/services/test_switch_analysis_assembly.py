"""
switch_analysis assembly (aev2.2, 2026-09-22) — deterministic, from
CoreAnswer and the existing evidence catalog only. See aev2/switch_
analysis.py's own docstring for exactly which 3 dimensions are
implemented and why business_exposure/risk_evidence are not.

Follows test_aev2_build1_restructuring.py's own pattern: build a plain
V3 response dict, project it through the real from_v3_response(), then
assemble through the real assemble_aev2() entry point — never construct
a CoreAnswer or a switch_analysis dict by hand.
"""
from __future__ import annotations

from app.services.ai_search.aev2.assemble import assemble_aev2
from app.services.ai_search.aev2.language_gate import FALLBACK_TEXT
from app.services.ai_search.aev2.mode import AEV2Mode
from app.services.ai_search.core_answer import from_v3_response

BEL = {"symbol": "BEL", "name": "Bharat Electronics Ltd"}
HAL = {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd"}

BEL_EVENT = {
    "id": "e-bel-1", "title": "BEL wins defence order worth 1,200 crore",
    "date": "2026-09-18", "companies": [BEL],
}
HAL_EVENT = {
    "id": "e-hal-1", "title": "HAL delivers first batch of Tejas Mk1A jets",
    "date": "2026-09-10", "companies": [HAL],
}


def _v3_response(**overrides) -> dict:
    base = {
        "query": "Should I continue holding BEL or switch to HAL?",
        "response_id": "resp-switch-1",
        "specialist": "comparison",
        "intent": "switch",
        "switch_holding": "Bharat Electronics Ltd",
        "switch_target": "Hindustan Aeronautics Ltd",
        "answer": {
            "bottom_line": "BEL's recent order win and HAL's delivery milestone both reflect strong defence-sector demand.",
            "summary": "ok",
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "risks": [],
        },
        "companies": [
            {"symbol": "BEL", "name": "Bharat Electronics Ltd", "price": "285.40", "change": "+1.10%",
             "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
            {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd", "price": "4,512.00", "change": "-0.30%",
             "positive": False, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        ],
        "related_events": [dict(BEL_EVENT), dict(HAL_EVENT)],
        "news": [], "policies": [],
        "investment_verdict": {"horizon": "6-12 months"},
        "confidence_breakdown": {
            "evidence_quality": 70.0, "market_confirmation": 60.0,
            "historical_similarity": 40.0, "data_freshness": 90.0,
        },
    }
    base.update(overrides)
    return base


def _assemble(**overrides):
    core = from_v3_response(_v3_response(**overrides))
    return assemble_aev2(core, mode=AEV2Mode.PUBLIC)


def test_switch_analysis_is_none_for_a_non_comparison_specialist():
    result = _assemble(specialist="company")
    assert result["switch_analysis"] is None


def test_switch_analysis_is_none_for_a_neutral_comparison_intent_even_with_two_real_companies():
    """2026-09-22 correction: decision_intent.py's holding/target
    extraction resolves for ANY comparison-shaped query, including a
    plain "Compare BEL and HAL" — without checking core.intent against
    SWITCH_LIKE_INTENTS, this would have mislabeled a neutral comparison
    as a "switch" with a "current holding". See comparison.py for the
    neutral counterpart this query should get instead."""
    result = _assemble(query="Compare BEL and HAL", intent="compare")
    assert result["switch_analysis"] is None


def test_switch_analysis_is_none_when_holding_or_target_does_not_resolve():
    result = _assemble(switch_holding="Nonexistent Company", switch_target="Hindustan Aeronautics Ltd")
    assert result["switch_analysis"] is None


def test_switch_analysis_is_none_when_holding_and_target_are_the_same_company():
    result = _assemble(switch_target="Bharat Electronics Ltd")
    assert result["switch_analysis"] is None


def test_switch_analysis_resolves_current_and_alternative_by_name():
    result = _assemble()
    sw = result["switch_analysis"]
    assert sw["relationship"] == "switch"
    assert sw["current_company"] == {"symbol": "BEL", "name": "Bharat Electronics Ltd"}
    assert sw["alternative_company"] == {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd"}


def test_direct_comparison_is_validated_when_bottom_line_passes_citation_check():
    result = _assemble()
    dc = result["switch_analysis"]["direct_comparison"]
    assert dc["validation_status"] == "validated"
    assert dc["text"] == "BEL's recent order win and HAL's delivery milestone both reflect strong defence-sector demand."
    assert set(dc["evidence_refs"]) == {"event:e-bel-1", "event:e-hal-1"}


def test_direct_comparison_fails_closed_on_advisory_language():
    result = _assemble(answer={
        "bottom_line": "You should switch from BEL to HAL for a stronger buy opportunity.",
        "summary": "ok", "what_happened": "", "why_it_happened": "", "immediate_impact": "",
        "medium_term": "", "long_term": "", "risks": [],
    })
    dc = result["switch_analysis"]["direct_comparison"]
    assert dc["validation_status"] == "unvalidated"
    assert dc["text"] == FALLBACK_TEXT["direct_comparison"]
    assert dc["evidence_refs"] == []


def test_direct_comparison_fails_closed_on_an_unsupported_number():
    result = _assemble(answer={
        "bottom_line": "BEL's order is worth 99,999 crore, dwarfing HAL's delivery.",
        "summary": "ok", "what_happened": "", "why_it_happened": "", "immediate_impact": "",
        "medium_term": "", "long_term": "", "risks": [],
    })
    dc = result["switch_analysis"]["direct_comparison"]
    assert dc["validation_status"] == "unvalidated"
    assert dc["text"] == FALLBACK_TEXT["direct_comparison"]


def test_recent_developments_dimension_is_comparable_when_both_companies_have_attributed_events():
    result = _assemble()
    dim = next(d for d in result["switch_analysis"]["dimensions"] if d["key"] == "recent_developments")
    assert dim["comparable"] is True
    assert "BEL wins defence order" in dim["current_company"]["display"]
    assert "HAL delivers first batch" in dim["alternative_company"]["display"]
    assert dim["current_company"]["evidence_refs"] == ["event:e-bel-1"]


def test_recent_developments_dimension_is_not_comparable_when_only_one_company_has_evidence():
    result = _assemble(related_events=[dict(BEL_EVENT)])
    dim = next(d for d in result["switch_analysis"]["dimensions"] if d["key"] == "recent_developments")
    assert dim["comparable"] is False
    assert dim["alternative_company"] is None
    assert "HAL" in dim["unavailable_reason"]


def test_price_reaction_dimension_comparable_when_both_prices_fetched():
    result = _assemble()
    dim = next(d for d in result["switch_analysis"]["dimensions"] if d["key"] == "price_reaction")
    assert dim["comparable"] is True
    assert dim["current_company"]["display"] == "285.40 (+1.10%)"
    assert dim["alternative_company"]["display"] == "4,512.00 (-0.30%)"


def test_price_reaction_dimension_omits_disadvantage_framing_when_one_fetch_failed():
    result = _assemble(companies=[
        {"symbol": "BEL", "name": "Bharat Electronics Ltd", "price": "285.40", "change": "+1.10%",
         "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd", "price": "—", "change": None, "positive": False},
    ])
    dim = next(d for d in result["switch_analysis"]["dimensions"] if d["key"] == "price_reaction")
    assert dim["comparable"] is False
    assert dim["alternative_company"] is None
    assert "HAL" in dim["unavailable_reason"]
    # Never implies the missing side is worse — no "disadvantage"/"weaker" language.
    assert "disadvantage" not in dim["unavailable_reason"].lower()
    assert "weak" not in dim["unavailable_reason"].lower()


def test_evidence_freshness_dimension_uses_the_most_recent_attributed_date_per_company():
    result = _assemble()
    dim = next(d for d in result["switch_analysis"]["dimensions"] if d["key"] == "evidence_freshness")
    assert dim["comparable"] is True
    assert dim["current_company"]["display"] == "2026-09-18"
    assert dim["alternative_company"]["display"] == "2026-09-10"


def test_conditions_favoring_are_derived_only_from_comparable_dimensions():
    result = _assemble()
    sw = result["switch_analysis"]
    # BEL: 1 development dated 2026-09-18 (more recent than HAL's 2026-09-10).
    favoring_current_text = " ".join(c["text"] for c in sw["conditions_favoring_current"])
    assert "more recent evidence" in favoring_current_text.lower()
    # Equal development counts (1 vs 1) -> recent_developments contributes
    # no condition to either side, only evidence_freshness does.
    assert sw["conditions_favoring_alternative"] == []


def test_what_changes_the_comparison_is_honestly_empty_with_no_deterministic_source():
    result = _assemble()
    assert result["switch_analysis"]["what_changes_the_comparison"] == []


def test_business_exposure_and_risk_evidence_dimensions_are_not_implemented():
    """Phase-one scope, not an oversight — see aev2/switch_analysis.py's
    module docstring for why neither has a real per-company data source
    in CoreAnswer today."""
    result = _assemble()
    keys = {d["key"] for d in result["switch_analysis"]["dimensions"]}
    assert keys == {"recent_developments", "price_reaction", "evidence_freshness"}
