"""
Step 3.4H.2b: the request-scoped latency contract. One ABSOLUTE deadline per interactive AI Search request, shared by the classifier, retrieval, the provider fallback chain and finalization.
Model-free: provider calls are stubbed (or a local 127.0.0.1 stub HTTP server drives the real `_call_provider`). Budgets here are small so the tests run in seconds; they are NOT the production values.
"""
from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest

from app.services import ai_service as S
from app.services import request_deadline as RD
from app.services.ai_search import market_pulse as mp_mod
from app.services.ai_search import pipeline as P
from app.services.ai_search.response_finalize import finalize_v3_response
from tests.services.test_ai_search_fail_closed import bundle, good_generation, pipe, tcs_bundle  # noqa: F401


# ── provider chain fixture: groq only, three models, real chain code, stubbed provider calls ──────────────────────────────────────

@pytest.fixture
def chain(monkeypatch):
    S._EXHAUSTED.clear()
    for k in ("openrouter_api_key", "mistral_api_key", "gemini_api_key"):
        monkeypatch.setattr(S.settings, k, "")
    monkeypatch.setattr(S.settings, "groq_api_key", "k")
    monkeypatch.setattr(S, "_GROQ_HIGH", ["m1", "m2"])
    monkeypatch.setattr(S, "_GROQ_FAST", ["m3"])
    rec = {"calls": [], "behaviour": {}}

    async def fake_provider(url, key, model, prompt, system="", max_tokens=200, extra_headers=None, failure_log=None):
        rec["calls"].append((model, round(time.monotonic() - rec.get("t0", time.monotonic()), 2)))
        b = rec["behaviour"].get(model, "ok")
        if b == "hang":
            await asyncio.sleep(60)
        return "answer-from-" + model if b == "ok" else ""

    monkeypatch.setattr(S, "_call_provider", fake_provider)
    yield rec
    S._EXHAUSTED.clear()


def run(coro):
    return asyncio.run(coro)


def timed(rec, total, reserve=0.3, min_attempt=0.5, cap=1.0, logs=None):
    async def go():
        with RD.scope(total=total, reserve=reserve, min_attempt=min_attempt, attempt_cap=cap):
            rec["t0"] = time.monotonic()
            t = time.monotonic()
            out = await S._call_with_fallback("p", "s", 50, failure_log=logs, priority="interactive")
            return out, time.monotonic() - t
    return run(go())


# ── no deadline: byte-identical behaviour ────────────────────────────────────────────────────────────────────────────────────────

def test_without_a_request_deadline_nothing_is_active_and_callers_see_the_old_behaviour(chain):
    assert RD.usable() is None and RD.remaining() is None and RD.active() is False
    chain["behaviour"] = {"m1": "fail", "m2": "ok"}
    out = run(S._call_with_fallback("p", "s", 50, priority="interactive"))
    assert out == "answer-from-m2" and [c[0] for c in chain["calls"]] == ["m1", "m2"]


def test_the_full_chain_order_and_arguments_are_unchanged_with_every_tier_configured(monkeypatch):
    S._EXHAUSTED.clear()
    for k in ("groq_api_key", "openrouter_api_key", "mistral_api_key", "gemini_api_key"):
        monkeypatch.setattr(S.settings, k, "key-" + k)
    seen = []

    async def fake_provider(*args, failure_log=None):
        seen.append(args)
        return ""

    monkeypatch.setattr(S, "_call_provider", fake_provider)
    run(S._call_with_fallback("P", "SYS", 77, priority="interactive"))
    models = [a[2] for a in seen]
    assert models == [*S._GROQ_HIGH, *S._GROQ_FAST, *S._OR_HIGH_QUALITY, *S._MISTRAL_MODELS, *S._GEMINI_MODELS, *S._OR_SMALL]
    for a in seen:
        assert a[3:6] == ("P", "SYS", 77)
        is_or = a[0] == S._OR_URL
        assert (len(a) == 7 and isinstance(a[6], dict)) if is_or else len(a) == 6        # extra headers passed positionally for OpenRouter only, exactly as before
    S._EXHAUSTED.clear()


