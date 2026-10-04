"""
Step 3.4D-2 regressions, built from the SAVED live CC1 generation (Step 3.4C artifact, forensic at 8f73198). No provider call anywhere.

  1. Conclusion scope: valuation-only evidence authorizes a valuation comparison, never an overall company-strength conclusion; partial analysis is preserved.
  2. Structured public claims: rating/direction/sentiment/confidence/scenario probabilities/impact scores/winner blocks are never public because the LLM generated them.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE
from app.services.ai_search import answer_authorization as AA
from app.services.ai_search import claim_sources as CS
from app.services.ai_search import conclusion_scope as SC
from app.services.ai_search import structured_authorization as SA
from app.services.ai_search.evidence import EvidenceBundle
from tests.services.test_ai_search_fail_closed import NOW, ann, ent, pipe, run_pipeline  # noqa: F401

_ART = Path(__file__).resolve().parents[2] / "benchmarks" / "ai_search" / "baseline_2026_10_04" / "step3_4c" / "openai_qualification.json"
QUERY = "TCS vs Infosys, which is stronger?"
ENTS = ent(["TCS", "INFY"], names={"TCS": "Tata Consultancy Services Ltd", "INFY": "Infosys Ltd"})


def saved():
    r = json.loads(_ART.read_text(encoding="utf-8"))["results"]["CC1"]
    return r["rejected_generation"][0]["generation"], r["evidence"]


def cc1_bundle(extra_announcements=()) -> EvidenceBundle:
    """The exact CC1 bundle, rebuilt from the saved evidence index (IDs asserted equal to the saved ones)."""
    _gen, ev = saved()
    b = EvidenceBundle()
    b.plan_kind, b.premise = "comparison", {}
    idx = ev["index"]
    for e in (x for x in idx if x["kind"] == "event"):
        b.events.append({"id": 1, "title": e["title"], "summary": e["summary"], "event_date": e["date"], "companies": [{"symbol": s} for s in e["companies"]]})
    for n in (x for x in idx if x["kind"] == "news"):
        b.news.append({"id": 1, "headline": n["title"], "summary": n["summary"], "published_at": n["date"], "source": n["source"]})
    for a in (x for x in idx if x["kind"] == "announcement"):
        b.announcements.append({"id": a["ref"].split(":", 1)[1], "subject": a["title"], "announcement_date": a["date"], "symbol": (a["companies"] or [None])[0], "category": "General"})
    b.announcements += list(extra_announcements)
    b.valuation = ev["valuation"]
    b.context_lines = list(ev["context_lines"])
    if not extra_announcements:
        assert [(x["id"], x["title"]) for x in b.index()] == [(x["id"], x["title"]) for x in idx]
    return b


def authorized_prose_variant(mutate=None) -> dict:
    """The saved generation with claim_sources rebuilt so EVERY factual sentence is covered verbatim: its prose passes Gate B, isolating the structured-claims question."""
    gen, _ = saved()
    g = copy.deepcopy(gen)
    if mutate:
        mutate(g)
    claims = []
    for s in CS.factual_sentences(g):
        low = s.lower()
        src = ["C1", "C2"] if ("13.3" in s or "15.1" in s) else (["A2"] if "tcs" in low else []) + (["A3"] if "infosys" in low else []) if ("best buy" in low and "columbia" in low) else ["A2"] if "best buy" in low else ["A3"] if "columbia" in low else ["E1"] if "us enterprise" in low else ["A2", "A3"]
        claims.append({"claim": s, "sources": src})
    g["claim_sources"] = claims
    return g


# ── 1. conclusion scope ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_saved_cc1_evidence_authorizes_a_valuation_comparison_not_overall_strength():
    s = SC.assess(QUERY, {"is_comparison": True}, ENTS, cc1_bundle(), UNIVERSE)
    assert s["requested"] == SC.OVERALL and s["authorized"] == SC.VALUATION_COMPARISON and s["partial"] is True
    assert s["missing"] == ["operating_evidence_TCS", "operating_evidence_INFY"]
    assert all(c["valuation"] and not c["operating"] for c in s["coverage"].values())


def test_operating_evidence_for_both_companies_authorizes_overall_strength():
    extra = [ann("a9", "Tata Consultancy Services Limited has informed the Exchange regarding financial results for the quarter, revenue and net profit", "TCS"),
             ann("a10", "Infosys Limited has informed the Exchange regarding financial results for the quarter, revenue and net profit", "INFY")]
    s = SC.assess(QUERY, {"is_comparison": True}, ENTS, cc1_bundle(extra), UNIVERSE)
    assert s["authorized"] == SC.OVERALL and s["partial"] is False and s["missing"] == []


def test_operating_evidence_for_only_one_company_is_still_partial():
    extra = [ann("a9", "Tata Consultancy Services Limited has informed the Exchange regarding financial results for the quarter", "TCS")]
    s = SC.assess(QUERY, {"is_comparison": True}, ENTS, cc1_bundle(extra), UNIVERSE)
    assert s["partial"] is True and s["missing"] == ["operating_evidence_INFY"]


@pytest.mark.parametrize("q", ["Which is cheaper, TCS or Infosys?", "Compare TCS and Infosys P/E", "Is TCS overvalued relative to Infosys?", "TCS vs Infosys valuation multiples"])
def test_a_valuation_question_is_fully_answered_by_valuation_evidence(q):
    s = SC.assess(q, {"is_comparison": True}, ENTS, cc1_bundle(), UNIVERSE)
    assert s["requested"] == SC.VALUATION and s["authorized"] == SC.VALUATION_COMPARISON and s["partial"] is False


@pytest.mark.parametrize("q", ["TCS vs Infosys, which is stronger?", "Which is the better company, TCS or Infosys?", "TCS or Infosys: which should I pick?"])
def test_broad_comparison_questions_request_overall_strength(q):
    assert SC.assess(q, {"is_comparison": True}, ENTS, cc1_bundle(), UNIVERSE)["requested"] == SC.OVERALL


def test_administrative_and_pr_items_do_not_count_as_operating_evidence():
    s = SC.assess(QUERY, {}, ENTS, cc1_bundle(), UNIVERSE)       # the saved bundle has a Best Buy PR, a Columbia PR, a share allotment, a management change, a meeting schedule
    assert not any(c["operating"] for c in s["coverage"].values())


def test_non_comparison_is_not_applicable():
    b = cc1_bundle()
    b.plan_kind = "company"
    assert SC.assess("How is TCS doing?", {}, ent(["TCS"]), b, UNIVERSE)["authorized"] == SC.NOT_APPLICABLE


@pytest.mark.parametrize("sentence,flagged", [
    ("Infosys is the stronger company overall.", True),
    ("Infosys is the better business and the winner of this comparison.", True),
    ("Investors should prefer Infosys over TCS.", True),
    ("Infosys is the stronger valuation-led choice at a P/E of 13.3 versus 15.1.", False),
    ("Infosys looks cheaper on P/B, at 4.54 versus 6.85.", False),
    ("The evidence does not establish which company is stronger overall.", False),
    ("A durable ranking requires growth and margin data that is not available.", False),
])
def test_overall_winner_sentences_are_overreach_only_when_unqualified_and_unhedged(sentence, flagged):
    partial = {"partial": True}
    got = SC.overreach({"summary": sentence}, partial)
    assert bool(got) is flagged, sentence


def test_overreach_is_ignored_when_the_full_conclusion_is_authorized():
    assert SC.overreach({"summary": "Infosys is the stronger company overall."}, {"partial": False}) == []


def test_the_saved_cc1_prose_is_valuation_scoped_so_it_is_not_overreach():
    gen, _ = saved()
    s = SC.assess(QUERY, {}, ENTS, cc1_bundle(), UNIVERSE)
    assert SC.overreach(gen, s) == []        # the saved prose hedged correctly; the problem was the structured fields beside it


def test_an_overall_winner_sentence_fails_gate_b_when_scope_is_partial_end_to_end(pipe):
    pipe["set_bundle"](cc1_bundle())

    def overall(g):
        g["summary"] = g["bottom_line"] = "Infosys is the stronger company overall."
    pipe["generation"] = (authorized_prose_variant(overall), False)
    raw, res, _ = run_pipeline("TCS vs Infosys, which is stronger? (3.4D-2 overreach)")
    assert res["degraded_reason"] == "claims_not_authorized" and "conclusion_scope_exceeded" in res["answer_authorization"]["reasons"]
    assert res["investment_verdict"]["rating"] == "Not Applicable" and "stronger company overall" not in json.dumps(res).lower()


# ── 2. structured claims: unit ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_sanitize_withholds_every_structured_analytical_claim_in_the_saved_generation():
    gen, _ = saved()
    clean, withheld = SA.sanitize(gen)
    assert clean["investment_verdict"] == {"rating": "Not Applicable", "direction": None, "confidence": None, "horizon": "", "top_picks": [], "risks": [], "catalysts": [], "opportunity_score": None,
                                           "risk_level": "", "suitable_for": ""}
    assert clean["scenarios"] == {} and clean["decision_intelligence"] == {} and clean["decision_engine_v2"] == {} and clean["opportunity_risk_matrix"] == {}
    assert clean["ai_conclusion"] == {} and clean["timeline_intelligence"] == {}
    assert clean["sentiment"] is None and clean["confidence"] is None and clean["confidence_self_rating"] is None
    assert all(c["impact_score"] is None and c["impact_type"] is None and c["confidence"] is None for c in clean["companies"])
    assert all(s["score"] is None and s["outlook"] is None and s["positive"] is None for s in clean["sectors"])
    assert all(d["confidence"] is None for d in clean["key_drivers"])
    for expected in ("investment_verdict", "scenarios", "decision_intelligence", "ai_conclusion", "sentiment", "companies.impact", "sectors.outlook", "key_drivers.confidence"):
        assert expected in withheld, expected


def test_sanitize_keeps_prose_and_names_and_does_not_mutate_its_input():
    gen, _ = saved()
    before = json.dumps(gen, sort_keys=True)
    clean, _ = SA.sanitize(gen)
    assert json.dumps(gen, sort_keys=True) == before
    assert clean["summary"] == gen["summary"] and clean["claim_sources"] == gen["claim_sources"]
    assert [c["symbol"] for c in clean["companies"]] == [c["symbol"] for c in gen["companies"]]
    assert clean["companies"][0]["reason"] == gen["companies"][0]["reason"]
    assert clean["key_drivers"][0]["title"] == gen["key_drivers"][0]["title"]


def test_sanitize_does_not_invent_a_neutral_cautious_or_no_clear_edge_conclusion():
    gen, _ = saved()
    clean, _ = SA.sanitize(gen)
    blob = json.dumps({k: clean[k] for k in ("investment_verdict", "ai_conclusion", "decision_engine_v2", "decision_intelligence", "scenarios")}).lower()
    assert not any(w in blob for w in ("neutral", "cautious", "no clear edge", "balanced", "hold", "mixed"))
    assert clean["investment_verdict"]["direction"] is None and clean["sentiment"] is None


def test_sanitize_of_an_answer_with_no_structured_claims_reports_nothing_withheld():
    clean, withheld = SA.sanitize({"summary": "TCS filed a result disclosure.", "claim_sources": []})
    assert withheld == [] and SA.public_summary(withheld)["state"] == "none_generated"


# ── 2. structured claims: end to end with the REAL assembly (only network/enrichment stubbed) ─────────────────────────────────────────

LEAKS = ("Selectively Constructive", "bullish", "Positive")


@pytest.fixture
def real_assembly(pipe, monkeypatch):
    from app.services.ai_search import enrichment as EN
    from app.services.ai_search import pipeline as P
    monkeypatch.setattr(EN, "_enrich_sync", lambda cos: [dict(c) for c in cos])
    monkeypatch.setattr(EN, "_fetch_chart_sync", lambda t: {"labels": [], "series": []})

    async def no_graph(*a, **k):
        return {"nodes": [], "edges": [], "ripple_chain": []}
    monkeypatch.setattr(P.ripple_graph_mod, "build", no_graph)
    return pipe


def test_saved_cc1_structured_claims_never_reach_public_output(real_assembly):
    pipe = real_assembly
    pipe["set_bundle"](cc1_bundle())
    g = authorized_prose_variant()
    assert AA.authorize(g, cc1_bundle(), ENTS, UNIVERSE, QUERY)["authorized"] is True      # the prose passes Gate B: only the structured claims are in question
    pipe["generation"] = (g, False)
    # run with the exact saved query intent (comparison) through the real assembly and finalizer
    import app.services.ai_search.entities as entities_mod
    raw, res, _ = run_pipeline("TCS vs Infosys, which is stronger? (3.4D-2 structured)")
    assert pipe["specialist"] == 1 and res["synthesis_incomplete"] is False and res["answer_authorization"]["authorized"] is True
    v = res["investment_verdict"]
    assert v["rating"] == "Not Applicable" and v["direction"] is None and v["top_picks"] == [] and v["catalysts"] == []
    assert v["rating"] != "Selectively Constructive" and v["direction"] != "bullish"
    assert res["answer"]["sentiment"] is None
    assert res["scenarios"] == {}
    assert res["ai_conclusion"] == {} and res["decision_engine_v2"] == {} and res["opportunity_risk_matrix"] == {} and res["timeline_intelligence"] == {}
    assert not res["decision_intelligence"] or "engine_recommendation" not in res["decision_intelligence"]
    assert all(c["impact_score"] is None and c["impact_type"] is None and c["confidence"] is None for c in res["companies"])
    assert all(s.get("score") is None and s.get("outlook") is None and "status" not in s for s in res["sectors"])
    assert all(d["confidence"] is None for d in res["key_drivers"])
    blob = json.dumps(res, ensure_ascii=False, default=str)
    assert not any(w in blob for w in ("Selectively Constructive", '"bullish"', '"current_view": "Positive"'))
    for forbidden_number in ('"probability": 30', '"probability": 50', '"probability": 20', '"impact_score": 58', '"confidence": 86', '"confidence": 72'):
        assert forbidden_number not in blob, forbidden_number
    # what stays: the sourced prose and an honest account of what was withheld
    assert res["structured_authorization"]["state"] == "unavailable" and "investment_verdict" in res["structured_authorization"]["withheld"]
    assert res["conclusion_scope"]["partial"] is True and res["conclusion_scope"]["authorized"] == "valuation_comparison"
    assert any("valuation comparison only" in c for c in res["confidence_data"]["caveats"])
    assert "P/E" in res["answer"]["summary"] or "13.3" in res["answer"]["summary"]


def test_engine_recommendation_is_not_attached_when_the_conclusion_is_only_partial(real_assembly):
    pipe = real_assembly
    pipe["set_bundle"](cc1_bundle())
    pipe["generation"] = (authorized_prose_variant(), False)
    _raw, res, _ = run_pipeline("TCS vs Infosys, which is stronger? (3.4D-2 engine)")
    assert "engine_recommendation" not in (res.get("decision_intelligence") or {})


def test_confidence_remains_the_deterministic_evidence_grounded_value(real_assembly):
    pipe = real_assembly
    pipe["set_bundle"](cc1_bundle())
    pipe["generation"] = (authorized_prose_variant(), False)
    _raw, res, _ = run_pipeline("TCS vs Infosys, which is stronger? (3.4D-2 confidence)")
    assert res["answer"]["confidence"] == res["confidence_data"]["score"] == res["confidence_breakdown"]["final_confidence"]
    assert res["answer"]["confidence"] != 69      # the model's self-rated 69 is not what is shown


def test_degraded_responses_carry_the_new_keys_as_none(pipe):
    pipe["set_bundle"](cc1_bundle())
    pipe["generation"] = None
    _raw, res, _ = run_pipeline("TCS vs Infosys, which is stronger? (3.4D-2 degraded)")
    assert res["degraded_reason"] == "capacity" and res["conclusion_scope"] is None and res["structured_authorization"] is None
