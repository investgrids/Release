"""
ui_mode.py — the interim projection from existing classification signals
onto one of this codebase's known UI modes (2026-09-21 AI Answer UI
work; priority order reordered and 5 explicit unsupported modes added
2026-09-22 per the intent-coverage audit). Not the eventual consolidated
IntentResolution contract — see the module's own docstring for why.

Test queries are drawn directly from the representative benchmark list
this feature will eventually be verified against end-to-end.
"""
from __future__ import annotations

from app.services.ai_search.ui_mode import UI_MODES, classify_ui_mode


def test_all_thirteen_modes_are_registered():
    assert len(UI_MODES) == 13
    assert len(set(UI_MODES)) == 13
    for expected in (
        "direct_company_research", "switch_analysis", "company_comparison",
        "factual_lookup", "policy_macro_impact", "market_pulse", "event_impact",
        "sector_theme_research", "technical_timing", "company_discovery",
        "portfolio_review", "earnings_preview", "multi_company_comparison",
    ):
        assert expected in UI_MODES


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
        entities={"companies": ["BEL", "HAL"], "company_matches": [{"name": "BEL"}, {"name": "HAL"}], "policies": []},
        query="Should I switch BEL to HAL?",
    )
    assert mode == "switch_analysis"


def test_company_comparison_without_a_personal_holding():
    mode = classify_ui_mode(
        specialist_kind="comparison",
        intent_data={"intent": "compare", "holding": None, "target": None},
        entities={"companies": ["INFY", "TCS"], "company_matches": [{"name": "INFY"}, {"name": "TCS"}], "policies": []},
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
        entities={"companies": ["HAL"], "company_matches": [{"name": "HAL"}], "policies": []},
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
    ever runs (pipeline.py's own market-pulse branch, checked before
    decision-intent classification even executes) — this classifier is
    never even called for it; ui_mode="market_pulse" is set directly at
    that call site, and this precedence is intentionally unchanged by
    the 2026-09-22 priority reorder. Documented here so the registry
    test suite has one place asserting every mode is reachable somehow."""
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


# ── 2026-09-22 priority-order fix: explicit news_reaction must win over
# the generic sector-specialist heuristic. Real production finding —
# "Banking sector just reported stronger credit growth" used to lose
# news_reaction and land on the unsupported sector_theme_research mode
# purely because "sector" appears in the text, even though the query is
# unambiguously about a specific, real news event. ─────────────────────

def test_news_reaction_wins_over_sector_specialist_when_no_company_names_resolve():
    """The actual bug scenario: _route_specialist only ever returns
    specialist_kind="sector" when NO company entities resolved (see its
    own guard, `and not entities.get("companies")`) — so this is exactly
    the shape a real "no named company, but a real event" news-reaction
    query produces."""
    mode = classify_ui_mode(
        specialist_kind="sector", intent_data={"intent": "news_reaction"},
        entities={"companies": [], "policies": []},
        query="Banking sector just reported stronger credit growth — what is the impact?",
    )
    assert mode == "event_impact"


def test_news_reaction_wins_over_sector_specialist_second_regression_case():
    mode = classify_ui_mode(
        specialist_kind="sector", intent_data={"intent": "news_reaction"},
        entities={"companies": [], "policies": []},
        query="What happened after the defence-sector order announcement?",
    )
    assert mode == "event_impact"


def test_news_reaction_already_worked_when_a_real_company_resolves_alongside_a_sector_word():
    """This variant names a real company (HDFC Bank), so _route_specialist
    never returns "sector" for it in the first place (its own guard
    requires an EMPTY companies list) — specialist_kind is "company"
    here, and this case already routed correctly even before the
    priority reorder. Kept as a regression guard proving the fix didn't
    change this already-working case."""
    mode = classify_ui_mode(
        specialist_kind="company", intent_data={"intent": "news_reaction"},
        entities={"companies": ["HDFCBANK"], "policies": []},
        query="How will this banking-sector announcement affect HDFC Bank?",
    )
    assert mode == "event_impact"


# ── Explicit unsupported intents (2026-09-22) — each gets its own named
# mode, never the coarse sector/company fallback, and each wins over the
# generic sector heuristic too (step 4 precedes step 6). ────────────────

def test_entry_timing_routes_to_technical_timing_not_direct_company_research():
    mode = classify_ui_mode(
        specialist_kind="company", intent_data={"intent": "entry_timing"},
        entities={"companies": ["TCS"], "policies": []},
        query="Is now a good time to enter TCS?",
    )
    assert mode == "technical_timing"


def test_entry_timing_wins_over_sector_specialist():
    mode = classify_ui_mode(
        specialist_kind="sector", intent_data={"intent": "entry_timing"},
        entities={"companies": [], "policies": []},
        query="Good entry point for the IT sector right now?",
    )
    assert mode == "technical_timing"


def test_list_picks_routes_to_company_discovery_not_direct_company_research():
    mode = classify_ui_mode(
        specialist_kind="company", intent_data={"intent": "list_picks"},
        entities={"companies": ["HAL", "BEL", "BEML"], "policies": []},
        query="Top 5 defence stocks to watch",
    )
    assert mode == "company_discovery"


def test_portfolio_review_routes_to_its_own_mode():
    mode = classify_ui_mode(
        specialist_kind="company", intent_data={"intent": "portfolio_review"},
        entities={"companies": ["TCS", "INFY", "RELIANCE"], "policies": []},
        query="I own TCS, Infosys, and Reliance — how concentrated is my portfolio?",
    )
    assert mode == "portfolio_review"


def test_earnings_preview_routes_to_its_own_mode():
    mode = classify_ui_mode(
        specialist_kind="company", intent_data={"intent": "earnings_preview"},
        entities={"companies": ["HDFCBANK"], "policies": []},
        query="What should I expect before HDFC Bank's earnings?",
    )
    assert mode == "earnings_preview"


# ── Multi-company comparison (2026-09-22) — an explicit "not supported
# yet" mode, never silently entering company_comparison to fail only
# inside that assembler's own len(core.companies) != 2 check. ──────────

def test_two_companies_still_reaches_company_comparison():
    mode = classify_ui_mode(
        specialist_kind="comparison", intent_data={"intent": "compare", "holding": None, "target": None},
        entities={"companies": ["INFY", "TCS"], "company_matches": [{"name": "INFY"}, {"name": "TCS"}], "policies": []},
        query="Compare Infosys and TCS",
    )
    assert mode == "company_comparison"


def test_three_companies_routes_to_multi_company_comparison():
    mode = classify_ui_mode(
        specialist_kind="comparison", intent_data={"intent": "compare", "holding": "TCS", "target": "INFY"},
        entities={
            "companies": ["TCS", "INFY", "WIPRO"],
            "company_matches": [{"name": "TCS"}, {"name": "INFY"}, {"name": "WIPRO"}],
            "policies": [],
        },
        query="Compare TCS, Infosys, and Wipro",
    )
    assert mode == "multi_company_comparison"


def test_five_companies_also_routes_to_multi_company_comparison():
    mode = classify_ui_mode(
        specialist_kind="comparison", intent_data={"intent": "compare", "holding": "TCS", "target": "INFY"},
        entities={
            "companies": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
            "company_matches": [{"name": n} for n in ("TCS", "INFY", "WIPRO", "HCLTECH", "TECHM")],
            "policies": [],
        },
        query="Compare the top 5 IT stocks",
    )
    assert mode == "multi_company_comparison"


def test_three_companies_wins_even_when_intent_is_switch_like():
    """A switch-like intent with 3+ resolved companies still isn't a
    2-sided personal-holding decision — multi_company_comparison takes
    priority over switch_analysis's own holding/target check."""
    mode = classify_ui_mode(
        specialist_kind="comparison", intent_data={"intent": "switch", "holding": "TCS", "target": "INFY"},
        entities={
            "companies": ["TCS", "INFY", "WIPRO"],
            "company_matches": [{"name": "TCS"}, {"name": "INFY"}, {"name": "WIPRO"}],
            "policies": [],
        },
        query="Should I switch from TCS to Infosys or Wipro?",
    )
    assert mode == "multi_company_comparison"


def test_missing_company_matches_key_defaults_to_zero_never_crashes():
    mode = classify_ui_mode(
        specialist_kind="comparison", intent_data={"intent": "compare", "holding": "TCS", "target": "INFY"},
        entities={"companies": ["TCS", "INFY"], "policies": []},  # no "company_matches" key at all
        query="Compare TCS and Infosys",
    )
    assert mode == "company_comparison"
