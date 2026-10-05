"""
Step 4A: macro-driver routing (MP2 crude oil -> Indian markets, MP3 weaker rupee -> Indian IT exporters). Deterministic, ZERO provider calls: real entity extraction, decision intent, `_route_specialist` and
`classify_ui_mode`. Gate A/B, retrieval, prompts and latency are not touched by this change.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.ai_search import entities as E
from app.services.ai_search import pipeline as P
from app.services.ai_search.decision_intent import _detect_decision_intent
from app.services.ai_search.macro_drivers import macro_driver
from app.services.ai_search.ui_mode import classify_ui_mode

QUESTIONS = {q["id"]: q for q in json.loads((Path(__file__).resolve().parents[2] / "benchmarks/ai_search/baseline_2026_10_04/questions.json").read_text(encoding="utf-8"))["questions"]}


def route(query: str):
    ents = E.extract_entities(query)
    snapshot = json.dumps(ents, sort_keys=True, default=str)
    intent = _detect_decision_intent(query)
    _spec, kind = P._route_specialist(query, intent, ents)
    ui = classify_ui_mode(specialist_kind=kind, intent_data=intent, entities=ents, query=query)
    assert json.dumps(ents, sort_keys=True, default=str) == snapshot       # routing never rewrites the resolved entities
    return kind, ui, ents


# ── frozen-18 routing qualification ─────────────────────────────────────────────────────────────────────────────────────────────

# EI3 ("banking sector just reported ... what is the impact?") has always routed to the sector specialist; its recorded expectation says company. Not part of Step 4A; pinned so a change is noticed.
KNOWN_MISMATCH = {"EI3": ("sector", "event_impact")}


@pytest.mark.parametrize("qid", sorted(QUESTIONS))
def test_frozen18_route_matches_the_recorded_expectation(qid):
    q = QUESTIONS[qid]
    kind, ui, _ = route(q["query"])
    exp = q["expected_route"]
    if qid in KNOWN_MISMATCH:
        assert (kind, ui) == KNOWN_MISMATCH[qid]
    else:
        assert (kind, ui) == (exp["specialist"], exp["ui_mode"]), (qid, kind, ui)


@pytest.mark.parametrize("qid", ["MP1", "MP2", "MP3"])
def test_macro_questions_keep_their_expected_entities(qid):
    q = QUESTIONS[qid]
    _, _, ents = route(q["query"])
    exp = q["expected_entities"]
    if "sectors" in exp:
        assert {s.lower() for s in ents["sectors"]} == {s.lower() for s in exp["sectors"]}
    assert ents["companies"] == []


# ── the two target questions ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_mp2_crude_oil_to_indian_markets_is_a_macro_question():
    assert route("How would higher crude oil prices affect Indian markets?")[:2] == ("company", "policy_macro_impact")


def test_mp3_weaker_rupee_to_it_exporters_goes_to_the_sector_specialist_as_a_macro_question():
    assert route("How would a weaker rupee affect Indian IT exporters?")[:2] == ("sector", "policy_macro_impact")


# ── adversarial: what must NOT change ───────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "How would higher crude oil prices affect Reliance?",
    "How would a weaker rupee affect Infosys and TCS?",
    "Should I buy TCS if the rupee weakens?",
])
def test_a_resolved_company_keeps_the_question_a_company_question(query):
    kind, ui, ents = route(query)
    assert ents["companies"] and kind == "company" and ui == "direct_company_research"        # policy_macro_impact would also unlock the market-wide engine verdict next to a company answer


def test_a_comparison_stays_a_comparison_even_when_a_macro_driver_is_mentioned():
    kind, ui, _ = route("Compare HDFC Bank and ICICI Bank after a weaker rupee")
    assert (kind, ui) == ("comparison", "company_comparison")


@pytest.mark.parametrize("query", [
    "What is crude oil?",
    "What is the rupee?",
    "Crude oil price today",
    "Is gold a hedge against a weaker rupee?",
    "What does FII selling mean for the Indian market?",
    "What is a P/E ratio and how should I read it?",
    "How does the MarketRipple Score work?",
])
def test_educational_or_mention_only_questions_are_not_macro_impact_questions(query):
    assert macro_driver(query) is None
    assert route(query)[:2] == ("company", "direct_company_research")


@pytest.mark.parametrize("query", [
    "Why are banking stocks down today?",
    "Tell me about banking",
])
def test_a_resolved_sector_without_a_trigger_or_driver_still_routes_as_before(query):
    assert route(query)[:2] == ("company", "direct_company_research")          # the documented sector-trigger limitation is untouched outside macro questions


@pytest.mark.parametrize("query,expected", [
    ("How would a weaker rupee affect the IT sector?", ("sector", "policy_macro_impact")),
    ("How would a stronger dollar affect pharma exporters?", ("sector", "policy_macro_impact")),
    ("What happens to Indian banks if the RBI cuts the repo rate?", ("sector", "policy_macro_impact")),
    ("How would rising oil prices hurt airlines?", ("company", "policy_macro_impact")),
    ("How does the rupee affect my SIP returns?", ("company", "policy_macro_impact")),
])
def test_other_macro_driver_shapes(query, expected):
    assert route(query)[:2] == expected


def test_a_driver_not_in_the_table_is_unchanged_and_documented_as_an_extension_point():
    assert route("How would inflation affect Indian markets?")[:2] == ("company", "direct_company_research")      # inflation, rates and FII flows are separate drivers; add a row to macro_drivers._DRIVERS


@pytest.mark.parametrize("query,driver", [
    ("How would higher crude oil prices affect Indian markets?", "crude_oil"),
    ("What happens to the market if Brent rises?", "crude_oil"),
    ("How would a weaker rupee affect Indian IT exporters?", "fx_rupee"),
    ("What is the impact of USDINR moving higher on exporters?", "fx_rupee"),
    ("How does a stronger dollar hurt emerging markets?", "fx_rupee"),
])
def test_macro_driver_detects_the_driver_when_an_effect_is_asked(query, driver):
    assert macro_driver(query) == driver


@pytest.mark.parametrize("query", [
    "crudely speaking, how would things change?",
    "How would a dollar store chain affect Indian retail?",
    "The rupee",
    "",
])
def test_macro_driver_is_conservative_about_word_boundaries_and_missing_impact_verbs(query):
    assert macro_driver(query) is None


def test_the_comparison_and_news_reaction_priorities_in_ui_mode_are_unchanged():
    ents = {"companies": [], "company_matches": [], "sectors": [], "policies": []}
    assert classify_ui_mode(specialist_kind="comparison", intent_data={"intent": "compare"}, entities=ents, query="How would the rupee affect X vs Y?") == "company_comparison"
    assert classify_ui_mode(specialist_kind="company", intent_data={"intent": "news_reaction"}, entities=ents, query="How would the rupee affect markets after this news?") == "event_impact"


@pytest.mark.parametrize("query", [
    "How is TCS doing in the IT sector?",
    "How would a weaker rupee affect TCS in the IT sector?",
    "What happens to HDFC Bank if the RBI cuts the repo rate?",
])
def test_a_resolved_company_wins_over_a_sector_word_or_a_sector_plus_driver(query):
    kind, _ui, ents = route(query)
    assert ents["companies"] and kind == "company"


@pytest.mark.parametrize("query", [
    "Which sectors benefit from lower crude prices?",
    "What sectors are hurt by a weaker rupee?",
    "Which industries gain when oil prices fall?",
    "Which defensive sectors help when the rupee falls?",
])
def test_sector_discovery_questions_are_not_macro_driver_questions(query):
    assert macro_driver(query) is None


def test_sector_discovery_keeps_its_existing_sector_theme_ui_mode():
    ents = {"companies": [], "sectors": ["energy"], "policies": []}
    assert classify_ui_mode(specialist_kind="sector", intent_data={"intent": "general"}, entities=ents, query="Which sectors benefit from lower crude prices?") == "sector_theme_research"
    assert route("Which sectors benefit from lower crude prices?")[:2] == ("sector", "sector_theme_research")
