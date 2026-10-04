"""
Evidence scope + claim-level source IDs, all offline. Covers: what each kind of evidence may support (tips articles, single-company filings, brand-only mentions), the BEL premise,
the announcement-context leak, evidence IDs in the prompts matching the evidence index, the claim_sources validator, and the offline gate's detection of IRRELEVANT evidence (not just an
empty bundle). Nothing here calls a model.
"""
from __future__ import annotations

import asyncio
import importlib.util
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE
from app.services.ai_search import claim_sources as CS
from app.services.ai_search import evidence as ev_mod
from app.services.ai_search import evidence_filter as F
from app.services.ai_search import evidence_scope as ES
from app.services.ai_search import pipeline as P
from app.services.ai_search.evidence import EvidenceBundle
from app.services.ai_search.specialists import company, comparison, sector

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
_p = Path(__file__).resolve().parents[2] / "benchmarks" / "ai_search" / "baseline_2026_10_04" / "step3" / "answer_checks.py"
_s = importlib.util.spec_from_file_location("answer_checks_scope", _p)
AC = importlib.util.module_from_spec(_s)
_s.loader.exec_module(AC)


def ent(companies=(), sectors=(), policies=()):
    return {"companies": list(companies), "company_matches": [], "sectors": list(sectors), "policies": list(policies)}


def ev_row(i, title, days_old=5, companies=(), summary="", cat="Market"):
    d = (NOW - timedelta(days=days_old)).isoformat()
    return {"id": i, "title": title, "summary": summary, "category": cat, "impact_score": 60, "companies": [{"symbol": s} for s in companies], "event_date": d, "published_at": d, "date": "", "source": "NSE"}


def news_row(i, headline, published="1h ago", source="ET", summary=""):
    return {"id": i, "headline": headline, "summary": summary, "published_at": published, "source": source}


def ann_row(i, subject, date="2026-10-01T00:00:00", symbol=None):
    return {"id": i, "subject": subject, "category": "General", "announcement_date": date, **({"symbol": symbol} if symbol else {})}


# ── scope rules ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("title,expected", [
    ("Top 3 stocks to buy: HDFC Bank, Infosys, BEL by Ganesh Dongre | Target price, stop-loss for IT, defence", True),
    ("Best 5 stocks to buy this week", True), ("Multibagger alert: this smallcap could double", True), ("Buy or sell: analysts on TCS", True),
    ("BEL bags Rs 2,100 crore order from Ministry of Defence", False), ("Stocks to watch: BEL, HAL in focus after order win", False), ("Nifty ends lower as IT falls", False),
])
def test_tips_articles_are_recognised_without_catching_real_event_news(title, expected):
    assert ES.is_tips_article(title) is expected


def test_single_company_filings_are_recognised():
    assert ES.is_single_company_filing("Tera Software Limited has informed the Exchange that Board of Directors approved") is True
    assert ES.is_single_company_filing("US enterprise IT spending contracts for second consecutive quarter") is False


@pytest.mark.parametrize("title,expected", [
    ("The Exchange has sought clarification from Oracle Financial Services Software Limited with respect to significant movement in price", True),
    ("Infosys Limited has informed the Exchange regarding an Investor Presentation", True),
    ("XYZ Ltd has intimated the stock exchange about a board meeting", True),
    ("Disclosure pursuant to Regulation 30 of SEBI LODR by ABC Industries", True),
    ("Nifty IT jumps 2%; Mphasis, Coforge, Infosys, TCS among top gainers", False),
    ("RBI MPC policy, oil prices, bond yields may drive market this week", False),
    ("US enterprise IT spending contracts for second consecutive quarter", False),
])
def test_single_company_exchange_communications_are_recognised_in_all_their_forms(title, expected):
    assert ES.is_single_company_filing(title) is expected


def test_a_tips_article_is_never_eligible_for_anything():
    item = {"kind": "news", "title": "Top 3 stocks to buy: HDFC Bank, Infosys, BEL", "summary": "", "companies": []}
    assert ES.eligible_for_company(item, "BEL", UNIVERSE)[0] is False and ES.eligible_for_sector(item)[0] is False


