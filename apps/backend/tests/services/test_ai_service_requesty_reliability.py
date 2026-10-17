"""
AI Search Reliability Fix 1 (2026-10-17).

Production evidence (read-only audit, same day): Requesty was observed
taking up to ~10.6s to fail under the shared 30s httpx read timeout --
large enough on its own to starve the rest of a 24s request-deadline
budget before later tiers (openrouter-small) are ever reached (confirmed
via real ai.deadline_stop/ai.deadline_cancel log lines pointing at exactly
those two tiers). A separate, smaller defect: a 200 response whose body
doesn't match the expected {choices: [{message: {content}}]} shape (seen
live as a bare KeyError('content')) was being charged the same 30s
"server_error" cooldown as a genuine timeout -- imprecise, and risked
masking a provider-format problem as a network outage.

This file covers three independent changes in app/services/ai_service.py:
  1. Requesty gets its own tight httpx timeout (_REQUESTY_TIMEOUT, 4s),
     every other provider keeps the shared _HTTP_TIMEOUT unchanged.
  2. A malformed-shape 200 response is classified as "schema_error" (fast,
     short cooldown, never logs the raw response body/content), distinct
     from a real timeout/connection failure.
  3. _deadline_stops_chain's existing deadline-stop path is now counted in
     _AI_USAGE (previously only deadline_cancels, from _attempt's
     asyncio.wait_for path, was tracked -- a tier stopped before any HTTP
     attempt even starts was invisible).

Same conventions as test_ai_service_cooldowns.py (httpx.MockTransport,
autouse _EXHAUSTED reset) and test_request_deadline_latency_contract.py
(request_deadline.scope() for real deadline interplay).
"""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from app.services import ai_service
from app.services import request_deadline as RD


@pytest.fixture(autouse=True)
def fresh_exhaustion_and_usage_state(monkeypatch):
    """_EXHAUSTED and _AI_USAGE are module-level, shared process state --
    give every test a clean slate, same pattern as test_ai_service_cooldowns.py."""
    monkeypatch.setattr(ai_service, "_EXHAUSTED", {})
    fresh_usage = {
        "calls_total": 0, "calls_success": 0, "calls_failed": 0, "fallback_invocations": 0,
        "tokens_total": 0, "latency_ms_total": 0.0, "cache_hits": 0, "cache_misses": 0,
        "timeouts": 0, "last_call_at": None, "last_success_at": None,
        "last_error_at": None, "last_error": None, "last_provider": None,
    }
    monkeypatch.setattr(ai_service, "_AI_USAGE", fresh_usage)


def _mock_client(handler):
    class _FakeAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)
    return _FakeAsyncClient


# ── 1. Requesty-specific bounded timeout ────────────────────────────────────

def test_requesty_timeout_constant_is_four_seconds_and_tighter_than_shared_default():
    assert ai_service._REQUESTY_TIMEOUT_S == 4.0
    assert ai_service._REQUESTY_TIMEOUT.read == 4.0
    assert ai_service._REQUESTY_TIMEOUT.connect == 4.0
    assert ai_service._REQUESTY_TIMEOUT.read < ai_service._HTTP_TIMEOUT.read


async def test_requesty_call_uses_the_requesty_specific_timeout(monkeypatch):
    captured = {}

    class _CapturingAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            kwargs["transport"] = httpx.MockTransport(
                lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
            )
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _CapturingAsyncClient)
    await ai_service._call_provider(ai_service._REQUESTY_URL, "key", "requesty-model", "prompt")

    assert captured["timeout"] is ai_service._REQUESTY_TIMEOUT
    assert captured["timeout"].read == 4.0


async def test_non_requesty_call_still_uses_the_shared_http_timeout_unchanged(monkeypatch):
    """Confirms this fix is scoped to Requesty only -- every other provider
    (Groq shown here) must be byte-identical to before."""
    captured = {}

    class _CapturingAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            kwargs["transport"] = httpx.MockTransport(
                lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
            )
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _CapturingAsyncClient)
    await ai_service._call_provider(ai_service._GROQ_URL, "key", "groq-model", "prompt")

    assert captured["timeout"] is ai_service._HTTP_TIMEOUT
    assert captured["timeout"].read == 30.0


