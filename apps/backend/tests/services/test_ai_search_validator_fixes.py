"""
Step 3.4G.1 regressions: the three mechanical authorization defects found by the 3.4F live specimens, reproduced from the saved EI3 and CC2 generations, plus adversarial cases proving the fixes
do not weaken Gate B.

  1. Signed numbers: a negative figure is grounded by the same negative figure (or by an unsigned magnitude whose sign was lost upstream), never by an explicitly opposite-signed one.
  2. `sectors[].explanation` is public model-written text and is scanned like every other claim surface.
  3. A period label ("52-week", "1-day") is a scope descriptor, not a figure; nothing broader is exempted.
No provider call.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE
from app.services.ai_search import answer_authorization as AA
from app.services.ai_search import claim_sources as CS
from app.services.ai_search import conclusion_scope as SC
from app.services.ai_search import figures as FG
from app.services.ai_search.evidence import EvidenceBundle
from tests.services.test_ai_search_fail_closed import bundle, ent  # noqa: F401

_ART = Path(__file__).resolve().parents[2] / "benchmarks" / "ai_search" / "baseline_2026_10_04" / "step3_4c" / "openai_3_4f_run2.json"
TODAY = date(2026, 10, 5)


def saved(qid):
    r = json.loads(_ART.read_text(encoding="utf-8"))["results"][qid]
    return r["rejected_generation"][0]["generation"], r["evidence"], r


def rebuild(ev) -> EvidenceBundle:
    """The exact saved bundle, rebuilt from the saved evidence snapshot (index ids and titles asserted equal)."""
    b = EvidenceBundle()
    b.plan_kind, b.premise = ev["plan_kind"], ev.get("premise") or {}
    for e in ev["events"]:
        b.events.append({"id": e["id"], "title": e["title"], "summary": e["summary"], "event_date": e["date"], "source": e.get("source"), "companies": [{"symbol": s} for s in e.get("companies") or []]})
    for n in ev["news"]:
        b.news.append({"id": n["id"], "headline": n["title"], "summary": n["summary"], "published_at": n["date"], "source": n.get("source")})
    sym_by_title = {i["title"]: (i["companies"] or [None])[0] for i in ev["index"] if i["kind"] == "announcement"}
    for a in ev["announcements"]:
        b.announcements.append({"id": a["id"], "subject": a["title"], "announcement_date": a["date"], "symbol": sym_by_title.get(a["title"]), "category": a.get("category")})
    b.valuation = ev.get("valuation") or {}
    b.sector_rows = ev.get("sector_rows") or []
    b.context_lines = list(ev.get("context_lines") or [])
    assert [(x["id"], x["title"]) for x in b.index()] == [(x["id"], x["title"]) for x in ev["index"]]
    return b


# ── the exact live failures ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_saved_ei3_generation_was_rejected_by_exactly_the_two_mechanical_defects_and_is_now_authorized():
    g, ev, r = saved("EI3")
    assert r["gate_b"]["reasons"] == ["claim_not_in_answer", "unsupported_figures"]          # what the live run reported
    b = rebuild(ev)
    ents = {"companies": [], "sectors": ["banking"], "policies": []}
    a = AA.authorize(g, b, ents, UNIVERSE, r["query"])
    assert a["authorized"] is True and a["reasons"] == [] and a["unsupported_figures"] == [], a
    assert "-0.4%" in g["sectors"][0]["explanation"] and "-0.7%" in g["sectors"][0]["explanation"]      # the negative figures that were falsely flagged


def test_the_saved_cc2_generation_was_rejected_by_exactly_the_two_mechanical_defects_and_is_now_authorized():
    g, ev, r = saved("CC2")
    assert r["gate_b"]["reasons"] == ["claim_not_in_answer", "uncovered_factual_sentences"]
    b = rebuild(ev)
    ents = {"companies": ["HDFCBANK", "ICICIBANK"], "company_matches": [{"symbol": "HDFCBANK", "name": "HDFC Bank Ltd"}, {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd"}], "sectors": [], "policies": []}
    a = AA.authorize(g, b, ents, UNIVERSE, r["query"])
    assert a["authorized"] is True and a["reasons"] == [], a
    scope = SC.assess(r["query"], {}, ents, b, UNIVERSE)
    assert scope["partial"] is True and scope["authorized"] == "valuation_comparison" and SC.overreach(g, scope) == []      # still valuation-only, still no winner


def test_the_two_saved_generations_still_carry_no_verdict_winner_or_invented_figure():
    for qid in ("EI3", "CC2"):
        g, ev, r = saved(qid)
        corpus = " ".join([json.dumps(ev["index"]), json.dumps(ev.get("valuation")), json.dumps(ev.get("context_lines")), json.dumps(ev.get("sector_rows"))])
        assert FG.unsupported_figures(g, corpus, r["query"], today=TODAY) == [], qid
        assert all((g.get("investment_verdict") or {}).get(k) in (None, "", [], {}) for k in ("rating", "direction", "confidence", "top_picks", "opportunity_score")) and not g.get("scenarios"), qid


# ── 1. signed numbers: adversarial ───────────────────────────────────────────────────────────────────────────────────────────────────

def figs(text, evidence):
    return [f["value"] for f in FG.unsupported_figures({"summary": text}, evidence, "q", today=TODAY)]


@pytest.mark.parametrize("label,text,evidence,flagged", [
    ("negative grounded by the same negative", "Banking is at -0.4%.", "Banking -0.4%", []),
    ("negative grounded by an unsigned magnitude whose sign was lost upstream", "Banking is at -0.4%.", "Banking fell 0.4% on the day", []),
    ("magnitude-only claim grounded by a negative figure", "Banking moved 0.4%.", "Banking -0.4%", []),
    ("explicit positive grounded by the same positive", "Private Bank rose +1.3%.", "Private Bank +1.3%", []),
    ("OPPOSITE: negative claim, evidence explicitly positive", "Banking is at -0.4%.", "Banking +0.4%", ["-0.4%"]),
    ("OPPOSITE: positive claim, evidence explicitly negative", "Banking rose +0.4%.", "Banking -0.4%", ["+0.4%"]),
    ("wrong magnitude", "Banking is at -4%.", "Banking -0.4%", ["-4%"]),
    ("sign cannot launder a different number", "Banking is at -0.5%.", "Banking -0.4%", ["-0.5%"]),
    ("a range hyphen is not a sign", "The range top is 1020.5.", "52W 681.9-1020.5", []),
    ("a range hyphen does not make a negative claim explicit-negative evidence", "The low is -681.9.", "52W 681.9-1020.5", []),   # unsigned magnitude present: sign treated as lost upstream (documented)
])
def test_signed_figures_are_grounded_with_their_direction(label, text, evidence, flagged):
    assert figs(text, evidence) == flagged, label


def test_an_explicit_opposite_sign_in_one_place_does_not_block_a_grounded_sign_elsewhere():
    assert figs("Banking is at -0.4%.", "Banking +0.4% last week; Banking -0.4% today") == []


def test_signed_figures_in_nested_public_fields_are_checked_the_same_way():
    ai = {"sectors": [{"name": "Banking", "explanation": "Banking fell -0.9% and Private Bank rose +1.3%."}]}
    assert [f["value"] for f in FG.unsupported_figures(ai, "Banking -0.4%; Private Bank +1.3%", "q", today=TODAY)] == ["-0.9%"]


# ── 2. sectors[].explanation is a scanned claim surface ──────────────────────────────────────────────────────────────────────────────

def sector_bundle():
    b = bundle("topic", sector_rows=[{"name": "Banking", "value": "-0.4%"}])
    b.context_lines = ["Sector performance (real, live 1-day change): Private Bank +1.3%; PSU Bank -0.7%; Banking -0.4%"]
    return b


def sector_gen(explanation, claim=None, sources=("C1",)):
    g = {"summary": "The available evidence does not substantiate the stated report.", "bottom_line": "The available evidence does not substantiate the stated report.", "claim_sources": [],
         "sectors": [{"name": "Banking", "explanation": explanation}], "companies": [], "key_drivers": [], "risks": [], "opportunities": []}
    if claim:
        g["claim_sources"] = [{"claim": claim, "sources": list(sources)}]
    return g


ENTS_BANK = {"companies": [], "sectors": ["banking"], "policies": []}


def test_a_sourced_sector_claim_is_authorized_and_is_now_inspected():
    s = "The live 1-day data show Banking at -0.4% and PSU Bank at -0.7%."
    assert s in CS.answer_pieces(sector_gen(s, s))
    assert AA.authorize(sector_gen(s, s), sector_bundle(), ENTS_BANK, UNIVERSE, "q")["authorized"] is True


def test_an_unclaimed_factual_sentence_hidden_in_a_sector_explanation_is_rejected():
    g = sector_gen("Banking rose 8% this week on strong credit growth.")
    a = AA.authorize(g, sector_bundle(), ENTS_BANK, UNIVERSE, "q")
    assert a["authorized"] is False and "claim_sources_missing" in a["reasons"] and "unsupported_figures" in a["reasons"]


def test_an_unclaimed_sector_sentence_next_to_a_valid_claim_is_reported_as_uncovered():
    ok = "The live 1-day data show Banking at -0.4%."
    g = sector_gen(ok + " Banking rose 8% this week on strong credit growth.", ok)
    a = AA.authorize(g, sector_bundle(), ENTS_BANK, UNIVERSE, "q")
    assert a["authorized"] is False and "uncovered_factual_sentences" in a["reasons"]


def test_a_claimed_but_ungrounded_figure_in_a_sector_explanation_still_fails_the_figure_check():
    s = "Banking rose 8% this week."
    a = AA.authorize(sector_gen(s, s), sector_bundle(), ENTS_BANK, UNIVERSE, "q")
    assert a["authorized"] is False and "unsupported_figures" in a["reasons"]


def test_an_opposite_signed_move_in_a_sourced_sector_claim_is_rejected():
    s = "The live 1-day data show Banking at +0.4%."
    a = AA.authorize(sector_gen(s, s), sector_bundle(), ENTS_BANK, UNIVERSE, "q")
    assert a["authorized"] is False and "unsupported_figures" in a["reasons"]


def test_a_claim_listed_for_a_sector_explanation_that_the_answer_does_not_contain_is_still_rejected():
    a = AA.authorize(sector_gen("Banking is mixed.", "The live 1-day data show Banking at -0.4%."), sector_bundle(), ENTS_BANK, UNIVERSE, "q")
    assert a["authorized"] is False and "claim_not_in_answer" in a["reasons"]


# ── 3. limitation sentences: narrow, no bypass ───────────────────────────────────────────────────────────────────────────────────────

LIMIT = "The available evidence supports comparison of the stated valuation multiples and 52-week ranges only; operating results, growth rates and margins are not available."


@pytest.mark.parametrize("sentence,factual", [
    (LIMIT, False),                                                               # the exact CC2 false positive
    ("Only 1-day sector data is available; forward demand cannot be established.", False),
    ("The evidence covers a 6-12 months window only; earnings are not available.", False),
    ("The 52-week high is 3350.", True),                                          # a figure remains
    ("Only 52-week ranges are available; revenue grew 14%.", True),               # factual assertion disguised as a limitation
    ("Operating results are not available, but the bank reported record profit.", True),     # event verb
    ("Only 52-week ranges are available; profit was Rs 2,000 crore.", True),
    ("52-week ranges only, and orders worth 1,200 were won.", True),
    ("Growth was 14% over the 52-week window.", True),
])
def test_only_a_period_label_is_exempt_from_the_factual_sentence_test(sentence, factual):
    assert CS.is_factual(sentence) is factual, sentence


def test_a_limitation_cannot_smuggle_a_figure_past_the_gates():
    b = bundle("company", announcements=[{"id": "a1", "subject": "TCS filed results", "announcement_date": "2026-10-01", "symbol": "TCS", "category": "General"}])
    g = {"summary": "Only 52-week ranges are available; revenue grew 14%.", "bottom_line": "Only 52-week ranges are available; revenue grew 14%.", "claim_sources": [], "companies": [], "sectors": []}
    a = AA.authorize(g, b, {"companies": ["TCS"], "sectors": [], "policies": []}, UNIVERSE, "q")
    assert a["authorized"] is False and set(a["reasons"]) >= {"claim_sources_missing", "unsupported_figures"}


def test_a_pure_limitation_answer_with_no_claims_is_not_rejected_for_missing_claims():
    g = {"summary": LIMIT, "bottom_line": LIMIT, "claim_sources": [], "companies": [], "sectors": []}
    b = bundle("company", announcements=[{"id": "a1", "subject": "TCS filed results", "announcement_date": "2026-10-01", "symbol": "TCS", "category": "General"}])
    a = AA.authorize(g, b, {"companies": ["TCS"], "sectors": [], "policies": []}, UNIVERSE, "q")
    assert "claim_sources_missing" not in a["reasons"]
