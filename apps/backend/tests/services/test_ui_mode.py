"""
ui_mode.py — the interim projection from existing classification signals
onto one of the 8 first-release AI Answer UI modes (2026-09-21 AI Answer
UI work). Not the eventual consolidated IntentResolution contract — see
the module's own docstring for why.

Test queries are drawn directly from the representative benchmark list
this feature will eventually be verified against end-to-end.
"""
from __future__ import annotations

from app.services.ai_search.ui_mode import UI_MODES, classify_ui_mode


def test_all_eight_first_release_modes_are_registered():
    assert len(UI_MODES) == 8
    assert len(set(UI_MODES)) == 8


def test_direct_company_research():
    mode = classify_ui_mode(
        specialist_kind="company", intent_data={"intent": "decision"},
        entities={"companies": ["HDFCBANK"], "policies": []},
        query="Should I research HDFC Bank now?",
    )
    assert mode == "direct_company_research"


def test_switch_analysis_when_holding_and_target_both_resolved():
    mode = classify_ui_mode(
        specialist_kind="comparison",
        intent_data={"intent": "switch", "holding": "BEL", "target": "HAL"},
        entities={"companies": ["BEL", "HAL"], "policies": []},
        query="Should I switch BEL to HAL?",
    )
    assert mode == "switch_analysis"


def test_company_comparison_without_a_personal_holding():
    mode = classify_ui_mode(
        specialist_kind="comparison",
        intent_data={"intent": "compare", "holding": None, "target": None},
        entities={"companies": ["INFY", "TCS"], "policies": []},
        query="Compare Infosys and TCS.",
    )
    assert mode == "company_comparison"


def test_comparison_specialist_without_holding_target_is_never_switch_analysis():
    """Even if intent_data.intent happens to be a switch-like label, no
    switch_analysis without BOTH a resolved holding and target — a bare
    "vs" comparison is not a personal-holding decision."""
    mode = classify_ui_mode(
        specialist_kind="comparison",
        intent_data={"intent": "buy", "holding": None, "target": "HAL"},
        entities={"companies": ["HAL"], "policies": []},
        query="Is HAL a good buy vs its peers?",
    )
    assert mode == "company_comparison"


def test_factual_lookup():
    mode = classify_ui_mode(
        specialist_kind="company", intent_data={"intent": "general"},
        entities={"companies": ["BAJAJ-AUTO"], "policies": []},
        query="What was Bajaj Auto's Q1 revenue?",
    )
    assert mode == "factual_lookup"


def test_policy_macro_impact_with_no_company_named():
    mode = classify_ui_mode(
        specialist_kind="company", intent_data={"intent": "general"},
        entities={"companies": [], "policies": ["rbi"]},
        query="What is the impact of an RBI rate cut on banking stocks?",
    )
    assert mode == "policy_macro_impact"


def test_policy_macro_impact_even_when_specific_companies_are_named():
    """"How will the defence budget affect BEL and HAL?" names two real
    companies, but the query is about a POLICY event's effect on them,
    not company_specialist's usual single/multi-company research framing
    — policy resolution takes priority."""
    mode = classify_ui_mode(
        specialist_kind="company", intent_data={"intent": "general"},
        entities={"companies": ["BEL", "HAL"], "policies": ["budget"]},
        query="How will the defence budget affect BEL and HAL?",
    )
    assert mode == "policy_macro_impact"


def test_market_pulse_is_set_directly_not_via_this_classifier():
    """Market Pulse short-circuits before entity/specialist resolution
    ever runs (pipeline.py's own market-pulse branch) — this classifier
    is never even called for it; ui_mode="market_pulse" is set directly
    at that call site. Documented here so the registry test suite has
    one place asserting all 8 modes are reachable somehow."""
    assert "market_pulse" in UI_MODES


def test_event_impact():
    mode = classify_ui_mode(
        specialist_kind="company", intent_data={"intent": "news_reaction"},
        entities={"companies": ["RELIANCE"], "policies": []},
        query="Reliance just announced a new refinery — what does this mean?",
    )
    assert mode == "event_impact"


def test_sector_theme_research():
    mode = classify_ui_mode(
        specialist_kind="sector", intent_data={"intent": "general"},
        entities={"companies": [], "sectors": ["energy"], "policies": []},
        query="Which sectors benefit from lower crude prices?",
    )
    assert mode == "sector_theme_research"


def test_known_limitation_sector_shaped_query_without_the_literal_word_sector():
    """Documents a real, pre-existing gap this classifier inherits, not
    introduces: _SECTOR_TRIGGER only fires on the literal word "sector"/
    "industry", so this query never reaches sector_specialist at all —
    it falls to company_specialist, and this classifier's own fallback
    is direct_company_research. See the module's own docstring and the
    2026-09-21 intent audit's Phase 3 remediation item."""
    mode = classify_ui_mode(
        specialist_kind="company", intent_data={"intent": "general"},
        entities={"companies": [], "policies": []},
        query="Why are banking stocks down today?",
    )
    assert mode == "direct_company_research"


def test_defaults_gracefully_on_missing_intent_data_and_entities():
    mode = classify_ui_mode(specialist_kind="company", intent_data=None, entities=None, query="")
    assert mode in UI_MODES