async def test_requesty_timeout_triggers_fast_and_is_classified_as_timeout(monkeypatch):
    """A Requesty response slower than 4s must raise httpx's own timeout
    (simulated here via ReadTimeout, since httpx.MockTransport can't model
    real wall-clock delay) and be classified exactly like any other
    provider timeout -- "server_error" reason, short cooldown -- unaffected
    by the schema-validation change in this same fix."""
    def handler(request):
        raise httpx.ReadTimeout("simulated requesty timeout", request=request)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider(ai_service._REQUESTY_URL, "key", "requesty-slow", "prompt")

    assert result == ""
    entry = ai_service._EXHAUSTED[("requesty", "requesty-slow")]
    assert entry.reason == "server_error"


# ── 2. Malformed response shape -> fast-failing schema_error, not a crash ──

@pytest.mark.parametrize("body", [
    {"choices": []},                                    # empty choices
    {"choices": [{"message": {}}]},                      # message present, content missing
    {"choices": [{}]},                                   # message missing entirely
    {"choices": [{"message": {"text": "wrong key"}}]},    # wrong key name, not "content"
    {"choices": "not-a-list"},                            # choices is the wrong type
    {},                                                    # choices missing entirely
])
async def test_malformed_response_shapes_are_classified_as_schema_error_not_a_crash(monkeypatch, body):
    def handler(request):
        return httpx.Response(200, json=body)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider(ai_service._REQUESTY_URL, "key", "requesty-malformed", "prompt")

    assert result == ""  # never raises -- the original KeyError would have propagated past this point
    entry = ai_service._EXHAUSTED[("requesty", "requesty-malformed")]
    assert entry.reason == "schema_error"


async def test_schema_error_gets_the_short_cooldown_not_the_long_ones(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {}}]})
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    await ai_service._call_provider(ai_service._REQUESTY_URL, "key", "requesty-schema", "prompt")

    entry = ai_service._EXHAUSTED[("requesty", "requesty-schema")]
    remaining = entry.expires_at - time.monotonic()
    assert 0 < remaining <= ai_service._COOLDOWN_S["server_error"] + 1
    assert remaining < ai_service._COOLDOWN_S["auth_error"]  # nowhere near the long, needs-a-human cooldowns


async def test_well_formed_response_with_genuinely_empty_content_is_not_a_schema_error(monkeypatch):
    """A real, valid response where the model returned empty content must
    stay classified as "empty" (pre-existing behavior), not get swept into
    the new schema_error path -- the shape was fine, only the content was
    blank."""
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider(ai_service._REQUESTY_URL, "key", "requesty-empty", "prompt")

    assert result == ""
    assert ("requesty", "requesty-empty") not in ai_service._EXHAUSTED  # empty content is not exhausted/cooled down


def test_schema_error_log_call_never_includes_the_raw_response_body(monkeypatch, caplog):
    """Must never log provider payload/content -- only which expected key
    was missing, confirmed by inspecting the actual log call's kwargs."""
    captured_kwargs = {}
    real_warning = ai_service.log.warning

    def _capturing_warning(event, **kwargs):
        if event == "ai.schema_error":
            captured_kwargs.update(kwargs)
        return real_warning(event, **kwargs)
    monkeypatch.setattr(ai_service.log, "warning", _capturing_warning)

    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"text": "sensitive-looking content"}}]})
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    asyncio.run(ai_service._call_provider(ai_service._REQUESTY_URL, "key", "requesty-log-check", "prompt"))

    assert captured_kwargs, "ai.schema_error was not logged"
    assert "data" not in captured_kwargs
    assert "content" not in captured_kwargs
    assert "sensitive-looking content" not in str(captured_kwargs)


# ── 3. Fallback to the next eligible provider on a schema_error ────────────

