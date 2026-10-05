"""
Step 3.4G.4 detector closure, from the saved SR2 live rejection (openai_sr2_g4.json). Two demonstrated false-positive classes in the factual-sentence detector, fixed without touching the rest of Gate B:
  1. fiscal/period labels (Q2, FY27, H1, 1Q26 ...) inside an evidence-limitation clause are not figures, using the SAME label definition the figure validator uses;
  2. a pronoun continuation of an evidence limitation ("...cannot be established from the evidence; it does not include reported operating results") is part of the limitation.
`claim_not_in_answer` is NOT changed: the model listed a claim it never wrote, and Gate B must keep rejecting that. No provider call.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE
from app.services.ai_search import answer_authorization as AA
from app.services.ai_search import claim_sources as CS
from app.services.ai_search import figures as FG
from app.services.ai_search.evidence import EvidenceBundle

_ART = Path(__file__).resolve().parents[2] / "benchmarks" / "ai_search" / "baseline_2026_10_04" / "step3_4c" / "openai_sr2_g4.json"
ENTS = {"companies": [], "sectors": ["it"], "policies": []}

SR2_Q2 = "The available evidence does not establish actual Q2 operating results or a full-year sector forecast."
SR2_PRONOUN = "A forward outlook for IT services cannot be established from the available evidence; it does not include reported operating results."


def rebuild(ev) -> EvidenceBundle:
    """The saved SR2 bundle, rebuilt exactly as the pipeline saw it: with the sector prompt's visibility caps applied, so the index matches the saved one (E1-E6, N1-N5)."""
    b = EvidenceBundle()
    b.plan_kind, b.premise, b.prompt_kind = ev["plan_kind"], ev.get("premise") or {}, "sector"
    for e in ev["events"]:
        b.events.append({"id": e["id"], "title": e["title"], "summary": e["summary"], "category": "Market", "impact_score": 0, "event_date": e["date"], "source": e.get("source"),
                         "companies": [{"symbol": x} for x in e.get("companies") or []]})
    for n in ev["news"]:
        b.news.append({"id": n["id"], "headline": n["title"], "summary": n["summary"], "published_at": n["date"], "source": n.get("source")})
    b.sector_rows = ev.get("sector_rows") or []
    b.context_lines = list(ev.get("context_lines") or [])
    assert [(x["id"], x["title"]) for x in b.index()] == [(x["id"], x["title"]) for x in ev["index"]]
    return b


def saved():
    r = json.loads(_ART.read_text(encoding="utf-8"))["results"]["SR2"]
    return r["rejected_generation"][0]["generation"], r["evidence"], r


# ── the exact saved failure ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_saved_sr2_rejection_had_exactly_the_two_false_positives_plus_one_correct_rejection_and_now_only_the_correct_one_remains():
    g, ev, r = saved()
    assert r["gate_b"]["reasons"] == ["claim_not_in_answer", "uncovered_factual_sentences"]            # what the live call reported
    b = rebuild(ev)
    cv = CS.validate_claim_sources(g["claim_sources"], b.index(), g, ENTS, UNIVERSE, {})
    assert cv["uncovered"] == []                                                                       # both limitation sentences are no longer "factual"
    a = AA.authorize(g, b, ENTS, UNIVERSE, r["query"])
    assert a["authorized"] is False and a["reasons"] == ["claim_not_in_answer"], a                     # the unlisted-in-answer claim is still rejected, and nothing else
    flagged = [c["claim"] for c in cv["claims"] if c.get("problems") and "claim_not_in_answer" in c["problems"]]
    assert flagged == ["IT was flat at +0.0% over one day, compared with FMCG at +1.3% and Banking at +0.2%."]


def test_removing_the_unwritten_claim_would_authorize_the_saved_generation():
    """Proves the two detector fixes were the only other blockers: with the model's own contract violation removed, Gate B authorizes the same answer."""
    g, ev, r = saved()
    g = json.loads(json.dumps(g))
    g["claim_sources"] = [c for c in g["claim_sources"] if not c["claim"].startswith("IT was flat")]
    assert AA.authorize(g, rebuild(ev), ENTS, UNIVERSE, r["query"])["authorized"] is True


def test_the_two_sr2_sentences_are_no_longer_factual():
    assert CS.is_factual(SR2_Q2) is False and CS.is_factual(SR2_PRONOUN) is False