def test_premise_groups_only_exist_for_a_question_phrased_as_news():
    assert ES.premise_groups("BEL just won a new defence order, what does this mean?")
    assert ES.premise_groups("What is the outlook for BEL?") == []
    assert ES.premise_groups("TCS just announced a new AI research center")


# ── filter: the Tera and BEL cases, and the Kotak research note ──────────────

def bundle(**kw):
    return SimpleNamespace(events=kw.get("events", []), news=kw.get("news", []), policies=kw.get("policies", []), announcements=kw.get("announcements", []), premise={})


def test_a_single_company_filing_is_removed_from_a_sector_bundle():
    q, e = "What is the outlook for the IT services sector?", ent(sectors=["it"])
    b = bundle(events=[ev_row("t1", "Tera Software Limited has informed the Exchange that Board of Directors approved fund raising", 54),
                       ev_row("s1", "Nifty IT crashes 11% in September: TCS, Infosys, Wipro among top losers", 3, summary="software exporters fall"),
                       ev_row("s2", "US enterprise IT spending contracts for second consecutive quarter", 3, ["TCS", "INFY", "WIPRO"])])
    rep = F.filter_bundle(b, F.plan_for(q, {}, e), q, e, NOW)
    assert [x["id"] for x in b.events] == ["s1", "s2"] and rep["events"]["dropped_single_company_filing"] == 1


def test_a_stock_tips_article_is_removed_from_every_bundle():
    q, e = "BEL just won a new defence order, what does this mean for the stock?", ent(["BEL"])
    b = bundle(news=[news_row("n1", "Top 3 stocks to buy: HDFC Bank, Infosys, BEL by Ganesh Dongre | Target price, stop-loss for IT, defence")])
    rep = F.filter_bundle(b, F.plan_for(q, {"intent": "news_reaction"}, e), q, e, NOW)
    assert b.news == [] and rep["news"]["dropped_tips"] == 1


def test_a_kotak_research_note_is_removed_from_a_kotak_bundle_but_the_banks_own_news_stays():
    q, e = "What is the outlook for Kotak Mahindra Bank?", ent(["KOTAKBANK"])
    b = bundle(news=[news_row("n1", "Largecaps face investor apathy, mid and smallcaps fuel euphoria: Kotak Institutional Equities"),
                     news_row("n2", "Kotak Mahindra Bank reports 12% rise in advances for the September quarter"),
                     news_row("n3", "Analysts at Kotak expect two rate cuts")])
    F.filter_bundle(b, F.plan_for(q, {}, e), q, e, NOW)
    assert [n["id"] for n in b.news] == ["n2"]


def test_bel_with_only_a_tips_article_has_an_unsupported_premise():
    q, e = "BEL just won a new defence order, what does this mean for the stock?", ent(["BEL"])
    b = bundle(news=[news_row("n1", "Top 3 stocks to buy: HDFC Bank, Infosys, BEL by Ganesh Dongre | Target price, stop-loss")])
    rep = F.filter_bundle(b, F.plan_for(q, {"intent": "news_reaction"}, e), q, e, NOW)
    assert rep["premise"]["required"] is True and rep["premise"]["supported"] is False and b.premise == rep["premise"]


def test_bel_with_a_real_order_announcement_has_a_supported_premise():
    q, e = "BEL just won a new defence order, what does this mean for the stock?", ent(["BEL"])
    b = bundle(announcements=[ann_row("a1", "Bharat Electronics Limited has informed the Exchange about receipt of orders worth Rs 1,200 crore", symbol="BEL")])
    rep = F.filter_bundle(b, F.plan_for(q, {"intent": "news_reaction"}, e), q, e, NOW)
    assert rep["premise"]["supported"] is True and rep["premise"]["supporting"]


