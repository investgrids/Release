"""
Regression suite — app.services.source_health, offline (pure in-process
state, no network, no DB).

Covers the classification logic: UNKNOWN for a never-observed source,
HEALTHY for a clean success, DEGRADED for a recent-but-recovered failure,
FAILED after 3 consecutive failures, STALE when successes have stopped
arriving but nothing has technically failed either, and the explicit
"zero events is not automatically unhealthy" distinction the task called
out (a successful fetch that legitimately returns nothing is HEALTHY, not
FAILED or STALE).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import app.services.source_health as source_health


def _fresh_source() -> str:
    # Each test gets its own source name so the shared module-level
    # _SOURCES dict never leaks state between tests.
    return f"pytest-source-{uuid.uuid4().hex[:8]}"


def test_unknown_for_never_observed_source():
    s = _fresh_source()
    health = source_health.get_source_health(s)
    assert health["status"] == "UNKNOWN"
    assert health["last_attempt_at"] is None


def test_healthy_after_clean_success():
    s = _fresh_source()
    source_health.record_fetch(s, success=True, event_count=5)
    health = source_health.get_source_health(s)
    assert health["status"] == "HEALTHY"
    assert health["events_today"] == 5
    assert health["success_count"] == 1


def test_zero_events_on_success_is_still_healthy_not_failed():
    # The explicit distinction the task called out: a source producing
    # zero events is not automatically unhealthy — SEBI's real fetch
    # regularly returns 0 items and that alone must not read as FAILED.
    s = _fresh_source()
    source_health.record_fetch(s, success=True, event_count=0)
    health = source_health.get_source_health(s)
    assert health["status"] == "HEALTHY"
    assert health["events_today"] == 0
    assert health["last_success_at"] is not None
    assert health["last_event_received_at"] is None  # fetch succeeded, but nothing was actually received


def test_failed_after_three_consecutive_failures():
    s = _fresh_source()
    source_health.record_fetch(s, success=True, event_count=3)  # establish a prior success
    for _ in range(3):
        source_health.record_fetch(s, success=False, failure_kind="http")
    health = source_health.get_source_health(s)
    assert health["status"] == "FAILED"
    assert health["consecutive_failures"] == 3
    assert health["http_failure_count"] == 3


def test_failed_when_never_succeeded_but_attempted():
    s = _fresh_source()
    source_health.record_fetch(s, success=False, failure_kind="http")
    health = source_health.get_source_health(s)
    assert health["status"] == "FAILED"


def test_degraded_after_single_failure_then_recovery():
    s = _fresh_source()
    source_health.record_fetch(s, success=True, event_count=1)
    source_health.record_fetch(s, success=False, failure_kind="parse")
    health = source_health.get_source_health(s)
    # consecutive_failures==1 after a real prior success is a flaky/
    # partial pattern (DEGRADED), not yet FAILED (needs 3 in a row).
    assert health["status"] == "DEGRADED"
    assert health["parse_failure_count"] == 1

    # A subsequent success resets consecutive_failures and returns to HEALTHY.
    source_health.record_fetch(s, success=True, event_count=2)
    health = source_health.get_source_health(s)
    assert health["status"] == "HEALTHY"
    assert health["consecutive_failures"] == 0


def test_stale_when_success_stopped_arriving():
    s = _fresh_source()
    rec = source_health._rec(s)
    # Directly backdate last_success_at rather than sleeping in a test —
    # simulates "fetches used to succeed, but the last one was 7 hours
    # ago," which is exactly what STALE is for.
    old = datetime.now(timezone.utc) - timedelta(hours=7)
    rec["last_attempt_at"] = old
    rec["last_success_at"] = old
    rec["success_count"] = 1
    health = source_health.get_source_health(s, stale_after_hours=6.0)
    assert health["status"] == "STALE"
    assert health["stale_since"] is not None


def test_events_today_and_last_hour_windows():
    s = _fresh_source()
    rec = source_health._rec(s)
    now = datetime.now(timezone.utc)
    rec["events"].append((now - timedelta(hours=20), 10))  # within 24h, outside last hour
    rec["events"].append((now - timedelta(minutes=5), 3))   # within both windows
    rec["last_success_at"] = now
    rec["last_attempt_at"] = now
    health = source_health.get_source_health(s)
    assert health["events_today"] == 13
    assert health["events_last_hour"] == 3


def test_latency_and_error_tracked_on_success():
    s = _fresh_source()
    source_health.record_fetch(s, success=True, event_count=2, latency_ms=123.4)
    health = source_health.get_source_health(s)
    assert health["latency_ms"] == 123.4
    assert health["avg_latency_ms"] == 123.4
    assert health["latest_error"] is None


def test_latest_error_recorded_on_failure_and_cleared_on_recovery():
    s = _fresh_source()
    source_health.record_fetch(s, success=False, failure_kind="http", error="HTTP 503", latency_ms=50.0)
    health = source_health.get_source_health(s)
    assert health["latest_error"] == "HTTP 503"
    assert health["latency_ms"] == 50.0

    # A subsequent success clears the error (it's the LATEST error, not a
    # permanent stain) but latency history still averages across both.
    source_health.record_fetch(s, success=True, event_count=1, latency_ms=100.0)
    health = source_health.get_source_health(s)
    assert health["latest_error"] is None
    assert health["avg_latency_ms"] == 100.0  # only successful-fetch latencies count toward the average


def test_unknown_source_exposes_latency_and_error_keys_as_none():
    s = _fresh_source()
    health = source_health.get_source_health(s)
    assert health["latency_ms"] is None
    assert health["avg_latency_ms"] is None
    assert health["latest_error"] is None


def test_get_all_source_health_covers_known_sources():
    results = source_health.get_all_source_health()
    names = [r["source"] for r in results]
    assert "NSE" in names
    assert "BSE" in names
    assert "RSS/Economic Times" in names
    assert "RSS/Google News India" in names
    assert "RBI" in names
    assert "PIB" in names
    assert "SEBI" in names
    assert len(names) == len(source_health.KNOWN_SOURCES)
