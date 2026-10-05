"""
Step 4C: the PUBLIC response contract tells the truth about what kind of answer was produced. Deterministic, model-free (zero provider calls).
  UNAVAILABLE != NEUTRAL, NOT_APPLICABLE != NEUTRAL, RETRIEVAL_FAILED != NO_EVIDENCE;
  evidence_count has one meaning (evidence items listed in the response) and no human-readable count contradicts it.
"""
from __future__ import annotations

import asyncio
import copy
import inspect
import json
import re
from pathlib import Path

import pytest

from app.services import ai_service as S
from app.services.ai_search import degraded_shape as DS
from app.services.ai_search import evidence_sufficiency as SUFF
from app.services.ai_search import pipeline as P
from app.services.ai_search import postprocess as PP
from app.services.ai_search.response_finalize import _derive_answer_availability, finalize_v3_response
from app.services.ai_search.specialists import base as spec_base
from tests.services.test_ai_search_fail_closed import bundle, good_generation, pipe, run_pipeline, tcs_bundle  # noqa: F401

ART = Path(__file__).resolve().parents[2] / "benchmarks/ai_search/baseline_2026_10_04/step3_4c"


def saved(file, qid):
    return copy.deepcopy(json.loads((ART / file).read_text(encoding="utf-8"))["results"][qid]["response"])


