"""
Unit tests for the NVIDIA "best effort" resilience layer in
`app/services/ai_service.py`: hard timeout, failure classification,
circuit breaker state machine, and metrics — all exercised deterministically
by monkeypatching `_call_nvidia_raw` rather than depending on real network
behavior (timeouts/429s/5xxs are not reliably reproducible against a live
API on demand).
"""
from __future__ import annotations

import pytest

from app.services import ai_service


@pytest.fixture(autouse=True)
def fresh_nvidia_state(monkeypatch):
    """Every test gets a clean circuit + metrics — this module-level state
    would otherwise leak between tests exactly like it leaks between
    requests in the running process (that's the point of it)."""
    monkeypatch.setattr(ai_service, "_nvidia_circuit", ai_service._CircuitBreaker(
        failure_threshold=ai_service._CIRCUIT_FAILURE_THRESHOLD,
        cooldown_s=ai_service._CIRCUIT_COOLDOWN_S,
    ))
    monkeypatch.setattr(ai_service, "_nvidia_metrics", ai_service._NvidiaMetrics())
    monkeypatch.setattr(ai_service.settings, "nvidia_api_key", "test-key")


async def test_success_records_metrics_and_closes_circuit(monkeypatch):
    async def _ok(prompt, system, max_tokens):
        return "real answer", None
    monkeypatch.setattr(ai_service, "_call_nvidia_raw", _ok)

    result = await ai_service._call_nvidia("q")

    assert result == "real answer"
    m = ai_service._nvidia_metrics.snapshot()
    assert m["attempts"] == 1
    assert m["successes"] == 1
    assert m["fallbacks"] == 0
    assert ai_service._nvidia_circuit.state == ai_service._CircuitState.CLOSED


@pytest.mark.parametrize("failure_kind,metric_key", [
    ("timeout", "timeouts"),
    ("rate_limited", "rate_limited"),
    ("server_error", "server_errors"),
    ("other", "other_failures"),
])
async def test_failure_kinds_are_classified_and_trigger_fallback(monkeypatch, failure_kind, metric_key):
    async def _fail(prompt, system, max_tokens):
        return "", failure_kind
    monkeypatch.setattr(ai_service, "_call_nvidia_raw", _fail)

    result = await ai_service._call_nvidia("q")

    assert result == ""   # caller must fall back — never raises, never blocks
    m = ai_service._nvidia_metrics.snapshot()
    assert m[metric_key] == 1
    assert m["fallbacks"] == 1


async def test_circuit_opens_after_threshold_consecutive_failures(monkeypatch):
    async def _fail(prompt, system, max_tokens):
        return "", "server_error"
    monkeypatch.setattr(ai_service, "_call_nvidia_raw", _fail)

    for _ in range(ai_service._CIRCUIT_FAILURE_THRESHOLD):
        await ai_service._call_nvidia("q")

    assert ai_service._nvidia_circuit.state == ai_service._CircuitState.OPEN
    assert ai_service._nvidia_metrics.snapshot()["circuit_opens"] == 1


async def test_open_circuit_skips_the_network_call_entirely(monkeypatch):
    calls = {"n": 0}

    async def _fail(prompt, system, max_tokens):
        calls["n"] += 1
        return "", "server_error"
    monkeypatch.setattr(ai_service, "_call_nvidia_raw", _fail)

    for _ in range(ai_service._CIRCUIT_FAILURE_THRESHOLD):
        await ai_service._call_nvidia("q")
    assert ai_service._nvidia_circuit.state == ai_service._CircuitState.OPEN
    calls_before_open_skip = calls["n"]

    # Circuit is open — this call must not reach _call_nvidia_raw at all.
    result = await ai_service._call_nvidia("q")

    assert result == ""
    assert calls["n"] == calls_before_open_skip, "circuit-open call should skip the network entirely"
    assert ai_service._nvidia_metrics.snapshot()["fallbacks"] == ai_service._CIRCUIT_FAILURE_THRESHOLD + 1


async def test_circuit_recovers_after_cooldown_on_successful_trial(monkeypatch):
    # Short cooldown so the test doesn't take 60s.
    ai_service._nvidia_circuit.cooldown_s = 0.05

    async def _fail(prompt, system, max_tokens):
        return "", "timeout"
    monkeypatch.setattr(ai_service, "_call_nvidia_raw", _fail)
    for _ in range(ai_service._CIRCUIT_FAILURE_THRESHOLD):
        await ai_service._call_nvidia("q")
    assert ai_service._nvidia_circuit.state == ai_service._CircuitState.OPEN

    import asyncio
    await asyncio.sleep(0.06)   # let the cooldown elapse

    async def _ok(prompt, system, max_tokens):
        return "recovered", None
    monkeypatch.setattr(ai_service, "_call_nvidia_raw", _ok)

    result = await ai_service._call_nvidia("q")

    assert result == "recovered"
    assert ai_service._nvidia_circuit.state == ai_service._CircuitState.CLOSED


async def test_no_api_key_short_circuits_without_touching_the_breaker(monkeypatch):
    monkeypatch.setattr(ai_service.settings, "nvidia_api_key", "")

    result = await ai_service._call_nvidia("q")

    assert result == ""
    assert ai_service._nvidia_metrics.snapshot()["attempts"] == 0


async def test_best_reasoning_tier_falls_back_to_medium_chain(monkeypatch):
    from app.ai_pipeline.models import tiers as tiers_module

    async def _fail(prompt, system, max_tokens):
        return "", "server_error"
    monkeypatch.setattr(ai_service, "_call_nvidia_raw", _fail)

    async def _fake_chain(prompt, system="", max_tokens=200):
        return "fallback answer from existing chain"
    monkeypatch.setattr(ai_service, "_call_with_fallback", _fake_chain)

    result = await tiers_module._best_reasoning_call("q")

    assert result == "fallback answer from existing chain"
