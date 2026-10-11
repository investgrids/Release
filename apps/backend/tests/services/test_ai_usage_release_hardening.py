"""Release hardening for the AI usage instrumentation: the AI Search answer contract is untouched, telemetry faults can never reach an AI request, nothing sensitive is stored or
reported, the admin report is authenticated, and its queries are bounded. Fake HTTP + temporary SQLite; no network."""
from __future__ import annotations

import copy
import json
import time
from datetime import datetime, timezone

import pytest
from sqlalchemy import event, insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.db.models_legacy  # noqa: F401
import app.db.session as session_mod
import app.services.ai_service as ai
import app.services.ai_usage as U
from app.db.base import Base
from app.db.models.ai_usage import AISearchRequestLog, AIUsageAttempt, AIUsageDaily
from tests.services.test_ai_usage_instrumentation import FakeResp, clean_state, fake_http, ok, patch_impl  # noqa: F401  (shared fixtures/helpers)

SECRET_QUESTION = "ZZ-PRIVATE-QUESTION-should-the-user-sell-all-his-ZZ"
SECRET_KEY = "ZZ-SECRET-API-KEY-12345-ZZ"


@pytest.fixture
async def db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'h.db'}", connect_args={"check_same_thread": False})
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(session_mod, "AsyncSessionLocal", factory)
    yield factory
    await engine.dispose()


# ── AI Search V2 contract: the wrapper passes every stage and payload through untouched ───────────────────────────

async def _drain(gen):
    return [item async for item in gen]


@pytest.mark.asyncio
async def test_wrapper_yields_exactly_what_the_pipeline_yields(monkeypatch):
    payload = {"query": "q", "schema_version": "v3.0", "specialist": "company", "answer": {"summary": "s"}, "citations": [{"id": 1}], "degraded_reason": None}
    snapshot = copy.deepcopy(payload)
    steps = [("intent", None), ("entities", None), ("reasoning", None), ("finalizing", payload)]
    import app.services.ai_search.pipeline as P
    patch_impl(monkeypatch, steps)
    wrapped = await _drain(P._run_v3_steps("q", None))
    assert [(s, l) for s, l, _ in wrapped] == [(s, s) for s, _ in steps]                 # same stages, same order
    assert wrapped[-1][2] is payload and payload == snapshot                              # the very same object, not copied, not mutated
    assert all(p is None for _, _, p in wrapped[:-1])


@pytest.mark.asyncio
async def test_pipeline_exceptions_propagate_unchanged(monkeypatch):
    import app.services.ai_search.pipeline as P
    class Boom(RuntimeError):
        pass
    patch_impl(monkeypatch, [("intent", None)], raises=Boom("original"))
    with pytest.raises(Boom, match="original"):
        await _drain(P._run_v3_steps("q", None))


# ── fault injection: telemetry can never interrupt an AI request ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ai_call_survives_every_telemetry_fault(monkeypatch):
    m = ai._GROQ_HIGH[0]
    fake_http(monkeypatch, {m: ok("answer", {"prompt_tokens": 5, "completion_tokens": 5})})
    monkeypatch.setattr(U.uuid, "uuid4", lambda: (_ for _ in ()).throw(RuntimeError("uuid broke")))        # id generation fails
    monkeypatch.setattr(U, "_enqueue", lambda row: (_ for _ in ()).throw(RuntimeError("queue broke")))       # the queue fails
    monkeypatch.setattr(U, "_caller_label", lambda: (_ for _ in ()).throw(RuntimeError("frame walk broke")))
    assert await ai._call_provider(ai._GROQ_URL, "k", m, "p", "", 10) == "answer"
    assert await ai._call_with_fallback("p", "", 10, priority="background") == "answer"


@pytest.mark.asyncio
async def test_search_request_survives_a_broken_recorder(monkeypatch):
    import app.services.ai_search.pipeline as P
    patch_impl(monkeypatch, [("reasoning", None), ("finalizing", {"specialist": "company"})])
    monkeypatch.setattr(U, "_enqueue_search", lambda row: (_ for _ in ()).throw(RuntimeError("recorder broke")))
    out = await _drain(P._run_v3_steps("q", None))
    assert out[-1][2] == {"specialist": "company"}                                        # the answer was delivered regardless