@pytest.fixture
def no_provider(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("a provider call was made")
    monkeypatch.setattr(S, "_call_with_fallback", boom)


def no_conclusion(res):
    """The public fields a response with no authorized conclusion must never fill with one."""
    assert res["answer"]["sentiment"] is None
    assert res["investment_verdict"]["direction"] is None
    assert res["investment_verdict"]["rating"] == "Not Applicable"
    assert res["investment_verdict"]["confidence"] is None and res["answer"]["confidence"] is None
    blob = json.dumps({"answer": res["answer"], "verdict": res["investment_verdict"]}).lower()
    assert "neutral" not in blob


# ── UNAVAILABLE != NEUTRAL (every no-conclusion shape) ───────────────────────────────────────────────────────────────────────

def test_the_shared_builders_never_encode_a_neutral_conclusion():
    v = DS.empty_investment_verdict()
    assert v["rating"] == "Not Applicable" and v["direction"] is None
    r = DS.build_degraded_shape(query="q", response_id="r", schema_version="v", specialist_kind="company", degraded_reason="capacity", summary="s")
    assert r["answer"]["sentiment"] is None and r["investment_verdict"]["direction"] is None


def test_the_pre_retrieval_shell_and_the_internal_specialist_stub_never_encode_a_neutral_conclusion():
    shell = P._degraded_shell("q", "unsupported_entity", "s")
    assert shell["answer"]["sentiment"] is None and shell["investment_verdict"]["direction"] is None
    stub = spec_base.degraded_response("q", "capacity") if "capacity" in inspect.signature(spec_base.degraded_response).parameters else spec_base.degraded_response("q")
    assert stub["sentiment"] is None and stub["confidence"] is None
    assert stub["investment_verdict"]["direction"] is None and stub["investment_verdict"]["rating"] == "Not Applicable" and stub["investment_verdict"]["confidence"] is None


@pytest.mark.parametrize("case", ["insufficient", "retrieval_failed", "capacity", "gate_b"])
def test_every_refusal_and_failure_through_the_real_pipeline_carries_no_conclusion(pipe, no_provider, case):
    if case == "insufficient":
        pipe["set_bundle"](bundle())
    elif case == "retrieval_failed":
        b = bundle(); b.retrieval_failures = {"news": "LiveNewsUnavailable"}; pipe["set_bundle"](b)
    elif case == "capacity":
        pipe["set_bundle"](tcs_bundle())
    else:
        pipe["set_bundle"](tcs_bundle()); pipe["generation"] = (good_generation(claim_sources=[]), False)
    q = "How is 3M India doing as a business?" if case in ("insufficient", "retrieval_failed") else "What is happening with TCS lately?"
    _raw, res, _ = run_pipeline(q + f" (4C {case})")
    no_conclusion(res)


def test_a_deadline_cut_off_carries_no_conclusion(pipe, no_provider, monkeypatch):
    from app.services import request_deadline as RD

    async def slow(*a, **k):
        await asyncio.sleep(60)
    monkeypatch.setattr(P.evidence_mod, "collect", slow)

    async def go():
        with RD.scope(total=3.0, reserve=0.5, min_attempt=1.0, attempt_cap=1.0):
            raw, was_cached = await P.run_ai_search_v3("What is happening with TCS lately? (4C deadline)", None)
        return finalize_v3_response("q", raw, x_admin_key=None, was_cached=was_cached)
    no_conclusion(asyncio.run(go()))


def test_an_authorized_answer_still_withholds_unauthorized_structured_claims_as_null():
    r = finalize_v3_response("q", saved("openai_3_4g2.json", "EI3"), x_admin_key=None, was_cached=True)
    assert r["answer"]["sentiment"] is None and r["investment_verdict"]["direction"] is None and r["investment_verdict"]["rating"] == "Not Applicable"


# ── RETRIEVAL_FAILED != NO_EVIDENCE; capacity; deadline; Gate B ──────────────────────────────────────────────────────────

def refusal(pipe, *, failed: bool):
    b = bundle()
    if failed:
        b.retrieval_failures = {"news": "LiveNewsUnavailable"}
    pipe["set_bundle"](b)
    return run_pipeline("How is 3M India doing as a business? (4C refusal %s)" % failed)[1]


def test_gate_a_reaches_the_same_verdict_with_and_without_a_failed_source_but_the_public_answer_differs(pipe, no_provider):
    from app.api.companies import _NSE_UNIVERSE
    ents = {"companies": ["3MINDIA"], "sectors": [], "policies": []}
    a, b = bundle(), bundle()
    b.retrieval_failures = {"news": "x"}
    ga, gb = SUFF.assess("q", {}, ents, a, _NSE_UNIVERSE), SUFF.assess("q", {}, ents, b, _NSE_UNIVERSE)
    assert (ga["status"], ga["kind"], ga["missing"]) == (gb["status"], gb["kind"], gb["missing"])         # Gate A logic is untouched
    absent, failed = refusal(pipe, failed=False), refusal(pipe, failed=True)
    assert absent["degraded_reason"] == "insufficient_evidence" and failed["degraded_reason"] == "retrieval_failed"
    assert absent["answer_availability"]["state"] == "no_verified_evidence" and failed["answer_availability"]["state"] == "temporarily_unavailable"
    assert absent["answer_availability"]["evidence_retrieval_completed"] is True and failed["answer_availability"]["evidence_retrieval_completed"] is False
    assert absent["answer_availability"]["reason"] == "evidence_insufficient" and failed["answer_availability"]["reason"] == "retrieval_failed"
    assert absent["public_title"] != failed["public_title"]


def test_a_failed_search_never_says_evidence_is_missing_and_exposes_no_internals(pipe, no_provider):
    failed = refusal(pipe, failed=True)
    text = json.dumps(failed, ensure_ascii=False)
    assert failed["evidence_sufficiency"] is None                                      # no "insufficient" verdict is published for a search that did not finish
    assert not re.search(r"not enough|enough recent|doesn't currently have|no evidence|insufficient", failed["answer"]["summary"], re.IGNORECASE)
    assert "can't tell whether supporting evidence exists" in failed["answer"]["summary"]
    for leak in ("LiveNewsUnavailable", "Traceback", "Exception", "retrieval_failures", "TimeoutError"):
        assert leak not in text


def test_a_genuine_absence_still_says_so(pipe, no_provider):
    absent = refusal(pipe, failed=False)
    assert absent["evidence_sufficiency"]["status"] == "INSUFFICIENT" and "enough recent" in absent["answer"]["summary"]


def test_the_refusal_stages_are_distinct_and_neither_is_reported_as_a_cache_hit(pipe, no_provider):
    async def stages(b):
        pipe["set_bundle"](b)
        seen = []
        async for stage, _label, payload in P._run_v3_steps("How is 3M India doing as a business? (4C stages)", None):
            seen.append(stage)
        return seen
    failed_b = bundle(); failed_b.retrieval_failures = {"news": "x"}
    assert "insufficient_evidence" in asyncio.run(stages(bundle())) and "retrieval_incomplete" not in asyncio.run(stages(bundle()))
    s = asyncio.run(stages(failed_b))
    assert "retrieval_incomplete" in s and "insufficient_evidence" not in s
    raw, cached = asyncio.run(P.run_ai_search_v3("How is 3M India doing as a business? (4C cache flag)", None))
    assert cached is False


def test_capacity_deadline_retrieval_timeout_and_gate_b_have_distinct_public_reasons():
    def reason(degraded_reason, **kw):
        res = {"synthesis_incomplete": True, "degraded_reason": degraded_reason, "related_events": [{"id": "e1"}] if kw.get("evidence") else [], "news": [], "policies": []}
        return _derive_answer_availability(res, is_market_pulse=False)
    reasons = {k: reason(k)["reason"] for k in ("insufficient_evidence", "retrieval_failed", "retrieval_deadline_exceeded", "capacity", "parse_failure", "deadline_exceeded", "claims_not_authorized")}
    assert len(set(reasons.values())) == len(reasons) and reasons["capacity"] == "provider_capacity" and reasons["retrieval_failed"] != reasons["retrieval_deadline_exceeded"]
    assert reason("capacity")["state"] == "temporarily_unavailable" and reason("retrieval_failed")["state"] == "temporarily_unavailable"
    assert reason("retrieval_failed")["evidence_retrieval_completed"] is False and reason("capacity")["evidence_retrieval_completed"] is True


def test_gate_b_rejection_remains_fail_closed(pipe, no_provider):
    pipe["set_bundle"](tcs_bundle())
    pipe["generation"] = (good_generation(claim_sources=[]), False)
    raw, res, _ = run_pipeline("What is happening with TCS lately? (4C gate b)")
    assert res["degraded_reason"] == "claims_not_authorized" and res["answer_availability"]["reason"] == "claims_not_authorized"
    assert "_rejected_generation" not in res and res["synthesis_incomplete"] is True and res["key_drivers"] == []
    assert good_generation()["summary"] not in json.dumps(res)                          # the rejected text never reaches the public response


# ── educational / product answers ────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("q", ["What is a P/E ratio and how should I read it?", "How does the MarketRipple Score work?"])
def test_educational_answers_expose_no_verdict_direction_or_confidence_and_no_market_evidence_count(pipe, no_provider, q):
    _raw, res, _ = run_pipeline(q)
    no_conclusion(res)
    assert res["answer"]["confidence_level"] == "unscored" and res["confidence_data"]["score"] is None and res["confidence_breakdown"]["final_confidence"] is None
    assert res["confidence"]["status"] == "unscored" and res["confidence"]["score"] is None
    av = res["answer_availability"]
    assert av["state"] == "available" and av["basis"] == "education" and av["reason"] is None and av["evidence_count"] == 0 and av["evidence_retrieval_completed"] is False
    assert res["answer"]["sources_count"] == 0 and res["evidence_score"]["source_count"] == 0 and res["evidence_score"]["stars"] is None
    assert res["specialist"] == "education" and res["education"]["current_market_evidence"] is False
    assert res["related_events"] == [] and res["news"] == [] and res["policies"] == []


def test_an_evidence_backed_answer_is_not_labelled_educational_and_the_basis_differs():
    r = finalize_v3_response("q", saved("openai_3_4g2.json", "EI3"), x_admin_key=None, was_cached=True)
    assert r["answer_availability"]["basis"] == "retrieved_evidence" and "education" not in r


# ── evidence_count: one meaning, every public count agrees ───────────────────────────────────────────────────────────────────

def test_evidence_count_is_the_number_of_evidence_items_listed_and_the_other_public_counts_equal_it():
    for file, qid in (("openai_3_4g2.json", "EI3"), ("openai_3_4g1.json", "CC2")):
        res = saved(file, qid)
        listed = len(res["related_events"]) + len(res["news"]) + len(res["policies"])
        r = finalize_v3_response("q", res, x_admin_key=None, was_cached=True)
        assert r["answer_availability"]["evidence_count"] == listed == r["answer"]["sources_count"] == r["evidence_score"]["source_count"]


def test_the_count_normalization_is_idempotent_and_leaves_other_fields_alone():
    res = saved("openai_3_4g2.json", "EI3")
    once = finalize_v3_response("q", copy.deepcopy(res), x_admin_key=None, was_cached=True)
    twice = finalize_v3_response("q", copy.deepcopy(once), x_admin_key=None, was_cached=True)
    assert once == twice
    changed = {k for k in once if once[k] != res.get(k)}
    assert changed <= {"answer", "evidence_score", "answer_availability"}               # an authorized answer is otherwise unchanged
    assert {k for k in once["answer"] if once["answer"][k] != res["answer"].get(k)} <= {"sources_count"}


@pytest.mark.parametrize("raw,dev,expect", [
    (["9 trusted sources", "Calibrated from 102 verified predictions (57% historical accuracy)"], 9, True),
    (["26 independent developments, corroborated by 27 sources"], 26, True),
    (["2 news & event sources"], 2, True),
    (["1 independent development, corroborated by 3 sources"], 1, True),
])
def test_the_confidence_copy_never_labels_a_development_count_as_sources(raw, dev, expect):
    out = PP.public_confidence_reasons(raw, dev)
    assert not any(re.search(r"\b\d+ (?:trusted |news & event )?sources?\b", r) for r in out)
    assert any("independent development" in r and str(dev) in r for r in out)
    assert [r for r in out if r.startswith("Calibrated")] == [r for r in raw if r.startswith("Calibrated")]       # unrelated reasons untouched


def test_with_no_developments_no_source_claim_is_made_at_all():
    assert PP.public_confidence_reasons(["2 news & event sources"], 0) == []


def test_a_real_confidence_run_contains_no_sources_wording_and_no_count_that_contradicts_evidence_count(monkeypatch):
    from app.services.ai_search.evidence import EvidenceBundle

    async def no_cal():
        return {}
    monkeypatch.setattr("app.services.ai_search.prediction_recording.get_search_calibration", no_cal)
    b = EvidenceBundle()
    b.news = [{"id": f"n{i}", "headline": f"h{i}"} for i in range(3)]
    b.announcements = [{"id": f"a{i}"} for i in range(6)]
    b.development_count = 9
    bd = asyncio.run(PP.compute_confidence_breakdown(b, {"confidence_self_rating": 5}, {}))
    text = " ".join(bd["reasons"])
    assert not re.search(r"\b\d+ (?:trusted |news & event )?sources?\b", text) and "9 independent developments" in text


def test_human_readable_counts_in_a_finalized_response_agree_with_evidence_count():
    res = saved("openai_3_4g1.json", "CC2")                                              # the historical defect: "9 trusted sources" next to evidence_count 3
    dev = res["evidence_score"]["development_count"]
    for holder in (res["confidence_data"], res["confidence_breakdown"]):
        holder["reasons"] = PP.public_confidence_reasons(holder["reasons"], dev)
    r = finalize_v3_response("q", res, x_admin_key=None, was_cached=True)
    n = r["answer_availability"]["evidence_count"]
    claimed = [int(m) for m in re.findall(r"\b(\d+) (?:trusted |evidence |news & event )?(?:sources?|items?)\b", json.dumps(r["confidence_data"]["reasons"] + r["confidence_breakdown"]["reasons"]))]
    assert n == 3 and all(c == n for c in claimed)


# ── partial stays partial ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_an_authorized_answer_with_a_narrowed_scope_stays_flagged_partial():
    r = finalize_v3_response("q", saved("openai_3_4g1.json", "CC2"), x_admin_key=None, was_cached=True)
    assert r["conclusion_scope"]["partial"] is True and r["conclusion_scope"]["authorized"] == "valuation_comparison"
    assert r["answer_availability"]["state"] == "available"                              # the answer exists for the narrowed scope; the scope field carries the partiality


@pytest.mark.parametrize("reason", ["claims_not_authorized", "grounding_collapsed"])
def test_a_withheld_answer_with_some_evidence_is_limited_not_unavailable_and_not_available(reason):
    res = {"synthesis_incomplete": True, "degraded_reason": reason, "related_events": [{"id": "e1"}, {"id": "e2"}], "news": [], "policies": []}
    av = _derive_answer_availability(res, is_market_pulse=False)
    assert av["state"] == "limited_evidence" and av["evidence_count"] == 2


def test_the_four_public_states_are_all_still_reachable():
    mk = lambda **kw: _derive_answer_availability({"related_events": [], "news": [], "policies": [], **kw}, is_market_pulse=False)["state"]
    assert mk(synthesis_incomplete=False) == "available"
    assert mk(synthesis_incomplete=True, degraded_reason="grounding_collapsed", related_events=[{"id": "e"}]) == "limited_evidence"
    assert mk(synthesis_incomplete=True, degraded_reason="insufficient_evidence") == "no_verified_evidence"
    assert mk(synthesis_incomplete=True, degraded_reason="capacity") == "temporarily_unavailable"


def test_market_pulse_availability_is_unchanged_in_state():
    av = _derive_answer_availability({"type": "market_pulse", "synthesis_incomplete": False, "indices": [{"n": 1}]}, is_market_pulse=True)
    assert av["state"] == "available" and av["basis"] == "market_data" and av["evidence_count"] == 1
