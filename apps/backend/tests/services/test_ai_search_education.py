"""
Step 4B: educational / product-knowledge contract. Deterministic and model-free (zero provider calls).
  * GE1 (P/E), GE2 (FII selling), GE3 (MarketRipple Score) are answered by a fixed contract built only from MarketRipple's own written sources, with no model call;
  * the same topics asked as CURRENT-DATA or COMPANY questions never use the contract and still need evidence;
  * nothing MarketRipple-specific can be invented, because the answer text is the source text.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from app.services import ai_service as S
from app.services.ai_search import education as ED
from app.services.ai_search import entities as E
from app.services.ai_search import evidence_filter as EF
from app.services.ai_search import evidence_sufficiency as SUFF
from app.services.ai_search.response_finalize import finalize_v3_response
from tests.services.test_ai_search_fail_closed import bundle, pipe, run_pipeline  # noqa: F401

REPO = Path(__file__).resolve().parents[4]
QUESTIONS = {q["id"]: q["query"] for q in json.loads((Path(__file__).resolve().parents[2] / "benchmarks/ai_search/baseline_2026_10_04/questions.json").read_text(encoding="utf-8"))["questions"]}
GE1, GE2, GE3 = QUESTIONS["GE1"], QUESTIONS["GE2"], QUESTIONS["GE3"]


def topic(q):
    return ED.topic_for(q, E.extract_entities(q))


# ── recognition ────────────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("q,expected", [(GE1, "pe_ratio"), (GE2, "fii_flows"), (GE3, "marketripple_score")])
def test_the_three_frozen_questions_use_their_contract(q, expected):
    assert topic(q) == expected


@pytest.mark.parametrize("q", [
    "What is TCS's current P/E?", "What is the P/E ratio of TCS?", "What is a P/E of 25?", "What is the P/E ratio of the banking sector?", "What is a good P/E ratio for IT stocks?",
    "How much did FIIs sell today?", "What does FII selling mean today?", "How is the latest FII selling affecting the Nifty?", "What is FII net selling this week?",
    "What is TCS's MarketRipple Score?", "What is the MarketRipple Score of HDFC Bank today?", "What is the current MarketRipple Score for banks?",
    "What is the Nifty today?", "Explain P/E and FII selling",
])
def test_company_current_numeric_or_multi_topic_questions_never_use_the_contract(q):
    assert topic(q) is None


# ── educational vs current-data: the retrieval plan and Gate A keep data questions evidence-bound ───────────────────────────

@pytest.mark.parametrize("q", ["What is a P/E ratio?", "What does FII selling mean for the Indian market?"])
def test_a_plain_definition_keeps_the_explanation_plan(q):
    assert EF.plan_for(q, {}, E.extract_entities(q)).kind == "explanation"


@pytest.mark.parametrize("q", ["What is the Nifty today?", "What is the price of gold today?", "What is the current repo rate?", "What does FII selling mean today?", "What is the latest P/E of the market?"])
def test_a_data_question_cannot_take_the_evidence_free_explanation_plan(q):
    assert EF.plan_for(q, {}, E.extract_entities(q)).kind != "explanation"


class _Empty:
    plan_kind = "topic"
    events: list = []
    news: list = []
    announcements: list = []
    policies: list = []
    sector_rows: list = []
    valuation: dict = {}
    macro_indices: list = []
    context_lines: list = []
    premise: dict = {}


@pytest.mark.parametrize("q", ["What is the Nifty today?", "How much did FIIs sell today?"])
def test_gate_a_refuses_those_data_questions_when_no_evidence_exists(q):
    from app.api.companies import _NSE_UNIVERSE
    ents = E.extract_entities(q)
    plan = EF.plan_for(q, {}, ents).kind
    assert plan == "topic"
    ev = _Empty()
    ev.plan_kind = plan
    assert SUFF.assess(q, {}, ents, ev, _NSE_UNIVERSE)["status"] == SUFF.INSUFFICIENT


# ── content: educational, no market claims, no advice ────────────────────────────────────────────────────────────────────

def resp(q, tid=None):
    return ED.build_response(q, tid or topic(q), schema_version="v3", ui_mode="direct_company_research")


@pytest.mark.parametrize("q", [GE1, GE2])
def test_general_education_is_plainly_educational_and_makes_no_market_or_company_claim(q):
    r = resp(q)
    text = ED.public_text(r)
    assert r["education"]["kind"] == ED.KIND_GENERAL and r["education"]["current_market_evidence"] is False
    assert r["specialist"] == "education" and r["synthesis_incomplete"] is False and r["degraded_reason"] is None
    assert not re.search(r"₹|\bcrore\b|\bcr\b|%|\btoday\b|\bcurrently\b|\bthis (week|month|year)\b", text, re.IGNORECASE)
    assert not re.search(r"\b(?:you should|we recommend|recommended|will (?:rise|fall|crash|rally|go up|go down)|is expected to|price target|strong buy|sell now)\b", text, re.IGNORECASE)
    assert "not a forecast" in text or "not a market forecast" in text            # says what it is not
    from app.api.companies import _NSE_UNIVERSE
    names = {c.get("symbol") for c in _NSE_UNIVERSE if c.get("symbol") and len(c["symbol"]) > 3}
    assert not any(re.search(r"\b" + re.escape(n) + r"\b", text) for n in names)  # no company is named


def test_ge1_covers_definition_reading_and_limits_from_its_source():
    t = ED.public_text(resp(GE1))
    for fragment in ["share price divided by its earnings per share", "how many rupees investors are willing to pay for every one rupee of a company's current annual profit",
                     "Higher P/E generally reflects higher expected future growth", "lower P/E can mean the stock is undervalued, or that the market expects earnings to decline",
                     "against the company's own historical average, against direct sector peers, or against the broader index", "one-off items"]:
        assert fragment in t or fragment.replace("Higher", "higher") in t, fragment


def test_ge2_covers_what_it_is_the_typical_effect_and_the_limits():
    t = ED.public_text(resp(GE2))
    for fragment in ["selling Indian securities", "net selling", "sustained FII buying or selling can meaningfully move the Nifty and the rupee", "a headwind for the market, all else equal",
                     "US interest rates, dollar strength, and risk appetite across all emerging markets", "the market often stays range-bound rather than falling sharply", "does not report how much FIIs bought or sold"]:
        assert fragment in t, fragment


@pytest.mark.parametrize("q", ["Should I buy stocks when FII selling is high?", "Will FII selling crash the market?"])
def test_an_education_question_asking_for_advice_or_a_forecast_gets_the_explanation_and_a_clear_refusal(q):
    q = "What does FII selling mean? " + q
    r = resp(q, "fii_flows")
    assert r["education"]["advice_requested"] is True and ED.ADVICE_NOTICE in r["answer"]["bottom_line"]
    assert not re.search(r"\bwill (?:rise|fall|crash|rally)\b", ED.public_text(r))


# ── MarketRipple Score: grounded in the deployed methodology, nothing invented ──────────────────────────────────────────────

def test_ge3_is_grounded_product_knowledge_with_the_published_pillars_bands_and_requirements():
    r = resp(GE3)
    t = ED.public_text(r)
    assert r["education"]["kind"] == ED.KIND_PRODUCT and r["education"]["grounding"] == "MarketRipple Score methodology"
    for fragment in ["Financial Strength 8/15", "Valuation 4/15", "Market Behaviour 3/15", "Strong is 75 to 100", "Positive is 60 to 74", "Neutral is 45 to 59", "Cautious is 0 to 44",
                     "Banks are scored on bank metrics", "Gross NPA %", "CET1 Ratio", "at least 65% overall evidence coverage", "Banking and 19 non-bank sectors",
                     "not a prediction of future share-price returns and not a recommendation about any stock", "never blends a subset of them with adjusted weights"]:
        assert fragment in t, fragment


def test_ge3_does_not_contain_the_superseded_four_pillar_definition():
    t = ED.public_text(resp(GE3)).lower()
    for stale in ["40%", "20%", "15%", "25%", "four pillars", "four weighted", "banking v1", "current intelligence (25"]:
        assert stale not in t, stale


@pytest.mark.parametrize("q", [
    "What is the exact formula for the MarketRipple Score?",
    "How does the MarketRipple Score weight each metric inside Financial Strength?",
    "What is the backtested accuracy of the MarketRipple Score?",
    "What is the secret algorithm behind the MarketRipple Score?",
])
def test_requests_for_detail_the_methodology_does_not_publish_get_a_notice_and_no_invention(q):
    base = resp(GE3)
    r = resp(q, "marketripple_score")
    assert r["education"]["beyond_published_detail"] is True
    assert r["answer"]["summary"] == base["answer"]["summary"] and r["key_drivers"][:-1] == base["key_drivers"]      # the published content is unchanged
    assert r["key_drivers"][-1]["explanation"] == ED.NOT_PUBLISHED_NOTICE
    assert r["answer"]["bottom_line"] == base["answer"]["bottom_line"] + " " + ED.NOT_PUBLISHED_NOTICE       # the only additions are the notice
    assert not re.search(r"\d", ED.NOT_PUBLISHED_NOTICE)                                                    # no new number, weight or band


@pytest.mark.parametrize("q", ["Is the MarketRipple Score a buy signal?", "Does a high MarketRipple Score mean the stock will go up?", "Will a high MarketRipple Score give good returns?"])
def test_product_questions_that_ask_for_prediction_or_advice_get_the_published_not_a_prediction_statement(q):
    assert topic(q) == "marketripple_score"
    r = resp(q)
    assert r["education"]["advice_requested"] is True
    assert "not a prediction of future share-price returns" in r["answer"]["bottom_line"] and ED.ADVICE_NOTICE in r["answer"]["bottom_line"]


# ── sources stay in sync ─────────────────────────────────────────────────────────────────────────────────────────────────────

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip()


def glossary_block(slug: str) -> str:
    src = (REPO / "apps/web/lib/glossary-data.ts").read_text(encoding="utf-8")
    i = src.index(f'slug: "{slug}"')
    j = src.find("slug:", i + 10)
    return norm(src[i: j if j != -1 else None])


def deployed_methodology() -> str | None:
    p = subprocess.run(["git", "show", "origin/main:apps/web/app/(knowledge)/methodology/marketripple-score/page.tsx"], cwd=REPO, capture_output=True)
    return norm(p.stdout.decode("utf-8")) if p.returncode == 0 and p.stdout else None


PE_COPIED = ["how many rupees investors are willing to pay for every one rupee of a company's current annual profit", "A P/E of 25 means the market is valuing the stock at 25 times its earnings",
             "higher expected future growth (or, sometimes, overvaluation)", "lower P/E can mean the stock is undervalued, or that the market expects earnings to decline",
             "against the company's own historical average, against direct sector peers, or against the broader index",
             "A P/E of 40 might be cheap for a fast-growing tech company and expensive for a slow-growing utility"]
FII_COPIED = [("fii", "large foreign entities that"), ("fii", "sustained FII buying or selling can meaningfully move the Nifty and the rupee"),
              ("fii", "FII flow data is watched closely as a sentiment indicator for how global capital views India relative to other emerging markets"),
              ("fii", "a headwind for the market, all else equal"),
              ("fii", "US interest rates, dollar strength, and risk appetite across all emerging markets all influence whether foreign money is flowing in or out"),
              ("dii", "the market often stays range-bound rather than falling sharply")]


@pytest.mark.parametrize("fragment", PE_COPIED)
def test_the_pe_contract_text_is_copied_from_the_glossary(fragment):
    assert fragment in glossary_block("pe-ratio")
    assert fragment in norm(ED.public_text(resp(GE1)))


@pytest.mark.parametrize("slug,fragment", FII_COPIED)
def test_the_fii_contract_text_is_copied_from_the_glossary(slug, fragment):
    assert fragment in glossary_block(slug)
    assert fragment in norm(ED.public_text(resp(GE2)))


def test_the_only_authored_sentence_is_declared_for_owner_review():
    declared = ED.TOPICS["pe_ratio"].authored_for_contract
    assert len(declared) == 1 and declared[0] in ED.public_text(resp(GE1))
    assert ED.TOPICS["fii_flows"].authored_for_contract == () and ED.TOPICS["marketripple_score"].authored_for_contract == ()


def test_ge3_facts_match_the_deployed_methodology_page():
    page = deployed_methodology()
    if page is None:
        pytest.skip("origin/main is not available in this checkout")
    for fact in ["8/15", "4/15", "3/15", "75 – 100", "60 – 74", "45 – 59", "0 – 44", "Gross NPA %", "Net NPA %", "CET1 Ratio", "ROA", "ROE", "NII Growth", "Profit Growth", "Revenue Growth %",
                 "ROCE", "Debt-to-Equity", "Interest Coverage", "At least 5 of 7 for Banking, or 4 of 6 for a non-bank sector", "At least 65% overall evidence coverage", "Banking and 19 non-bank sectors",
                 "Finance and Insurance", "never blends a subset of them with adjusted weights", "It is not a prediction of future share-price returns and not a buy/sell recommendation",
                 "structurally cannot affect the MarketRipple Score number"]:
        assert fact in page, fact
    sectors = re.search(r"SUPPORTED_INDUSTRIAL_SECTORS = \[(.*?)\];", page)
    assert sectors and len(re.findall(r'"[^"]+"', sectors.group(1))) == 19
    t = norm(ED.public_text(resp(GE3)))
    for fact in ["8/15", "4/15", "3/15", "ROCE", "Debt-to-Equity", "Interest Coverage", "19 non-bank sectors", "65%"]:
        assert fact in t, fact


# ── end to end through the real pipeline: no model, honest availability, still safe ──────────────────────────────────────────

@pytest.fixture
def no_provider(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("a provider call was made")
    monkeypatch.setattr(S, "_call_with_fallback", boom)


@pytest.mark.parametrize("q,tid", [(GE1, "pe_ratio"), (GE2, "fii_flows"), (GE3, "marketripple_score")])
def test_end_to_end_the_curated_questions_make_no_model_call_and_pass_the_safety_gate(pipe, no_provider, q, tid):
    raw, res, cached = run_pipeline(q)
    assert pipe["specialist"] == 0 and cached is False
    assert res["education"]["topic"] == tid and res["degraded_reason"] is None and res["synthesis_incomplete"] is False
    assert res["answer_availability"] == {"state": "available", "evidence_retrieval_completed": False, "evidence_count": 0, "reason": None, "basis": "education",
                                          "kind": "product_information" if tid == "marketripple_score" else "education", "scope": "full", "conclusion_authorized": False}
    assert res["answer"]["summary"] == ED.TOPICS[tid].summary                       # the safety gate did not rewrite or degrade the contract text
    assert res["investment_verdict"]["rating"] == "Not Applicable" and res["scenarios"] == {}


@pytest.mark.parametrize("q", ["What is TCS's current P/E?", "What is TCS's MarketRipple Score?"])
def test_end_to_end_company_questions_still_need_company_evidence(pipe, no_provider, q):
    pipe["set_bundle"](bundle())
    raw, res, _ = run_pipeline(q)
    assert "education" not in res and res["degraded_reason"] == "insufficient_evidence" and pipe["specialist"] == 0


def test_end_to_end_a_data_question_is_refused_for_missing_evidence_not_answered_from_memory(pipe, no_provider):
    pipe["set_bundle"](bundle(plan="topic"))
    raw, res, _ = run_pipeline("How much did FIIs sell today?")
    assert "education" not in res and res["degraded_reason"] == "insufficient_evidence" and pipe["specialist"] == 0


def test_no_generic_fallback_invents_product_facts_because_the_product_topic_never_reaches_a_model(pipe, no_provider):
    for q in ["How does the MarketRipple Score work?", "What is the exact formula for the MarketRipple Score?", "Is the MarketRipple Score a buy signal?"]:
        raw, res, _ = run_pipeline(q)
        assert res["education"]["kind"] == ED.KIND_PRODUCT and pipe["specialist"] == 0
