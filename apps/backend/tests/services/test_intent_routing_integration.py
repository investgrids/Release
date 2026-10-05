"""
Exhaustive intent-to-ui_mode routing (2026-09-22, intent-coverage
audit). Exercises pipeline.py's own _route_specialist together with
ui_mode.py's classify_ui_mode — the two real functions a live query
actually passes through, in order — for every one of the 12 decision-
intent labels decision_intent.py can produce, plus the zero/one/two/
three-company boundary and the news_reaction/sector-trigger overlap
this audit's own priority-order fix closes.

Market Pulse is deliberately NOT exercised here: it short-circuits
_run_v3_steps BEFORE decision-intent classification ever runs (see
pipeline.py's own comment on that branch) — there is no _route_
specialist/classify_ui_mode call to make for it at all. Documented as
its own fact, not a gap in this file's coverage.
"""
from __future__ import annotations

from app.services.ai_search.pipeline import _route_specialist
from app.services.ai_search.ui_mode import classify_ui_mode


def _company_entities(*symbols: str) -> dict:
    """Builds both the plain `companies` list _route_specialist's own
    sector-routing guard reads (`not entities.get("companies")`) and the
    richer `company_matches` list resolve_comparison/classify_ui_mode's
    multi-company check read — real production entities.py output
    carries both."""
    return {
        "companies": list(symbols),
        "company_matches": [{"name": s, "symbol": s, "match_type": "exact", "matched_text": s} for s in symbols],
        "policies": [],
    }


def _route(query: str, intent: str, entities: dict, **intent_overrides) -> tuple[str, str]:
    """Returns (specialist_kind, ui_mode) — the two real outputs a live
    query produces, in the same order pipeline.py itself computes them."""
    intent_data = {"intent": intent, "holding": None, "target": None, "is_comparison": False, **intent_overrides}
    _specialist_fn, specialist_kind = _route_specialist(query, intent_data, entities)
    mode = classify_ui_mode(specialist_kind=specialist_kind, intent_data=intent_data, entities=entities, query=query)
    return specialist_kind, mode


# ── The 12 decision-intent labels — comparison-shaped and not ───────────

def test_switch_comparison_shaped():
    kind, mode = _route(
        "Should I switch BEL to HAL?", "switch", _company_entities("BEL", "HAL"),
        holding="BEL", target="HAL", is_comparison=True,
    )
    assert kind == "comparison"
    assert mode == "switch_analysis"


def test_switch_not_comparison_shaped():
    kind, mode = _route("Should I switch my approach with TCS?", "switch", _company_entities("TCS"))
    assert kind == "company"
    assert mode == "direct_company_research"


def test_hold_comparison_shaped():
    kind, mode = _route(
        "Should I hold BEL or switch to HAL?", "hold", _company_entities("BEL", "HAL"),
        holding="BEL", target="HAL", is_comparison=True,
    )
    assert kind == "comparison"
    assert mode == "switch_analysis"


def test_hold_not_comparison_shaped():
    kind, mode = _route("Should I keep holding TCS?", "hold", _company_entities("TCS"))
    assert kind == "company"
    assert mode == "direct_company_research"


def test_sell_comparison_shaped():
    kind, mode = _route(
        "Should I sell TCS and buy Infosys instead?", "sell", _company_entities("TCS", "INFY"),
        holding="TCS", target="INFY", is_comparison=True,
    )
    assert kind == "comparison"
    assert mode == "switch_analysis"


def test_sell_not_comparison_shaped():
    kind, mode = _route("When should I sell TCS?", "sell", _company_entities("TCS"))
    assert kind == "company"
    assert mode == "direct_company_research"


def test_buy_comparison_shaped():
    kind, mode = _route(
        "Should I buy TCS instead of Infosys?", "buy", _company_entities("TCS", "INFY"),
        holding="INFY", target="TCS", is_comparison=True,
    )
    assert kind == "comparison"
    assert mode == "switch_analysis"


def test_buy_not_comparison_shaped():
    kind, mode = _route("Should I buy TCS?", "buy", _company_entities("TCS"))
    assert kind == "company"
    assert mode == "direct_company_research"


def test_decision_comparison_shaped():
    kind, mode = _route(
        "Is TCS or Infosys the safer bet?", "decision", _company_entities("TCS", "INFY"),
        holding="TCS", target="INFY", is_comparison=True,
    )
    assert kind == "comparison"
    assert mode == "switch_analysis"


def test_decision_not_comparison_shaped():
    kind, mode = _route("Is TCS a good investment?", "decision", _company_entities("TCS"))
    assert kind == "company"
    assert mode == "direct_company_research"


def test_compare_two_companies():
    kind, mode = _route(
        "Compare TCS and Infosys", "compare", _company_entities("TCS", "INFY"),
        holding="TCS", target="INFY", is_comparison=True,
    )
    assert kind == "comparison"
    assert mode == "company_comparison"


def test_compare_three_companies_routes_to_multi_company_comparison():
    kind, mode = _route(
        "Compare TCS, Infosys, and Wipro", "compare", _company_entities("TCS", "INFY", "WIPRO"),
        holding="TCS", target="INFY", is_comparison=True,
    )
    assert kind == "comparison"
    assert mode == "multi_company_comparison"


def test_general_fallback_comparison_shape():
    """"HDFC or ICICI?" — no explicit decision-intent keyword fires
    (intent stays "general"), but the shared compare regex fallback
    still resolves holding/target — see decision_intent.py's own
    "Fallback: try compare regex... even when no decision-intent keyword
    fired at all" comment."""
    kind, mode = _route(
        "HDFC or ICICI?", "general", _company_entities("HDFCBANK", "ICICIBANK"),
        holding="HDFC", target="ICICI", is_comparison=True,
    )
    assert kind == "comparison"
    assert mode == "company_comparison"


