"""
Step 3: the answer-level checks are proven here on hand-built fixtures, offline. These tests show the GATE works (it catches the failures it exists to catch and does not
flag good answers). They say nothing about the quality of real model answers; that is the live run's job.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE

_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "ai_search" / "baseline_2026_10_04" / "step3" / "answer_checks.py"
_spec = importlib.util.spec_from_file_location("answer_checks", _PATH)
AC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(AC)


def ev(events=(), news=(), announcements=(), policies=(), valuation=None, sector_rows=None, macro=None, context=()):
    return {"plan_kind": "topic", "filter_report": {}, "events": list(events), "news": list(news), "announcements": list(announcements), "policies": list(policies),
            "valuation": valuation or {}, "vix": None, "sector_rows": sector_rows or [], "macro_indices": macro or [], "context_lines": list(context), "historical": []}


def event(i, title, date="2026-09-20T00:00:00", companies=(), summary=""):
    return {"id": i, "title": title, "summary": summary, "date": date, "source": "NSE", "companies": list(companies)}


def ann(i, title, date="2026-10-01T00:00:00"):
    return {"id": i, "title": title, "category": "General", "date": date}


def news(i, title, date="1d ago", source="Economic Times", summary=""):
    return {"id": i, "title": title, "summary": summary, "date": date, "source": source}


def answer(**fields):
    return {"answer": {k: v for k, v in fields.items()}, "key_drivers": [], "insights": [], "companies": [], "investment_verdict": {}, "decision_engine_v2": {}}


# ── the two lexical traps ───────────────────────────────────────────────────

def test_a_single_company_filing_cannot_support_a_sector_claim():
    e = ev(events=[event("t1", "Tera Software Limited has informed the Exchange that Board of Directors approved fund raising")])
    res = answer(summary="IT sector software firms announced board approvals for fund raising this month.")
    claims = AC.claim_checks(res, e, "IT outlook", [], ["it"], UNIVERSE)
    assert claims and claims[0]["scope"] == "sector" and claims[0]["status"] == "ineligible_only"
    assert "single-company exchange filing" in claims[0]["matched"][0]["ineligible_because"]


def test_a_sector_wide_event_does_support_a_sector_claim():
    e = ev(events=[event("s1", "US enterprise IT spending contracts for second consecutive quarter", companies=["TCS", "INFY", "WIPRO"])])
    res = answer(summary="US enterprise IT spending contracted for a second consecutive quarter, a headwind for the IT sector.")
    claims = AC.claim_checks(res, e, "IT outlook", [], ["it"], UNIVERSE)
    assert claims[0]["status"] == "supported"


def test_a_kotak_research_note_is_not_a_kotak_mahindra_bank_fact():
    e = ev(news=[news("n1", "Largecaps face investor apathy, mid and smallcaps fuel euphoria: Kotak Institutional Equities")])
    res = answer(summary="Kotak Mahindra Bank says largecaps face investor apathy while smallcaps fuel euphoria.")
    claims = AC.claim_checks(res, e, "Kotak outlook", ["KOTAKBANK"], [], UNIVERSE)
    assert claims[0]["scope"] == "company" and claims[0]["status"] == "ineligible_only"


def test_kotak_mahindra_bank_own_filing_does_support_a_kotak_claim():
    e = ev(announcements=[ann("a1", "Kotak Mahindra Bank Limited has informed the Exchange about General Updates")])
    res = answer(summary="Kotak Mahindra Bank filed a general updates disclosure with the Exchange on 1 October.")
    claims = AC.claim_checks(res, e, "Kotak outlook", ["KOTAKBANK"], [], UNIVERSE)
    assert claims[0]["status"] == "supported"


@pytest.mark.parametrize("text,expected", [
    ("Kotak Securities launches new platform", None),
    ("Kotak Institutional Equities sees upside", None),
    ("Kotak Mahindra Bank reports Q2 business update", "strong"),
    ("Analysts at Kotak expect rate cuts", "weak"),
])
def test_company_name_matching_distinguishes_the_bank_from_other_kotak_entities(text, expected):
    assert AC.names_company(text, AC.company_terms("KOTAKBANK", UNIVERSE)) == expected


# ── numbers, dates, citations ───────────────────────────────────────────────

def test_numbers_must_appear_in_the_evidence_or_the_query():
    e = ev(news=[news("n1", "Rupee holds steady at 95.44 amidst RBI intervention")], sector_rows=[{"name": "IT", "value": "+1.7%"}])
    res = answer(summary="The rupee is at 95.44 and TCS revenue grew 14% while IT is up 1.7%.")
    flagged = [f["number"] for f in AC.unsupported_numbers(res, e, "q")]
    assert flagged == ["14%"]


def test_horizon_phrases_and_years_are_not_flagged_as_unsupported_numbers():
    res = answer(summary="The 6-12 months view for 2026 is cautious; over 3 years it may change.")
    assert AC.unsupported_numbers(res, ev(), "q") == []


def test_a_recency_claim_resting_on_old_evidence_is_flagged():
    e = ev(events=[event("d1", "Defence capital expenditure raised by Rs. 45,000 Cr in revised estimates", date="2026-07-08T00:00:00", companies=["BEL", "HAL", "BHARATFORG"])])
    res = answer(summary="BEL just won a new defence order after capital expenditure was raised in revised estimates.")
    claims = AC.claim_checks(res, e, "BEL order", ["BEL"], [], UNIVERSE)
    problems = AC.recency_claims(claims, e, max_age_days=45)
    assert problems and "days old" in problems[0]["problem"]


def test_a_recency_claim_with_no_dated_support_is_flagged():
    res = answer(summary="TCS recently announced a new AI research centre.")
    claims = AC.claim_checks(res, ev(), "TCS", ["TCS"], [], UNIVERSE)
    assert AC.recency_claims(claims, ev(), 45)


def test_citation_check_finds_ids_and_sources_the_bundle_does_not_contain():
    e = ev(events=[event("e1", "x")], news=[news("n1", "y", source="Mint")])
    res = {"source_attribution": ["event:e1", "news:n1", "event:ghost"], "citations": ["Mint", "Ghost Daily"], "related_events": [{"id": "e1", "title": "x"}, {"id": "zz", "title": "ghost event"}], "news": []}
    c = AC.citation_check(res, e)
    assert c["attribution_ids_not_in_evidence"] == ["event:ghost"] and c["citation_sources_not_in_news"] == ["Ghost Daily"] and c["shown_events_not_in_evidence"] == ["ghost event"]
    assert c["claim_level_attribution_available"] is False


# ── honest "insufficient recent evidence" (BEL, 3M India) ────────────────────

def test_empty_evidence_with_an_honest_answer_passes():
    res = answer(summary="There is no recent verified evidence about a new BEL order in the data MarketRipple holds, so the impact cannot be assessed.")
    r = AC.insufficient_evidence_check(res, ev(), "BEL just won a new defence order", UNIVERSE, ["BEL"])
    assert r["applicable"] and r["status"] == "PASS"


def test_empty_evidence_with_a_confident_invented_story_fails():
    res = answer(summary="BEL won a Rs 5,000 crore order which will lift margins by 120 bps and drive record revenue.")
    r = AC.insufficient_evidence_check(res, ev(), "BEL just won a new defence order", UNIVERSE, ["BEL"])
    assert r["status"] == "FAIL" and r["unsupported_numbers"] >= 1


def test_empty_evidence_with_a_hedge_that_still_asserts_unsupported_facts_fails():
    res = answer(summary="Limited evidence is available, but BEL announced a Rs 5,000 crore order.")
    r = AC.insufficient_evidence_check(res, ev(), "BEL", UNIVERSE, ["BEL"])
    assert r["status"] == "FAIL"


def test_the_insufficiency_check_is_not_applicable_when_evidence_exists():
    assert AC.insufficient_evidence_check(answer(summary="x"), ev(news=[news("n1", "y")]), "q", UNIVERSE, [])["applicable"] is False


# ── score and rank references ───────────────────────────────────────────────

def test_a_marketripple_score_statement_is_flagged_because_the_pipeline_never_reads_the_score():
    res = answer(summary="Kotak Mahindra Bank has a MarketRipple Score of 52 and looks strong.")
    r = AC.score_reference_check(res, {"KOTAKBANK": {"score": 47.7, "band": "Neutral"}})
    assert r["score_statements_in_text"]


def test_an_ai_verdict_that_contradicts_the_published_band_is_flagged_but_neutral_never_is():
    pub = {"KOTAKBANK": {"score": 30.0, "band": "Cautious"}}
    res = answer(summary="x")
    res["investment_verdict"] = {"rating": "Constructive"}
    assert AC.score_reference_check(res, pub)["contradicts_published_band"]
    res["investment_verdict"] = {"rating": "Neutral"}
    assert AC.score_reference_check(res, pub)["contradicts_published_band"] == []


def test_a_comparison_that_prefers_the_lower_scored_company_is_flagged():
    pub = {"HDFCBANK": {"score": 46.2, "band": "Neutral"}, "ICICIBANK": {"score": 48.8, "band": "Neutral"}}
    res = answer(summary="HDFCBANK looks stronger than ICICIBANK on this evidence.")
    r = AC.comparison_rank_check(res, pub, None)
    assert r["checkable"] and r["text_prefers_lower_scored"] is True
    ok = AC.comparison_rank_check(answer(summary="ICICIBANK looks stronger than HDFCBANK."), pub, None)
    assert ok["text_prefers_lower_scored"] is False


def test_comparison_rank_is_unverified_without_both_scores():
    assert AC.comparison_rank_check(answer(summary="x"), {"TCS": {"score": None}, "INFY": {"score": None}}, None)["checkable"] is False


# ── snapshot ────────────────────────────────────────────────────────────────

def test_snapshot_preserves_the_whole_bundle_as_plain_data():
    b = SimpleNamespace(plan_kind="company", filter_report={"x": 1}, events=[{"id": "e1", "title": "t", "summary": "s", "event_date": "2026-09-01T00:00:00", "source": "NSE", "companies": [{"symbol": "TCS"}]}],
                        news=[{"id": "n1", "headline": "h", "summary": "", "published_at": "1d ago", "source": "Mint"}], announcements=[{"id": "a1", "subject": "S", "category": "C", "announcement_date": "2026-10-01"}],
                        policies=[], valuation={"TCS": {"pe": 15.1}}, vix_level=14.4, sector_rows=[], macro_indices=[], context_lines=["l"], similar_historical=[])
    s = AC.snapshot_evidence(b)
    assert s["events"][0]["companies"] == ["TCS"] and s["news"][0]["title"] == "h" and AC.evidence_total(s) == 3