def test_a_company_announcement_that_does_not_mention_an_order_does_not_support_the_order_premise():
    q, e = "BEL just won a new defence order", ent(["BEL"])
    b = bundle(announcements=[ann_row("a1", "Bharat Electronics Limited has informed the Exchange about Newspaper Publication", symbol="BEL")])
    assert F.filter_bundle(b, F.plan_for(q, {}, e), q, e, NOW)["premise"]["supported"] is False


def test_a_question_without_an_event_premise_does_not_require_one():
    q, e = "What is the outlook for BEL?", ent(["BEL"])
    assert F.filter_bundle(bundle(), F.plan_for(q, {}, e), q, e, NOW)["premise"]["required"] is False


# ── the bundle: premise notice, index, context text ─────────────────────────

def test_premise_notice_appears_only_for_an_unsupported_premise():
    b = EvidenceBundle()
    assert b.premise_notice() == ""
    b.premise = {"required": True, "terms": ["order"], "supported": False}
    assert "could not be verified" in b.premise_notice() and "order" in b.premise_notice()
    b.premise = {"required": True, "terms": ["order"], "supported": True}
    assert b.premise_notice() == ""


def _full_bundle():
    b = EvidenceBundle()
    b.events = [ev_row("e1", "US enterprise IT spending contracts", 3, ["TCS", "INFY", "WIPRO"]), ev_row("e2", "RBI holds repo rate", 4)]
    b.news = [news_row("n1", "Rupee holds steady at 95.44"), news_row("n2", "TCS wins large deal")]
    b.policies = [{"id": "p1", "title": "RBI policy", "ministry": "RBI", "summary": ""}]
    b.announcements = [ann_row("a1", "TCS board outcome", symbol="TCS"), ann_row("a2", "Infosys press release", symbol="INFY")]
    b.context_lines = ["TCS: P/E 15.1, P/B 6.85", "India VIX current level: 14.4"]
    return b


def test_index_ids_follow_the_order_the_prompt_uses():
    ids = [e["id"] for e in _full_bundle().index()]
    assert ids == ["E1", "E2", "N1", "N2", "P1", "A1", "A2", "C1", "C2"]


def test_context_text_tags_context_lines_and_announcements():
    t = _full_bundle().to_context_text()
    assert "[C1] TCS: P/E 15.1" in t and "[A1] TCS: TCS board outcome" in t and "[A2] INFY: Infosys press release" in t


def test_every_id_shown_in_each_prompt_resolves_in_the_index():
    b = _full_bundle()
    index_ids = {e["id"] for e in b.index()}
    e1 = ent(["TCS"])
    prompts = {
        "company": company.build_prompt("TCS outlook", b, {"intent": "general"}, e1),
        "sector": sector.build_prompt("IT sector outlook", b, {}, ent(sectors=["it"])),
        "pairwise": comparison.build_prompt("TCS vs Infosys", b, {"is_comparison": True, "holding": "Tata Consultancy Services Ltd", "target": "Infosys Ltd"}, ent(["TCS", "INFY"])),
    }
    for name, p in prompts.items():
        shown = set(re.findall(r"\[([ENPAC]\d{1,2})\]", p))
        assert shown and shown <= index_ids, (name, shown - index_ids)
        assert '"claim_sources"' in p and "EXACTLY" in p and "never invent one" in p.lower()


def test_prompts_carry_the_verification_note_only_when_the_premise_is_unsupported():
    b = _full_bundle()
    b.premise = {"required": True, "terms": ["order"], "supported": False}
    assert "VERIFICATION NOTE" in company.build_prompt("BEL just won an order", b, {"intent": "news_reaction"}, ent(["BEL"]))
    b.premise = {}
    assert "VERIFICATION NOTE" not in company.build_prompt("BEL outlook", b, {}, ent(["BEL"]))


# ── the announcement-context leak ───────────────────────────────────────────