async def test_schema_error_on_one_tier_falls_through_to_the_next(monkeypatch):
    """Same tier-order-unchanged guarantee test_ai_service_cooldowns.py's
    test_fallback_tier_order_unchanged_skips_a_cooling_model_within_the_same_tier
    already proves for a rate_limit -- confirms a schema_error behaves the
    same way: _call_provider returning "" is all _call_with_fallback_inner
    needs to move on, regardless of which reason caused the empty result."""
    monkeypatch.setattr(ai_service.settings, "groq_api_key", "k")
    monkeypatch.setattr(ai_service.settings, "openrouter_api_key", "")
    monkeypatch.setattr(ai_service.settings, "mistral_api_key", "")
    monkeypatch.setattr(ai_service.settings, "gemini_api_key", "")
    monkeypatch.setattr(ai_service.settings, "requesty_api_key", "")
    monkeypatch.setattr(ai_service, "_GROQ_HIGH", ["groq-model-a"])
    monkeypatch.setattr(ai_service, "_GROQ_FAST", ["groq-model-b"])

    calls = []

    async def fake_call_provider(base_url, api_key, model, prompt, system="", max_tokens=200, extra_headers=None, failure_log=None):
        calls.append(model)
        if model == "groq-model-a":
            return ""  # simulates the schema_error path already having returned "" upstream
        return "answer-from-b"

    monkeypatch.setattr(ai_service, "_call_provider", fake_call_provider)
    result = await ai_service._call_with_fallback("prompt", priority="background")

    assert result == "answer-from-b"
    assert calls == ["groq-model-a", "groq-model-b"]


# ── 4. deadline_stops telemetry (lightweight, no DB migration) ─────────────

def test_deadline_stops_counter_starts_at_zero_when_absent():
    assert ai_service._AI_USAGE.get("deadline_stops", 0) == 0


def test_deadline_stops_chain_increments_the_counter_each_time_it_fires():
    with RD.scope(total=1.0, reserve=0.0, min_attempt=5.0, attempt_cap=1.0):
        # min_attempt (5s) > usable (~1s) -- guaranteed to stop the chain
        stopped_first = ai_service._deadline_stops_chain(None, "requesty")
        stopped_second = ai_service._deadline_stops_chain(None, "openrouter-small")

    assert stopped_first is True
    assert stopped_second is True
    assert ai_service._AI_USAGE["deadline_stops"] == 2


def test_deadline_stops_does_not_increment_when_no_deadline_is_active():
    assert ai_service._deadline_stops_chain(None, "requesty") is False
    assert ai_service._AI_USAGE.get("deadline_stops", 0) == 0


def test_get_ai_usage_stats_surfaces_deadline_stops_and_cancels():
    ai_service._AI_USAGE["deadline_stops"] = 3
    ai_service._AI_USAGE["deadline_cancels"] = 1
    stats = ai_service.get_ai_usage_stats()
    assert stats["deadline_stops"] == 3
    assert stats["deadline_cancels"] == 1


async def test_deadline_cancel_path_unaffected_by_requesty_timeout_change(monkeypatch):
    """Cancellation semantics (request_deadline.mark_expired(), the
    asyncio.wait_for(budget) path in _attempt(), ai.deadline_cancel
    logging) must be byte-identical to before -- this fix only tightens
    Requesty's own httpx timeout; it does not touch _attempt()."""
    monkeypatch.setattr(ai_service.settings, "groq_api_key", "k")
    monkeypatch.setattr(ai_service, "_GROQ_HIGH", ["groq-hang"])

    async def hanging_call_provider(base_url, api_key, model, prompt, system="", max_tokens=200, extra_headers=None, failure_log=None):
        await asyncio.sleep(10)
        return "too-late"

    monkeypatch.setattr(ai_service, "_call_provider", hanging_call_provider)

    # attempt_cap (5.0) is deliberately far above usable (~0.3s) so usable,
    # not the cap, is the binding constraint -- budget < cap is exactly
    # what routes _attempt() into the "request budget ran out" branch
    # (ai.deadline_cancel) rather than the "provider used its whole normal
    # allowance" branch (budget >= cap, a provider-side timeout instead).
    with RD.scope(total=0.3, reserve=0.0, min_attempt=0.05, attempt_cap=5.0):
        text, stop = await ai_service._attempt(
            "groq-hq", "groq", ai_service._GROQ_URL, "k", "groq-hang", "prompt", "", 50, None, None,
        )

    assert text == ""
    assert stop is True
    assert ai_service._AI_USAGE.get("deadline_cancels", 0) == 1
    assert ("groq", "groq-hang") not in ai_service._EXHAUSTED  # the request budget failed it, not the provider