# ── remaining-budget propagation ─────────────────────────────────────────────────────────────────────────────────────────────

def test_provider_one_hangs_provider_two_gets_only_the_remaining_budget_and_the_request_stays_bounded(chain):
    chain["behaviour"] = {"m1": "hang", "m2": "hang", "m3": "ok"}
    logs: list = []
    out, elapsed = timed(chain, total=2.5, reserve=0.3, min_attempt=0.5, cap=1.5, logs=logs)
    assert out == ""                                                     # fail closed: no answer, no fresh budget for anybody
    assert elapsed < 2.5 - 0.3 + 0.35                                    # the usable window (deadline minus reserve) bounds the whole chain
    starts = dict(chain["calls"])
    assert "m1" in starts and "m2" in starts and "m3" not in starts      # m2 was tried on what remained; m3 never started
    assert starts["m2"] >= 1.4                                           # m1 held the first 1.5 s cap; m2 started after, with less than a full cap left
    assert [l["reason"] for l in logs if l.get("model") in ("m2", "m3", None)] and logs[-1]["reason"] == "deadline"


def test_insufficient_remaining_budget_prevents_another_provider_from_starting(chain):
    chain["behaviour"] = {"m1": "hang", "m2": "ok", "m3": "ok"}
    out, elapsed = timed(chain, total=1.6, reserve=0.3, min_attempt=0.5, cap=1.0)
    assert [c[0] for c in chain["calls"]] == ["m1"] and out == ""        # after m1's 1.0 s only 0.3 s are usable (< 0.5 min): the healthy m2 must not be started
    assert elapsed < 1.4


def test_the_attempt_that_used_its_whole_normal_allowance_is_charged_like_any_provider_timeout(chain):
    chain["behaviour"] = {"m1": "hang", "m2": "ok"}
    out, _ = timed(chain, total=4.0, reserve=0.3, min_attempt=0.5, cap=1.0)
    assert out == "answer-from-m2"
    assert S._is_exhausted("groq", "m1") is True and S._is_exhausted("groq", "m2") is False       # existing health behaviour for a genuine provider timeout


def test_an_attempt_cancelled_early_by_the_request_budget_does_not_poison_provider_health(chain):
    chain["behaviour"] = {"m1": "hang"}
    logs: list = []
    out, elapsed = timed(chain, total=1.2, reserve=0.2, min_attempt=0.5, cap=5.0, logs=logs)       # the budget (1.0 s usable) ends the attempt well before its 5 s normal allowance
    assert out == "" and elapsed < 1.4
    assert S._is_exhausted("groq", "m1") is False                       # our SLA expiring is not the provider's failure
    assert logs[0] == {"model": "m1", "provider": "groq-hq", "reason": "deadline"}
    assert RD.expired() is False                                        # scope has exited; the flag is per request


