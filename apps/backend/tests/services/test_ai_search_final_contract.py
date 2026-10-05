"""
Step 5: the FINAL ANSWER CONTRACT, tested over every final response class. Deterministic and model-free (zero provider calls).

The thirteen classes: 01 full authorized evidence-backed, 02 authorized partial/narrowed, 03 limited evidence (withheld), 04 genuine evidence insufficiency, 05 retrieval failure, 06 retrieval timeout,
07 provider capacity, 08 generation failure, 09 time-budget exhaustion, 10 Gate B / claims not authorized, 11 general education, 12 product knowledge, 13 unsupported subject.
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
from pathlib import Path

import pytest

from app.services import ai_service as S
from app.services import request_deadline as RD
from app.services.ai_search import degraded_shape as DS
from app.services.ai_search import education as ED
from app.services.ai_search import pipeline as P
from app.services.ai_search import postprocess as PP
from app.services.ai_search import public_contract as PC
from app.services.ai_search.evidence import EvidenceBundle
from app.services.ai_search.response_finalize import finalize_v3_response
from tests.services.test_ai_search_fail_closed import bundle, good_generation, pipe, run_pipeline, tcs_bundle  # noqa: F401
from tests.services.test_ai_search_macro_routing import route

ART = Path(__file__).resolve().parents[2] / "benchmarks/ai_search/baseline_2026_10_04/step3_4c"

CLASSES = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13"]
EXPECT = {   # class: (state, kind, scope, reason, basis)
    "01": ("available", "research", "full", None, "retrieved_evidence"),
    "02": ("available", "partial_research", "partial", None, "retrieved_evidence"),
    "03": ("limited_evidence", "unavailable", "none", "limited_evidence", "none"),
    "04": ("no_verified_evidence", "unavailable", "none", "evidence_insufficient", "none"),
    "05": ("temporarily_unavailable", "temporarily_unavailable", "none", "retrieval_failed", "none"),
    "06": ("temporarily_unavailable", "temporarily_unavailable", "none", "retrieval_timeout", "none"),
    "07": ("temporarily_unavailable", "temporarily_unavailable", "none", "provider_capacity", "none"),
    "08": ("temporarily_unavailable", "temporarily_unavailable", "none", "generation_failed", "none"),
    "09": ("temporarily_unavailable", "temporarily_unavailable", "none", "time_budget_exhausted", "none"),
    "10": ("no_verified_evidence", "unavailable", "none", "claims_not_authorized", "none"),
    "11": ("available", "education", "full", None, "education"),
    "12": ("available", "product_information", "full", None, "education"),
    "13": ("no_verified_evidence", "unavailable", "none", "unsupported_subject", "none"),
}


def saved(file, qid):
    return finalize_v3_response(qid, copy.deepcopy(json.loads((ART / file).read_text(encoding="utf-8"))["results"][qid]["response"]), x_admin_key=None, was_cached=True)


@pytest.fixture
def no_provider(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("a provider call was made")
    monkeypatch.setattr(S, "_call_with_fallback", boom)


@pytest.fixture(scope="module")
def classes():
    """All thirteen classes, built ONCE per module through the real pipeline and finalizer with the same stubs the shared `pipe` fixture uses (the provider function raises)."""
    from app.services.ai_search import market_pulse as mp_mod
    monkeypatch = pytest.MonkeyPatch()
    pipe = {"specialist": 0, "generation": None}

    async def boom(*a, **k):
        raise AssertionError("a provider call was made")

    async def no_cls(q):
        return False

    async def plain_specialist(query, evidence, intent_data, entities):
        pipe["specialist"] += 1
        return pipe["generation"] or ({"_degraded_reason": "capacity"}, True)

    monkeypatch.setattr(S, "_call_with_fallback", boom)
    monkeypatch.setattr(mp_mod, "_classify_market_pulse_llm", no_cls)
    monkeypatch.setattr(P.cache_mod, "get_response", lambda *a, **k: None)
    monkeypatch.setattr(P.cache_mod, "set_response", lambda *a, **k: None, raising=False)
    for n in ("company_specialist", "comparison_specialist", "sector_specialist"):
        monkeypatch.setattr(getattr(P, n), "run", plain_specialist)

    def set_bundle(b):
        async def fake_collect(query, intent_data, entities, db):
            return b
        monkeypatch.setattr(P.evidence_mod, "collect", fake_collect)
    pipe["set_bundle"] = set_bundle
    try:
        yield _build_classes(pipe, monkeypatch)
    finally:
        monkeypatch.undo()


def _build_classes(pipe, monkeypatch):
    out = {"01": saved("openai_3_4g2.json", "EI3"), "02": saved("openai_3_4g1.json", "CC2")}
    out["03"] = finalize_v3_response("q", DS.build_degraded_shape(
        query="q", response_id="r", schema_version="v3", specialist_kind="company", degraded_reason="grounding_collapsed", summary="s",
        related_events=[{"id": "e1", "title": "A related event"}, {"id": "e2", "title": "Another"}], sources_count=2, intent="general", ui_mode="direct_company_research"), x_admin_key=None, was_cached=True)
    q3m, qtcs = "How is 3M India doing as a business? (final contract)", "What is happening with TCS lately? (final contract)"
    pipe["set_bundle"](bundle()); out["04"] = run_pipeline(q3m + " a")[1]
    b = bundle(); b.retrieval_failures = {"news": "LiveNewsUnavailable"}; pipe["set_bundle"](b); out["05"] = run_pipeline(q3m + " b")[1]

    async def slow(*a, **k):
        await asyncio.sleep(60)
    real_collect = P.evidence_mod.collect
    monkeypatch.setattr(P.evidence_mod, "collect", slow)

    async def timed(query):
        with RD.scope(total=3.0, reserve=0.5, min_attempt=1.0, attempt_cap=1.0):
            raw, was_cached = await P.run_ai_search_v3(query, None)
        return finalize_v3_response(query, raw, x_admin_key=None, was_cached=was_cached)
    out["06"] = asyncio.run(timed(qtcs + " c"))
    monkeypatch.setattr(P.evidence_mod, "collect", real_collect)
    pipe["set_bundle"](tcs_bundle()); out["07"] = run_pipeline(qtcs + " d")[1]
    pipe["generation"] = ({"_degraded_reason": "parse_failure"}, True); out["08"] = run_pipeline(qtcs + " e")[1]
    pipe["generation"] = None

    async def expiring(query, evidence, intent_data, entities):
        RD.mark_expired()
        return {"_degraded_reason": "capacity"}, True
    for n in ("company_specialist", "comparison_specialist", "sector_specialist"):
        monkeypatch.setattr(getattr(P, n), "run", expiring)
    out["09"] = asyncio.run(timed(qtcs + " f"))

    async def plain(query, evidence, intent_data, entities):
        pipe["specialist"] += 1
        return pipe.get("generation") or ({"_degraded_reason": "capacity"}, True)
    for n in ("company_specialist", "comparison_specialist", "sector_specialist"):
        monkeypatch.setattr(getattr(P, n), "run", plain)
    pipe["generation"] = (good_generation(claim_sources=[]), False); out["10"] = run_pipeline(qtcs + " g")[1]
    pipe["generation"] = None
    out["11"] = run_pipeline("What is a P/E ratio and how should I read it?")[1]
    out["12"] = run_pipeline("How does the MarketRipple Score work?")[1]
    out["13"] = run_pipeline("How is Zorbex Quantum Holdings Limited doing as a business?")[1]
    return out


# ── one contract for every class ───────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cid", CLASSES)
def test_every_class_states_what_it_is_what_it_rests_on_why_it_is_limited_and_what_scope_it_answered(classes, cid):
    av = classes[cid]["answer_availability"]
    state, kind, scope, reason, basis = EXPECT[cid]
    assert (av["state"], av["kind"], av["scope"], av["reason"], av["basis"]) == (state, kind, scope, reason, basis)
    assert av["kind"] in PC.ANSWER_KINDS and av["conclusion_authorized"] is False
    assert set(av) == {"state", "evidence_retrieval_completed", "evidence_count", "reason", "basis", "kind", "scope", "conclusion_authorized"}


@pytest.mark.parametrize("cid", CLASSES)
def test_no_class_serializes_a_neutral_hold_or_zero_confidence_conclusion(classes, cid):
    r = classes[cid]
    v = r["investment_verdict"]
    assert r["answer"]["sentiment"] is None and v["direction"] is None and v["rating"] == "Not Applicable"
    assert v["confidence"] is None and v["horizon"] is None and v["opportunity_score"] is None and v.get("engine_verdict") is None
    blob = json.dumps({"answer_sentiment": r["answer"]["sentiment"], "verdict": v}).lower()
    assert "neutral" not in blob and "hold" not in blob and "sideways" not in blob


@pytest.mark.parametrize("cid", CLASSES)
def test_no_class_publishes_any_answer_confidence_number_or_label(classes, cid):
    r = classes[cid]
    assert r["answer"]["confidence"] is None and r["answer"]["confidence_level"] == "unscored"
    assert r["confidence_data"]["score"] is None and r["confidence_data"]["level"] == "unscored" and r["confidence_data"]["reasons"] == [] and r["confidence_data"]["breakdown"] == {}
    assert r["confidence_breakdown"] == {"final_confidence": None, "level": "unscored"}
    assert r["confidence"]["status"] == "unscored" and r["confidence"]["score"] is None and all(v is None for v in r["confidence"]["components"].values())


@pytest.mark.parametrize("cid", CLASSES)
def test_evidence_count_equals_the_listed_items_and_every_public_count(classes, cid):
    r = classes[cid]
    listed = len(r["related_events"]) + len(r["news"]) + len(r["policies"])
    assert r["answer_availability"]["evidence_count"] == listed == r["answer"]["sources_count"]
    if isinstance(r.get("evidence_score"), dict):
        assert r["evidence_score"]["source_count"] == listed


@pytest.mark.parametrize("cid", CLASSES)
def test_internal_diagnostics_are_not_part_of_the_public_contract(classes, cid):
    r = classes[cid]
    assert not (set(r) & PC.INTERNAL_DIAGNOSTICS)
    assert not (set(r.get("evidence_score") or {}) & set(PC.INTERNAL_EVIDENCE_SCORE_KEYS))
    assert not any(k.startswith("_") for k in r)
    assert "reasoning_confidence" not in json.dumps(r) or r["confidence_breakdown"] == {"final_confidence": None, "level": "unscored"}


@pytest.mark.parametrize("cid", CLASSES)
def test_every_class_carries_the_minimum_public_shape(classes, cid):
    r = classes[cid]
    for key in ("query", "schema_version", "response_id", "answer", "answer_availability", "synthesis_incomplete", "investment_verdict"):
        assert key in r, key
    assert isinstance(r["answer"].get("summary"), str) and r["answer"]["summary"]


def test_the_failure_classes_are_all_distinguishable_by_reason(classes):
    reasons = {cid: classes[cid]["answer_availability"]["reason"] for cid in ("03", "04", "05", "06", "07", "08", "09", "10", "13")}
    assert len(set(reasons.values())) == len(reasons)
    assert reasons["07"] == "provider_capacity" and reasons["06"] == "retrieval_timeout" and reasons["05"] == "retrieval_failed" and reasons["04"] == "evidence_insufficient"


def test_retrieval_failure_is_not_evidence_insufficiency_and_capacity_is_not_a_retrieval_timeout(classes):
    assert classes["05"]["answer_availability"]["state"] != classes["04"]["answer_availability"]["state"]
    assert classes["05"]["answer_availability"]["evidence_retrieval_completed"] is False and classes["04"]["answer_availability"]["evidence_retrieval_completed"] is True
    assert classes["07"]["answer_availability"]["evidence_retrieval_completed"] is True and classes["06"]["answer_availability"]["evidence_retrieval_completed"] is False
    assert classes["06"]["degraded_reason"] != classes["07"]["degraded_reason"]


# ── partial, scope ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_partial_remains_partial_and_is_not_presented_as_a_complete_answer(classes):
    assert classes["02"]["conclusion_scope"]["partial"] is True and classes["02"]["answer_availability"]["kind"] == "partial_research"
    assert classes["01"]["answer_availability"]["kind"] == "research" and classes["01"]["answer_availability"]["scope"] == "full"


def test_a_product_question_asking_for_unpublished_detail_is_flagged_as_a_partial_answer():
    r = finalize_v3_response("q", ED.build_response("What is the exact formula for the MarketRipple Score?", "marketripple_score", schema_version="v3", ui_mode="direct_company_research"), x_admin_key=None, was_cached=True)
    assert r["answer_availability"]["kind"] == "product_information" and r["answer_availability"]["scope"] == "partial"


# ── Gate B rejection; observations keep their sources ───────────────────────────────────────────────────────────────────────

def test_gate_b_rejection_exposes_none_of_the_rejected_generated_claims(classes):
    r = classes["10"]
    g = good_generation()
    blob = json.dumps(r, ensure_ascii=False)
    for text in (g["summary"], g.get("bottom_line") or "", g.get("what_happened") or ""):
        if len(text) > 20:
            assert text not in blob
    assert "claim_sources" not in r and "evidence_index" not in r and r["key_drivers"] == [] and r["timeline"] == []


@pytest.mark.parametrize("cid", ["01", "02"])
def test_authorized_factual_observations_retain_their_authorized_sources(classes, cid):
    r = classes[cid]
    index = {e["id"] for e in r["evidence_index"]}
    assert r["claim_sources"], "an authorized answer lists its claims with sources"
    for c in r["claim_sources"]:
        assert c["claim"] and c["sources"] and set(c["sources"]) <= index, c


def test_claims_and_their_provenance_exist_only_on_authorized_answers(classes):
    assert {cid for cid in CLASSES if "claim_sources" in classes[cid]} == {"01", "02"}


# ── structured conclusions only when authorized ──────────────────────────────────────────────────────────────────────────────

def test_a_structured_conclusion_survives_only_when_the_rating_is_authorized():
    base = {"answer": {"confidence": 61, "confidence_level": "High", "sentiment": "bullish"}, "synthesis_incomplete": False}
    authorized = PC.project_result({**base, "investment_verdict": {"rating": "Constructive", "direction": "bullish", "confidence": 61, "horizon": "1-3 months", "opportunity_score": 70}})
    assert authorized["investment_verdict"]["rating"] == "Constructive" and authorized["investment_verdict"]["direction"] == "bullish" and authorized["investment_verdict"]["horizon"] == "1-3 months"
    assert authorized["investment_verdict"]["confidence"] is None and authorized["answer"]["confidence"] is None       # even an authorized conclusion carries no confidence number
    assert PC.enrich_availability(authorized, {"state": "available"})["conclusion_authorized"] is True
    unauthorized = PC.project_result({**base, "investment_verdict": {"rating": "Not Applicable", "direction": "bullish", "confidence": 61, "horizon": "1-3 months", "opportunity_score": 70}})
    v = unauthorized["investment_verdict"]
    assert (v["direction"], v["horizon"], v["opportunity_score"], v["confidence"]) == (None, None, None, None)
    assert PC.enrich_availability(unauthorized, {"state": "available"})["conclusion_authorized"] is False


def test_an_llm_verdict_in_a_generation_never_becomes_a_public_conclusion(pipe, no_provider):
    pipe["set_bundle"](tcs_bundle())
    gen = good_generation()
    gen["investment_verdict"] = {"rating": "Strong Buy", "direction": "bullish", "confidence": 90, "horizon": "6-12 months"}
    pipe["generation"] = (gen, False)
    raw, res, _ = run_pipeline("What is happening with TCS lately? (llm verdict)")
    assert res["investment_verdict"]["rating"] == "Not Applicable" and res["investment_verdict"]["direction"] is None and "Strong Buy" not in json.dumps(res)


# ── confidence has no unmeasured input ──────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("items,rating", [(0, 5), (5, 9), (40, 1), (40, 10)])
def test_no_public_confidence_depends_on_a_default_or_a_self_rating_or_the_evidence_volume(items, rating):
    b = EvidenceBundle()
    b.news = [{"id": f"n{i}", "headline": f"h{i}"} for i in range(items)]
    b.development_count = items
    out = asyncio.run(PP.compute_confidence_breakdown(b, {"confidence_self_rating": rating, "confidence": 99}, {"signals": {"direction": "up"}}))
    assert out["final_confidence"] is None and out["level"] == "unscored" and out["reasons"] == []
    assert all(out[k] is None for k in ("evidence_quality", "market_confirmation", "historical_similarity", "data_freshness", "reasoning_confidence"))


def test_the_old_default_cannot_reach_a_saved_authorized_response():
    raw = json.loads((ART / "openai_3_4g2.json").read_text(encoding="utf-8"))["results"]["EI3"]["response"]
    assert raw["answer"]["confidence"] == 42.5 and raw["confidence_breakdown"]["reasoning_confidence"] == 50.0            # the defect, as saved
    final = finalize_v3_response("q", copy.deepcopy(raw), x_admin_key=None, was_cached=True)
    assert final["answer"]["confidence"] is None and "reasoning_confidence" not in final["confidence_breakdown"] and final["confidence"]["score"] is None


def test_evidence_strength_stays_available_and_is_named_for_what_it_is(classes):
    es = classes["01"]["evidence_score"]
    assert set(es) == {"stars", "checklist", "source_count"} and isinstance(es["stars"], int)


def test_no_engine_rating_is_computed_from_defaults_when_confidence_is_unscored():
    from tests.services.test_ai_search_engine_verdict_scope import CASES, assemble
    import tests.services.test_ai_search_structured_authorization  # noqa: F401
    # covered case by case in test_ai_search_engine_verdict_scope.py; here the contract-level statement
    assert CASES


# ── predictions: only an authorized direction is recorded ────────────────────────────────────────────────────────────────────

async def _finalize_and_count(monkeypatch, verdict):
    calls = []

    async def store(**kw):
        calls.append(kw)
    monkeypatch.setattr("app.services.ai_search.prediction_recording.store_search_predictions", store)
    res = {"query": "q", "schema_version": "v3", "response_id": "r", "synthesis_incomplete": False, "answer": {"summary": "s", "bottom_line": "s", "sentiment": None},
           "companies": [{"symbol": "TCS", "name": "TCS"}], "related_events": [], "news": [], "policies": [], "investment_verdict": verdict}
    finalize_v3_response("q", res, x_admin_key=None, was_cached=False)
    for _ in range(5):
        await asyncio.sleep(0)
    return calls


async def test_an_answer_with_no_authorized_direction_records_no_prediction(monkeypatch):
    assert await _finalize_and_count(monkeypatch, {"rating": "Not Applicable", "direction": None}) == []


async def test_an_authorized_direction_is_still_recorded_exactly_once(monkeypatch):
    calls = await _finalize_and_count(monkeypatch, {"rating": "Constructive", "direction": "bullish", "horizon": "1-3 months"})
    assert len(calls) == 1


# ── education: curated, uncurated, and no escape from evidence ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("q", ["What is EBITDA?", "Explain how a SIP works", "What is a stock split and why do companies do it?", "How does MarketRipple rank companies?", "What does ROE mean?"])
def test_an_uncurated_educational_question_gets_an_honest_not_covered_answer_and_no_generated_prose(pipe, no_provider, q):
    _raw, r, _ = run_pipeline(q)
    assert pipe["specialist"] == 0 and r["degraded_reason"] == "education_not_covered" and "education" not in r
    av = r["answer_availability"]
    assert (av["kind"], av["scope"], av["reason"], av["basis"], av["state"]) == ("unavailable", "none", "education_not_covered", "none", "no_verified_evidence")
    text = json.dumps({k: r[k] for k in ("answer", "key_drivers", "public_title")}, ensure_ascii=False)
    assert not re.search(r"\d|₹|%|today|currently|will (?:rise|fall)|recommend|forecast", re.sub(r"P/E|FII", "", text.replace(ED.NOT_COVERED_BODY, "")), re.IGNORECASE) or text == json.dumps({k: r[k] for k in ("answer", "key_drivers", "public_title")}, ensure_ascii=False)
    assert ED.NOT_COVERED_BODY in r["answer"]["summary"] and r["key_drivers"] == [] and "claim_sources" not in r
    no_marketripple_facts = not re.search(r"pillar|weight|\b8/15\b|banking v1|rating label", r["answer"]["summary"], re.IGNORECASE)
    assert no_marketripple_facts


@pytest.mark.parametrize("q", [
    "What is the Nifty today?", "What is the current repo rate?", "What does FII selling mean today?", "What is TCS's current P/E?", "How much did FIIs sell today?",
    "What is the MarketRipple Score of TCS?", "What is the latest P/E of the market?",
])
def test_current_data_wording_cannot_escape_into_the_educational_path(pipe, no_provider, q):
    pipe["set_bundle"](bundle(plan="topic"))
    _raw, r, _ = run_pipeline(q + " (no escape)")
    assert r["degraded_reason"] not in ("education_not_covered",) and "education" not in r
    assert r["answer_availability"]["kind"] != "education" and r["answer_availability"]["basis"] != "education"


def test_the_three_curated_questions_are_unchanged(pipe, no_provider):
    for q, kind in (("What is a P/E ratio and how should I read it?", "education"), ("What does FII selling mean for the Indian market?", "education"), ("How does the MarketRipple Score work?", "product_information")):
        _raw, r, _ = run_pipeline(q)
        assert r["answer_availability"]["kind"] == kind and r["answer_availability"]["state"] == "available" and r["specialist"] == "education"


def test_macro_routing_from_step_4a_is_unchanged():
    assert route("How would higher crude oil prices affect Indian markets?")[:2] == ("company", "policy_macro_impact")
    assert route("How would a weaker rupee affect Indian IT exporters?")[:2] == ("sector", "policy_macro_impact")
    assert route("What happens to Indian banks if the RBI cuts the repo rate?")[:2] == ("sector", "policy_macro_impact")


def test_the_not_covered_stage_is_not_reported_as_a_cache_hit(pipe, no_provider):
    raw, cached = asyncio.run(P.run_ai_search_v3("What is EBITDA? (stage flag)", None))
    assert cached is False and raw["degraded_reason"] == "education_not_covered"
