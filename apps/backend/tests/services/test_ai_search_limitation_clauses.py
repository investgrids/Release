"""
Step 3.4G.2 regressions: factual-sentence detection is per clause. An event verb inside an explicit statement about what the EVIDENCE does or does not contain is a limitation, not an assertion;
generic negation is not. Built from the exact EI3 sentence the 3.4G.1 live rerun rejected. No provider call.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE
from app.services.ai_search import answer_authorization as AA
from app.services.ai_search import claim_sources as CS
from tests.services.test_ai_search_fail_closed import bundle  # noqa: F401
from tests.services.test_ai_search_validator_fixes import rebuild

_ART = Path(__file__).resolve().parents[2] / "benchmarks" / "ai_search" / "baseline_2026_10_04" / "step3_4c" / "openai_3_4g1.json"
EI3_SENTENCE = "The supplied evidence does not include credit-growth data, so the reported strengthening and its impact cannot be assessed."


@pytest.mark.parametrize("sentence,factual", [
    # limitations: an explicit evidence-availability / inability-to-assess clause
    (EI3_SENTENCE, False),
    ("The supplied evidence does not include credit-growth data, so the reported strengthening cannot be assessed.", False),
    ("Credit growth was not reported in the supplied evidence.", False),
    ("The supplied evidence does not substantiate a stronger credit-growth report.", False),
    ("The available data contains no announced orders for the bank.", False),
    ("Information on filed disclosures is not available in the current evidence.", False),
    # factual: an assertion disguised next to, or inside, a limitation
    ("Credit-growth data is not available, but banks reported record profit.", True),
    ("The evidence does not show credit growth; SBI reported a 12% increase.", True),
    ("The evidence does not include credit-growth data, so SBI reported record profit.", True),
    ("The evidence does not include credit-growth data, and TCS reported results.", True),
    ("SBI reported results, but the evidence does not include credit-growth data.", True),
    ("The supplied evidence does not include the figure, so the company's reported growth cannot be assessed; it reported record profit.", True),
    # generic negation is NOT exempt: a negated assertion about a company is itself a claim
    ("The company did not report a profit.", True),
    ("TCS has not announced any new order.", True),
    ("The bank never disclosed its provisions.", True),
    # figures always make a clause factual, whatever the framing
    ("The supplied evidence does not include the rate, so the 6.5% repo rate cannot be assessed.", True),
    ("The supplied evidence does not include credit-growth data; Banking rose 0.6%.", True),
    # earlier cases stay as they were
    ("The available evidence supports comparison of the stated valuation multiples and 52-week ranges only; operating results are not available.", False),
    ("Only 52-week ranges are available; revenue grew 14%.", True),
])
def test_clause_level_factual_detection(sentence, factual):
    assert CS.is_factual(sentence) is factual, sentence


def test_a_consequence_clause_is_exempt_only_when_it_follows_an_evidence_absence_clause_and_states_an_inability():
    assert CS.is_factual("The reported strengthening cannot be assessed.") is True       # no absence clause before it: a bare mention of a reported event stays factual
    assert CS.is_factual("The evidence does not include the data, so TCS reported profit.") is True      # consequence clause without an inability statement


# ── the exact live failure ───────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_saved_ei3_rerun_was_rejected_only_for_the_limitation_sentence_and_is_now_authorized():
    r = json.loads(_ART.read_text(encoding="utf-8"))["results"]["EI3"]
    g, ev = r["rejected_generation"][0]["generation"], r["evidence"]
    assert r["gate_b"]["reasons"] == ["uncovered_factual_sentences"]                      # what the live rerun reported
    b = rebuild(ev)
    ents = {"companies": [], "sectors": ["banking"], "policies": []}
    assert CS.validate_claim_sources(g["claim_sources"], b.index(), g, ents, UNIVERSE, {})["uncovered"] == []
    a = AA.authorize(g, b, ents, UNIVERSE, r["query"])
    assert a["authorized"] is True and a["reasons"] == [] and a["unsupported_figures"] == [], a
    assert EI3_SENTENCE in " ".join(CS.answer_pieces(g))                                  # the limitation is still public text, just not a factual claim
    assert g["claim_sources"][0]["claim"] in " ".join(CS.answer_pieces(g))               # and the grounded signed sector claim is accepted


def test_the_ei3_generation_still_fails_if_a_disguised_assertion_is_added_to_the_limitation():
    r = json.loads(_ART.read_text(encoding="utf-8"))["results"]["EI3"]
    g, ev = json.loads(json.dumps(r["rejected_generation"][0]["generation"])), r["evidence"]
    g["bottom_line"] = EI3_SENTENCE.replace("cannot be assessed.", "cannot be assessed, and SBI reported record credit growth.")
    b = rebuild(ev)
    a = AA.authorize(g, b, {"companies": [], "sectors": ["banking"], "policies": []}, UNIVERSE, r["query"])
    assert a["authorized"] is False and "uncovered_factual_sentences" in a["reasons"]


def test_an_unclaimed_negated_company_assertion_is_rejected():
    b = bundle("company", announcements=[{"id": "a1", "subject": "TCS filed results", "announcement_date": "2026-10-01", "symbol": "TCS", "category": "General"}])
    g = {"summary": "The company did not report a profit.", "bottom_line": "The company did not report a profit.", "claim_sources": [], "companies": [], "sectors": []}
    a = AA.authorize(g, b, {"companies": ["TCS"], "sectors": [], "policies": []}, UNIVERSE, "q")
    assert a["authorized"] is False and "claim_sources_missing" in a["reasons"]
