"""
Step 3.4G.2: presentation alignment. Invariant:  retrieved ⊃ selected ⊃ model-visible = claim-authorizable.

  * every evidence id a model may cite exists as a marker in the REAL prompt for that specialist, and every marker the prompt shows is citable;
  * the sector specialist now shows the selected news;
  * Gate B's corpus is exactly what the model saw: a fact that lives only in hidden evidence (a ranked item the prompt cut off, a summary, an item date the prompt omits) cannot ground a claim.
No provider call.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE
from app.services.ai_search import answer_authorization as AA
from app.services.ai_search.evidence import PROMPT_VISIBLE, EvidenceBundle
from app.services.ai_search.specialists import company as company_spec
from app.services.ai_search.specialists import comparison as comparison_spec
from app.services.ai_search.specialists import sector as sector_spec
from tests.services.test_ai_search_fail_closed import NOW, ann, ent, news_row, pipe, run_pipeline, tcs_bundle  # noqa: F401


def events(n, lead="Event", companies=("TCS",), summary=""):
    out = []
    for i in range(1, n + 1):
        d = (NOW - timedelta(days=i)).isoformat()
        out.append({"id": f"ev{i}", "title": f"{lead} {i} distinct headline number {i}", "summary": summary, "category": "Market", "impact_score": 60, "companies": [{"symbol": s} for s in companies],
                    "event_date": d, "published_at": d, "date": ""})
    return out


def big_bundle(kind, plan="company") -> EvidenceBundle:
    b = EvidenceBundle()
    b.plan_kind, b.prompt_kind = plan, kind
    b.events = events(10)
    b.news = [news_row(f"n{i}", f"News headline {i} unique wording {i}") for i in range(1, 11)]
    b.policies = [{"id": f"p{i}", "title": f"Policy {i}", "summary": "", "ministry": "Min"} for i in range(1, 6)]
    b.announcements = [ann(f"a{i}", f"Tata Consultancy Services Limited has informed the Exchange regarding matter {i}", "TCS") for i in range(1, 9)]
    b.context_lines = ["TCS: P/E 15.1, P/B 6.85", "INFY: P/E 14.1, P/B 4.54"]
    b.valuation = {"TCS": {"pe": 15.1, "pb": 6.85}, "INFY": {"pe": 14.1, "pb": 4.54}}
    b.sector_rows = [{"name": f"Sector{i}", "value": f"+{i}.0%"} for i in range(1, 15)]
    return b


E2 = {"companies": ["TCS", "INFY"], "company_matches": [{"name": "Tata Consultancy Services", "symbol": "TCS"}, {"name": "Infosys", "symbol": "INFY"}], "sectors": [], "policies": []}
E1 = {"companies": ["TCS"], "company_matches": [], "sectors": [], "policies": []}
ES = {"companies": [], "company_matches": [], "sectors": ["it"], "policies": []}
E3 = {"companies": ["TCS", "INFY", "WIPRO"], "company_matches": [{"name": "Tata Consultancy Services", "symbol": "TCS"}, {"name": "Infosys", "symbol": "INFY"}, {"name": "Wipro", "symbol": "WIPRO"}], "sectors": [], "policies": []}


def prompts():
    return {
        "company": (company_spec.build_prompt("How is TCS doing?", big_bundle("company"), {}, E1), big_bundle("company")),
        "sector": (sector_spec.build_prompt("IT sector outlook", big_bundle("sector", "topic"), {}, ES), big_bundle("sector", "topic")),
        "comparison_pairwise": (comparison_spec.build_prompt("TCS vs Infosys", big_bundle("comparison", "comparison"), {"holding": "Tata Consultancy Services", "target": "Infosys", "is_comparison": True}, E2),
                                big_bundle("comparison", "comparison")),
        "comparison_multi": (comparison_spec._build_multi_compare_prompt("Compare TCS Infosys Wipro", big_bundle("comparison", "comparison"), E3), big_bundle("comparison", "comparison")),
    }


MARKER = re.compile(r"\[([ENPAC]\d{1,3})\]")
PROMPTS = prompts()


@pytest.mark.parametrize("name", list(PROMPTS))
def test_every_citable_id_is_in_the_prompt_and_every_prompt_marker_is_citable(name):
    prompt, bundle = PROMPTS[name]
    ids = {i["id"] for i in bundle.index()}
    shown = set(MARKER.findall(prompt))
    assert ids == shown, (name, sorted(ids - shown), sorted(shown - ids))


def test_the_visibility_caps_are_the_single_source_of_truth_for_prompt_and_index():
    for name, kind in (("company", "company"), ("sector", "sector"), ("comparison_pairwise", "comparison"), ("comparison_multi", "comparison")):
        _prompt, b = PROMPTS[name]
        idx = b.index()
        for letter, key in (("E", "events"), ("N", "news"), ("P", "policies")):
            assert sum(1 for i in idx if i["id"].startswith(letter)) == min(PROMPT_VISIBLE[kind][key], {"events": 10, "news": 10, "policies": 5}[key]), (name, letter)
        assert sum(1 for i in idx if i["id"].startswith("A")) == 8 and sum(1 for i in idx if i["id"].startswith("C")) == 2


def test_the_sector_specialist_now_shows_the_selected_news():
    prompt, b = PROMPTS["sector"]
    assert "Related market news headlines" in prompt
    for n in b.news[:PROMPT_VISIBLE["sector"]["news"]]:
        assert n["headline"] in prompt
    assert b.news[PROMPT_VISIBLE["sector"]["news"]]["headline"] not in prompt          # the same bounded budget: the sixth news item is not shown, and has no id either
    assert "N6" not in {i["id"] for i in b.index()}


def test_company_and_comparison_prompts_still_show_the_same_slices_as_before():
    assert PROMPT_VISIBLE == {"company": {"events": 5, "news": 5, "policies": 3}, "sector": {"events": 6, "news": 5, "policies": 4}, "comparison": {"events": 4, "news": 4, "policies": 0}}


# ── the corpus is what the model saw ─────────────────────────────────────────────────────────────────────────────────────────────

def test_visible_text_contains_what_the_prompt_shows_and_nothing_hidden():
    b = big_bundle("company")
    b.events[6]["title"] = "Hidden event seven reported revenue of 98765 crore"            # rank 7: beyond the 5 the company prompt shows
    b.events[0]["summary"] = "Summary-only fact: margins widened 77 bps"                   # prompts never show summaries
    b.news[7]["headline"] = "Hidden news eight says orders worth 55555 crore"
    text = b.visible_text()
    assert "Event 1 distinct headline" in text and "News headline 1" in text and "TCS: P/E 15.1" in text
    assert "98765" not in text and "77 bps" not in text and "55555" not in text


def test_sector_rows_are_visible_text_only_for_the_sector_prompt():
    assert "Sector12" in big_bundle("sector", "topic").visible_text() and "Sector13" not in big_bundle("sector", "topic").visible_text()
    assert "Sector1 " not in big_bundle("company").visible_text()


def test_the_legacy_bundle_without_a_prompt_kind_keeps_the_internal_corpus():
    b = big_bundle("company")
    b.prompt_kind = None
    b.events[6]["title"] = "Hidden event seven reported revenue of 98765 crore"
    assert "98765" in AA.evidence_corpus(b)


# ── the adversarial regressions: hidden evidence cannot authorize a claim ─────────────────────────────────────────────────────────

def gen(sentence, source):
    return {"summary": sentence, "bottom_line": sentence, "claim_sources": [{"claim": sentence, "sources": [source]}], "companies": [], "sectors": [], "key_drivers": [], "risks": [], "opportunities": []}


def hidden_fact_bundle() -> EvidenceBundle:
    b = big_bundle("company")
    b.events[6]["title"] = "TCS signed a deal worth 98765 crore with a European bank"        # E7: retrieved and selected, but the company prompt shows only E1-E5
    return b


def test_a_claim_citing_hidden_evidence_is_rejected_as_an_unknown_source():
    b = hidden_fact_bundle()
    assert "E7" not in {i["id"] for i in b.index()}
    a = AA.authorize(gen("TCS signed a deal worth 98765 crore with a European bank.", "E7"), b, ent(["TCS"]), UNIVERSE, "How is TCS doing?")
    assert a["authorized"] is False and "unknown_source" in a["reasons"]


def test_a_figure_that_exists_only_in_hidden_evidence_cannot_ground_a_claim_citing_visible_evidence():
    b = hidden_fact_bundle()
    a = AA.authorize(gen("TCS signed a deal worth 98765 crore with a European bank.", "A1"), b, ent(["TCS"]), UNIVERSE, "How is TCS doing?")
    assert a["authorized"] is False and "unsupported_figures" in a["reasons"]


def test_a_figure_that_exists_only_in_a_summary_the_model_never_saw_cannot_ground_a_claim():
    b = big_bundle("company")
    b.events[0]["summary"] = "TCS margins widened 77 bps in the quarter."
    a = AA.authorize(gen("TCS margins widened 77 bps in the quarter.", "E1"), b, ent(["TCS"]), UNIVERSE, "How is TCS doing?")
    assert a["authorized"] is False and "unsupported_figures" in a["reasons"]


def test_an_item_date_the_prompt_never_showed_cannot_ground_a_stated_date():
    b = big_bundle("company")
    iso = b.events[0]["event_date"][:10]
    a = AA.authorize(gen(f"TCS announced a development on {iso}.", "E1"), b, ent(["TCS"]), UNIVERSE, "How is TCS doing?")
    assert a["authorized"] is False and "unsupported_figures" in a["reasons"]


def test_a_visible_announcement_date_and_a_visible_title_figure_still_ground_claims():
    b = big_bundle("company")
    b.events[0]["title"] = "TCS wins deal worth 4321 crore"
    d = b.announcements[0]["announcement_date"][:10]
    ok_fig = AA.authorize(gen("TCS wins deal worth 4321 crore.", "E1"), b, ent(["TCS"]), UNIVERSE, "How is TCS doing?")
    ok_date = AA.authorize(gen(f"TCS informed the Exchange regarding matter 1 on {d}.", "A1"), b, ent(["TCS"]), UNIVERSE, "How is TCS doing?")
    assert ok_fig["authorized"] is True, ok_fig
    assert ok_date["authorized"] is True, ok_date


def test_the_same_hidden_fact_is_authorized_only_if_the_prompt_actually_showed_it():
    b = big_bundle("company")
    b.events[3]["title"] = "TCS signed a deal worth 98765 crore with a European bank"        # E4: inside the five the prompt shows
    a = AA.authorize(gen("TCS signed a deal worth 98765 crore with a European bank.", "E4"), b, ent(["TCS"]), UNIVERSE, "How is TCS doing?")
    assert a["authorized"] is True, a


# ── the pipeline wires it ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_pipeline_tells_the_bundle_which_prompt_it_feeds(pipe):
    b = tcs_bundle()
    b.prompt_kind = None
    pipe["set_bundle"](b)
    run_pipeline("What is happening with TCS lately? (3.4G.2 wiring)")
    assert b.prompt_kind == "company"
