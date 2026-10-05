"""
Step 3.4G.3: cold-start evidence reliability.

The defect: `collect` ran its events, news and policies lookups concurrently on ONE AsyncSession. On the first use of a cold connection pool SQLAlchemy raised "This session is provisioning a new
connection; concurrent operations are not permitted", `gather(return_exceptions=True)` swallowed it, and a whole evidence source silently became []. These tests reproduce that failure against a real
(temporary) SQLite database with a fresh engine per run, then prove: no concurrent operations on one session, a failing source is never silently [] (name and exception class are logged, recorded
internally, and the other sources survive), and the first invocation on a cold pool behaves like later ones. No provider call, no network.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.db.models_legacy as legacy  # registers NewsArticle on the shared Base
from app.db.base import Base
from app.db.models.event import Event, GovernmentPolicy
from app.services.ai_search import evidence as ev_mod
from app.services.ai_search import retrieval as RT
from app.services.ai_search import evidence_sufficiency as suff_mod

NOW = datetime.now(timezone.utc)
QUERY = "What is the outlook for the IT services sector?"
ENTITIES = {"companies": [], "sectors": ["it"], "policies": []}


async def make_db(tmp_path, name):
    """A brand-new engine (so a cold pool) over a temp SQLite file seeded with IT events, news and a policy."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / (name + '.db')}", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        for i in range(3):
            s.add(Event(id=f"ev{i}", title=f"Infosys TCS software demand headline number {i} cloud", summary="software exporters", source="rss", event_date=NOW - timedelta(days=i + 1),
                        published_at=NOW - timedelta(days=i + 1), impact_score=5.0, companies="[]", sectors="[]"))
        for i in range(2):
            s.add(legacy.NewsArticle(id=f"nw{i}", headline=f"Infosys TCS software outlook news number {i}", summary="software exporters", source="ET", published_at="2h ago", companies=[], impact_score=5.0))
        s.add(GovernmentPolicy(external_id="ext-1", title="RBI policy note", summary="rbi", ministry="Finance"))
        await s.commit()
    await engine.dispose()                      # drop the seeding connection: the next use of this engine is a genuine cold-pool first use
    return engine, factory


def stub_non_db_sources(monkeypatch):
    """Everything collect() reads that is not one of the three DB lookups under test is made inert and offline."""
    async def boom(*a, **k):
        raise RuntimeError("offline")

    async def no_live_news(limit=20):
        return []

    async def no_clustering(db, bundle):
        bundle.development_count = 0

    monkeypatch.setattr(RT, "get_live_news", no_live_news)
    monkeypatch.setattr(ev_mod, "_fetch_valuation_sync", lambda syms: {})
    monkeypatch.setattr(ev_mod, "_fetch_vix_sync", lambda: None)
    monkeypatch.setattr(ev_mod, "_apply_clustering", no_clustering)
    monkeypatch.setattr(ev_mod.cache_mod, "component", lambda kind, sig, factory: factory())
    import app.services.intelligence.engine as eng
    import app.services.historical_memory_service as hist
    monkeypatch.setattr(eng, "get_intelligence_state", boom)
    monkeypatch.setattr(hist, "find_similar_events", boom)


# ── the root cause, reproduced rather than mocked ───────────────────────────────────────────────────────────────────────────────

def test_two_concurrent_operations_on_one_session_of_a_cold_pool_fail_exactly_as_in_production(tmp_path):
    async def go():
        engine, factory = await make_db(tmp_path, "repro")
        await engine.dispose()                                    # a cold pool again, as on the first request after a process start
        async with factory() as s:
            return await asyncio.gather(s.execute(text("select 1")), s.execute(text("select 1")), return_exceptions=True)

    results = asyncio.run(go())
    assert any(isinstance(r, InvalidRequestError) for r in results), results       # the swallowed error that silently emptied a source


# ── the fix ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _collect(factory):
    async def go():
        async with factory() as db:
            return await ev_mod.collect(QUERY, {}, ENTITIES, db)
    return asyncio.run(go())


def test_the_first_collect_on_a_cold_pool_returns_the_same_evidence_as_later_ones(tmp_path, monkeypatch):
    stub_non_db_sources(monkeypatch)
    runs = []
    for k in range(3):                                            # a fresh engine each time: every invocation is a cold-pool first use
        engine, factory = asyncio.run(make_db(tmp_path, f"cold{k}"))
        b = _collect(factory)
        runs.append((sorted(e["id"] for e in b.events), [n.get("id") for n in b.news], len(b.policies), dict(b.retrieval_failures)))
        asyncio.run(engine.dispose())
    assert runs[0] == runs[1] == runs[2]
    assert runs[0][0] and runs[0][1] and runs[0][3] == {}         # events AND news found on the very first call (whichever lookup lost the old race), no source failed