@pytest.fixture
def stubbed(monkeypatch):
    async def fake_events(db, query, limit=10, entities=None, tagged_only=False, terms=None):
        return []

    async def fake_news(db, query, limit=8, entities=None, entity_terms=None):
        return []

    async def fake_policies(db, query, limit=5, entities=None):
        return []

    async def fake_ann(sym, limit=8):
        return [ann_row(f"fresh-{sym}", f"{sym} board outcome", (NOW - timedelta(days=3)).isoformat()), ann_row(f"stale-{sym}", f"{sym} old circular", (datetime.now(timezone.utc) - timedelta(days=200)).isoformat())]

    async def boom(*a, **k):
        raise RuntimeError("offline")

    async def no_cluster(db, bundle):
        bundle.development_count = 0

    monkeypatch.setattr(ev_mod, "_search_events", fake_events)
    monkeypatch.setattr(ev_mod, "_search_news", fake_news)
    monkeypatch.setattr(ev_mod, "_search_policies", fake_policies)
    monkeypatch.setattr(ev_mod, "_fetch_valuation_sync", lambda syms: {})
    monkeypatch.setattr(ev_mod, "_fetch_vix_sync", lambda: None)
    monkeypatch.setattr(ev_mod, "_apply_clustering", no_cluster)
    monkeypatch.setattr(ev_mod.cache_mod, "component", lambda kind, sig, factory: factory())
    import app.services.company_announcements_service as cas
    import app.services.historical_memory_service as hist
    import app.services.intelligence.engine as eng
    monkeypatch.setattr(cas, "get_recent_announcements", fake_ann)
    monkeypatch.setattr(eng, "get_intelligence_state", boom)
    monkeypatch.setattr(hist, "find_similar_events", boom)


def test_a_filtered_announcement_never_reaches_the_prompt_text(stubbed):
    b = asyncio.run(ev_mod.collect("What is happening with TCS lately?", {}, ent(["TCS"]), db=None))
    text = b.to_context_text()
    assert "TCS board outcome" in text and "TCS old circular" not in text
    assert [a["id"] for a in b.announcements] == ["fresh-TCS"]


# ── claim_sources validator ─────────────────────────────────────────────────

def idx(*entries):
    return [{"id": i, "kind": k, "title": t, "summary": "", "companies": c} for i, k, t, c in entries]


def answer(**kw):
    return {"answer": kw}


def test_a_well_sourced_answer_validates_ok():
    index = idx(("E1", "event", "US enterprise IT spending contracts for second consecutive quarter", ["TCS", "INFY", "WIPRO"]))
    claim = "US enterprise IT spending contracted for a second consecutive quarter."
    r = CS.validate_claim_sources([{"claim": claim, "sources": ["E1"]}], index, answer(summary=claim), ent(sectors=["it"]), UNIVERSE)
    assert r["status"] == "ok" and r["claims"][0]["status"] == "ok" and r["summary"]["uncovered_factual_sentences"] == 0


def test_ids_are_normalised_and_unknown_ids_are_reported():
    index = idx(("E1", "event", "Rupee falls to 96", []))
    claim = "The rupee fell to 96 against the dollar."
    r = CS.validate_claim_sources([{"claim": claim, "sources": ["[e1]", "E9"]}], index, answer(summary=claim), ent(), UNIVERSE)
    assert r["claims"][0]["sources"] == ["E1", "E9"] and any("unknown_source: E9" in p for p in r["claims"][0]["problems"])


def test_a_claim_with_no_source_and_a_claim_not_in_the_answer_are_reported():
    r = CS.validate_claim_sources([{"claim": "TCS won a Rs 500 crore deal.", "sources": []}, {"claim": "A sentence the model never wrote.", "sources": ["E1"]}],
                                  idx(("E1", "event", "x", [])), answer(summary="TCS won a Rs 500 crore deal."), ent(["TCS"]), UNIVERSE)
    assert "no_source" in r["claims"][0]["problems"] and "claim_not_in_answer" in r["claims"][1]["problems"] and r["status"] == "problems"