def test_a_trickling_provider_cannot_escape_the_request_attempt_deadline(monkeypatch):
    """Real HTTP: a server sends one byte every 0.4 s. httpx's 1 s read timeout never fires (it bounds only the gap between bytes); the MarketRipple attempt budget does."""
    S._EXHAUSTED.clear()
    state = {"eof": None}

    async def handle(reader, writer):
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            n = next((int(l.split(b":")[1]) for l in head.split(b"\r\n") if l.lower().startswith(b"content-length:")), 0)
            await reader.readexactly(n)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 100000\r\n\r\n")
            await writer.drain()
            while True:
                if reader.at_eof():
                    state["eof"] = time.monotonic()
                    return
                writer.write(b" ")
                await writer.drain()
                await asyncio.sleep(0.1)
        except (ConnectionError, asyncio.IncompleteReadError):
            state["eof"] = time.monotonic()
        finally:
            writer.close()

    async def go():
        srv = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = srv.sockets[0].getsockname()[1]
        monkeypatch.setattr(S, "_GROQ_URL", f"http://127.0.0.1:{port}/v1")
        monkeypatch.setattr(S.settings, "groq_api_key", "k")
        for k in ("openrouter_api_key", "mistral_api_key", "gemini_api_key"):
            monkeypatch.setattr(S.settings, k, "")
        monkeypatch.setattr(S, "_GROQ_HIGH", ["trickle-model"])
        monkeypatch.setattr(S, "_GROQ_FAST", [])
        monkeypatch.setattr(S, "_HTTP_TIMEOUT", httpx.Timeout(connect=5.0, read=1.0, write=10.0, pool=5.0))
        with RD.scope(total=2.5, reserve=0.3, min_attempt=0.5, attempt_cap=1.5):
            t = time.monotonic()
            out = await S._call_with_fallback("p", "s", 50, priority="interactive")
            elapsed = time.monotonic() - t
        end = time.monotonic()
        await asyncio.sleep(0.3)
        srv.close()
        return out, elapsed, end

    out, elapsed, end = run(go())
    assert out == "" and 1.3 < elapsed < 1.9                             # ended by the 1.5 s attempt budget, not by a never-firing read timeout
    assert state["eof"] is not None and state["eof"] - end < 0.5         # the connection was closed by the cancel
    S._EXHAUSTED.clear()


def test_outer_cancellation_propagates_and_releases_the_tier_slot(chain):
    chain["behaviour"] = {"m1": "hang"}
    limiter = S._TIER_LIMITERS["groq-hq"]

    async def go():
        with RD.scope(total=10, reserve=0.3, min_attempt=0.5, attempt_cap=5.0):
            task = asyncio.ensure_future(S._call_with_fallback("p", "s", 50, priority="interactive"))
            await asyncio.sleep(0.3)
            assert limiter._in_flight == 1
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        return limiter._in_flight

    assert run(go()) == 0                                                # a client disconnect is not swallowed and frees the slot


# ── classifier budget ────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_classifier_that_cannot_answer_in_its_slice_is_not_market_pulse_and_does_not_enlarge_the_specialists_budget(chain, monkeypatch):
    monkeypatch.setattr(mp_mod.settings, "ai_search_classifier_budget_seconds", 1.2)
    chain["behaviour"] = {"m1": "hang", "m2": "hang", "m3": "hang"}

    async def go():
        with RD.scope(total=8.0, reserve=1.0, min_attempt=2.0, attempt_cap=5.0):
            before = RD.usable()
            t = time.monotonic()
            verdict = await mp_mod._classify_market_pulse_llm("how is sentiment today")
            spent = time.monotonic() - t
            after = RD.usable()
            return verdict, spent, before, after

    verdict, spent, before, after = run(go())
    assert verdict is False                                              # same outcome as any classifier failure: normal research route, never a more permissive one
    assert spent < 1.6                                                   # the classifier's own slice (1.2 s), not a provider-cap or chain journey
    assert after <= before - spent + 0.05                                # the specialist's usable budget shrank by what the classifier consumed: no fresh budget
    assert before < 8.0                                                  # and the total never exceeded the one absolute deadline


def test_the_classifier_sub_budget_never_uses_the_finalization_reserve(chain, monkeypatch):
    monkeypatch.setattr(mp_mod.settings, "ai_search_classifier_budget_seconds", 30.0)       # larger than the request
    chain["behaviour"] = {"m1": "hang", "m2": "hang", "m3": "hang"}

    async def go():
        with RD.scope(total=3.0, reserve=1.5, min_attempt=0.3, attempt_cap=5.0):
            t = time.monotonic()
            await mp_mod._classify_market_pulse_llm("q")
            return time.monotonic() - t, RD.remaining()

    spent, remaining = run(go())
    assert spent < 1.7 and remaining >= 1.3                              # about 1.5 s of the 3 s were spendable; the reserve is intact for authorization and assembly


