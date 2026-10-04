"""
Step 3.4A regressions: Gate A (pre-model evidence sufficiency) and Gate B (post-model answer authorization), reproducing the live CR2 failure from Step 3.3b.

The CR2 fixture is the REAL generation Gemini returned for "How is 3M India doing as a business?" with an empty evidence bundle (saved in step3_3b_gemini/gemini_qualification.json):
a confident analysis, a bullish verdict, invented earnings-release dates and scenario figures, and `claim_sources: []`. These tests prove that today that question never reaches a specialist, and
that even if it did, the generation would be withheld and nothing from it would reach a client. No model is called anywhere in this file.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE
from app.services.ai_search import answer_authorization as AA
from app.services.ai_search import evidence_sufficiency as ES
from app.services.ai_search import figures as FG
from app.services.ai_search import market_pulse as mp_mod
from app.services.ai_search import pipeline as P
from app.services.ai_search import safety_gate
from app.services.ai_search.evidence import EvidenceBundle
from app.services.ai_search.response_finalize import _derive_answer_availability, finalize_v3_response
from app.services.ai_search.specialists.base import parse_specialist_json

_FIXTURE = Path(__file__).resolve().parents[2] / "benchmarks" / "ai_search" / "baseline_2026_10_04" / "step3_3b_gemini" / "gemini_qualification.json"
CR2_QUERY = "How is 3M India doing as a business?"
NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def ent(companies=(), sectors=(), policies=(), names=None):
    return {"companies": list(companies), "company_matches": [{"symbol": s, "name": (names or {}).get(s, s)} for s in companies], "sectors": list(sectors), "policies": list(policies)}


def bundle(plan="company", events=(), news=(), announcements=(), policies=(), valuation=None, sector_rows=None, premise=None, context=()):
    b = EvidenceBundle()
    b.plan_kind, b.premise = plan, premise or {}
    b.events, b.news, b.policies = list(events), list(news), list(policies)
    b.announcements, b.valuation, b.sector_rows, b.context_lines = list(announcements), valuation or {}, sector_rows or [], list(context)
    return b


def ann(i, subject, symbol, days=3):
    return {"id": i, "subject": subject, "category": "General", "announcement_date": (NOW - timedelta(days=days)).isoformat(), "symbol": symbol}


def ev_row(i, title, companies=(), days=3, summary=""):
    d = (NOW - timedelta(days=days)).isoformat()
    return {"id": i, "title": title, "summary": summary, "category": "Market", "impact_score": 60, "companies": [{"symbol": s} for s in companies], "event_date": d, "published_at": d, "date": ""}


def news_row(i, headline, published="1h ago", summary=""):
    return {"id": i, "headline": headline, "summary": summary, "published_at": published, "source": "ET"}


def real_cr2_generation() -> dict:
    d = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    raw = d["results"]["CR2"]["calls"][0]["raw_output"]
    parsed, degraded = parse_specialist_json(raw, CR2_QUERY)
    assert degraded is False
    return parsed


# ── Gate A, unit: sufficiency is about the question's requirement, never a count ────────────────────────────────────────────────────────

def test_cr2_empty_bundle_is_insufficient_for_a_company_assessment():
    r = ES.assess(CR2_QUERY, {}, ent(["3MINDIA"]), bundle(), UNIVERSE)
    assert r["status"] == ES.INSUFFICIENT and r["kind"] == "company_assessment" and r["missing"] == ["current_company_evidence"]
    assert r["reason"] == "no_recent_company_evidence" and r["missing_entities"] == ["3MINDIA"]


def test_ten_irrelevant_items_still_count_as_zero_company_evidence():
    ev = [ev_row(f"e{i}", "RBI holds repo rate", days=2) for i in range(10)]
    news = [news_row(f"n{i}", "Nifty ends flat as banks drag") for i in range(5)]
    assert ES.assess(CR2_QUERY, {}, ent(["3MINDIA"]), bundle(events=ev, news=news), UNIVERSE)["status"] == ES.INSUFFICIENT


def test_administrative_filings_alone_do_not_satisfy_a_company_assessment():
    b = bundle(announcements=[ann("a1", "3M India Limited has informed the Exchange about Newspaper Publication", "3MINDIA"), ann("a2", "3M India Limited has informed the Exchange about Trading Window closure", "3MINDIA"),
                              ann("a3", "3M India Limited has informed the Exchange about General Updates", "3MINDIA")])
    assert ES.assess(CR2_QUERY, {}, ent(["3MINDIA"]), b, UNIVERSE)["status"] == ES.INSUFFICIENT


def test_one_substantive_company_filing_is_enough_for_a_company_assessment():
    b = bundle(announcements=[ann("a1", "3M India Limited has informed the Exchange regarding Outcome of Board Meeting and financial results", "3MINDIA")])
    r = ES.assess(CR2_QUERY, {}, ent(["3MINDIA"]), b, UNIVERSE)
    assert r["status"] == ES.SUFFICIENT and r["satisfied"] == ["current_company_evidence"]


def test_bel_event_with_an_unestablished_premise_is_insufficient_even_with_other_bel_material():
    premise = {"required": True, "terms": ["order"], "supported": False, "supporting": []}
    b = bundle(announcements=[ann("a1", "Bharat Electronics Limited has informed the Exchange regarding a press release", "BEL")], premise=premise)
    r = ES.assess("BEL just won a new defence order, what does this mean for the stock?", {"intent": "news_reaction"}, ent(["BEL"]), b, UNIVERSE)
    assert r["status"] == ES.INSUFFICIENT and r["kind"] == "event_impact" and r["missing"] == ["event_verification"] and r["reason"] == "event_premise_not_established"


def test_a_supported_event_premise_is_sufficient():
    premise = {"required": True, "terms": ["order"], "supported": True, "supporting": ["Bharat Electronics ... orders worth Rs 1,200 crore"]}
    r = ES.assess("BEL just won a new defence order", {}, ent(["BEL"]), bundle(premise=premise), UNIVERSE)
    assert r["status"] == ES.SUFFICIENT


def test_a_comparison_never_lets_one_companys_evidence_stand_in_for_the_others():
    b = bundle("comparison", announcements=[ann("a1", "Tata Consultancy Services Limited has informed the Exchange regarding results", "TCS")], valuation={"TCS": {"pe": 15.1, "pb": 6.8}})
    r = ES.assess("TCS vs Infosys, which is stronger?", {"is_comparison": True}, ent(["TCS", "INFY"]), b, UNIVERSE)
    assert r["status"] == ES.INSUFFICIENT and r["missing_entities"] == ["INFY"] and r["satisfied"] == ["evidence_for_TCS"]


def test_a_comparison_is_sufficient_when_each_side_has_evidence_or_valuation():
    b = bundle("comparison", announcements=[ann("a1", "Tata Consultancy Services Limited has informed the Exchange regarding results", "TCS")], valuation={"TCS": {"pe": 15.1}, "INFY": {"pe": 13.3, "pb": 4.5}})
    assert ES.assess("TCS vs Infosys", {"is_comparison": True}, ent(["TCS", "INFY"]), b, UNIVERSE)["status"] == ES.SUFFICIENT


def test_a_sector_assessment_is_not_satisfied_by_one_companys_filing():
    b = bundle("topic", events=[ev_row("t1", "Tera Software Limited has informed the Exchange that Board approved fund raising")])
    r = ES.assess("What is the outlook for the IT services sector?", {}, ent(sectors=["it"]), b, UNIVERSE)
    assert r["status"] == ES.INSUFFICIENT and r["missing"] == ["sector_evidence_it"]


def test_a_sector_assessment_is_satisfied_by_a_sector_wide_item_or_the_live_sector_row():
    wide = bundle("topic", events=[ev_row("s1", "US enterprise IT spending contracts for second consecutive quarter", ["TCS", "INFY", "WIPRO"])])
    assert ES.assess("IT sector outlook", {}, ent(sectors=["it"]), wide, UNIVERSE)["status"] == ES.SUFFICIENT
    row = bundle("topic", sector_rows=[{"name": "IT", "value": "+1.7%"}])
    assert ES.assess("IT sector outlook", {}, ent(sectors=["it"]), row, UNIVERSE)["status"] == ES.SUFFICIENT


def test_macro_transmission_needs_the_stated_condition_and_the_named_sector():
    q = "What happens to Indian banks if the RBI cuts the repo rate?"
    e = ent(sectors=["banking"], policies=["rbi", "repo rate"])
    cond_only = bundle("topic", news=[news_row("n1", "Repo rate may climb to 6% in FY27, economists say")])
    r = ES.assess(q, {}, e, cond_only, UNIVERSE)
    assert r["status"] == ES.INSUFFICIENT and r["missing"] == ["sector_evidence_banking"] and r["satisfied"] == ["macro_condition_evidence"]
    both = bundle("topic", news=[news_row("n1", "Repo rate may climb to 6% in FY27, economists say"), news_row("n2", "Bank credit growth slows as lenders cut loan rates")], sector_rows=[{"name": "Banking", "value": "-0.4%"}])
    assert ES.assess(q, {}, e, both, UNIVERSE)["status"] == ES.SUFFICIENT


def test_a_sector_scan_needs_live_sector_rows():
    assert ES.assess("Which sectors look weak in the market at the moment?", {}, ent(), bundle("topic"), UNIVERSE)["status"] == ES.INSUFFICIENT
    assert ES.assess("Which sectors look weak in the market at the moment?", {}, ent(), bundle("topic", sector_rows=[{"name": "IT", "value": "-1%"}]), UNIVERSE)["status"] == ES.SUFFICIENT


def test_explanations_are_not_gated_here():
    assert ES.assess("What is a P/E ratio and how should I read it?", {}, ent(), bundle("explanation"), UNIVERSE)["kind"] == "not_gated"


def test_public_messages_say_what_cannot_be_established_without_advisory_language():
    r = ES.assess(CR2_QUERY, {}, ent(["3MINDIA"], names={"3MINDIA": "3M India Ltd"}), bundle(), UNIVERSE)
    title, body = ES.public_message(r, ent(["3MINDIA"], names={"3MINDIA": "3M India Ltd"}), UNIVERSE)
    assert title == "Not enough recent evidence" and "3M India" in body and "won't infer" in body
    premise = {"required": True, "terms": ["order"], "supported": False}
    r2 = {"kind": "event_impact", "missing_entities": ["BEL"]}
    t2, b2 = ES.public_message(r2, ent(["BEL"], names={"BEL": "Bharat Electronics Ltd"}), UNIVERSE, premise)
    assert t2 == "I couldn't verify the stated event" and "Bharat Electronics" in b2 and "order" in b2


# ── Gate A, end to end: the specialist is never called ──────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def pipe(monkeypatch):
    calls = {"specialist": 0}

    async def no_classifier(q):
        return False

    def stub(kind):
        async def run(query, evidence, intent_data, entities):
            calls["specialist"] += 1
            return calls.get("generation") or ({"_degraded_reason": "capacity"}, True)
        return run

    monkeypatch.setattr(mp_mod, "_classify_market_pulse_llm", no_classifier)
    monkeypatch.setattr(P.cache_mod, "get_response", lambda *a, **k: None)
    monkeypatch.setattr(P.cache_mod, "set_response", lambda *a, **k: None, raising=False)
    for name in ("company_specialist", "comparison_specialist", "sector_specialist"):
        monkeypatch.setattr(getattr(P, name), "run", stub(name))

    def set_bundle(b):
        async def fake_collect(query, intent_data, entities, db):
            return b
        monkeypatch.setattr(P.evidence_mod, "collect", fake_collect)

    calls["set_bundle"] = set_bundle
    return calls


def run_pipeline(query):
    async def go():
        raw, was_cached = await P.run_ai_search_v3(query, None)
        return raw, finalize_v3_response(query, raw, x_admin_key=None, was_cached=was_cached), was_cached
    return asyncio.run(go())


def test_cr2_with_zero_evidence_never_calls_a_specialist_and_invents_nothing(pipe):
    pipe["set_bundle"](bundle())
    raw, res, cached = run_pipeline("How is 3M India doing as a business? (gate A case 1)")
    assert pipe["specialist"] == 0 and cached is False
    assert res["degraded_reason"] == "insufficient_evidence" and res["synthesis_incomplete"] is True
    text = json.dumps(res, ensure_ascii=False).lower()
    for leaked in ("zero-debt", "honeywell", "siemens", "bullish", "constructive", "2026-11-10", "2027-02-12", "18%", "200 bps", "return capital"):
        assert leaked not in text, leaked
    assert res["investment_verdict"]["rating"] == "Not Applicable" and res["answer"]["confidence"] is None
    assert res["timeline"] == [] and res["scenarios"] == {} and res["key_drivers"] == [] and res["companies"] == []
    assert res["evidence_sufficiency"]["status"] == "INSUFFICIENT" and res["evidence_sufficiency"]["missing"] == ["current_company_evidence"]
    assert res["public_title"] == "Not enough recent evidence"
    assert res["answer_availability"]["state"] == "no_verified_evidence"


def test_bel_with_an_unestablished_premise_never_calls_a_specialist(pipe):
    b = bundle(announcements=[ann("a1", "Bharat Electronics Limited has informed the Exchange regarding a press release", "BEL")], premise={"required": True, "terms": ["order"], "supported": False, "supporting": []})
    pipe["set_bundle"](b)
    raw, res, _ = run_pipeline("BEL just won a new defence order, what does this mean for the stock? (gate A case 2)")
    assert pipe["specialist"] == 0 and res["degraded_reason"] == "insufficient_evidence"
    assert res["premise_check"]["status"] == "not_established" and res["evidence_sufficiency"]["kind"] == "event_impact"
    assert res["investment_verdict"]["rating"] == "Not Applicable" and "confirmed" in res["answer"]["summary"]


def test_a_comparison_missing_one_side_never_calls_a_specialist(pipe):
    b = bundle("comparison", announcements=[ann("a1", "Tata Consultancy Services Limited has informed the Exchange regarding results", "TCS")], valuation={"TCS": {"pe": 15.1}})
    pipe["set_bundle"](b)
    raw, res, _ = run_pipeline("TCS vs Infosys, which is stronger? (gate A case 3)")
    assert pipe["specialist"] == 0 and res["evidence_sufficiency"]["missing_entities"] == ["INFY"] and res["decision_intelligence"] is None


def test_insufficiency_responses_pass_the_recommendation_language_safety_gate(pipe):
    pipe["set_bundle"](bundle())
    raw, res, _ = run_pipeline("How is 3M India doing as a business? (gate A safety)")
    assert safety_gate.find_v3_safety_violation(res) is None


def test_insufficient_responses_are_not_cached_and_do_not_record_predictions(pipe):
    pipe["set_bundle"](bundle())
    q = "How is 3M India doing as a business? (gate A cache)"
    run_pipeline(q)
    pipe["set_bundle"](bundle(announcements=[ann("a1", "3M India Limited has informed the Exchange regarding financial results", "3MINDIA")]))
    pipe["generation"] = ({"_degraded_reason": "capacity"}, True)
    _raw, res, _ = run_pipeline(q)
    assert pipe["specialist"] == 1 and res["degraded_reason"] != "insufficient_evidence"   # the second run reached the specialist: nothing was cached from the first


# ── Gate B, unit: the real CR2 generation is not authorized ─────────────────────────────────────────────────────────────────────────────

def test_the_real_cr2_generation_is_rejected_for_every_reason_it_should_be():
    gen = real_cr2_generation()
    assert gen.get("claim_sources") == []
    auth = AA.authorize(gen, bundle(), ent(["3MINDIA"]), UNIVERSE, CR2_QUERY)
    assert auth["applicable"] and auth["authorized"] is False
    assert "claim_sources_missing" in auth["reasons"] and "unsupported_figures" in auth["reasons"]
    values = {f["value"] for f in auth["unsupported_figures"]}
    assert {"2026-11-10", "2027-02-12"} <= values and "18%" in values and "200" in values
    assert not any(v in values for v in ("85", "82"))      # the model's own confidence fields are structured numbers, not prose


def test_a_rejected_generation_never_leaks_into_the_public_response():
    gen = real_cr2_generation()
    b = bundle()
    auth = AA.authorize(gen, b, ent(["3MINDIA"]), UNIVERSE, CR2_QUERY)
    AA.REJECTED_GENERATIONS.clear()
    res = P._build_rejected_response(CR2_QUERY, gen, b, ent(["3MINDIA"]), {}, "company", auth)
    assert res["degraded_reason"] == "claims_not_authorized" and "_rejected_generation" in res and res["_rejected_generation"]["generation"] is gen
    public = finalize_v3_response(CR2_QUERY, res, x_admin_key=None, was_cached=False)
    assert "_rejected_generation" not in public
    text = json.dumps(public, ensure_ascii=False).lower()
    for leaked in ("zero-debt", "honeywell", "siemens", "bullish", "constructive", "2026-11-10", "2027-02-12", "18%", "200 bps", "operational performance"):
        assert leaked not in text, leaked
    assert public["investment_verdict"]["rating"] == "Not Applicable" and public["answer"]["confidence"] is None
    assert public["timeline"] == [] and public["scenarios"] == {} and public["key_drivers"] == []
    assert public["answer_authorization"]["authorized"] is False and "claim_sources_missing" in public["answer_authorization"]["reasons"]
    assert public["public_title"] == "This analysis couldn't be verified" and safety_gate.find_v3_safety_violation(public) is None
    assert AA.REJECTED_GENERATIONS[-1]["generation"] is gen and AA.REJECTED_GENERATIONS[-1]["reasons"] == auth["reasons"]


def tcs_bundle():
    return bundle("company", announcements=[ann("a1", "Tata Consultancy Services Limited has informed the Exchange regarding financial results", "TCS")])


def good_generation(**over):
    sent = "TCS filed a financial results disclosure with the Exchange."
    g = {"summary": sent, "bottom_line": sent, "what_happened": "", "claim_sources": [{"claim": sent, "sources": ["A1"]}], "timeline": [], "scenarios": {}, "key_drivers": [], "companies": []}
    g.update(over)
    return g


def test_a_fully_sourced_generation_is_authorized():
    auth = AA.authorize(good_generation(), tcs_bundle(), ent(["TCS"]), UNIVERSE, "What is happening with TCS lately?")
    assert auth["authorized"] is True and auth["reasons"] == []


def test_empty_claim_sources_with_a_factual_sentence_is_rejected():
    auth = AA.authorize(good_generation(claim_sources=[]), tcs_bundle(), ent(["TCS"]), UNIVERSE, "What is happening with TCS lately?")
    assert auth["authorized"] is False and auth["reasons"] == ["claim_sources_missing"]


def test_a_generation_with_no_factual_sentences_and_no_claim_sources_is_not_blocked_for_that_reason():
    g = good_generation(claim_sources=[], summary="The picture depends on how the evidence develops.", bottom_line="The picture depends on how the evidence develops.")
    assert AA.authorize(g, tcs_bundle(), ent(["TCS"]), UNIVERSE, "What is happening with TCS lately?")["authorized"] is True


def test_an_unknown_source_id_is_rejected():
    g = good_generation(claim_sources=[{"claim": "TCS filed a financial results disclosure with the Exchange.", "sources": ["A9"]}])
    assert "unknown_source" in AA.authorize(g, tcs_bundle(), ent(["TCS"]), UNIVERSE, "q")["reasons"]


def test_an_ineligible_source_for_a_factual_claim_is_rejected():
    b = bundle("company", news=[news_row("n1", "Top 3 stocks to buy: HDFC Bank, Infosys, BEL by Ganesh Dongre | Target price, stop-loss")], premise={})
    sent = "Bharat Electronics won a new defence order."
    g = good_generation(summary=sent, bottom_line=sent, claim_sources=[{"claim": sent, "sources": ["N1"]}])
    auth = AA.authorize(g, b, ent(["BEL"]), UNIVERSE, "BEL outlook")
    assert auth["authorized"] is False and "ineligible_sources" in auth["reasons"]


def test_an_uncovered_factual_sentence_is_rejected():
    g = good_generation(what_happened="Quarterly revenue rose 14% year on year.")
    auth = AA.authorize(g, tcs_bundle(), ent(["TCS"]), UNIVERSE, "q")
    assert auth["authorized"] is False and "uncovered_factual_sentences" in auth["reasons"]


def test_an_invented_date_hidden_in_the_timeline_is_rejected_even_when_the_prose_is_sourced():
    g = good_generation(timeline=[{"date": "2026-11-10", "title": "Q2 FY27 Earnings Release", "description": "The company reports quarterly results."}])
    auth = AA.authorize(g, tcs_bundle(), ent(["TCS"]), UNIVERSE, "q")
    assert auth["authorized"] is False and auth["reasons"] == ["unsupported_figures"]


def test_scenario_figures_not_in_the_evidence_are_rejected():
    g = good_generation(scenarios={"bull": {"outcome": "Volume growth exceeds 18% YoY with margin expansion above 200 bps."}})
    assert "unsupported_figures" in AA.authorize(g, tcs_bundle(), ent(["TCS"]), UNIVERSE, "q")["reasons"]


def test_a_claim_restating_an_unestablished_premise_is_rejected():
    b = bundle("company", announcements=[ann("a1", "Bharat Electronics Limited has informed the Exchange about Outcome of Board Meeting", "BEL")], premise={"required": True, "terms": ["order"], "supported": False})
    sent = "Bharat Electronics won a large defence order."
    g = good_generation(summary=sent, bottom_line=sent, claim_sources=[{"claim": sent, "sources": ["A1"]}])
    assert "premise_unsupported" in AA.authorize(g, b, ent(["BEL"]), UNIVERSE, "BEL just won a defence order")["reasons"]


def test_explanations_are_not_subject_to_the_gate_yet():
    auth = AA.authorize({"summary": "A P/E ratio of 20 means investors pay 20 times earnings."}, bundle("explanation"), ent(), UNIVERSE, "What is a P/E ratio?")
    assert auth["applicable"] is False and auth["authorized"] is True


# ── Gate B, end to end ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_sufficient_question_reaches_the_specialist_and_an_unauthorized_generation_is_withheld(pipe):
    pipe["set_bundle"](tcs_bundle())
    pipe["generation"] = (good_generation(claim_sources=[]), False)
    raw, res, _ = run_pipeline("What is happening with TCS lately? (gate B case 1)")
    assert pipe["specialist"] == 1
    assert res["degraded_reason"] == "claims_not_authorized" and "_rejected_generation" not in res
    assert res["answer_authorization"]["reasons"] == ["claim_sources_missing"] and res["investment_verdict"]["rating"] == "Not Applicable"
    assert "_rejected_generation" in raw      # kept internally, before the finalizer strips it
    assert res["answer_availability"]["state"] in ("limited_evidence", "no_verified_evidence")


def test_an_authorized_generation_is_assembled_and_carries_the_decision(pipe, monkeypatch):
    async def fake_assemble(query, ai, evidence, kind, was_degraded, report, db, entities, **kw):
        return {"query": query, "response_id": "r1", "synthesis_incomplete": False, "answer": {"summary": ai["summary"]}, "companies": [], "investment_verdict": {"rating": "Neutral"}}
    monkeypatch.setattr(P, "_assemble_response", fake_assemble)
    pipe["set_bundle"](tcs_bundle())
    pipe["generation"] = (good_generation(), False)
    raw, res, _ = run_pipeline("What is happening with TCS lately? (gate B case 2)")
    assert res["synthesis_incomplete"] is False and res["answer_authorization"]["authorized"] is True and res["evidence_sufficiency"]["status"] == "SUFFICIENT"


def test_a_specialist_capacity_failure_is_not_reported_as_an_authorization_failure(pipe):
    pipe["set_bundle"](tcs_bundle())
    raw, res, _ = run_pipeline("What is happening with TCS lately? (gate B capacity)")
    assert res["degraded_reason"] == "capacity" and "_rejected_generation" not in raw


# ── figures ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_dates_in_any_common_format_pass_only_when_the_evidence_contains_them():
    ai = {"timeline": [{"date": "2026-10-01", "title": "Results"}, {"date": "2026-11-10", "title": "Results"}], "summary": "The meeting was on 1 Oct 2026 and the next is on Nov 10, 2026."}
    flagged = {f["value"] for f in FG.unsupported_figures(ai, "Press release dated October 1, 2026", "q", today=NOW.date())}
    assert flagged == {"2026-11-10"}


def test_todays_date_and_the_questions_own_numbers_are_allowed():
    ai = {"summary": "As of 4 Oct 2026 the question assumes a 12% move."}
    assert FG.unsupported_figures(ai, "", "Why did it fall 12% last week?", today=NOW.date()) == []


def test_years_fiscal_labels_horizons_and_structured_numbers_are_exempt():
    ai = {"summary": "For FY27 and Q2 over the next 6-12 months, 3 factors matter in 2027.", "key_drivers": [{"title": "Demand", "explanation": "Steady.", "confidence": 85}],
          "scenarios": {"bull": {"probability": 25, "outcome": "Better."}}}
    assert FG.unsupported_figures(ai, "", "q", today=NOW.date()) == []


def test_figures_present_in_the_evidence_pass():
    ai = {"summary": "Nifty IT fell 11% in September and the rupee is near 95.44."}
    assert FG.unsupported_figures(ai, "Nifty IT crashes 11% in September. Rupee holds steady at 95.44", "q", today=NOW.date()) == []


# ── finalizer ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_answer_availability_for_the_new_reasons():
    base = {"synthesis_incomplete": True, "related_events": [], "news": [], "policies": []}
    assert _derive_answer_availability({**base, "degraded_reason": "insufficient_evidence"}, is_market_pulse=False)["state"] == "no_verified_evidence"
    shown = {**base, "degraded_reason": "claims_not_authorized", "related_events": [{"id": 1}]}
    assert _derive_answer_availability(shown, is_market_pulse=False)["state"] == "limited_evidence"
    assert _derive_answer_availability({**base, "degraded_reason": "claims_not_authorized"}, is_market_pulse=False)["state"] == "no_verified_evidence"
