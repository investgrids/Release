"""
Step 3.4G.5: the composition contract (observations first, synthesis second, prose and claims consistent in both directions). Model-free:
  * the contract is in every specialist prompt, names no expected fact, and demands nothing the evidence might not hold (no padding, no winner, no invented outlook or causality);
  * on the saved SR2 evidence the concepts the contract should be able to draw on are visible and citable in the actual sector prompt;
  * a generation that follows the contract on that evidence passes Gate B, and the two ways of breaking prose/claim consistency are still rejected;
  * insufficient evidence still never reaches the model.
No provider call. Gate A/B logic unchanged.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE
from app.services.ai_search import answer_authorization as AA
from app.services.ai_search import claim_sources as CS
from app.services.ai_search import schema as S
from app.services.ai_search.specialists import sector as sector_spec
from tests.services.test_ai_search_detector_closure import ENTS, rebuild, saved
from tests.services.test_ai_search_fail_closed import bundle, pipe, run_pipeline  # noqa: F401
from tests.services.test_ai_search_generation_contract import PROHIBITED_KEYS, PROMPTS

RULES = S.COMPOSITION_RULES


# ── the contract text ────────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["company", "pairwise", "multi", "sector"])
def test_the_composition_contract_is_in_every_claim_bearing_prompt_exactly_once(name):
    assert PROMPTS[name].count(RULES) == 1


@pytest.mark.parametrize("fragment", [
    "observations first, synthesis second", "usually 3 to 5, fewer when the evidence holds fewer informative facts, none when it holds none",
    "copied exactly into \"claim_sources\"", "prefer concrete, quantified, dated or directional items over generic market commentary", "when items point in different directions include both",
    "Do not pad", "do not state something because it is typical of the topic", "no new figure, date or event and no verdict, forecast, winner or recommendation",
    "every factual sentence anywhere in your answer must be listed in \"claim_sources\"", "every \"claim_sources\" entry must be a sentence you actually wrote in the answer text",
    "never list a claim you did not write and never write a fact you did not list",
])
def test_the_contract_states_the_demanded_properties(fragment):
    assert fragment in RULES, fragment


def test_the_contract_names_no_expected_fact_and_no_topic_specific_example():
    low = RULES.lower()
    for token in ("accenture", "september", "nifty", "11%", "infosys", "tcs", "kotak", "rbi", "repo", "rally", "weak"):
        assert re.search(r"(?<![a-z])" + re.escape(token) + r"(?![a-z])", low) is None, token
    assert "accenture-led" not in low and "the september decline" not in low
    assert re.search(r"\d", re.sub(r"\(\d\)", "", RULES.replace("3 to 5", ""))) is None      # no figure other than the 3-to-5 count and the (1)-(4) list markers


def test_the_contract_never_demands_a_fact_or_a_minimum_count():
    low = RULES.lower()
    for forbidden in ("you must state", "must mention", "always include", "at least three", "at least 3", "exactly five", "exactly 5", "must include both"):
        assert forbidden not in low, forbidden
    assert "none when it holds none" in low and "when items point in different directions include both" in low      # allowed to be empty; no forced symmetry


def test_the_contract_keeps_the_limits_that_stop_manufactured_conclusions():
    low = RULES.lower()
    assert "never name a winner" in low and "not an outlook it does not state" in low and "state a causal link only if a listed item states it" in low
    assert "instead of filling space with unrelated facts" in low


def test_the_schema_groups_describe_the_same_structure():
    assert "OBSERVATIONS" in S.EVIDENCE_GROUP and "SYNTHESIS" in S.INVESTMENT_GROUP
    low = S.INVESTMENT_GROUP.lower()
    assert '"rating"' not in low and '"direction"' not in low and "verdict_scale" not in low


@pytest.mark.parametrize("name", ["company", "pairwise", "multi", "sector"])
def test_no_prohibited_output_structure_came_back(name):
    assert [k for k in PROHIBITED_KEYS if k in PROMPTS[name]] == []


def test_the_comparison_prompts_still_forbid_a_winner_and_do_not_request_one():
    for name in ("pairwise", "multi"):
        p = PROMPTS[name].lower()
        assert "never name a winner" in p and "do not name a winner" in p and '"winner"' not in p


# ── insufficient evidence still never reaches the model ───────────────────────────────────────────────────────────────────────

def test_an_insufficient_evidence_bundle_still_makes_no_model_call(pipe):
    pipe["set_bundle"](bundle())
    _raw, res, _ = run_pipeline("How is 3M India doing as a business? (3.4G.5 refusal)")
    assert pipe["specialist"] == 0 and res["degraded_reason"] == "insufficient_evidence"


# ── SR2: the evidence the contract can draw on is visible and citable ───────────────────────────────────────────────────────────

def sr2_prompt_and_bundle():
    g, ev, r = saved()
    b = rebuild(ev)
    prompt = sector_spec.build_prompt(r["query"], b, {}, {"companies": [], "company_matches": [], "sectors": ["it"], "policies": []})
    return g, ev, r, b, prompt


CONCEPTS = {
    "earlier_weakness": re.compile(r"(?:crash|fall|slump|declin|slid|drop)\w*", re.I),
    "external_read_through": re.compile(r"accenture", re.I),
    "caution": re.compile(r"divided|weaker growth|growth recovery|dilemma|pressure|slowdown", re.I),
}


def test_saved_sr2_evidence_contains_each_concept_as_a_visible_citable_item():
    _g, _ev, _r, b, prompt = sr2_prompt_and_bundle()
    idx = {i["id"]: i for i in b.index()}
    shown = set(re.findall(r"\[([ENPAC]\d{1,3})\]", prompt))
    assert set(idx) == shown                                                      # everything citable is shown and vice versa
    for concept, rx in CONCEPTS.items():
        hits = [i for i, it in idx.items() if it["kind"] in ("event", "news") and rx.search(it["title"] or "")]
        assert hits, concept                                                       # visible and citable
        assert all(h in shown for h in hits)
    sector_line = [ln for ln in prompt.splitlines() if ln.startswith("- IT:")]
    assert sector_line and "1-day change" in sector_line[0]                        # the current sector move is in the prompt, with its figure
    assert any(it["kind"] == "event" and "11%" in (it["title"] or "") for it in idx.values())        # the September 11% fall is in a visible title, not only in a hidden summary


# ── a contract-following generation on that evidence passes Gate B; broken consistency is still rejected ──────────────────────────

def contract_generation(b, overrides=None):
    idx = {i["id"]: i for i in b.index()}
    e_fall = next(i for i, it in idx.items() if it["kind"] == "event" and "11%" in it["title"])
    e_acn = next(i for i, it in idx.items() if it["kind"] == "event" and "Accenture" in it["title"] and "22%" in it["title"])
    n_div = next(i for i, it in idx.items() if it["kind"] == "news" and "divided" in it["title"].lower())
    obs = [("Nifty IT crashed 11% in September, with TCS, Infosys and Wipro among the top losers.", [e_fall]),
           ("Accenture shares jumped a record 22% on an earnings boost, lifting Infosys and Wipro ADRs.", [e_acn]),
           ("Coverage describes the Street as divided on the fortunes of Indian IT after Accenture's growth beat.", [n_div])]
    g = {"summary": "The visible evidence is mixed rather than clearly positive or negative.",
         "bottom_line": "The earlier decline and the positive external read-through pull in different directions, and the caution about growth means a clear forward outlook is not established.",
         "what_happened": " ".join(s for s, _ in obs), "why_it_happened": "", "claim_sources": [{"claim": s, "sources": ids} for s, ids in obs],
         "key_drivers": [], "risks": [], "opportunities": [], "companies": [], "sectors": [], "timeline": [], "scenarios": {}}
    g.update(overrides or {})
    return g


def test_a_contract_following_generation_on_the_saved_sr2_evidence_is_authorized():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    g = contract_generation(b)
    for s in (g["summary"], g["bottom_line"]):
        assert CS.is_factual(s) is False                                           # the synthesis introduces no figure, date or event
    a = AA.authorize(g, b, ENTS, UNIVERSE, r["query"])
    assert a["authorized"] is True, a
    cited = {i for c in g["claim_sources"] for i in c["sources"]}
    assert len(cited) >= 3 and len(g["claim_sources"]) == 3                        # several distinct high-information items used


def test_listing_a_claim_the_answer_never_states_is_still_rejected():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    g = contract_generation(b)
    g["claim_sources"].append({"claim": "IT was flat at +0.0% over one day.", "sources": ["C2"]})
    a = AA.authorize(g, b, ENTS, UNIVERSE, r["query"])
    assert a["authorized"] is False and "claim_not_in_answer" in a["reasons"]


def test_writing_an_observation_without_listing_it_is_still_rejected():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    g = contract_generation(b)
    g["what_happened"] += " Nifty IT jumped 2% intraday on the first of October."
    a = AA.authorize(g, b, ENTS, UNIVERSE, r["query"])
    assert a["authorized"] is False and "uncovered_factual_sentences" in a["reasons"]


def test_an_observation_with_a_full_date_that_lives_only_in_a_hidden_summary_is_rejected():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    hidden = "The Q2 results season begins on 8 October 2026 with TCS reporting first."     # the date lives only in a summary the prompt never showed
    g = contract_generation(b)
    g["what_happened"] += " " + hidden
    g["claim_sources"].append({"claim": hidden, "sources": ["E2"]})
    a = AA.authorize(g, b, ENTS, UNIVERSE, r["query"])
    assert a["authorized"] is False and "unsupported_figures" in a["reasons"]


@pytest.mark.xfail(strict=True, reason="KNOWN PERMISSIVE GAP (found in 3.4G.5, Gate B frozen in this step): a day-month date with no year ('8 October', 'Oct 8') is not parsed as a date, and the lone digit is exempt as a "
                                       "single-digit number, so a hidden-summary date written without a year is not caught. Needs its own fix.")
def test_a_year_less_date_from_a_hidden_summary_is_not_yet_caught():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    hidden = "The Q2 results season begins on 8 October with TCS reporting first."
    g = contract_generation(b)
    g["what_happened"] += " " + hidden
    g["claim_sources"].append({"claim": hidden, "sources": ["E2"]})
    a = AA.authorize(g, b, ENTS, UNIVERSE, r["query"])
    assert a["authorized"] is False


def test_a_synthesis_that_smuggles_a_verdict_or_forecast_is_not_hidden_by_the_contract():
    _g, _ev, r, b, _p = sr2_prompt_and_bundle()
    g = contract_generation(b, {"bottom_line": "IT will rally 15% by year end as Accenture's beat flows through to Indian exporters."})
    a = AA.authorize(g, b, ENTS, UNIVERSE, r["query"])
    assert a["authorized"] is False and ({"uncovered_factual_sentences", "unsupported_figures"} & set(a["reasons"]))