# ── pipeline checkpoints (stubbed specialist/collect, real _run_v3_steps) ─────────────────────────────────────────────────────

def run_with_deadline(query, **scope_kw):
    async def go():
        with RD.scope(**scope_kw):
            raw, was_cached = await P.run_ai_search_v3(query, None)
        return raw, finalize_v3_response(query, raw, x_admin_key=None, was_cached=was_cached)
    return run(go())


def test_retrieval_cut_off_by_the_budget_is_a_retrieval_failure_never_no_evidence(pipe, monkeypatch):
    async def slow_collect(query, intent_data, entities, db):
        await asyncio.sleep(60)
    monkeypatch.setattr(P.evidence_mod, "collect", slow_collect)
    t = time.monotonic()
    raw, res = run_with_deadline("What is happening with TCS lately? (deadline retrieval)", total=3.0, reserve=0.5, min_attempt=1.0, attempt_cap=1.0)
    assert time.monotonic() - t < 2.2                                    # retrieval got 3.0 - 0.5 - 1.0 = 1.5 s
    assert pipe["specialist"] == 0
    assert raw["degraded_reason"] == "retrieval_deadline_exceeded" and raw["_retrieval_failures"] == {"deadline": "TimeoutError"}
    assert res["degraded_reason"] == "retrieval_deadline_exceeded" and "_retrieval_failures" not in res
    av = res["answer_availability"]
    assert av["state"] == "temporarily_unavailable" and av["evidence_retrieval_completed"] is False
    assert res.get("evidence_sufficiency") is None and "insufficient_evidence" not in json.dumps(res)       # an infrastructure condition, not a statement about the evidence


def test_no_specialist_call_starts_when_too_little_time_is_left_after_retrieval(pipe, monkeypatch):
    pipe["set_bundle"](tcs_bundle())
    real = P.suff_mod.assess

    def slow_assess(*a, **k):
        time.sleep(1.8)                                                  # slow synchronous work between retrieval and generation
        return real(*a, **k)
    monkeypatch.setattr(P.suff_mod, "assess", slow_assess)
    raw, res = run_with_deadline("What is happening with TCS lately? (deadline before specialist)", total=3.0, reserve=0.5, min_attempt=1.0, attempt_cap=1.0)
    assert pipe["specialist"] == 0 and res["degraded_reason"] == "deadline_exceeded"
    assert res["answer_availability"]["state"] == "temporarily_unavailable"


def test_gate_b_still_authorizes_a_generation_that_arrives_inside_the_finalization_reserve(pipe, monkeypatch):
    async def fake_assemble(query, ai, evidence, kind, was_degraded, report, db, entities, **kw):
        return {"query": query, "response_id": "r1", "synthesis_incomplete": False, "answer": {"summary": ai["summary"]}, "companies": [], "investment_verdict": {"rating": "Neutral"}}
    monkeypatch.setattr(P, "_assemble_response", fake_assemble)
    pipe["set_bundle"](tcs_bundle())

    async def late_specialist(query, evidence, intent_data, entities):
        pipe["specialist"] += 1
        await asyncio.sleep(max(RD.usable() - 0.05, 0))                  # uses the whole usable window: finishes inside the reserve
        return good_generation(), False
    for name in ("company_specialist", "comparison_specialist", "sector_specialist"):
        monkeypatch.setattr(getattr(P, name), "run", late_specialist)
    raw, res = run_with_deadline("What is happening with TCS lately? (deadline reserve)", total=3.0, reserve=1.0, min_attempt=0.5, attempt_cap=2.0)
    assert res["synthesis_incomplete"] is False and res["answer_authorization"]["authorized"] is True        # the reserve left room for Gate B and assembly