def test_the_retrieval_lookups_never_overlap_on_the_shared_session(monkeypatch):
    stub_non_db_sources(monkeypatch)
    state = {"in_flight": 0, "max": 0, "order": []}

    def tracked(name, rows):
        async def fn(*a, **k):
            state["in_flight"] += 1
            state["max"] = max(state["max"], state["in_flight"])
            state["order"].append(name)
            await asyncio.sleep(0.01)
            state["in_flight"] -= 1
            return rows
        return fn

    monkeypatch.setattr(ev_mod, "_search_events", tracked("events", []))
    monkeypatch.setattr(ev_mod, "_search_news", tracked("news", []))
    monkeypatch.setattr(ev_mod, "_search_policies", tracked("policies", []))
    entities = {"companies": [], "sectors": ["it"], "policies": ["rbi"]}
    asyncio.run(ev_mod.collect(QUERY, {}, entities, db=None))
    assert state["max"] == 1 and state["order"] == ["events", "news", "policies"]


# ── the partial-failure contract ───────────────────────────────────────────────────────────────────────────────────────────────

def _failing_news_collect(monkeypatch, tmp_path):
    stub_non_db_sources(monkeypatch)

    async def boom_news(*a, **k):
        raise RuntimeError("secret query text that must not be logged: " + QUERY)

    monkeypatch.setattr(ev_mod, "_search_news", boom_news)
    logged = []
    monkeypatch.setattr(ev_mod.log, "warning", lambda event, **kw: logged.append((event, kw)))
    engine, factory = asyncio.run(make_db(tmp_path, "partial"))
    b = _collect(factory)
    asyncio.run(engine.dispose())
    return b, logged


def test_a_failing_source_keeps_the_other_sources_and_is_recorded_not_silently_empty(monkeypatch, tmp_path):
    b, _ = _failing_news_collect(monkeypatch, tmp_path)
    assert b.events and b.news == []                                              # events retained, news empty
    assert b.retrieval_failures == {"news": "RuntimeError"}                       # ...and the emptiness is explained as a FAILURE
    assert b.filter_report["retrieval_failures"] == {"news": "RuntimeError"}      # visible in the internal diagnostics too


def test_a_genuinely_empty_source_is_not_reported_as_a_failure(monkeypatch, tmp_path):
    stub_non_db_sources(monkeypatch)

    async def empty_news(*a, **k):
        return []

    monkeypatch.setattr(ev_mod, "_search_news", empty_news)
    engine, factory = asyncio.run(make_db(tmp_path, "empty"))
    b = _collect(factory)
    asyncio.run(engine.dispose())
    assert b.news == [] and b.retrieval_failures == {} and b.filter_report["retrieval_failures"] == {}


def test_the_failure_log_carries_the_source_name_and_exception_class_only(monkeypatch, tmp_path):
    _b, logged = _failing_news_collect(monkeypatch, tmp_path)
    events = [(e, kw) for e, kw in logged if e == "ai_search_v3.evidence_source_failed"]
    assert events == [("ai_search_v3.evidence_source_failed", {"source": "news", "error_class": "RuntimeError"})]
    assert "secret" not in repr(logged) and QUERY not in repr(logged)


def test_every_source_failing_is_recorded_for_each_source(monkeypatch):
    stub_non_db_sources(monkeypatch)

    async def boom(*a, **k):
        raise ValueError("x")

    for name in ("_search_events", "_search_news", "_search_policies"):
        monkeypatch.setattr(ev_mod, name, boom)
    monkeypatch.setattr(ev_mod.log, "warning", lambda *a, **k: None)
    b = asyncio.run(ev_mod.collect(QUERY, {}, {"companies": [], "sectors": ["it"], "policies": ["rbi"]}, db=None))
    assert b.retrieval_failures == {"events": "ValueError", "news": "ValueError", "policies": "ValueError"}
    assert b.events == b.news == b.policies == []


def test_a_source_failure_does_not_weaken_gate_a(monkeypatch, tmp_path):
    """A failed source leaves less evidence; Gate A judges the evidence that exists exactly as before. The failure flag never changes the sufficiency decision."""
    b, _ = _failing_news_collect(monkeypatch, tmp_path)
    flagged = suff_mod.assess(QUERY, {}, ENTITIES, b, [])
    b.retrieval_failures = {}
    unflagged = suff_mod.assess(QUERY, {}, ENTITIES, b, [])
    assert flagged == unflagged


# ── the same defect in the pairwise decision engine ──────────────────────────────────────────────────────────────────────────────

def test_the_pairwise_decision_engine_lookups_do_not_share_a_session_concurrently():
    src = open(ev_mod.__file__.replace("evidence.py", "pipeline.py"), encoding="utf-8").read()
    assert "asyncio.gather(_opp_for(" not in src                                  # both lookups share one AsyncSession: sequential since Step 3.4G.3
    assert "_opp_a = await _opp_for(_sym_a)" in src and "_opp_b = await _opp_for(_sym_b)" in src
