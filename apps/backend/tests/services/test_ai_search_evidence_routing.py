"""
Step 2 retrieval planning and evidence checks: what is fetched depends on the question type, and stale or irrelevant evidence is removed before it reaches
the answer. Pure functions are tested directly; collect() is tested with every data source stubbed, so nothing here touches the network or a model.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.ai_search import evidence as ev_mod
from app.services.ai_search import evidence_filter as F
from app.services.ai_search import pipeline as P

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def ent(companies=(), sectors=(), policies=()):
    return {"companies": list(companies), "company_matches": [], "sectors": list(sectors), "policies": list(policies)}


# ── plan_for ────────────────────────────────────────────────────────────────

def test_comparison_plans_events_announcements_and_valuation_for_both_companies():
    p = F.plan_for("TCS vs Infosys, which is stronger?", {"is_comparison": True}, ent(["TCS", "INFY"]))
    assert p.kind == "comparison" and p.events == "tagged" and p.news == "entity"
    assert p.announcements_for == ["TCS", "INFY"] and p.valuation_for == ["TCS", "INFY"]


def test_single_company_plan_is_company_scoped_with_announcements():
    p = F.plan_for("What is happening with TCS lately?", {}, ent(["TCS"]))
    assert (p.kind, p.events, p.news, p.announcements_for) == ("company", "tagged", "entity", ["TCS"])


def test_event_question_gets_the_tighter_age_window():
    p = F.plan_for("BEL just won a new order", {"intent": "news_reaction"}, ent(["BEL"]))
    assert p.age_key == "company_event" and F.MAX_AGE_DAYS[p.age_key]["events"] < F.MAX_AGE_DAYS["company"]["events"]


@pytest.mark.parametrize("q", ["What is a P/E ratio and how should I read it?", "How does the MarketRipple Score work?", "Explain repo rate in simple terms"])
def test_educational_questions_fetch_no_company_event_news_or_policy_data(q):
    p = F.plan_for(q, {}, ent())
    assert (p.kind, p.events, p.news, p.policies, p.announcements_for, p.valuation_for) == ("explanation", "none", "none", False, [], [])


def test_a_question_that_names_a_company_is_not_an_explanation_even_if_it_starts_with_what_is():
    assert F.plan_for("What is happening with HDFC Bank?", {}, ent(["HDFCBANK"])).kind == "company"
    assert F.plan_for("What is the outlook for the IT sector?", {}, ent(sectors=["it"])).kind == "topic"


def test_sector_and_policy_questions_use_word_retrieval_with_relevance_checks():
    p = F.plan_for("What happens to Indian banks if the RBI cuts the repo rate?", {}, ent(sectors=["banking"], policies=["rbi", "repo rate"]))
    assert (p.kind, p.events, p.news, p.policies) == ("topic", "words", "words", True)


# ── age_days ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("Oct 01, 2026", 3.5), ("2026-09-04", 30.5), ("2026-10-04T06:00:00", 0.25), ("44m ago", 44 / 1440), ("1h ago", 1 / 24), ("1d ago", 1.0), ("2 weeks ago", 14.0),
])
def test_age_days_reads_every_date_shape_the_bundle_carries(value, expected):
    assert F.age_days(value, NOW) == pytest.approx(expected, abs=0.6)


@pytest.mark.parametrize("value", [None, "", "yesterday-ish", "sometime", 123])
def test_age_days_never_guesses(value):
    assert F.age_days(value, NOW) is None


# ── filter_bundle ───────────────────────────────────────────────────────────

def bundle(events=(), news=(), policies=(), announcements=()):
    return SimpleNamespace(events=list(events), news=list(news), policies=list(policies), announcements=list(announcements))


def event(title, days_old, symbols=(), summary=""):
    d = (NOW - timedelta(days=days_old)).isoformat()
    return {"id": title, "title": title, "summary": summary, "companies": [{"symbol": s} for s in symbols], "event_date": d, "published_at": d, "date": ""}


def test_company_plan_drops_events_not_tagged_to_the_company_and_events_older_than_the_window():
    b = bundle(events=[event("TCS result", 5, ["TCS"]), event("ICICI filing", 2, ["ICICIBANK"]), event("TCS old deal", 200, ["TCS"])])
    rep = F.filter_bundle(b, F.plan_for("TCS outlook", {}, ent(["TCS"])), "TCS outlook", ent(["TCS"]), NOW)
    assert [e["title"] for e in b.events] == ["TCS result"]
    assert rep["events"] == {"kept": 1, "dropped_stale": 1, "dropped_irrelevant": 1}


def test_company_news_must_name_the_company_and_have_a_readable_recent_date():
    b = bundle(news=[
        {"headline": "TCS wins large deal", "summary": "", "published_at": "2h ago"},
        {"headline": "RBI repo rate may climb", "summary": "", "published_at": "1h ago"},
        {"headline": "TCS old story", "summary": "", "published_at": "2026-06-01"},
        {"headline": "TCS undated story", "summary": "", "published_at": "whenever"},
    ])
    rep = F.filter_bundle(b, F.plan_for("TCS outlook", {}, ent(["TCS"])), "TCS outlook", ent(["TCS"]), NOW)
    assert [n["headline"] for n in b.news] == ["TCS wins large deal"]
    assert rep["news"]["dropped_irrelevant"] == 1 and rep["news"]["dropped_stale"] == 1 and rep["news"]["dropped_undated"] == 1


def test_policies_are_kept_only_when_the_question_named_that_policy():
    pol = [{"title": "RBI keeps repo rate unchanged", "summary": "", "ministry": "RBI"}, {"title": "FOMC minutes", "summary": "", "ministry": "US Federal Reserve"}]
    b = bundle(policies=list(pol))
    F.filter_bundle(b, F.plan_for("RBI repo rate cut", {}, ent(policies=["rbi", "repo rate"])), "RBI repo rate cut", ent(policies=["rbi", "repo rate"]), NOW)
    assert [p["title"] for p in b.policies] == ["RBI keeps repo rate unchanged"]
    b2 = bundle(policies=list(pol))
    F.filter_bundle(b2, F.plan_for("What is a P/E ratio?", {}, ent()), "What is a P/E ratio?", ent(), NOW)
    assert b2.policies == []


def test_explanation_plan_removes_everything_that_word_matching_would_have_injected():
    b = bundle(events=[event("Indian Oil approval", 2)], news=[{"headline": "market wrap", "summary": "", "published_at": "1h ago"}],
               policies=[{"title": "FOMC", "summary": "", "ministry": ""}])
    F.filter_bundle(b, F.plan_for("What is a P/E ratio?", {}, ent()), "What is a P/E ratio?", ent(), NOW)
    assert b.events == [] and b.news == [] and b.policies == []


def test_topic_events_need_the_named_sector_or_two_distinctive_question_words():
    b = bundle(events=[event("Bank credit growth rises", 3), event("Cement prices fall", 3)])
    F.filter_bundle(b, F.plan_for("How is the banking sector doing?", {}, ent(sectors=["banking"])), "How is the banking sector doing?", ent(sectors=["banking"]), NOW)
    assert [e["title"] for e in b.events] == ["Bank credit growth rises"]


# ── collect() with every source stubbed ─────────────────────────────────────

@pytest.fixture
def stubbed(monkeypatch):
    calls = {"events": [], "news": [], "policies": 0, "announcements": [], "valuation": []}

    async def fake_events(db, query, limit=10, entities=None, tagged_only=False, terms=None):
        sym = ((entities or {}).get("companies") or [None])[0]
        calls["events"].append((sym, tagged_only) if sym or tagged_only else ("topic", tuple(terms or ())))
        return [event(f"{sym} development", 5, [sym])] if sym else [event("Indian Oil approval", 2)]

    async def fake_news(db, query, limit=8, entities=None, entity_terms=None):
        calls["news"].append(entity_terms)
        return []

    async def fake_policies(db, query, limit=5, entities=None):
        calls["policies"] += 1
        return [{"id": "p1", "title": "FOMC minutes", "summary": "", "ministry": "US Federal Reserve"}]

    def fake_valuation(symbols):
        calls["valuation"].append(list(symbols))
        return {s: {"pe": 20.0, "pb": 3.0} for s in symbols}

    async def fake_announcements(sym, limit=8):
        calls["announcements"].append(sym)
        return [{"id": f"a-{sym}", "subject": f"{sym} board outcome", "category": "Board Meeting", "announcement_date": (NOW - timedelta(days=2)).isoformat()}]

    async def no_clustering(db, bundle):
        bundle.development_count = 0

    monkeypatch.setattr(ev_mod, "_search_events", fake_events)
    monkeypatch.setattr(ev_mod, "_search_news", fake_news)
    monkeypatch.setattr(ev_mod, "_search_policies", fake_policies)
    monkeypatch.setattr(ev_mod, "_fetch_valuation_sync", fake_valuation)
    monkeypatch.setattr(ev_mod, "_fetch_vix_sync", lambda: None)
    monkeypatch.setattr(ev_mod, "_apply_clustering", no_clustering)
    monkeypatch.setattr(ev_mod.cache_mod, "component", lambda kind, sig, factory: factory())
    import app.services.company_announcements_service as cas
    monkeypatch.setattr(cas, "get_recent_announcements", fake_announcements)
    # sources collect() reaches inside try/except: make them fail fast offline
    import app.services.intelligence.engine as eng
    import app.services.historical_memory_service as hist

    async def boom(*a, **k):
        raise RuntimeError("offline")

    monkeypatch.setattr(eng, "get_intelligence_state", boom)
    monkeypatch.setattr(hist, "find_similar_events", boom)
    return calls


def run_collect(query, intent, entities):
    return asyncio.run(ev_mod.collect(query, intent, entities, db=None))


def test_comparison_collect_fetches_events_announcements_and_valuation_for_both_companies(stubbed):
    b = run_collect("TCS vs Infosys, which is stronger?", {"is_comparison": True}, ent(["TCS", "INFY"]))
    assert stubbed["events"] == [("TCS", True), ("INFY", True)]
    assert sorted(stubbed["announcements"]) == ["INFY", "TCS"]
    assert stubbed["valuation"] == [["TCS", "INFY"]] and set(b.valuation) == {"TCS", "INFY"}
    assert {e["title"] for e in b.events} == {"TCS development", "INFY development"}
    assert b.plan_kind == "comparison" and stubbed["policies"] == 0


def test_explanation_collect_fetches_no_company_event_news_policy_or_announcement(stubbed):
    b = run_collect("What is a P/E ratio and how should I read it?", {}, ent())
    assert stubbed["events"] == [] and stubbed["news"] == [] and stubbed["policies"] == 0 and stubbed["announcements"] == [] and stubbed["valuation"] == []
    assert b.events == b.news == b.policies == b.announcements == [] and b.plan_kind == "explanation"


def test_company_collect_is_company_scoped_and_fetches_its_announcements(stubbed):
    b = run_collect("What is happening with TCS lately?", {}, ent(["TCS"]))
    assert stubbed["events"] == [("TCS", True)] and stubbed["announcements"] == ["TCS"]
    assert [a["subject"] for a in b.announcements] == ["TCS board outcome"]


# ── degraded copy ───────────────────────────────────────────────────────────

def test_degraded_copy_describes_only_the_events_actually_displayed():
    assert "No supporting evidence is shown" in P.degraded_evidence_sentence(0)
    assert P.degraded_evidence_sentence(1) == "1 related event found for this question is listed below."
    assert P.degraded_evidence_sentence(3) == "3 related events found for this question are listed below."


def _degraded(evidence_events, entities):
    ev = SimpleNamespace(events=evidence_events, news=[{"headline": "x"}], policies=[])
    ai = {"bottom_line": "There isn't enough freshly generated analysis to answer this question with confidence right now — the synthesis step didn't complete."}
    return P._build_degraded_response("q", ai, ev, "company", "capacity", entities, "rid")


def test_degraded_response_never_promises_news_it_does_not_show():
    r = _degraded([event("ICICI filing", 2, ["ICICIBANK"])], ent(["KOTAKBANK"]))
    assert r["news"] == [] and r["related_events"] == []
    assert "below" not in r["answer"]["summary"] and "No supporting evidence is shown" in r["answer"]["summary"]


def test_degraded_response_counts_the_tagged_events_it_does_show():
    r = _degraded([event("Kotak result", 2, ["KOTAKBANK"])], ent(["KOTAKBANK"]))
    assert len(r["related_events"]) == 1 and "1 related event found for this question is listed below." in r["answer"]["summary"]
    assert r["answer"]["sources_count"] == 1


# ── topic retrieval by the named sector's / macro vocabulary ─────────────────

def test_topic_search_terms_use_sector_policy_and_macro_vocabulary_not_raw_words():
    t = F.topic_search_terms("How would a weaker rupee affect Indian IT exporters?", ent(sectors=["it"]))
    assert "software" in t and "rupee" in t and "usd/inr" in t
    assert "it" not in t           # the 2-letter word that is a substring of almost any title
    crude = F.topic_search_terms("How would higher crude oil prices affect Indian markets?", ent())
    assert "crude" in crude and "brent" in crude


def test_topic_collect_searches_by_those_terms(stubbed):
    run_collect("What is the outlook for the IT services sector?", {}, ent(sectors=["it"]))
    assert stubbed["events"][0][0] == "topic" and "software" in stubbed["events"][0][1]


def test_macro_items_are_relevant_to_a_macro_question_without_a_named_sector():
    b = bundle(events=[event("Rupee falls to 96 against dollar", 3), event("Cement prices fall", 3)])
    q, e = "How would a weaker rupee affect Indian IT exporters?", ent(sectors=["it"])
    F.filter_bundle(b, F.plan_for(q, {}, e), q, e, NOW)
    assert [x["title"] for x in b.events] == ["Rupee falls to 96 against dollar"]