@pytest.mark.asyncio
async def test_saturated_queue_plus_dead_database_never_slows_or_breaks_requests(db, monkeypatch):
    monkeypatch.setattr(session_mod, "AsyncSessionLocal", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    m = ai._GROQ_HIGH[0]
    fake_http(monkeypatch, {m: ok("a", {"prompt_tokens": 1, "completion_tokens": 1})})
    t0 = time.perf_counter()
    for _ in range(U.QUEUE_MAX + 300):                                                    # saturate the queue while the database is down
        assert await ai._call_provider(ai._GROQ_URL, "k", m, "p", "", 10) == "a"
    assert time.perf_counter() - t0 < 10                                                  # request path never waits on the database
    assert len(U._queue) <= U.QUEUE_MAX and U._stats["dropped"] > 0                       # bounded; drops are counted, not silent


# ── nothing sensitive is stored or reported ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_prompt_question_or_key_reaches_any_table_or_report(db, monkeypatch):
    monkeypatch.setattr(ai.settings, "groq_api_key", SECRET_KEY, raising=False)
    m = ai._GROQ_HIGH[0]
    fake_http(monkeypatch, {m: ok("answer text SHOULD-NOT-BE-STORED", {"prompt_tokens": 50, "completion_tokens": 20})})
    import app.services.ai_search.pipeline as P

    async def impl(query, dbs, session_context=None):
        yield "reasoning", "reasoning", None
        await ai._call_with_fallback(f"Question: {query}", f"system uses {SECRET_KEY}", 100, priority="interactive")
        yield "finalizing", "finalizing", {"specialist": "company", "answer": {"summary": SECRET_QUESTION}}
    monkeypatch.setattr(P, "_run_v3_steps_impl", impl)
    U.mark_api_request()
    await _drain(P._run_v3_steps(SECRET_QUESTION, None))
    assert await U.flush_pending() >= 2
    async with db() as s:
        await U.rollup_and_prune(s)
        rep = await U.usage_report(s, hours=24)
        everything = []
        for model in (AIUsageAttempt, AISearchRequestLog, AIUsageDaily):
            for row in (await s.execute(model.__table__.select())).all():
                everything.append(repr(tuple(row)))
    blob = json.dumps(rep, default=str) + "|".join(everything)
    for secret in (SECRET_QUESTION, SECRET_KEY, "SHOULD-NOT-BE-STORED", "Question:"):
        assert secret not in blob, f"leaked: {secret}"
    assert rep["ai_search"]["user_requests"]["requests"] == 1                              # the request itself is recorded (counts only)


# ── admin endpoint: authenticated, clamped, bounded ───────────────────────────────────────────────────────────────

@pytest.fixture
def client(db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.db.session import get_db
    from app.main import app

    async def _db():
        async with db() as s:
            yield s
    inner = getattr(app, "app", app)              # app.main wraps the FastAPI app in ProxyHeadersMiddleware; overrides live on the inner app
    inner.dependency_overrides[get_db] = _db
    yield TestClient(app)
    inner.dependency_overrides.pop(get_db, None)


def test_admin_report_requires_the_admin_key(client, monkeypatch):
    monkeypatch.setattr("app.core.security.settings.admin_api_key", "the-admin-key", raising=False)
    assert client.get("/api/admin/ai-usage").status_code == 401
    assert client.get("/api/admin/ai-usage", headers={"X-Admin-Key": "wrong"}).status_code == 401
    r = client.get("/api/admin/ai-usage", headers={"X-Admin-Key": "the-admin-key"})
    assert r.status_code == 200 and {"ai_search", "features", "models", "gaps", "recorder"} <= set(r.json())
    monkeypatch.setattr("app.core.security.settings.admin_api_key", "", raising=False)
    assert client.get("/api/admin/ai-usage", headers={"X-Admin-Key": "anything"}).status_code == 503      # no key configured = endpoint disabled, not open


def test_admin_report_window_is_clamped(client, monkeypatch):
    monkeypatch.setattr("app.core.security.settings.admin_api_key", "k", raising=False)
    h = {"X-Admin-Key": "k"}
    assert client.get("/api/admin/ai-usage?hours=100000", headers=h).json()["window_hours"] == U.MAX_REPORT_HOURS
    assert client.get("/api/admin/ai-usage?hours=0", headers=h).json()["window_hours"] == 1


@pytest.mark.asyncio
async def test_report_query_count_does_not_grow_with_row_count(db):
    engine_holder = {}

    async def count_queries(n_rows: int) -> int:
        async with db() as s:
            await s.execute(AIUsageAttempt.__table__.delete())
            await s.commit()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            await s.execute(insert(AIUsageAttempt), [{"ts": now, "operation": f"op{i % 5}", "call_id": f"c{i}", "attempt_no": 1, "provider": "groq", "model": "m", "outcome": "success",
                                                      "usage_source": "provider", "input_tokens": 1, "output_tokens": 1, "n": 1} for i in range(n_rows)])
            await s.commit()
        seen = []
        async with db() as s:
            sync_engine = (await s.connection()).sync_connection.engine
            def _on(conn, cursor, statement, *a):
                seen.append(statement)
            event.listen(sync_engine, "before_cursor_execute", _on)
            try:
                await U.usage_report(s, hours=24)
            finally:
                event.remove(sync_engine, "before_cursor_execute", _on)
        return len(seen)

    small, large = await count_queries(50), await count_queries(5000)
    assert small == large and large <= 8                                                   # constant number of aggregate queries, not one per row


# ── cooldown skips made by the chain itself are counted (the main skip path) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_chain_level_cooldown_skips_are_counted_and_no_http_call_is_made(monkeypatch):
    calls = fake_http(monkeypatch, {})
    for m in list(ai._GROQ_HIGH) + list(ai._GROQ_FAST):                       # the test fixture leaves only the Groq tier configured
        ai._mark_exhausted("groq", m, "rate_limit")
    with U.operation("event_enrichment", track=True):
        assert await ai._call_with_fallback("p", "", 10, priority="background") == ""
        assert U.cooldown_only() is True                                       # nothing was really attempted; everything was a cooldown skip
    assert calls == [] and not rows_in_queue()
    assert sum(n for (op, prov, model, outcome), n in U._skips.items() if outcome == "skipped_cooldown" and op == "event_enrichment") >= 1


def rows_in_queue():
    return list(U._queue)