def test_a_tera_software_filing_cannot_be_the_source_of_a_sector_claim():
    index = idx(("E1", "event", "Tera Software Limited has informed the Exchange that Board of Directors approved fund raising", []))
    claim = "IT sector software firms are raising funds."
    r = CS.validate_claim_sources([{"claim": claim, "sources": ["E1"]}], index, answer(summary=claim), ent(sectors=["it"]), UNIVERSE)
    assert r["claims"][0]["status"] == "problem" and any(p.startswith("ineligible_sources") and "single-company" in p for p in r["claims"][0]["problems"])


def test_a_stock_tips_article_cannot_be_the_source_of_a_bel_claim():
    index = idx(("N1", "news", "Top 3 stocks to buy: HDFC Bank, Infosys, BEL by Ganesh Dongre | Target price, stop-loss", []))
    claim = "Bharat Electronics won a new defence order."
    r = CS.validate_claim_sources([{"claim": claim, "sources": ["N1"]}], index, answer(summary=claim), ent(["BEL"]), UNIVERSE)
    assert any(p.startswith("ineligible_sources") and "stock-tips" in p for p in r["claims"][0]["problems"])


def test_a_kotak_research_note_cannot_be_the_source_of_a_kotak_mahindra_bank_claim():
    index = idx(("N1", "news", "Largecaps face investor apathy: Kotak Institutional Equities", []))
    claim = "Kotak Mahindra Bank sees largecaps facing investor apathy."
    r = CS.validate_claim_sources([{"claim": claim, "sources": ["N1"]}], index, answer(summary=claim), ent(["KOTAKBANK"]), UNIVERSE)
    assert r["claims"][0]["status"] == "problem"


def test_one_eligible_source_is_enough_even_if_another_cited_source_is_not():
    index = idx(("A1", "announcement", "Kotak Mahindra Bank Limited has informed the Exchange about General Updates", ["KOTAKBANK"]),
                ("N1", "news", "Kotak Institutional Equities strategy note", []))
    claim = "Kotak Mahindra Bank filed a general updates disclosure."
    r = CS.validate_claim_sources([{"claim": claim, "sources": ["A1", "N1"]}], index, answer(summary=claim), ent(["KOTAKBANK"]), UNIVERSE)
    assert r["claims"][0]["status"] == "ok" and r["claims"][0]["ineligible"] == ["N1"]


def test_a_claim_about_the_unverified_event_is_flagged_as_premise_unsupported():
    index = idx(("A1", "announcement", "Bharat Electronics Limited has informed the Exchange about Newspaper Publication", ["BEL"]))
    claim = "Bharat Electronics won a large defence order."
    premise = {"required": True, "terms": ["order"], "supported": False}
    r = CS.validate_claim_sources([{"claim": claim, "sources": ["A1"]}], index, answer(summary=claim), ent(["BEL"]), UNIVERSE, premise)
    assert any(p.startswith("premise_unsupported") for p in r["claims"][0]["problems"])


def test_factual_sentences_with_no_claim_entry_are_reported_as_uncovered():
    index = idx(("E1", "event", "Rupee falls to 96", []))
    r = CS.validate_claim_sources([{"claim": "The rupee fell to 96.", "sources": ["E1"]}], index,
                                  answer(summary="The rupee fell to 96. Exports rose 14% last quarter."), ent(), UNIVERSE)
    assert r["status"] == "problems" and any("14%" in s for s in r["uncovered"])


def test_no_claim_sources_is_not_provided_and_malformed_entries_are_reported():
    assert CS.validate_claim_sources(None, [], answer(summary="x"), ent(), UNIVERSE)["status"] == "not_provided"
    assert CS.validate_claim_sources([], [], answer(summary="x"), ent(), UNIVERSE)["status"] == "not_provided"
    r = CS.validate_claim_sources([{"claim": "x"}, "junk"], [], answer(summary="x"), ent(), UNIVERSE)
    assert [c["status"] for c in r["claims"]] == ["malformed", "malformed"]


def test_pipeline_premise_check_shapes():
    assert P._premise_check(SimpleNamespace(premise={})) == {"status": "not_applicable", "terms": []}
    assert P._premise_check(SimpleNamespace(premise={"required": True, "terms": ["order"], "supported": False}))["status"] == "unsupported"
    assert P._premise_check(SimpleNamespace(premise={"required": True, "terms": ["order"], "supported": True, "supporting": ["x"]}))["status"] == "supported"


