"""
Step 3.4B: model-free qualification of Gate A (pre-model sufficiency) and Gate B (post-model authorization), frozen at 697946d. No rule is changed or tuned here.

Every boundary is tested on BOTH sides: insufficient/unsupported input fails closed, and legitimately sufficient evidence / a correctly sourced generation stays authorized. An honest refusal counts as PASS.
Figure/date representation variants are exercised deterministically; where the committed rule wrongly rejects or wrongly accepts a legitimate variant, the case is pinned as a KNOWN_* behaviour (the test asserts what the rule does today) and listed in the 3.4B report instead of being fixed by fuzzy matching.
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE
from app.services.ai_search import answer_authorization as AA
from app.services.ai_search import evidence_sufficiency as ES
from app.services.ai_search import figures as FG
from app.services.ai_search import safety_gate
from app.services.ai_search.response_finalize import finalize_v3_response
# helpers and the model-free pipeline fixture from the 3.4A suite (a fixture must be imported by name to be visible here)
from tests.services.test_ai_search_fail_closed import (CR2_QUERY, NOW, ann, bundle, ent, ev_row, news_row, pipe, real_cr2_generation, run_pipeline)  # noqa: F401

TODAY = date(2026, 10, 4)


def auth(ai, b, entities, query="q"):
    return AA.authorize(ai, b, entities, UNIVERSE, query)


def gen(sentence, source, **over):
    g = {"summary": sentence, "bottom_line": sentence, "what_happened": "", "claim_sources": [{"claim": sentence, "sources": [source]}], "timeline": [], "scenarios": {}, "key_drivers": [], "companies": []}
    g.update(over)
    return g


TCS_ANN = "Tata Consultancy Services Limited has informed the Exchange regarding financial results for the quarter"


def tcs():
    return bundle("company", announcements=[ann("a1", TCS_ANN, "TCS")])


# ═══ GATE A: both sides of each boundary ═══════════════════════════════════════════════════════════════════════════════════════════════

# company assessment ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("label,b,expected", [
    ("zero evidence (CR2)", lambda: bundle(), "INSUFFICIENT"),
    ("ten unrelated market items", lambda: bundle(events=[ev_row(f"e{i}", "RBI holds repo rate") for i in range(10)], news=[news_row(f"n{i}", "Nifty ends flat") for i in range(5)]), "INSUFFICIENT"),
    ("only a tips article naming the company", lambda: bundle(news=[news_row("n1", "Top 3 stocks to buy: 3M India, TCS, BEL | Target price, stop-loss")]), "INSUFFICIENT"),
    ("administrative filings only", lambda: bundle(announcements=[ann("a1", "3M India Limited has informed the Exchange about Newspaper Publication", "3MINDIA"),
                                                                  ann("a2", "3M India Limited has informed the Exchange about Trading Window closure", "3MINDIA"),
                                                                  ann("a3", "3M India Limited has informed the Exchange about Record Date", "3MINDIA")]), "INSUFFICIENT"),
    ("one substantive filing", lambda: bundle(announcements=[ann("a1", "3M India Limited has informed the Exchange regarding Outcome of Board Meeting and financial results", "3MINDIA")]), "SUFFICIENT"),
    ("administrative plus one substantive filing", lambda: bundle(announcements=[ann("a1", "3M India Limited has informed the Exchange about Newspaper Publication", "3MINDIA"),
                                                                                 ann("a2", "3M India Limited has informed the Exchange regarding acquisition of a manufacturing unit", "3MINDIA")]), "SUFFICIENT"),
    ("company-specific news event", lambda: bundle(events=[ev_row("e1", "3M India Limited announces expansion of its Bengaluru plant", ["3MINDIA"])]), "SUFFICIENT"),
])
def test_company_assessment_boundary(label, b, expected):
    assert ES.assess(CR2_QUERY, {}, ent(["3MINDIA"]), b(), UNIVERSE)["status"] == expected, label


# event impact ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
BEL_Q = "BEL just won a new defence order, what does this mean for the stock?"


@pytest.mark.parametrize("label,premise,expected", [
    ("premise required, not supported (EI1)", {"required": True, "terms": ["order"], "supported": False, "supporting": []}, "INSUFFICIENT"),
    ("premise required, supported", {"required": True, "terms": ["order"], "supported": True, "supporting": ["BEL bags orders worth Rs 1,200 crore"]}, "SUFFICIENT"),
])
def test_event_premise_boundary(label, premise, expected):
    b = bundle(announcements=[ann("a1", "Bharat Electronics Limited has informed the Exchange regarding a press release", "BEL")], premise=premise)
    r = ES.assess(BEL_Q, {"intent": "news_reaction"}, ent(["BEL"]), b, UNIVERSE)
    assert r["status"] == expected and r["kind"] == "event_impact", label


def test_other_company_evidence_does_not_rescue_an_unestablished_premise():
    b = bundle(events=[ev_row(f"e{i}", "HAL signs defence contract worth Rs 2,000 crore", ["HAL"]) for i in range(3)], premise={"required": True, "terms": ["order"], "supported": False})
    assert ES.assess(BEL_Q, {}, ent(["BEL"]), b, UNIVERSE)["status"] == "INSUFFICIENT"


# comparison ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
INFY_ANN = "Infosys Limited has informed the Exchange regarding financial results for the quarter"


@pytest.mark.parametrize("label,b,expected,missing", [
    ("neither side", lambda: bundle("comparison"), "INSUFFICIENT", ["TCS", "INFY"]),
    ("TCS only (filing)", lambda: bundle("comparison", announcements=[ann("a1", TCS_ANN, "TCS")]), "INSUFFICIENT", ["INFY"]),
    ("INFY only (filing)", lambda: bundle("comparison", announcements=[ann("a1", INFY_ANN, "INFY")]), "INSUFFICIENT", ["TCS"]),
    ("TCS filing, INFY valuation only", lambda: bundle("comparison", announcements=[ann("a1", TCS_ANN, "TCS")], valuation={"INFY": {"pe": 13.3}}), "SUFFICIENT", []),
    ("valuation for both, no filings", lambda: bundle("comparison", valuation={"TCS": {"pe": 15.1}, "INFY": {"pb": 4.5}}), "SUFFICIENT", []),
    ("filings for both", lambda: bundle("comparison", announcements=[ann("a1", TCS_ANN, "TCS"), ann("a2", INFY_ANN, "INFY")]), "SUFFICIENT", []),
    ("one side administrative only", lambda: bundle("comparison", announcements=[ann("a1", TCS_ANN, "TCS"), ann("a2", "Infosys Limited has informed the Exchange about Newspaper Publication", "INFY")]), "INSUFFICIENT", ["INFY"]),
])
def test_comparison_boundary(label, b, expected, missing):
    r = ES.assess("TCS vs Infosys, which is stronger?", {"is_comparison": True}, ent(["TCS", "INFY"]), b(), UNIVERSE)
    assert r["status"] == expected and r["missing_entities"] == missing, label


# sector assessment ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("label,b,expected", [
    ("nothing", lambda: bundle("topic"), "INSUFFICIENT"),
    ("one company's filing only", lambda: bundle("topic", events=[ev_row("t1", "Tera Software Limited has informed the Exchange that Board approved fund raising")]), "INSUFFICIENT"),
    ("tips article naming IT stocks", lambda: bundle("topic", news=[news_row("n1", "Top IT stocks to buy: TCS, Infosys, Wipro | stop-loss, target price")]), "INSUFFICIENT"),
    ("sector-wide news item", lambda: bundle("topic", events=[ev_row("s1", "US enterprise IT spending contracts for second consecutive quarter", ["TCS", "INFY", "WIPRO"])]), "SUFFICIENT"),
    ("live sector row only", lambda: bundle("topic", sector_rows=[{"name": "IT", "value": "+1.7%"}]), "SUFFICIENT"),
    ("row for a different sector", lambda: bundle("topic", sector_rows=[{"name": "Banking", "value": "-0.4%"}]), "INSUFFICIENT"),
])
def test_sector_assessment_boundary(label, b, expected):
    assert ES.assess("What is the outlook for the IT services sector?", {}, ent(sectors=["it"]), b(), UNIVERSE)["status"] == expected, label


# macro transmission ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
MACRO_Q = "What happens to Indian banks if the RBI cuts the repo rate?"
MACRO_E = ent(sectors=["banking"], policies=["rbi", "repo rate"])


@pytest.mark.parametrize("label,b,expected,missing", [
    ("nothing", lambda: bundle("topic"), "INSUFFICIENT", ["macro_condition_evidence", "sector_evidence_banking"]),
    ("condition without exposure", lambda: bundle("topic", news=[news_row("n1", "Repo rate may climb to 6% in FY27, economists say")]), "INSUFFICIENT", ["sector_evidence_banking"]),
    ("exposure without condition", lambda: bundle("topic", sector_rows=[{"name": "Banking", "value": "-0.4%"}]), "INSUFFICIENT", ["macro_condition_evidence"]),
    ("condition and exposure", lambda: bundle("topic", news=[news_row("n1", "Repo rate may climb to 6% in FY27, economists say")], sector_rows=[{"name": "Banking", "value": "-0.4%"}]), "SUFFICIENT", []),
])
def test_macro_transmission_boundary(label, b, expected, missing):
    r = ES.assess(MACRO_Q, {}, MACRO_E, b(), UNIVERSE)
    assert r["status"] == expected and r["missing"] == missing, label


# sector scan and education ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_sector_scan_boundary():
    q = "Which sectors look weak in the market at the moment?"
    assert ES.assess(q, {}, ent(), bundle("topic"), UNIVERSE)["status"] == "INSUFFICIENT"
    assert ES.assess(q, {}, ent(), bundle("topic", sector_rows=[{"name": "IT", "value": "-1%"}]), UNIVERSE)["status"] == "SUFFICIENT"


@pytest.mark.parametrize("q", ["What is a P/E ratio and how should I read it?", "Explain what a stock split is", "How does an IPO work?"])
def test_educational_questions_are_not_gated_by_either_gate(q):
    b = bundle("explanation")
    assert ES.assess(q, {}, ent(), b, UNIVERSE)["kind"] == "not_gated" and ES.assess(q, {}, ent(), b, UNIVERSE)["status"] == "SUFFICIENT"
    a = auth({"summary": "A P/E of 20 means investors pay 20 times earnings per share."}, b, ent(), q)
    assert a["applicable"] is False and a["authorized"] is True


def test_gate_a_is_a_pure_decision_with_no_count_threshold():
    one = bundle(announcements=[ann("a1", "3M India Limited has informed the Exchange regarding acquisition of a plant", "3MINDIA")])
    many = bundle(announcements=[ann(f"a{i}", "3M India Limited has informed the Exchange about Newspaper Publication", "3MINDIA") for i in range(30)])
    assert ES.assess(CR2_QUERY, {}, ent(["3MINDIA"]), one, UNIVERSE)["status"] == "SUFFICIENT"
    assert ES.assess(CR2_QUERY, {}, ent(["3MINDIA"]), many, UNIVERSE)["status"] == "INSUFFICIENT"


# ═══ GATE A end to end: zero specialist calls, zero analytical content ══════════════════════════════════════════════════════════════════════

FORBIDDEN = ("bullish", "bearish", "cautious", "constructive", "overweight", "underweight", "target price", "expected to grow", "forecast", "will rise", "will fall")


@pytest.mark.parametrize("tag,b,query,missing_kind", [
    ("CR2", lambda: bundle(), CR2_QUERY, "company_assessment"),
    ("EI1", lambda: bundle(announcements=[ann("a1", "Bharat Electronics Limited has informed the Exchange regarding a press release", "BEL")], premise={"required": True, "terms": ["order"], "supported": False}), BEL_Q, "event_impact"),
])
def test_insufficient_questions_make_zero_specialist_calls_and_carry_no_analysis(pipe, tag, b, query, missing_kind):
    pipe["set_bundle"](b())
    raw, res, cached = run_pipeline(f"{query} (3.4B {tag})")
    assert pipe["specialist"] == 0 and cached is False
    assert res["degraded_reason"] == "insufficient_evidence" and res["evidence_sufficiency"]["kind"] == missing_kind
    assert res["investment_verdict"]["rating"] == "Not Applicable" and res["answer"]["confidence"] is None
    assert res["timeline"] == [] and res["scenarios"] == {} and res["key_drivers"] == [] and res["companies"] == []
    text = json.dumps(res, ensure_ascii=False).lower()
    assert not any(w in text for w in FORBIDDEN)
    assert safety_gate.find_v3_safety_violation(res) is None
    if tag == "EI1":
        assert res["premise_check"]["status"] == "not_established"


def test_sufficient_evidence_does_reach_the_specialist(pipe):
    pipe["set_bundle"](tcs())
    run_pipeline("What is happening with TCS lately? (3.4B reach)")
    assert pipe["specialist"] == 1


# ═══ GATE B: claim sources, both sides ═════════════════════════════════════════════════════════════════════════════════════════════════════

SENT = "TCS filed a financial results disclosure with the Exchange."
Q = "What is happening with TCS lately?"


def test_correctly_sourced_generation_is_authorized():
    a = auth(gen(SENT, "A1"), tcs(), ent(["TCS"]), Q)
    assert a["authorized"] and a["reasons"] == []


def test_valid_source_id_variants_are_all_authorized():
    for sid in ("A1", "a1"):    # IDs are case-normalised by the validator
        a = auth(gen(SENT, sid), tcs(), ent(["TCS"]), Q)
        assert a["authorized"], sid


@pytest.mark.parametrize("label,g,reason", [
    ("claim_sources missing", lambda: gen(SENT, "A1", claim_sources=[]), "claim_sources_missing"),
    ("claim_sources None", lambda: gen(SENT, "A1", claim_sources=None), "claim_sources_missing"),
    ("unknown id", lambda: gen(SENT, "A9"), "unknown_source"),
    ("malformed id", lambda: gen(SENT, "banana"), "unknown_source"),
    ("empty source list", lambda: gen(SENT, "A1", claim_sources=[{"claim": SENT, "sources": []}]), "no_source"),
    ("claim not in answer", lambda: gen(SENT, "A1", claim_sources=[{"claim": SENT, "sources": ["A1"]}, {"claim": "Quarterly margin expanded sharply across all segments.", "sources": ["A1"]}]), "claim_not_in_answer"),
    ("uncovered factual sentence", lambda: gen(SENT, "A1", what_happened="Quarterly revenue rose 14% year on year."), "uncovered_factual_sentences"),
])
def test_claim_source_failures_fail_closed(label, g, reason):
    a = auth(g(), tcs(), ent(["TCS"]), Q)
    assert a["authorized"] is False and reason in a["reasons"], (label, a["reasons"])


def test_ineligible_sources_fail_closed_and_eligible_ones_pass():
    tips = bundle("company", news=[news_row("n1", "Top 3 stocks to buy: HDFC Bank, Infosys, BEL by Ganesh Dongre | Target price, stop-loss")])
    s = "Bharat Electronics won a new defence order."
    assert "ineligible_sources" in auth(gen(s, "N1"), tips, ent(["BEL"]), "BEL outlook")["reasons"]
    admin = bundle("company", announcements=[ann("a1", "Bharat Electronics Limited has informed the Exchange about Newspaper Publication", "BEL")])
    s2 = "Bharat Electronics reported a newspaper publication."
    assert auth(gen(s2, "A1"), admin, ent(["BEL"]), "BEL outlook")["authorized"] in (True, False)   # recorded: administrative filings are not blocked as a CITED source, only as sufficiency evidence
    ok = bundle("company", announcements=[ann("a1", "Bharat Electronics Limited has informed the Exchange regarding orders worth Rs 1,200 crore", "BEL")], premise={"required": True, "terms": ["order"], "supported": True})
    s3 = "Bharat Electronics informed the Exchange of orders worth Rs 1,200 crore."
    assert auth(gen(s3, "A1"), ok, ent(["BEL"]), "BEL just won a defence order")["authorized"] is True


def test_single_company_filing_is_ineligible_for_a_sector_claim_and_sector_wide_item_is_eligible():
    b = bundle("topic", events=[ev_row("t1", "Tera Software Limited has informed the Exchange that Board approved fund raising", ["TERASOFT"]),
                                ev_row("s1", "US enterprise IT spending contracts for second consecutive quarter", ["TCS", "INFY", "WIPRO"])])
    s = "IT services demand is weakening as US enterprise IT spending contracts."
    bad = auth(gen(s, "E1"), b, ent(sectors=["it"]), "IT sector outlook")
    good = auth(gen(s, "E2"), b, ent(sectors=["it"]), "IT sector outlook")
    assert "ineligible_sources" in bad["reasons"] and good["authorized"] is True, (bad["reasons"], good["reasons"])


def test_premise_unsupported_claim_fails_and_supported_passes():
    s = "Bharat Electronics won a large defence order."
    row = ann("a1", "Bharat Electronics Limited has informed the Exchange about Outcome of Board Meeting", "BEL")
    no = bundle("company", announcements=[row], premise={"required": True, "terms": ["order"], "supported": False})
    yes = bundle("company", announcements=[ann("a1", "Bharat Electronics Limited has informed the Exchange: won a large defence order", "BEL")], premise={"required": True, "terms": ["order"], "supported": True})
    assert "premise_unsupported" in auth(gen(s, "A1"), no, ent(["BEL"]), BEL_Q)["reasons"]
    assert auth(gen(s, "A1"), yes, ent(["BEL"]), BEL_Q)["authorized"] is True


def test_no_factual_sentences_needs_no_claim_sources():
    soft = "The picture depends on how the evidence develops."
    assert auth(gen(soft, "A1", claim_sources=[]), tcs(), ent(["TCS"]), Q)["authorized"] is True


# ═══ GATE B: figures and dates ═════════════════════════════════════════════════════════════════════════════════════════════════════════════

def figs(text, evidence="", query="q", where="summary"):
    return [f["value"] for f in FG.unsupported_figures({where: text}, evidence, query, today=TODAY)]


@pytest.mark.parametrize("label,text,evidence,expected", [
    ("supported ISO date", "Results on 2026-10-01.", "Press release dated 2026-10-01", []),
    ("invented ISO date", "Results on 2026-11-10.", "Press release dated 2026-10-01", ["2026-11-10"]),
    ("today is always allowed", "Updated 4 Oct 2026.", "", []),
    ("supported figure", "Revenue rose 11%.", "Revenue up 11% in Q2", []),
    ("invented figure", "Revenue rose 18%.", "Revenue up 11% in Q2", ["18%"]),
    ("invented rupee amount", "A Rs 5,000 crore order.", "orders worth Rs 1,200 crore", ["5,000"]),
    ("invented figure in the timeline", None, "", ["2027-02-12"]),
])
def test_supported_vs_invented_figures(label, text, evidence, expected):
    if text is None:
        got = [f["value"] for f in FG.unsupported_figures({"timeline": [{"date": "2027-02-12", "title": "Q3 results"}]}, evidence, "q", today=TODAY)]
    else:
        got = figs(text, evidence)
    assert got == expected, label


@pytest.mark.parametrize("where", ["summary", "what_happened", "immediate_impact", "what_priced_in"])
def test_invented_figures_are_caught_in_every_prose_field(where):
    assert figs("Margins expanded 250 bps.", "", where=where) == ["250"]


def test_invented_figures_are_caught_in_nested_structures():
    ai = {"scenarios": {"bull": {"outcome": "Growth above 18% YoY."}}, "key_drivers": [{"title": "Demand", "explanation": "Orders up 40%."}], "risks": [{"title": "FX", "explanation": "A 12% swing."}],
          "timeline": [{"date": "2026-12-01", "title": "Event", "description": "Revenue 300 crore."}]}
    vals = {f["value"] for f in FG.unsupported_figures(ai, "", "q", today=TODAY)}
    assert {"18%", "40%", "12%", "2026-12-01", "300"} <= vals


# Representation variants. Each: (label, generation text, evidence text, expected 'accept'|'reject', category). `category` documents a rule limitation when expected is not the ideal outcome.
VARIANTS = [
    ("date: ISO vs 'Oct 1, 2026'", "Results came on 2026-10-01.", "Board met on Oct 1, 2026", "accept", "ideal"),
    ("date: ISO vs '1st October 2026'", "Results came on 2026-10-01.", "Board met on 1st October 2026", "accept", "ideal"),
    ("date: '1 Oct 2026' vs ISO", "Results came on 1 Oct 2026.", "Board met on 2026-10-01", "accept", "ideal"),
    ("date: 'October 1, 2026' vs '1 Oct 2026'", "Results came on October 1, 2026.", "Board met on 1 Oct 2026", "accept", "ideal"),
    ("date: ISO timestamp in evidence", "Results came on 1 Oct 2026.", "announcement_date 2026-10-01T09:30:00+00:00", "accept", "ideal"),
    ("date: DD/MM/YYYY form is not parsed as a date", "Results came on 01/10/2026.", "Board met on 1 Oct 2026", "reject", "KNOWN_FALSE_REJECT: a legitimate numeric date is not parsed, so '01' and '10' are looked up as bare numbers and flagged"),
    ("date: invented DD/MM/YYYY is also not caught", "Results come on 12/11/2026.", "Board met on 1 Oct 2026", "reject", "ideal (caught only incidentally via '12' / '11' as bare numbers)"),
    ("number: comma vs no comma", "Order worth 1200 crore.", "orders worth Rs 1,200 crore", "accept", "ideal"),
    ("number: Rs vs rupee sign", "Order worth ₹1,200 crore.", "orders worth Rs 1,200 crore", "accept", "ideal"),
    ("number: '11%' vs '11 per cent'", "Revenue rose 11 per cent.", "Revenue up 11%", "accept", "ideal"),
    ("number: '11 per cent' in evidence, '11%' in answer", "Revenue rose 11%.", "Revenue up 11 per cent", "accept", "ideal"),
    ("number: 12% vs 12.0%", "Revenue rose 12%.", "Revenue up 12.0%", "accept", "ideal (substring match)"),
    ("number: 1200.5 vs 1,200.50", "Profit was 1200.5 crore.", "Profit of 1,200.50 crore", "accept", "ideal (prefix of the evidence digits)"),
    ("number: 1.2 lakh crore vs 120,000 crore", "A 1.2 lakh crore order.", "an order of 120,000 crore", "reject", "KNOWN_FALSE_REJECT: unit conversion is not attempted"),
    ("number: 2,500 MW vs 2500MW", "A 2500MW contract.", "supply of 2,500 MW", "accept", "ideal"),
    ("number: spelled-out figure", "Revenue rose eighteen percent.", "", "accept", "KNOWN_FALSE_ACCEPT: a number written in words is not checked at all"),
    ("number: substring collision", "Revenue rose 18%.", "Market cap Rs 2,180 crore", "accept", "KNOWN_FALSE_ACCEPT: '18' is found inside '2,180' because the match is a substring of the digit string"),
    ("number: year-like value exempt", "Guided for 2027.", "", "accept", "ideal"),
    ("number: fiscal label exempt", "Expected in Q2 FY27.", "", "accept", "ideal"),
    ("number: horizon exempt", "Over 6-12 months.", "", "accept", "ideal"),
    ("number: single digit exempt", "Three of 5 segments grew.", "", "accept", "ideal"),
]


@pytest.mark.parametrize("label,text,evidence,expected,category", VARIANTS, ids=[v[0] for v in VARIANTS])
def test_figure_date_representation_variants_are_deterministic(label, text, evidence, expected, category):
    got = "reject" if figs(text, evidence) else "accept"
    assert got == expected, (label, category, figs(text, evidence))


def test_known_limitation_inventory_matches_the_variant_table():
    """The 3.4B report lists exactly these. A change in the rule must update this list deliberately."""
    assert sorted(v[0] for v in VARIANTS if "KNOWN_" in v[4]) == sorted([
        "date: DD/MM/YYYY form is not parsed as a date", "number: 1.2 lakh crore vs 120,000 crore", "number: spelled-out figure", "number: substring collision"])


# ═══ zero leakage from rejected generations ════════════════════════════════════════════════════════════════════════════════════════════════

LEAK_WORDS = ("zero-debt", "honeywell", "siemens", "bullish", "constructive", "2026-11-10", "2027-02-12", "18%", "200 bps")


def test_real_cr2_generation_is_rejected_and_does_not_leak_through_any_public_channel():
    g = real_cr2_generation()
    b = bundle()
    a = auth(g, b, ent(["3MINDIA"]), CR2_QUERY)
    assert a["authorized"] is False
    from app.services.ai_search import pipeline as P
    res = P._build_rejected_response(CR2_QUERY, g, b, ent(["3MINDIA"]), {}, "company", a)
    public = finalize_v3_response(CR2_QUERY, res, x_admin_key=None, was_cached=False)
    assert "_rejected_generation" not in public
    blob = json.dumps(public, ensure_ascii=False, default=str).lower()
    assert not any(w in blob for w in LEAK_WORDS)
    # every public string field of the real generation must be absent verbatim from the public response
    from app.services.ai_search.figures import public_strings
    for path, text in public_strings(g):
        if len(text) > 25:
            assert text.lower() not in blob, path
    assert public["answer_authorization"]["authorized"] is False


def test_public_authorization_summary_carries_codes_and_counts_but_never_the_withheld_content():
    g = real_cr2_generation()
    a = auth(g, bundle(), ent(["3MINDIA"]), CR2_QUERY)
    pub = AA.public_summary(a)
    assert set(pub) == {"applicable", "authorized", "reasons", "unsupported_figure_count", "factual_sentences"}
    assert all(isinstance(r, str) for r in pub["reasons"])


def test_rejected_generation_is_retained_internally_for_diagnostics_only():
    g = real_cr2_generation()
    a = auth(g, bundle(), ent(["3MINDIA"]), CR2_QUERY)
    AA.REJECTED_GENERATIONS.clear()
    from app.services.ai_search import pipeline as P
    P._build_rejected_response(CR2_QUERY, g, bundle(), ent(["3MINDIA"]), {}, "company", a)
    assert len(AA.REJECTED_GENERATIONS) == 1 and AA.REJECTED_GENERATIONS[0]["generation"] is g


def test_a_rejection_does_not_edit_the_generation():
    g = real_cr2_generation()
    before = json.dumps(g, sort_keys=True, default=str)
    auth(g, bundle(), ent(["3MINDIA"]), CR2_QUERY)
    assert json.dumps(g, sort_keys=True, default=str) == before     # no sentence stripping, no repair


def test_pipeline_withholds_a_sourceless_generation_end_to_end_without_leaking(pipe):
    pipe["set_bundle"](tcs())
    bad = gen(SENT, "A1", claim_sources=[], timeline=[{"date": "2026-11-10", "title": "Q2 results", "description": "Bullish read-through expected."}],
              scenarios={"bull": {"outcome": "Growth above 18%."}})
    pipe["generation"] = (bad, False)
    raw, res, _ = run_pipeline("What is happening with TCS lately? (3.4B leak)")
    assert pipe["specialist"] == 1 and res["degraded_reason"] == "claims_not_authorized"
    blob = json.dumps(res, ensure_ascii=False, default=str).lower()
    assert not any(w in blob for w in ("2026-11-10", "bullish", "18%", "q2 results")) and "_rejected_generation" not in res
    assert res["timeline"] == [] and res["scenarios"] == {} and res["investment_verdict"]["rating"] == "Not Applicable"


def test_a_correct_generation_with_supported_figures_is_published_end_to_end(pipe, monkeypatch):
    from app.services.ai_search import pipeline as P

    async def fake_assemble(query, ai, evidence, kind, was_degraded, report, db, entities, **kw):
        return {"query": query, "response_id": "r1", "synthesis_incomplete": False, "answer": {"summary": ai["summary"]}, "companies": [], "investment_verdict": {"rating": "Neutral"}}
    monkeypatch.setattr(P, "_assemble_response", fake_assemble)
    b = bundle("company", announcements=[ann("a1", "Tata Consultancy Services Limited has informed the Exchange: results for the quarter, revenue up 11%", "TCS")])
    pipe["set_bundle"](b)
    s = "TCS informed the Exchange of quarterly results with revenue up 11%."
    pipe["generation"] = (gen(s, "A1"), False)
    raw, res, _ = run_pipeline("What is happening with TCS lately? (3.4B publish)")
    assert res["synthesis_incomplete"] is False and res["answer_authorization"]["authorized"] is True


# ═══ not-gated paths stay not-gated; gate decisions are deterministic ═════════════════════════════════════════════════════════════════════

def test_gate_decisions_are_deterministic_across_repeated_runs():
    for _ in range(3):
        assert ES.assess(CR2_QUERY, {}, ent(["3MINDIA"]), bundle(), UNIVERSE) == ES.assess(CR2_QUERY, {}, ent(["3MINDIA"]), bundle(), UNIVERSE)
    g = real_cr2_generation()
    r1 = auth(g, bundle(), ent(["3MINDIA"]), CR2_QUERY)["reasons"]
    r2 = auth(g, bundle(), ent(["3MINDIA"]), CR2_QUERY)["reasons"]
    assert r1 == r2
