"""
AI Search reliability follow-up (2026-09-20, revised same day after review).
Deterministic tests for the provider-aware exhaustion/cooldown mechanism in
app/services/ai_service.py:

  - Cooldowns are keyed by (provider, model), not model alone -- the same
    model id string reached through two different providers must not share
    exhaustion state.
  - Reset-header parsing (_parse_retry_after) supports delta-seconds,
    absolute Unix seconds, absolute Unix milliseconds (OpenRouter), Groq's
    compact duration strings ("5m46s"), and an RFC 9110 HTTP-date -- capped
    at a 24h ceiling, not 1h, since a real daily-quota reset can be ~11h out.
  - 402 (billing) is a short, recoverable cooldown plus an explicit
    provider/model-scoped _clear_exhaustion escape hatch for operational
    verification (e.g. confirming a restored subscription) without waiting.
  - 401/403 are classified as auth/config failures (long cooldown, not a
    30s retry loop against a key that cannot self-heal).
  - The connect/read timeout split (_HTTP_TIMEOUT) keeps a short connect
    timeout without shortening the read timeout a slow-but-live reasoning
    model may need.
  - Cooldown expiry, recovery, and concurrent-call safety.
  - The _call_with_fallback tier/model iteration order is unchanged.

Real _call_provider/_is_exhausted/_mark_exhausted/_parse_retry_after logic
is exercised throughout -- only the HTTP transport is replaced with
httpx.MockTransport, so nothing here depends on any provider's live
behavior (rate limits, billing state, uptime).

Note on test_ai_service_nvidia.py::test_best_reasoning_tier_falls_back_to_medium_chain:
that failure pre-dates this change (a stale test fixture calling
_call_with_fallback without the priority= kwarg its real signature has
required since before this work started) and is confirmed unrelated --
it fails on a call-signature mismatch in the test's own mock, never
reaching any of the _call_provider/_EXHAUSTED logic this file covers.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.services import ai_service


@pytest.fixture(autouse=True)
def fresh_exhaustion_state(monkeypatch):
    """_EXHAUSTED is module-level, shared process state -- give every test
    a clean slate exactly like test_ai_service_nvidia.py does for the
    NVIDIA circuit breaker."""
    monkeypatch.setattr(ai_service, "_EXHAUSTED", {})


def _mock_client(handler):
    """A drop-in httpx.AsyncClient whose transport is fully mocked -- no
    real network call is ever made."""
    class _FakeAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)
    return _FakeAsyncClient


# ── Reset-header parsing: delta-seconds, HTTP-date, alternate headers ───────

def test_parse_retry_after_numeric_seconds():
    headers = httpx.Headers({"retry-after": "45"})
    assert ai_service._parse_retry_after(headers) == 45.0


def test_parse_retry_after_http_date():
    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    headers = httpx.Headers({"retry-after": future.strftime("%a, %d %b %Y %H:%M:%S GMT")})
    result = ai_service._parse_retry_after(headers)
    assert result is not None
    assert 25.0 <= result <= 31.0


def test_parse_retry_after_alternate_header_name():
    headers = httpx.Headers({"x-ratelimit-reset-requests": "10"})
    assert ai_service._parse_retry_after(headers) == 10.0


def test_parse_retry_after_missing_header_returns_none():
    assert ai_service._parse_retry_after(httpx.Headers({})) is None


# ── Multi-header precedence: a valid Retry-After wins; a bad one doesn't mask ──

def test_valid_positive_retry_after_takes_precedence_over_other_reset_headers():
    """When multiple reset headers are present, a valid positive
    Retry-After wins outright -- the other header's (very different)
    value is never even considered."""
    headers = httpx.Headers({
        "retry-after": "120",
        "x-ratelimit-reset": "999999999999",
    })
    assert ai_service._parse_retry_after(headers) == 120.0


@pytest.mark.parametrize("bad_retry_after", [
    "not-a-number-or-date",  # malformed
    "-30",                    # negative
    "0",                      # zero
])
def test_malformed_negative_or_zero_retry_after_does_not_mask_a_valid_future_reset(bad_retry_after):
    headers = httpx.Headers({"retry-after": bad_retry_after, "x-ratelimit-reset": "1800"})
    assert ai_service._parse_retry_after(headers) == 1800.0


def test_past_retry_after_does_not_mask_a_valid_future_reset():
    past_s = datetime.now(timezone.utc).timestamp() - 500  # a past absolute Unix timestamp
    headers = httpx.Headers({
        "retry-after": str(int(past_s)),
        "x-ratelimit-reset": "1800",
    })
    assert ai_service._parse_retry_after(headers) == 1800.0


def test_all_headers_non_positive_falls_back_to_the_best_zero_result():
    """If every present header is malformed or non-positive, the function
    still returns its best (clamped-to-zero) answer rather than None --
    None is reserved for 'nothing here was parseable at all'."""
    headers = httpx.Headers({"retry-after": "-30", "x-ratelimit-reset": "0"})
    assert ai_service._parse_retry_after(headers) == 0.0


# ── Reset-header parsing: absolute Unix timestamps (OpenRouter), Groq durations ──

def test_parse_retry_after_openrouter_style_unix_ms_reset_beyond_one_hour():
    """OpenRouter's real daily-quota reset can be observed ~11h out -- the
    OLD 1h cap silently defeated this header entirely, so the chain kept
    retrying hourly against a quota that wasn't resetting for another 10
    hours. Must now survive uncapped (11h < the new 24h ceiling)."""
    eleven_hours_s = 11 * 3600
    reset_at_ms = (datetime.now(timezone.utc).timestamp() + eleven_hours_s) * 1000
    headers = httpx.Headers({"x-ratelimit-reset": str(int(reset_at_ms))})

    result = ai_service._parse_retry_after(headers)

    assert result is not None
    assert eleven_hours_s - 5 <= result <= eleven_hours_s + 5
    assert result < ai_service._MAX_RETRY_AFTER_S  # not clamped -- genuinely under the new ceiling


def test_parse_retry_after_absolute_unix_seconds_reset():
    two_hours_s = 2 * 3600
    reset_at_s = datetime.now(timezone.utc).timestamp() + two_hours_s
    headers = httpx.Headers({"x-ratelimit-reset": str(int(reset_at_s))})

    result = ai_service._parse_retry_after(headers)

    assert result is not None
    assert two_hours_s - 5 <= result <= two_hours_s + 5


def test_parse_retry_after_small_numeric_value_stays_a_relative_delta():
    """A small number (well under the epoch-seconds threshold) must be
    read as RFC 9110 delta-seconds, not misinterpreted as an absolute
    timestamp near the Unix epoch."""
    headers = httpx.Headers({"retry-after": "300"})
    assert ai_service._parse_retry_after(headers) == 300.0


def test_parse_retry_after_groq_style_duration_string():
    headers = httpx.Headers({"retry-after": "5m46s"})
    result = ai_service._parse_retry_after(headers)
    assert result == pytest.approx(5 * 60 + 46, abs=0.01)


def test_parse_retry_after_groq_style_duration_string_hours_only():
    headers = httpx.Headers({"retry-after": "2h"})
    assert ai_service._parse_retry_after(headers) == pytest.approx(2 * 3600, abs=0.01)


def test_parse_retry_after_caps_at_the_24h_safety_ceiling():
    far_future_ms = (datetime.now(timezone.utc).timestamp() + 999 * 3600) * 1000
    headers = httpx.Headers({"retry-after": str(int(far_future_ms))})
    assert ai_service._parse_retry_after(headers) == ai_service._MAX_RETRY_AFTER_S


def test_max_retry_after_is_24_hours_not_1_hour():
    assert ai_service._MAX_RETRY_AFTER_S == 24 * 3600.0


# ── Malformed, negative, and past reset values ──────────────────────────────

def test_parse_retry_after_malformed_value_returns_none():
    headers = httpx.Headers({"retry-after": "not-a-number-or-date"})
    assert ai_service._parse_retry_after(headers) is None


def test_parse_retry_after_negative_delta_clamps_to_zero_not_none():
    headers = httpx.Headers({"retry-after": "-5"})
    assert ai_service._parse_retry_after(headers) == 0.0


def test_parse_retry_after_past_absolute_timestamp_clamps_to_zero():
    past_s = datetime.now(timezone.utc).timestamp() - 100
    headers = httpx.Headers({"x-ratelimit-reset": str(int(past_s))})
    assert ai_service._parse_retry_after(headers) == 0.0


def test_parse_retry_after_empty_duration_string_falls_through_to_none():
    headers = httpx.Headers({"retry-after": ""})
    assert ai_service._parse_retry_after(headers) is None


# ── Per-reason cooldown table sanity ─────────────────────────────────────────

def test_cooldown_durations_reflect_how_fast_each_failure_can_resolve():
    assert ai_service._COOLDOWN_S["not_found"] > ai_service._COOLDOWN_S["auth_error"]
    assert ai_service._COOLDOWN_S["auth_error"] > ai_service._COOLDOWN_S["billing"]
    assert ai_service._COOLDOWN_S["billing"] > ai_service._COOLDOWN_S["rate_limit"]
    assert ai_service._COOLDOWN_S["rate_limit"] > ai_service._COOLDOWN_S["server_error"]


def test_billing_cooldown_is_short_enough_for_same_day_recovery_testing():
    """A fixed 6h billing cooldown (the original design) would have
    blocked the planned Mistral smoke test for hours after the
    subscription was actually fixed. Must be in the 30-60 minute range."""
    assert 30 * 60 <= ai_service._COOLDOWN_S["billing"] <= 60 * 60


# ── _mark_exhausted / _is_exhausted: keyed by (provider, model) ─────────────

def test_is_exhausted_true_before_cooldown_elapses(monkeypatch):
    fake_time = {"t": 1000.0}
    monkeypatch.setattr(ai_service.time, "monotonic", lambda: fake_time["t"])

    ai_service._mark_exhausted("groq", "model-x", "server_error")
    assert ai_service._is_exhausted("groq", "model-x") is True

    fake_time["t"] += ai_service._COOLDOWN_S["server_error"] - 1
    assert ai_service._is_exhausted("groq", "model-x") is True


def test_is_exhausted_false_and_entry_popped_after_cooldown_elapses(monkeypatch):
    fake_time = {"t": 1000.0}
    monkeypatch.setattr(ai_service.time, "monotonic", lambda: fake_time["t"])

    ai_service._mark_exhausted("groq", "model-y", "rate_limit")
    fake_time["t"] += ai_service._COOLDOWN_S["rate_limit"] + 1

    assert ai_service._is_exhausted("groq", "model-y") is False
    assert ("groq", "model-y") not in ai_service._EXHAUSTED  # recovered, not just reporting false


def test_mark_exhausted_explicit_cooldown_overrides_reason_default(monkeypatch):
    fake_time = {"t": 0.0}
    monkeypatch.setattr(ai_service.time, "monotonic", lambda: fake_time["t"])

    ai_service._mark_exhausted("groq", "model-z", "rate_limit", cooldown_s=5.0)
    fake_time["t"] = 4.0
    assert ai_service._is_exhausted("groq", "model-z") is True
    fake_time["t"] = 6.0
    assert ai_service._is_exhausted("groq", "model-z") is False


def test_same_model_name_on_two_providers_has_independent_cooldowns(monkeypatch):
    """The core bug this review flagged: _EXHAUSTED used to key on model
    id alone, so a model exhausted via one provider would incorrectly
    suppress an identically-named model on a completely different
    provider. Must now be fully independent."""
    fake_time = {"t": 1000.0}
    monkeypatch.setattr(ai_service.time, "monotonic", lambda: fake_time["t"])
    shared_model = "shared-name-v1"

    ai_service._mark_exhausted("groq", shared_model, "rate_limit")

    assert ai_service._is_exhausted("groq", shared_model) is True
    assert ai_service._is_exhausted("openrouter", shared_model) is False


def test_clear_exhaustion_is_scoped_to_provider_and_model(monkeypatch):
    """The billing-recovery escape hatch must never clear the whole
    table -- only the exact provider (and, if given, model) named."""
    ai_service._mark_exhausted("mistral", "mistral-small", "billing")
    ai_service._mark_exhausted("mistral", "open-mistral-nemo", "billing")
    ai_service._mark_exhausted("groq", "openai/gpt-oss-120b", "rate_limit")

    removed = ai_service._clear_exhaustion("mistral", "mistral-small")

    assert removed == 1
    assert ai_service._is_exhausted("mistral", "mistral-small") is False
    assert ai_service._is_exhausted("mistral", "open-mistral-nemo") is True  # untouched
    assert ai_service._is_exhausted("groq", "openai/gpt-oss-120b") is True  # untouched


def test_clear_exhaustion_without_model_clears_only_that_providers_entries():
    ai_service._mark_exhausted("mistral", "mistral-small", "billing")
    ai_service._mark_exhausted("mistral", "open-mistral-nemo", "billing")
    ai_service._mark_exhausted("groq", "openai/gpt-oss-120b", "rate_limit")

    removed = ai_service._clear_exhaustion("mistral")

    assert removed == 2
    assert ai_service._is_exhausted("mistral", "mistral-small") is False
    assert ai_service._is_exhausted("mistral", "open-mistral-nemo") is False
    assert ai_service._is_exhausted("groq", "openai/gpt-oss-120b") is True  # untouched -- not a global clear


# ── _call_provider: classification by HTTP status / exception ──────────────

async def test_call_provider_429_uses_retry_after_header(monkeypatch):
    def handler(request):
        return httpx.Response(429, headers={"retry-after": "37"})
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider("https://fake/v1/chat", "key", "model-429a", "prompt")

    assert result == ""
    entry = ai_service._EXHAUSTED[("unknown", "model-429a")]
    assert entry.reason == "rate_limit"
    remaining = entry.expires_at - time.monotonic()
    assert 30 <= remaining <= 40  # ~37s from the header, not the flat 120s default


async def test_call_provider_429_without_header_uses_default_cooldown(monkeypatch):
    def handler(request):
        return httpx.Response(429)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider("https://fake/v1/chat", "key", "model-429b", "prompt")

    assert result == ""
    entry = ai_service._EXHAUSTED[("unknown", "model-429b")]
    assert entry.reason == "rate_limit"
    remaining = entry.expires_at - time.monotonic()
    assert 115 <= remaining <= 120


async def test_call_provider_402_marks_a_short_recoverable_billing_cooldown(monkeypatch):
    def handler(request):
        return httpx.Response(402)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider("https://fake/v1/chat", "key", "model-402", "prompt")

    assert result == ""
    entry = ai_service._EXHAUSTED[("unknown", "model-402")]
    assert entry.reason == "billing"
    remaining = entry.expires_at - time.monotonic()
    assert 30 * 60 <= remaining <= 60 * 60


async def test_call_provider_401_marks_auth_error_not_server_error(monkeypatch):
    def handler(request):
        return httpx.Response(401)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider("https://fake/v1/chat", "key", "model-401", "prompt")

    assert result == ""
    entry = ai_service._EXHAUSTED[("unknown", "model-401")]
    assert entry.reason == "auth_error"
    remaining = entry.expires_at - time.monotonic()
    assert remaining > ai_service._COOLDOWN_S["server_error"] * 10  # not a quick transient retry


async def test_call_provider_403_marks_auth_error(monkeypatch):
    def handler(request):
        return httpx.Response(403)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider("https://fake/v1/chat", "key", "model-403", "prompt")

    assert result == ""
    assert ai_service._EXHAUSTED[("unknown", "model-403")].reason == "auth_error"


async def test_call_provider_404_marks_not_found_with_the_longest_cooldown(monkeypatch):
    def handler(request):
        return httpx.Response(404)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider("https://fake/v1/chat", "key", "model-404", "prompt")

    assert result == ""
    entry = ai_service._EXHAUSTED[("unknown", "model-404")]
    assert entry.reason == "not_found"
    remaining = entry.expires_at - time.monotonic()
    assert remaining > ai_service._COOLDOWN_S["auth_error"]  # the longest of all reasons


async def test_call_provider_5xx_marks_server_error_with_a_short_cooldown(monkeypatch):
    def handler(request):
        return httpx.Response(503)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider("https://fake/v1/chat", "key", "model-503", "prompt")

    assert result == ""
    entry = ai_service._EXHAUSTED[("unknown", "model-503")]
    assert entry.reason == "server_error"
    remaining = entry.expires_at - time.monotonic()
    assert 0 < remaining <= ai_service._COOLDOWN_S["rate_limit"]


async def test_call_provider_timeout_marks_server_error_cooldown(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("simulated timeout", request=request)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider("https://fake/v1/chat", "key", "model-timeout", "prompt")

    assert result == ""
    entry = ai_service._EXHAUSTED[("unknown", "model-timeout")]
    assert entry.reason == "server_error"


async def test_call_provider_success_does_not_mark_exhausted(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    result = await ai_service._call_provider("https://fake/v1/chat", "key", "model-ok", "prompt")

    assert result == "ok"
    assert ("unknown", "model-ok") not in ai_service._EXHAUSTED


async def test_call_provider_skips_already_exhausted_pair_without_a_network_call(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))
    ai_service._mark_exhausted("unknown", "model-cooling", "server_error")

    result = await ai_service._call_provider("https://fake/v1/chat", "key", "model-cooling", "prompt")

    assert result == ""
    assert calls["n"] == 0  # never even attempted the HTTP call


async def test_call_provider_recovers_once_cooldown_elapses(monkeypatch):
    fake_time = {"t": 1000.0}
    monkeypatch.setattr(ai_service.time, "monotonic", lambda: fake_time["t"])

    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "recovered"}}]})
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))
    ai_service._mark_exhausted("unknown", "model-recovers", "server_error")

    result_during = await ai_service._call_provider("https://fake/v1/chat", "key", "model-recovers", "prompt")
    assert result_during == ""

    fake_time["t"] += ai_service._COOLDOWN_S["server_error"] + 1
    result_after = await ai_service._call_provider("https://fake/v1/chat", "key", "model-recovers", "prompt")
    assert result_after == "recovered"


async def test_call_provider_identical_model_name_on_two_real_providers_stays_independent(monkeypatch):
    """End-to-end version of the (provider, model) keying fix: the SAME
    model id string, called through two different base_urls (Groq vs
    OpenRouter), must not let a failure on one suppress the other."""
    def handler(request):
        if str(request.url) == ai_service._GROQ_URL:
            return httpx.Response(429, headers={"retry-after": "500"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "openrouter-ok"}}]})
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    shared_model = "shared-name-v1"
    groq_result = await ai_service._call_provider(ai_service._GROQ_URL, "key", shared_model, "prompt")
    or_result = await ai_service._call_provider(ai_service._OR_URL, "key", shared_model, "prompt")

    assert groq_result == ""
    assert or_result == "openrouter-ok"
    assert ai_service._is_exhausted("groq", shared_model) is True
    assert ai_service._is_exhausted("openrouter", shared_model) is False


# ── Billing recovery: clear-then-retry, not stuck for the full cooldown ────

async def test_call_provider_billing_cooldown_can_be_cleared_for_recovery_verification(monkeypatch):
    """Mirrors the real operational scenario this review called out: a
    Mistral 402 during the capacity incident, followed later by a
    subscription fix that needs verifying without waiting out even the
    shortened billing cooldown."""
    responses = iter([httpx.Response(402), httpx.Response(200, json={"choices": [{"message": {"content": "billing-fixed"}}]})])

    def handler(request):
        return next(responses)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    first = await ai_service._call_provider(ai_service._MISTRAL_URL, "key", "mistral-small", "prompt")
    assert first == ""
    assert ai_service._is_exhausted("mistral", "mistral-small") is True

    cleared = ai_service._clear_exhaustion("mistral", "mistral-small")
    assert cleared == 1

    second = await ai_service._call_provider(ai_service._MISTRAL_URL, "key", "mistral-small", "prompt")
    assert second == "billing-fixed"


# ── Timeout: connect/read split, not a universal shortened value ───────────

def test_http_timeout_read_is_unchanged_from_the_original_default():
    """The original code used a single blanket 30s httpx timeout. A
    universal drop to 12s risked truncating a slow-but-live
    reasoning-model response. The read timeout must stay at 30s;
    only the connect timeout (for genuinely unreachable hosts) is
    shortened."""
    assert ai_service._HTTP_TIMEOUT.read == 30.0
    assert ai_service._HTTP_TIMEOUT.connect == 5.0
    assert ai_service._HTTP_TIMEOUT.connect < ai_service._HTTP_TIMEOUT.read


async def test_call_provider_uses_the_connect_read_split_timeout(monkeypatch):
    captured = {}

    class _CapturingAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            kwargs["transport"] = httpx.MockTransport(
                lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
            )
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _CapturingAsyncClient)
    await ai_service._call_provider("https://fake/v1/chat", "key", "model-timeout-check", "prompt")

    assert captured["timeout"] is ai_service._HTTP_TIMEOUT
    assert captured["timeout"].read == 30.0


# ── Concurrency: parallel fallback calls must not corrupt cooldown state ───

async def test_concurrent_calls_across_models_do_not_corrupt_cooldown_state(monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        model = body["model"]
        if model.endswith("-fail"):
            return httpx.Response(429, headers={"retry-after": "50"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    models = [f"concurrent-model-{i}{'-fail' if i % 2 == 0 else ''}" for i in range(20)]
    results = await asyncio.gather(*[
        ai_service._call_provider("https://fake/v1/chat", "key", m, "prompt") for m in models
    ])

    for model, result in zip(models, results):
        if model.endswith("-fail"):
            assert result == ""
            entry = ai_service._EXHAUSTED[("unknown", model)]
            assert entry.reason == "rate_limit"
        else:
            assert result == "ok"
            assert ("unknown", model) not in ai_service._EXHAUSTED

    fail_count = sum(1 for m in models if m.endswith("-fail"))
    assert len(ai_service._EXHAUSTED) == fail_count  # no lost or duplicated entries


async def test_concurrent_calls_to_the_same_model_leave_a_single_consistent_entry(monkeypatch):
    """Every concurrent call to the identical (provider, model) pair
    returns 429 -- the dict must end up with exactly one coherent entry,
    not a torn or duplicated write."""
    def handler(request):
        return httpx.Response(429, headers={"retry-after": "60"})
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", _mock_client(handler))

    await asyncio.gather(*[
        ai_service._call_provider("https://fake/v1/chat", "key", "hot-model", "prompt")
        for _ in range(15)
    ])

    assert len(ai_service._EXHAUSTED) == 1
    entry = ai_service._EXHAUSTED[("unknown", "hot-model")]
    assert entry.reason == "rate_limit"
    assert 55 <= entry.expires_at - time.monotonic() <= 60


# ── _call_with_fallback: tier/model iteration order is unchanged ───────────

async def test_fallback_tier_order_unchanged_skips_a_cooling_model_within_the_same_tier(monkeypatch):
    """Only _call_provider's internal error classification and _EXHAUSTED's
    shape changed in this refactor -- the tier loop structure itself (which
    provider/model is tried in which order) must be exactly as before.
    Marks the first Groq-HQ model exhausted and confirms the chain moves to
    the next model in that SAME tier before ever reaching a later tier."""
    if not ai_service.settings.groq_api_key or len(ai_service._GROQ_HIGH) < 2:
        pytest.skip("requires a configured Groq key and >=2 Groq HQ models in this environment")

    ai_service._mark_exhausted("groq", ai_service._GROQ_HIGH[0], "rate_limit")
    seen_models = []

    async def _fake_call_provider(base_url, api_key, model, prompt, system="", max_tokens=200, extra_headers=None, failure_log=None):
        seen_models.append(model)
        return "ok" if model == ai_service._GROQ_HIGH[1] else ""

    monkeypatch.setattr(ai_service, "_call_provider", _fake_call_provider)
    result = await ai_service._call_with_fallback("prompt", priority="background")

    assert result == "ok"
    assert ai_service._GROQ_HIGH[0] not in seen_models  # skipped -- still cooling down
    assert seen_models[0] == ai_service._GROQ_HIGH[1]
