"""AI usage instrumentation: honest token capture, per-feature tagging, one row per AI Search request, bounded queue, rollup/prune, and no prompt or question text stored.
Fake HTTP layer + temporary SQLite database; no network, no provider call."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.db.models_legacy  # noqa: F401  (registers the shared Base's tables)
import app.db.session as session_mod
import app.services.ai_service as ai
import app.services.ai_usage as U
from app.db.base import Base
from app.db.models.ai_usage import AISearchRequestLog, AIUsageAttempt, AIUsageDaily

SECRET_PROMPT = "ZZ-SECRET-USER-QUESTION-ABOUT-MY-PORTFOLIO-ZZ"


class FakeResp:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code, self._d, self.headers = status, data if data is not None else {}, headers or {}

    def json(self):
        return self._d

    def raise_for_status(self):
        pass


def ok(content="hello", usage=None):
    d = {"choices": [{"message": {"content": content}}]}
    if usage is not None:
        d["usage"] = usage
    return FakeResp(200, d)


def fake_http(monkeypatch, script):
    """script: {model: FakeResp | Exception | list of them (consumed in order)}"""
    calls = []

    class Client:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            calls.append(json["model"])
            item = script[json["model"]]
            if isinstance(item, list):
                item = item.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    monkeypatch.setattr(ai.httpx, "AsyncClient", Client)
    return calls


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    ai._EXHAUSTED.clear()
    U._queue.clear(); U._search_queue.clear(); U._skips.clear()
    for k in U._stats:
        U._stats[k] = 0
    monkeypatch.setattr(ai.settings, "groq_api_key", "test-key", raising=False)
    for name in ("openrouter_api_key", "mistral_api_key", "gemini_api_key", "requesty_api_key", "nvidia_api_key"):
        monkeypatch.setattr(ai.settings, name, "", raising=False)
    yield
    ai._EXHAUSTED.clear()


@pytest.fixture
async def db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'u.db'}", connect_args={"check_same_thread": False})
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "AsyncSessionLocal", factory)
    yield factory
    await engine.dispose()


def rows():
    return list(U._queue)


# ── tokens: provider-reported or unknown, never zero ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provider_reported_tokens_are_recorded_and_missing_usage_is_unknown_not_zero(monkeypatch):
    m1, m2 = ai._GROQ_HIGH[0], ai._GROQ_HIGH[1]
    fake_http(monkeypatch, {m1: ok("a", {"prompt_tokens": 120, "completion_tokens": 30}), m2: ok("b")})
    await ai._call_provider(ai._GROQ_URL, "k", m1, SECRET_PROMPT, "sys", 50)
    await ai._call_provider(ai._GROQ_URL, "k", m2, SECRET_PROMPT, "sys", 50)
    a, b = rows()
    assert (a["input_tokens"], a["output_tokens"], a["usage_source"], a["outcome"]) == (120, 30, "provider", "success")
    assert (b["input_tokens"], b["output_tokens"], b["usage_source"], b["outcome"]) == (None, None, "unknown", "success")   # unknown, NOT 0


@pytest.mark.asyncio
async def test_failure_outcomes_are_classified(monkeypatch):
    m = [f"fake/model-{i}" for i in range(5)]
    fake_http(monkeypatch, {m[0]: FakeResp(429), m[1]: FakeResp(402), m[2]: FakeResp(503), m[3]: FakeResp(401), m[4]: ai.httpx.ReadTimeout("slow")})
    for model in m:
        await ai._call_provider(ai._GROQ_URL, "k", model, "p", "", 10)
    assert [r["outcome"] for r in rows()] == ["rate_limited", "billing", "server_error", "auth_error", "timeout"]
    assert rows()[0]["http_status"] == 429 and rows()[4]["http_status"] is None


@pytest.mark.asyncio
async def test_cooling_down_models_are_counted_as_skips_not_http_attempts(monkeypatch):
    m = ai._GROQ_HIGH[0]
    calls = fake_http(monkeypatch, {m: FakeResp(429)})
    await ai._call_provider(ai._GROQ_URL, "k", m, "p", "", 10)          # real attempt, marks the model exhausted
    await ai._call_provider(ai._GROQ_URL, "k", m, "p", "", 10)          # skipped by the cooldown: no HTTP call
    await ai._call_provider(ai._GROQ_URL, "k", m, "p", "", 10)
    assert calls == [m] and len(rows()) == 1
    assert sum(U._skips.values()) == 2


# ── feature tags and retry numbering ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_operation_tag_and_attempt_numbers_across_a_fallback_chain(monkeypatch):
    m1, m2 = ai._GROQ_HIGH[0], ai._GROQ_HIGH[1]
    fake_http(monkeypatch, {m1: FakeResp(429), m2: ok("done", {"prompt_tokens": 10, "completion_tokens": 5})})
    with U.operation("article_generation"):
        text = await ai._call_with_fallback(SECRET_PROMPT, "sys", 100, priority="background")
    assert text == "done"
    r = rows()
    assert [x["operation"] for x in r] == ["article_generation", "article_generation"]
    assert [x["attempt_no"] for x in r] == [1, 2] and r[0]["call_id"] == r[1]["call_id"]
    assert [x["outcome"] for x in r] == ["rate_limited", "success"]


@pytest.mark.asyncio
async def test_untagged_callers_are_never_invisible(monkeypatch):
    m = ai._GROQ_HIGH[0]
    fake_http(monkeypatch, {m: ok("x")})
    await ai._call_with_fallback("p", "", 10, priority="background")
    assert rows()[0]["operation"].startswith("other:")


# ── AI Search: exactly one request row ─────────────────────────────────────────────────────────────────────────

async def _consume(gen):
    out = []
    async for item in gen:
        out.append(item)
    return out


def patch_impl(monkeypatch, steps, call_llm=False, raises=None):
    import app.services.ai_search.pipeline as P

    async def impl(query, db, session_context=None):
        for stage, payload in steps:
            if stage == "reasoning" and call_llm:
                await ai._call_with_fallback(query, "s", 100, priority="interactive")
            yield stage, stage, payload
        if raises:
            raise raises

    monkeypatch.setattr(P, "_run_v3_steps_impl", impl)
    return P


@pytest.mark.asyncio
async def test_one_search_request_row_with_llm_calls_tokens_and_no_question_text(monkeypatch):
    m = ai._GROQ_HIGH[0]
    fake_http(monkeypatch, {m: ok("a", {"prompt_tokens": 1000, "completion_tokens": 400})})
    P = patch_impl(monkeypatch, [("intent", None), ("reasoning", None), ("finalizing", {"specialist": "company", "query": SECRET_PROMPT})], call_llm=True)
    U.mark_api_request()
    await _consume(P._run_v3_steps(SECRET_PROMPT, None))
    (req,) = list(U._search_queue)
    assert (req["origin"], req["outcome"], req["specialist"], req["cache_hit"]) == ("api", "answered", "company", False)
    assert (req["llm_calls"], req["llm_attempts"], req["input_tokens"], req["output_tokens"]) == (1, 1, 1000, 400)
    assert req["query_len"] == len(SECRET_PROMPT)
    assert rows()[0]["request_id"] == req["request_id"] and rows()[0]["operation"] == "ai_search"
    assert SECRET_PROMPT not in repr(req) and SECRET_PROMPT not in repr(rows())


@pytest.mark.asyncio
async def test_cache_hit_degraded_error_and_abandoned_requests(monkeypatch):
    P = patch_impl(monkeypatch, [("finalizing", {"specialist": "sector"})])
    await _consume(P._run_v3_steps("q", None))
    P = patch_impl(monkeypatch, [("reasoning", None), ("finalizing", {"degraded_reason": "capacity"})])
    await _consume(P._run_v3_steps("q", None))
    P = patch_impl(monkeypatch, [("reasoning", None)], raises=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await _consume(P._run_v3_steps("q", None))
    P = patch_impl(monkeypatch, [("reasoning", None), ("finalizing", {})])
    gen = P._run_v3_steps("q", None)
    await gen.__anext__()
    await gen.aclose()                                                    # client went away before the answer
    reqs = list(U._search_queue)
    assert [(r["outcome"], r["cache_hit"]) for r in reqs[:2]] == [("answered", True), ("degraded", False)]
    assert reqs[1]["degraded_reason"] == "capacity"
    assert (reqs[2]["outcome"], reqs[2]["degraded_reason"]) == ("error", "RuntimeError")
    assert (reqs[3]["outcome"], reqs[3]["degraded_reason"]) == ("error", "GeneratorExit")
    assert len(reqs) == 4                                                 # exactly one row each, never two


# ── bounded queue, flush, rollup, prune, report ───────────────────────────────────────────────────────────────

def test_queue_is_bounded_and_drops_are_counted():
    for i in range(U.QUEUE_MAX + 10):
        U._queue.append({"x": i}) if False else U._enqueue({"ts": datetime.now(timezone.utc), "operation": "o", "call_id": None, "request_id": None, "attempt_no": 1, "provider": "p", "model": "m",
                                                          "outcome": "success", "http_status": 200, "latency_ms": 1, "input_tokens": None, "output_tokens": None, "usage_source": "unknown", "n": 1})
    assert len(U._queue) == U.QUEUE_MAX and U._stats["dropped"] == 10


@pytest.mark.asyncio
async def test_flush_writes_rows_and_a_db_failure_never_raises(db, monkeypatch):
    m = ai._GROQ_HIGH[0]
    fake_http(monkeypatch, {m: ok("a", {"prompt_tokens": 7, "completion_tokens": 3})})
    with U.operation("event_enrichment"):
        await ai._call_provider(ai._GROQ_URL, "k", m, SECRET_PROMPT, "sys", 10)
    assert await U.flush_pending() == 1
    async with db() as s:
        r = (await s.execute(select(AIUsageAttempt))).scalars().one()
        assert (r.operation, r.input_tokens, r.output_tokens, r.usage_source) == ("event_enrichment", 7, 3, "provider")
        assert SECRET_PROMPT not in repr([getattr(r, c.name) for c in AIUsageAttempt.__table__.columns])
    async def broken(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(session_mod, "AsyncSessionLocal", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    U._enqueue({"ts": datetime.now(timezone.utc), "operation": "o", "call_id": None, "request_id": None, "attempt_no": 1, "provider": "p", "model": "m", "outcome": "success", "http_status": 200,
                "latency_ms": 1, "input_tokens": None, "output_tokens": None, "usage_source": "unknown", "n": 1})
    assert await U.flush_pending() == 0 and U._stats["flush_errors"] == 1
    assert len(U._queue) == 1 and U._stats["dropped"] == 0                  # a transient failure keeps the row for the next flush, it is not lost


@pytest.mark.asyncio
async def test_persistent_flush_failure_eventually_drops_instead_of_growing_forever(db, monkeypatch):
    monkeypatch.setattr(session_mod, "AsyncSessionLocal", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    monkeypatch.setattr(U, "_consecutive_failures", 0)
    U._enqueue({"ts": datetime.now(timezone.utc), "operation": "o", "call_id": None, "request_id": None, "attempt_no": 1, "provider": "p", "model": "m", "outcome": "success", "http_status": 200,
                "latency_ms": 1, "input_tokens": None, "output_tokens": None, "usage_source": "unknown", "n": 1})
    for _ in range(U._MAX_CONSECUTIVE_FLUSH_FAILURES + 1):
        await U.flush_pending()
    assert len(U._queue) == 0 and U._stats["dropped"] == 1


@pytest.mark.asyncio
async def test_rollup_prunes_old_rows_into_daily_totals_idempotently(db):
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=U.ATTEMPT_RETENTION_DAYS + 3)).replace(tzinfo=None)
    new = (now - timedelta(hours=2)).replace(tzinfo=None)
    def a(ts, outcome, i=None, o=None):
        return AIUsageAttempt(ts=ts, operation="triage", provider="groq", model="m", outcome=outcome, usage_source="provider" if i is not None else "unknown", input_tokens=i, output_tokens=o, latency_ms=100, n=1)
    async with db() as s:
        s.add_all([a(old, "success", 100, 20), a(old, "success", 50, 10), a(old, "success"), a(old, "rate_limited"), a(new, "success", 5, 5)])
        await s.commit()
    async with db() as s:
        res = await U.rollup_and_prune(s)
    assert res["deleted_raw"] == 4
    async with db() as s:
        assert (await s.execute(select(func.count()).select_from(AIUsageAttempt))).scalar_one() == 1                          # only the recent row remains
        daily = {r.outcome: r for r in (await s.execute(select(AIUsageDaily))).scalars().all()}
        assert (daily["success"].attempts, daily["success"].input_tokens, daily["success"].output_tokens, daily["success"].attempts_with_usage) == (3, 150, 30, 2)   # the unknown-usage attempt counts as an attempt, adds no tokens
        assert daily["rate_limited"].attempts == 1
    async with db() as s:
        again = await U.rollup_and_prune(s)
    assert again["deleted_raw"] == 0                                                                                            # nothing left to roll up: totals are not double counted
    async with db() as s:
        assert sum(r.attempts for r in (await s.execute(select(AIUsageDaily))).scalars().all()) == 4


@pytest.mark.asyncio
async def test_hard_row_cap_rolls_up_the_oldest_rows(db, monkeypatch):
    monkeypatch.setattr(U, "MAX_RAW_ROWS", 5)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with db() as s:
        s.add_all([AIUsageAttempt(ts=now - timedelta(minutes=i), operation="o", provider="p", model="m", outcome="success", usage_source="unknown", n=1) for i in range(12)])
        await s.commit()
    async with db() as s:
        res = await U.rollup_and_prune(s)
    assert res["deleted_by_cap"] == 7
    async with db() as s:
        assert (await s.execute(select(func.count()).select_from(AIUsageAttempt))).scalar_one() == 5
        assert sum(r.attempts for r in (await s.execute(select(AIUsageDaily))).scalars().all()) == 7


@pytest.mark.asyncio
async def test_report_separates_known_and_unknown_tokens_and_never_prices_the_unknown(db):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with db() as s:
        s.add_all([
            AIUsageAttempt(ts=now, operation="article_generation", call_id="c1", provider="groq", model="openai/gpt-oss-120b", outcome="rate_limited", usage_source="unknown", n=1),
            AIUsageAttempt(ts=now, operation="article_generation", call_id="c1", provider="groq", model="openai/gpt-oss-20b", outcome="success", usage_source="provider", input_tokens=3000, output_tokens=2000, n=1),
            AIUsageAttempt(ts=now, operation="triage", call_id="c2", provider="groq", model="qwen/qwen3.8-27b", outcome="success", usage_source="unknown", n=1),
            AIUsageAttempt(ts=now, operation="triage", call_id="c3", provider="somepaid", model="big", outcome="success", usage_source="provider", input_tokens=10, output_tokens=10, n=1),
            AIUsageAttempt(ts=now, operation="triage", provider="groq", model="qwen/qwen3.8-27b", outcome="skipped_cooldown", usage_source="unknown", n=9),
            AISearchRequestLog(ts=now, request_id="r1", origin="api", outcome="answered", cache_hit=False, latency_ms=900, llm_calls=1, llm_attempts=2, input_tokens=500, output_tokens=200, tokens_unknown_attempts=0),
            AISearchRequestLog(ts=now, request_id="r2", origin="api", outcome="degraded", degraded_reason="capacity", llm_calls=1, llm_attempts=4, tokens_unknown_attempts=0),
            AISearchRequestLog(ts=now, request_id="r3", origin="internal", outcome="answered", llm_calls=1, llm_attempts=1, tokens_unknown_attempts=1),
        ])
        await s.commit()
    async with db() as s:
        rep = await U.usage_report(s, hours=24)
    art, tri = rep["features"]["article_generation"], rep["features"]["triage"]
    assert (art["calls"], art["calls_succeeded"], art["attempts"], art["successes"]) == (1, 1, 2, 1)
    assert (art["input_tokens"], art["output_tokens"], art["attempts_with_usage"]) == (3000, 2000, 1)
    assert art["cost_usd"] == 0.0 and art["cost_covered_attempts"] == 1                                         # free-tier groq: priced at 0 with a basis, only for attempts with known tokens
    assert tri["success_attempts_unknown_usage"] == 1 and tri["skipped_cooldown"] == 9
    assert tri["cost_unpriced_attempts"] == 1                                                                   # the unknown-price paid model is excluded from cost, not guessed
    us = rep["ai_search"]["user_requests"]
    assert (us["requests"], us["answered"], us["degraded"], us["llm_calls"], us["llm_attempts"]) == (2, 1, 1, 2, 6)
    assert us["degraded_reasons"] == {"capacity": 1} and rep["ai_search"]["internal_pipeline_calls"]["requests"] == 1
    assert rep["ai_search"]["internal_pipeline_calls"]["requests_with_unknown_tokens"] == 1
