"""
Step 3.4G.1: deterministic evidence ranking. Candidates are filtered by the existing rules FIRST, then ranked (coverage, recency, substance, impact), then selected within a bounded budget with
near-duplicate suppression; comparisons are selected per company; the news window no longer depends on cache state. No provider call, no database (retrieval is stubbed).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.ai_search import evidence_filter as F
from app.services.ai_search import evidence_ranking as R
from app.services.ai_search import retrieval as RT

NOW = datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc)


def ent(companies=(), sectors=(), policies=()):
    return {"companies": list(companies), "sectors": list(sectors), "policies": list(policies)}


def ev(i, title, days=2, impact=5.0, companies=(), summary=""):
    d = (NOW - timedelta(days=days)).isoformat()
    return {"id": f"e{i}", "title": title, "summary": summary, "category": "Market", "impact_score": impact, "companies": [{"symbol": s} for s in companies], "event_date": d, "published_at": d, "date": ""}


def news(i, headline, ago="1h ago", impact=5.0, summary=""):
    return {"id": f"n{i}", "headline": headline, "summary": summary, "published_at": ago, "source": "ET", "impact_score": impact}


def ann(i, subject, days=2, category=None, description=None, sym="TCS"):
    return {"id": f"a{i}", "subject": subject, "category": category, "description": description, "announcement_date": (NOW - timedelta(days=days)).isoformat(), "symbol": sym}


_WORDS = ["merger", "dividend", "guidance", "capex", "layoffs", "hiring", "pricing", "margin", "cloud", "tariff", "visa", "demand", "contract", "client", "attrition", "forecast", "analyst",
          "quarter", "currency", "supply", "regulator", "audit", "rating", "buyback", "subsidiary", "patent", "outage", "strike", "approval", "expansion", "restructuring", "partnership", "lawsuit",
          "launch", "recall", "tender", "export", "import", "inflation", "budget"]


def distinct(i: int, lead: str) -> str:
    """A title that shares only its lead word with the others, so near-duplicate suppression cannot apply."""
    return f"{lead} {_WORDS[i % 40]} {_WORDS[(i * 7 + 3) % 40]} {_WORDS[(i * 11 + 5) % 40]} {_WORDS[(i * 13 + 9) % 40]}"


def plan(q, entities, intent=None):
    return F.plan_for(q, intent or {}, entities)


# ── score components ────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_substance_ranks_results_and_rates_above_routine_and_administrative_items():
    assert R.substance("Infosys Q2 results beat estimates, revenue up") > R.substance("Company X informed the Exchange about something unusual") > R.substance("Allotment of shares under ESOP")
    assert R.substance("Newspaper Publication of results") == 0.0                    # administrative regex wins even though the word results is present
    assert R.substance("RBI MPC may hike repo rate") > R.substance("Plant visit schedule of analyst meet")


def test_coverage_counts_distinct_question_terms_in_the_title_more_than_in_the_summary():
    terms = ["rbi", "repo", "rate cut"]
    two_in_title = R.coverage("RBI may cut repo rate", "", terms)
    one_in_title = R.coverage("RBI remains cautious on crypto", "", terms)
    summary_only = R.coverage("Markets await policy", "RBI repo decision due", terms)
    assert two_in_title > summary_only > 0 and two_in_title > one_in_title and R.coverage("Cement prices fall", "", terms) == 0.0
    assert R.coverage("anything", "", []) == 0.5


def test_recency_falls_linearly_inside_the_age_window_and_undated_is_neutral():
    assert R._recency(0.0, 60) == 1.0 and R._recency(30.0, 60) == 0.5 and R._recency(90.0, 60) == 0.0 and R._recency(None, 60) == 0.4


def test_score_is_the_weighted_sum_and_every_component_is_recorded():
    s = R.score_item(title="RBI MPC may hike repo rate", summary="", age=1.0, limit_days=60, impact=0, terms=["rbi", "repo", "mpc"])
    assert set(s) == {"coverage", "recency", "substance", "impact", "score"}
    assert s["score"] == pytest.approx(sum(R.WEIGHTS[k] * s[k] for k in R.WEIGHTS), abs=1e-3)
    assert abs(sum(R.WEIGHTS.values()) - 1.0) < 1e-9


# ── selection, diversity, determinism ───────────────────────────────────────────────────────────────────────────────────────────

def _select(titles, budget, **kw):
    rows = [{"id": i, "title": t} for i, t in enumerate(titles)]
    scored = [{"score": 1.0 - 0.01 * i, "recency": 0.5, "_title": t, **{k: 0 for k in ("coverage", "substance", "impact")}} for i, t in enumerate(titles)]
    return R.select(rows, scored, budget)


def test_near_duplicates_are_not_selected_together_and_never_fill_leftover_budget():
    titles = ["RBI MPC may hike repo rate next week experts", "RBI MPC may hike repo rate next week: experts share strategy", "Infosys wins large cloud deal", "Banks see credit growth pickup"]
    sel, trace = _select(titles, budget=4)
    assert [r["id"] for r in sel] == [0, 2, 3]                                             # the duplicate (id 1) is left out even though budget remains
    assert any(t["duplicate_deferred"] for t in trace)


def test_the_budget_is_a_ceiling_and_the_best_distinct_items_win():
    titles = [distinct(i, "Story") for i in range(8)]
    sel, _ = _select(titles, budget=3)
    assert [r["id"] for r in sel] == [0, 1, 2]


def test_two_different_filings_by_the_same_company_are_not_duplicates_of_each_other():
    a = "Infosys Limited has informed the Exchange regarding Allotment of 175865 Shares."
    b = "Infosys Limited has informed the Exchange about change in Management"
    assert R._title_jaccard(a, b) < R.DUP_JACCARD
    assert R._title_jaccard("Kotak Mahindra Bank Limited has informed the Exchange about General Updates.", "Kotak Mahindra Bank Limited has informed the Exchange about General Updates") >= R.DUP_JACCARD


def test_selection_is_deterministic_and_ties_break_on_recency_then_input_order():
    rows = [{"id": i, "title": f"title {i} unique{i}{i}{i}"} for i in range(4)]
    scored = [{"score": 0.5, "recency": r, "_title": rows[i]["title"], "coverage": 0, "substance": 0, "impact": 0} for i, r in enumerate([0.2, 0.9, 0.9, 0.1])]
    first, _ = R.select(rows, scored, 3)
    second, _ = R.select(rows, scored, 3)
    assert [r["id"] for r in first] == [r["id"] for r in second] == [1, 2, 0]


# ── filter BEFORE limit; relevance beats stored impact ───────────────────────────────────────────────────────────────────────────

def test_a_pool_full_of_high_impact_filings_does_not_displace_lower_impact_on_topic_events():
    q, e = "What is the outlook for the IT services sector?", ent(sectors=["it"])
    filings = [ev(i, f"Company{i} Software Limited has informed the Exchange about Board Meeting", impact=9.5) for i in range(40)]
    topical = [ev(100 + i, t, impact=2.0) for i, t in enumerate(["Nifty IT crashes 11% in September as Infosys slides", "Software spending slowdown hits Wipro demand outlook",
                                                                  "Accenture results lift TCS shares", "HCLTech Q2 results dates announced for software exporters"])]
    b = SimpleNamespace(events=filings + topical, news=[], policies=[], announcements=[])
    F.filter_bundle(b, plan(q, e), q, e, NOW)
    assert {x["id"] for x in b.events} == {"e100", "e101", "e102", "e103"}               # filings removed by the filter, then the on-topic events ranked in
    assert b.rank_trace["events"]


def test_on_topic_rate_items_beat_off_topic_high_impact_items_for_a_rate_question():
    q, e = "What happens to Indian banks if the RBI cuts the repo rate?", ent(sectors=["banking"], policies=["rbi", "repo rate"])
    off = [ev(i, f"RBI remains cautious on crypto story {i}x{i}", impact=9.0) for i in range(12)]
    on = [ev(100 + i, t, impact=1.0) for i, t in enumerate(["RBI MPC may cut repo rate next week, banks eye margins", "Repo rate decision: what a cut means for bank lending rates"])]
    b = SimpleNamespace(events=off + on, news=[], policies=[], announcements=[])
    F.filter_bundle(b, plan(q, e), q, e, NOW)
    top2 = [x["id"] for x in b.events[:2]]
    assert set(top2) == {"e100", "e101"} and len(b.events) <= R.EVENT_BUDGET


def test_the_event_bundle_never_exceeds_its_budget():
    q, e = "What is the outlook for the IT services sector?", ent(sectors=["it"])
    rows = [ev(i, distinct(i, "Infosys"), impact=3.0) for i in range(30)]
    b = SimpleNamespace(events=rows, news=[], policies=[], announcements=[])
    F.filter_bundle(b, plan(q, e), q, e, NOW)
    assert len(b.events) == R.EVENT_BUDGET


# ── comparisons are selected per company ─────────────────────────────────────────────────────────────────────────────────────────

def test_a_comparison_cannot_be_filled_by_one_company():
    q, e = "TCS vs Infosys, which is stronger?", ent(["TCS", "INFY"])
    tcs = [ev(i, distinct(i, "TCS"), companies=["TCS"], impact=9.0) for i in range(12)]
    infy = [ev(100 + i, distinct(i + 20, "Infosys"), companies=["INFY"], impact=1.0) for i in range(2)]
    b = SimpleNamespace(events=tcs + infy, news=[], policies=[], announcements=[])
    F.filter_bundle(b, plan(q, e, {"is_comparison": True}), q, e, NOW)
    ids = {x["id"] for x in b.events}
    assert {"e100", "e101"} <= ids and sum(1 for i in ids if i.startswith("e") and int(i[1:]) < 100) == R.COMPARISON_PER_COMPANY


# ── news: window independent of cache state; ranked, bounded ───────────────────────────────────────────────────────────────────────

def _live_feed(n=60):
    return [{"id": f"x{i}", "headline": ("IT stocks Infosys TCS Wipro outlook " if i in (45, 52) else "Market wrap ") + f"item {i}", "summary": "", "source": "ET", "published_at": f"{i + 1}m ago", "impact_score": 5.0} for i in range(n)]


@pytest.mark.parametrize("warm", [True, False])
def test_the_news_candidate_window_is_the_same_on_a_warm_and_a_cold_cache(monkeypatch, warm):
    feed = _live_feed()

    async def get_live_news(limit=20):
        return list(feed[:limit]) if warm else list(feed)           # the real function: [:limit] when warm, everything (up to 60) when cold

    monkeypatch.setattr(RT, "get_live_news", get_live_news)
    class NoDb:
        async def execute(self, stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    out = asyncio.run(RT._search_news(NoDb(), "outlook for IT services", limit=20, entities=ent(sectors=["it"]), entity_terms=["infosys", "tcs", "wipro"], live_window=RT.POOL_NEWS_WINDOW))
    assert {n["id"] for n in out} == {"x45", "x52"}                    # the on-topic items beyond the newest 20 are found whatever the cache state


def test_news_is_ranked_by_relevance_and_bounded_and_deduplicated():
    q, e = "What is the outlook for the IT services sector?", ent(sectors=["it"])
    rows = [news(1, "Stock market outlook today Sensex Nifty prediction"), news(2, "Indian IT Q2 earnings dilemma deepens: weaker growth for TCS Infosys Wipro"),
            news(3, "Indian IT Q2 earnings dilemma deepens: weaker growth for TCS Infosys Wipro."), news(4, "Wipro share price live updates")] + [news(10 + i, distinct(i, "Infosys")) for i in range(14)]
    b = SimpleNamespace(events=[], news=rows, policies=[], announcements=[])
    F.filter_bundle(b, plan(q, e), q, e, NOW)
    titles = [n["headline"] for n in b.news]
    assert len(b.news) <= R.NEWS_BUDGET and sum("earnings dilemma" in t for t in titles) == 1


# ── announcements: substance before administrative recency; stale counted; budget ─────────────────────────────────────────────────

def test_substantive_filings_outrank_newer_administrative_ones_and_repeats_collapse():
    rows = [ann(1, "Kotak Mahindra Bank Limited has informed the Exchange about General Updates.", days=1), ann(2, "Kotak Mahindra Bank Limited has informed the Exchange about General Updates", days=2),
            ann(3, "Kotak Mahindra Bank Limited has informed the Exchange regarding Outcome of Board Meeting and financial results for the quarter", days=30),
            ann(4, "Kotak Mahindra Bank Limited has informed the Exchange regarding Allotment of 1000 Shares under ESOP", days=3)]
    q, e = "What is the outlook for Kotak Mahindra Bank?", ent(["KOTAKBANK"])
    sel, trace, stale = R.rank_announcements(rows, q, e, plan(q, e), 5, NOW)
    assert sel[0]["id"] == "a3" and stale == 0
    assert sum(1 for r in sel if "General Updates" in r["subject"]) == 1


def test_announcements_older_than_the_window_are_dropped_before_ranking_and_counted():
    rows = [ann(1, "TCS has informed the Exchange regarding financial results", days=200), ann(2, "TCS has informed the Exchange regarding a press release", days=5)]
    q, e = "What is happening with TCS lately?", ent(["TCS"])
    sel, _, stale = R.rank_announcements(rows, q, e, plan(q, e), 5, NOW)
    assert [r["id"] for r in sel] == ["a2"] and stale == 1


def test_the_announcement_budget_is_respected():
    rows = [ann(i, f"TCS has informed the Exchange regarding {distinct(i, 'matter')}", days=i + 1) for i in range(20)]
    q, e = "What is happening with TCS lately?", ent(["TCS"])
    sel, _, _ = R.rank_announcements(rows, q, e, plan(q, e), 5, NOW)
    assert len(sel) == 5


# ── retrieval pools are not cut by impact_score ──────────────────────────────────────────────────────────────────────────────────

def _compiled_event_sql(**kw):
    seen = {}

    class FakeDb:
        async def execute(self, stmt):
            seen["sql"] = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    asyncio.run(RT._search_events(FakeDb(), "outlook IT", **kw))
    return seen["sql"]


def test_the_event_pool_is_ordered_by_recency_not_by_stored_impact_when_requested():
    pooled = _compiled_event_sql(limit=RT.POOL_EVENTS_TOPIC, entities=ent(sectors=["it"]), terms=["software"], pool_by_recency=True)
    legacy = _compiled_event_sql(limit=30, entities=ent(sectors=["it"]), terms=["software"])
    assert "coalesce" in pooled.split("order by")[1].split(",")[0] and f"limit {RT.POOL_EVENTS_TOPIC}" in pooled
    assert legacy.split("order by")[1].strip().startswith("events.impact_score desc") or "impact_score desc" in legacy.split("order by")[1].split(" limit")[0]


def test_pool_sizes_are_bounded_and_much_larger_than_the_old_cuts():
    assert RT.POOL_EVENTS_TOPIC >= 20 * 30 and RT.POOL_EVENTS_TAGGED > 30 and RT.POOL_NEWS_WINDOW == 60 and RT.POOL_ANNOUNCEMENTS > 8


# ── nothing about ranking leaks into the evidence items the response publishes ──────────────────────────────────────────────────

def test_ranking_details_live_on_the_bundle_trace_not_on_the_items():
    q, e = "What is the outlook for the IT services sector?", ent(sectors=["it"])
    b = SimpleNamespace(events=[ev(1, "Nifty IT crashes 11% as TCS Infosys Wipro slide")], news=[news(1, "IT outlook Infosys TCS Wipro")], policies=[], announcements=[])
    F.filter_bundle(b, plan(q, e), q, e, NOW)
    assert all("_rank" not in x and "score" not in x and "components" not in x for x in b.events + b.news)
    assert b.rank_trace["events"][0]["selected"] is True and {"coverage", "recency", "substance", "impact", "score"} <= set(b.rank_trace["events"][0])