# ── the offline gate: irrelevant evidence, not just empty ───────────────────

def snap(plan, events=(), news=(), announcements=(), premise=None):
    return {"plan_kind": plan, "events": list(events), "news": list(news), "announcements": list(announcements), "policies": [], "valuation": {}, "sector_rows": [], "macro_indices": [],
            "context_lines": [], "premise": premise, "index": None, "historical": [], "vix": None, "filter_report": {}}


def test_gate_flags_a_single_filing_in_a_sector_bundle_and_a_tips_article_anywhere():
    e = snap("topic", events=[{"id": "t", "title": "Tera Software Limited has informed the Exchange about board outcome", "summary": "", "companies": [], "date": None}],
             news=[{"id": "n", "title": "Top 3 stocks to buy: HDFC Bank, Infosys, BEL", "summary": "", "date": None}])
    r = AC.bundle_irrelevance(e, [], ["it"])
    assert r["status"] == "FAIL" and {x["why"] for x in r["irrelevant_items"]} == {"single-company exchange filing", "stock-tips article"} and r["relevant_total"] == 0


def test_gate_treats_a_non_empty_but_irrelevant_bel_bundle_as_insufficient_evidence():
    e = snap("company", news=[{"id": "n", "title": "Top 3 stocks to buy: HDFC Bank, Infosys, BEL by Ganesh Dongre", "summary": "", "date": "32m ago"}],
             premise={"required": True, "terms": ["order"], "supported": False})
    assert AC.evidence_total(e) == 1
    honest = answer(summary="MarketRipple has no verified evidence that BEL won a new order, so the impact cannot be assessed.")
    invented = answer(summary="BEL won a Rs 2,100 crore order that lifts its order book and margins.")
    ok = AC.insufficient_evidence_check(honest, e, "BEL just won a new defence order", UNIVERSE, ["BEL"])
    bad = AC.insufficient_evidence_check(invented, e, "BEL just won a new defence order", UNIVERSE, ["BEL"])
    assert ok["applicable"] and ok["applies_because"] != "empty bundle" and ok["status"] == "PASS"
    assert bad["status"] == "FAIL"


def test_gate_does_not_flag_company_evidence_that_names_the_company():
    e = snap("company", announcements=[{"id": "a", "title": "Tata Consultancy Services Limited has informed the Exchange about results", "summary": "", "companies": ["TCS"], "date": "2026-10-01"}])
    assert AC.bundle_irrelevance(e, ["TCS"], [])["status"] == "PASS"


def test_gate_revalidates_claim_sources_independently_and_reports_disagreement():
    index = [{"id": "E1", "kind": "event", "title": "Tera Software Limited has informed the Exchange that Board approved fund raising", "summary": "", "companies": []}]
    claim = "IT sector software firms are raising funds."
    res = {"answer": {"summary": claim}, "claim_sources": [{"claim": claim, "sources": ["E1"], "status": "ok", "problems": []}]}   # the pipeline (wrongly) said ok
    e = snap("topic", events=[{"id": "x", "title": "t", "summary": "", "companies": [], "date": None}])
    e["index"] = index
    r = AC.claim_source_check(res, e, ent(sectors=["it"]))
    assert r["checkable"] and r["status"] == "problems" and r["disagrees_with_pipeline_on"]
    assert AC.claim_source_check({"answer": {"summary": "x"}}, e, ent())["checkable"] is False


def test_snapshot_records_the_premise_and_the_index():
    b = _full_bundle()
    b.premise = {"required": True, "terms": ["order"], "supported": False}
    b.plan_kind, b.filter_report, b.valuation, b.vix_level, b.sector_rows, b.macro_indices, b.similar_historical = "company", {}, {}, None, [], [], []
    s = AC.snapshot_evidence(b)
    assert s["premise"]["supported"] is False and [i["id"] for i in s["index"]][:2] == ["E1", "E2"]