def test_a_generation_with_no_time_left_to_authorize_is_never_published(pipe, monkeypatch):
    pipe["set_bundle"](tcs_bundle())

    async def overrunning_specialist(query, evidence, intent_data, entities):
        pipe["specialist"] += 1
        await asyncio.sleep(max(RD.remaining() - 0.02, 0))               # returns with almost nothing left, past the reserve
        return good_generation(), False
    for name in ("company_specialist", "comparison_specialist", "sector_specialist"):
        monkeypatch.setattr(getattr(P, name), "run", overrunning_specialist)
    raw, res = run_with_deadline("What is happening with TCS lately? (deadline authorization)", total=2.0, reserve=0.5, min_attempt=0.5, attempt_cap=2.0)
    assert pipe["specialist"] == 1 and res["degraded_reason"] == "deadline_exceeded"
    assert "authorized" not in json.dumps(res.get("answer_authorization") or {}).lower() or res["answer_authorization"].get("authorized") is not True
    assert good_generation()["summary"] not in json.dumps(res)           # unauthorized content never reaches the response


def test_a_provider_chain_stopped_by_the_budget_is_reported_as_deadline_not_capacity(pipe, monkeypatch):
    pipe["set_bundle"](tcs_bundle())

    async def chain_expired(query, evidence, intent_data, entities):
        pipe["specialist"] += 1
        RD.mark_expired()                                                # what _attempt/_deadline_stops_chain do when the budget ends the chain
        return {"_degraded_reason": "capacity"}, True
    for name in ("company_specialist", "comparison_specialist", "sector_specialist"):
        monkeypatch.setattr(getattr(P, name), "run", chain_expired)
    raw, res = run_with_deadline("What is happening with TCS lately? (deadline reason)", total=5.0, reserve=0.5, min_attempt=0.5, attempt_cap=2.0)
    assert res["degraded_reason"] == "deadline_exceeded" and res["answer_availability"]["state"] == "temporarily_unavailable"


def test_a_genuine_provider_failure_without_a_deadline_is_still_capacity(pipe):
    pipe["set_bundle"](tcs_bundle())
    raw, res, _ = __import__("tests.services.test_ai_search_fail_closed", fromlist=["run_pipeline"]).run_pipeline("What is happening with TCS lately? (no deadline capacity)")
    assert res["degraded_reason"] == "capacity"


# ── scope plumbing ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_scope_is_per_request_restored_and_disabled_by_a_zero_budget():
    assert RD.active() is False
    with RD.scope(total=5.0, reserve=1.0, min_attempt=1.0, attempt_cap=2.0):
        assert RD.active() and 3.5 < RD.usable() <= 4.0
        with RD.sub_budget(1.0):
            assert RD.usable() <= 1.0
        assert RD.usable() > 3.0                                         # the parent deadline is untouched by the sub-budget
    assert RD.active() is False
    with RD.scope(total=0):
        assert RD.active() is False                                      # AI_SEARCH_TOTAL_BUDGET_SECONDS=0 turns the mechanism off


def test_a_sub_budget_can_never_extend_the_request_deadline():
    with RD.scope(total=2.0, reserve=0.5, min_attempt=0.5, attempt_cap=1.0):
        with RD.sub_budget(60.0):
            assert RD.usable() <= 1.5


def test_the_streaming_wrapper_applies_the_deadline_and_the_http_routes_use_the_scope():
    from app.api import ai_search as route
    seen = []

    async def steps():
        seen.append(RD.active())
        yield 1
        seen.append(RD.active())

    async def go():
        return [x async for x in route._bounded(steps())]

    assert run(go()) == [1] and seen == [True, True] and RD.active() is False
    import inspect
    src = inspect.getsource(route)
    assert src.count("request_deadline.scope()") == 3                    # /search, /search/v3 and (inside _bounded) the stream route
    assert "_bounded(_run_v3_steps(" in src


def test_background_callers_get_no_deadline_because_only_the_routes_set_it(chain):
    async def go():
        return RD.usable()
    assert run(go()) is None