# ── 1. fiscal / period labels ───────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("label", ["Q1", "Q2", "Q4", "Q2 FY27", "Q2FY27", "Q2'27", "FY26", "FY27", "FY2026", "FY26-27", "FY26/27", "H1", "H2", "H1 FY27", "1Q26", "4Q"])
def test_fiscal_labels_inside_an_evidence_limitation_are_not_figures(label):
    assert CS.is_factual(f"The available evidence does not include {label} operating results.") is False, label
    assert FG._FISCAL.fullmatch(label), label                                           # the same definition the figure validator uses


@pytest.mark.parametrize("not_a_label", ["Q5", "SQ2", "Q2x", "FY2", "H3", "5Q"])
def test_things_that_only_look_like_fiscal_labels_are_not_exempted(not_a_label):
    assert FG._FISCAL.fullmatch(not_a_label) is None, not_a_label


@pytest.mark.parametrize("sentence", [
    "The evidence does not include Q2 data; revenue rose 12% in Q2.",                     # a figure remains in a separate clause
    "The evidence does not establish growth, but TCS reported Q2 profit.",               # an event in its own clause
    "TCS reported Q2 results.",                                                           # not a limitation: verb
    "Infosys Q2 profit beat estimates.",                                                  # not a limitation: the label keeps its digit, so this stays factual as before
    "Q2 revenue was Rs 500 crore.",
    "The evidence does not include Q2 results; the company posted a 14% margin.",
])
def test_a_fiscal_label_never_hides_an_assertion_or_a_real_figure(sentence):
    assert CS.is_factual(sentence) is True, sentence


def test_the_fiscal_exemption_applies_only_inside_a_limitation_clause():
    assert CS.is_factual("Infosys Q2 profit beat estimates.") is True and CS.is_factual("Infosys profit beat estimates.") is False       # unchanged behaviour outside limitations


# ── 2. pronoun continuation ────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sentence,factual", [
    (SR2_PRONOUN, False),
    ("The evidence cannot establish X; it does not include reported operating results.", False),
    ("The evidence cannot establish growth; it does not report a profit figure.", False),
    ("The evidence does not establish growth; it does not include reported results.", False),
    ("The supplied data cannot show a trend; this does not include filed accounts.", False),
    # the adversarial boundary: assertions after a limitation stay factual
    ("The evidence does not establish growth; it reported record profit.", True),
    ("The evidence cannot establish growth; it reported record profit.", True),
    ("The evidence does not establish growth; it did not report a profit.", True),        # past tense reads as an event about someone, not about the evidence
    ("The evidence does not establish growth; it announced a buyback.", True),
    ("The evidence does not establish growth; it does not include X, and TCS reported results.", True),
    ("The company is secretive; it does not report profit.", True),                       # no evidence limitation before the pronoun
    ("The company cannot establish a profit; it reported record profit.", True),         # the subject is not the evidence
    ("The evidence cannot establish growth; it does not include reported operating results of Rs 500 crore.", True),     # a figure always wins
    ("It does not include reported operating results.", True),                            # a bare pronoun clause with no limitation before it
])
def test_pronoun_continuation_of_an_evidence_limitation(sentence, factual):
    assert CS.is_factual(sentence) is factual, sentence


def test_the_figure_validator_still_exempts_the_same_labels_and_still_checks_real_numbers():
    ai = {"summary": "FY27 and Q2 FY27 and H1 results for 1Q26 matter, but revenue rose 18%."}
    assert [f["value"] for f in FG.unsupported_figures(ai, "", "q")] == ["18%"]


# ── nothing else in Gate B moved ───────────────────────────────────────────────────────────────────────────────────────────────

def test_an_invented_figure_or_unlisted_claim_in_a_limitation_style_answer_is_still_rejected():
    from tests.services.test_ai_search_fail_closed import bundle
    b = bundle("topic", sector_rows=[{"name": "IT", "value": "+0.0%"}])
    g = {"summary": "The evidence does not include Q2 results; IT revenue grew 14% in Q2.", "bottom_line": "The evidence does not include Q2 results; IT revenue grew 14% in Q2.", "claim_sources": [],
         "companies": [], "sectors": [], "key_drivers": [], "risks": [], "opportunities": []}
    a = AA.authorize(g, b, ENTS, UNIVERSE, "IT outlook")
    assert a["authorized"] is False and "claim_sources_missing" in a["reasons"] and "unsupported_figures" in a["reasons"]