def test_general_no_comparison_shape():
    kind, mode = _route("Tell me about HDFC Bank", "general", _company_entities("HDFCBANK"))
    assert kind == "company"
    assert mode == "direct_company_research"


def test_news_reaction_no_sector_overlap():
    kind, mode = _route(
        "Reliance just announced a new refinery — what does this mean?",
        "news_reaction", _company_entities("RELIANCE"),
    )
    assert kind == "company"
    assert mode == "event_impact"


def test_news_reaction_never_routes_to_comparison_even_if_comparison_shaped():
    """news_reaction is in _route_specialist's own comparison-exclusion
    list — a "reaction to X vs Y" phrasing still never hijacks the
    comparison specialist."""
    kind, mode = _route(
        "Reaction to TCS vs Infosys results season", "news_reaction", _company_entities("TCS", "INFY"),
        holding="TCS", target="INFY", is_comparison=True,
    )
    assert kind != "comparison"
    assert mode == "event_impact"


def test_news_reaction_wins_over_sector_specialist_end_to_end():
    """The real bug this audit's priority-order fix closes, exercised
    through the ACTUAL _route_specialist -> classify_ui_mode pipeline,
    not just a hand-constructed specialist_kind."""
    entities = {"companies": [], "company_matches": [], "policies": []}
    kind, mode = _route(
        "Banking sector just reported stronger credit growth — what is the impact?",
        "news_reaction", entities,
    )
    assert kind == "sector", "test setup assumes the sector trigger fires with zero companies resolved"
    assert mode == "event_impact"


def test_earnings_preview_routes_to_its_own_mode_never_comparison():
    kind, mode = _route(
        "What should I expect before HDFC Bank vs ICICI's earnings?",
        "earnings_preview", _company_entities("HDFCBANK", "ICICIBANK"),
        holding="HDFC", target="ICICI", is_comparison=True,
    )
    assert kind != "comparison"
    assert mode == "earnings_preview"


def test_entry_timing_routes_to_technical_timing_never_comparison():
    kind, mode = _route(
        "Good entry point for TCS vs Infosys?", "entry_timing", _company_entities("TCS", "INFY"),
        holding="TCS", target="INFY", is_comparison=True,
    )
    assert kind != "comparison"
    assert mode == "technical_timing"


def test_entry_timing_wins_over_sector_specialist_end_to_end():
    entities = {"companies": [], "company_matches": [], "policies": []}
    kind, mode = _route("Good entry point for the IT sector right now?", "entry_timing", entities)
    assert kind == "sector"
    assert mode == "technical_timing"


def test_portfolio_review_routes_to_its_own_mode_never_comparison():
    kind, mode = _route(
        "I own TCS and Infosys vs my friend's portfolio — how am I doing?",
        "portfolio_review", _company_entities("TCS", "INFY"),
        holding="TCS", target="INFY", is_comparison=True,
    )
    assert kind != "comparison"
    assert mode == "portfolio_review"


def test_list_picks_routes_to_company_discovery_never_comparison():
    kind, mode = _route(
        "Top 5 defence stocks vs top 5 IT stocks", "list_picks",
        _company_entities("HAL", "BEL", "TCS", "INFY", "WIPRO"),
        holding="defence", target="IT", is_comparison=True,
    )
    assert kind != "comparison"
    assert mode == "company_discovery"


# ── Zero/one/two/three-company boundary (comparison specialist path) ────

def test_zero_companies_falls_to_direct_company_research():
    kind, mode = _route("What's moving the market today?", "general", {"companies": [], "company_matches": [], "policies": []})
    assert kind == "company"
    assert mode == "direct_company_research"


def test_one_company_falls_to_direct_company_research():
    kind, mode = _route("Tell me about TCS", "general", _company_entities("TCS"))
    assert kind == "company"
    assert mode == "direct_company_research"


def test_two_companies_comparison_shaped_reaches_company_comparison():
    kind, mode = _route(
        "TCS vs Infosys, which is better?", "general", _company_entities("TCS", "INFY"),
        holding="TCS", target="INFY", is_comparison=True,
    )
    assert kind == "comparison"
    assert mode == "company_comparison"


def test_three_companies_comparison_shaped_reaches_multi_company_comparison():
    kind, mode = _route(
        "TCS vs Infosys vs Wipro, which is better?", "general", _company_entities("TCS", "INFY", "WIPRO"),
        holding="TCS", target="INFY", is_comparison=True,
    )
    assert kind == "comparison"
    assert mode == "multi_company_comparison"


# ── Market Pulse precedence — documented, not exercised here ────────────

def test_market_pulse_never_reaches_route_specialist_or_classify_ui_mode():
    """Market Pulse's own detector runs first, inside _run_v3_steps,
    before decision-intent classification even executes — see
    pipeline.py's own market-pulse branch. Neither _route_specialist nor
    classify_ui_mode is ever called for a market-pulse-classified query;
    ui_mode="market_pulse" is set directly at that call site. This test
    only documents the fact (both functions remain agnostic of Market
    Pulse entirely — grep confirms neither name appears in either
    module), since there's nothing to route through this file's own
    _route helper for it."""
    import inspect
    from app.services.ai_search import pipeline as pipeline_mod
    from app.services.ai_search import ui_mode as ui_mode_mod

    assert "market_pulse" not in inspect.getsource(pipeline_mod._route_specialist)
    assert "market_pulse" not in inspect.getsource(ui_mode_mod.classify_ui_mode)
