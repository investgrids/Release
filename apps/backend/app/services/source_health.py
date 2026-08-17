"""
Source-level health tracking for ingestion providers (NSE, BSE, each of
the 6 RSS feeds individually, RBI, PIB, SEBI).

Reuses app.services.aipe.perf_stats's existing architecture choice —
in-process, resets on deploy, no new DB table — rather than inventing a
new persistence layer for what is, in a single long-running Railway
process, genuinely transient operational telemetry. Extends it with the
fields that pattern didn't have and this audit's Phase 6 asked for:
events_today/last_hour, HTTP-vs-parse failure counts, consecutive-failure
streaks, and a HEALTHY/DEGRADED/STALE/FAILED/UNKNOWN classification
distinct from publishing.py's compute_health (that one is shaped for
AIPE engines — queue size, latency, retry rate; a data source's real
question is simpler: is it still successfully returning data, and is
"zero events" a quiet period or a break).

Confirmed live via this same 2026-08 audit: BSE has been failing in
production for multiple days with zero dashboard signal, and SEBI/RSS
per-feed failures were previously invisible even in logs. This module is
what /api/sources/health (Phase 7, not yet built) would read from — the
tracking itself is the prerequisite either way.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

FailureKind = Literal["http", "parse"] | None

_MAX_SAMPLES = 500  # bounded ring buffer of (timestamp, event_count) per source

_SOURCES: dict[str, dict[str, Any]] = {}

# Every source this module is meant to track — used by get_all_source_
# health's default and to make an untracked-but-expected source visibly
# UNKNOWN rather than just absent from the dashboard.
KNOWN_SOURCES = [
    "NSE", "BSE",
    "RSS/Economic Times", "RSS/Moneycontrol", "RSS/NDTV Profit",
    "RSS/Business Standard", "RSS/Livemint", "RSS/Google News India",
    "RBI", "PIB", "SEBI", "Fed",
    # Phase 5F.3 — macro_rates (Phase 5C) had zero source_health calls
    # until this fix, exactly the same invisible-failure class BSE was
    # before Phase 5D found it.
    "US Treasury", "Fed H.15", "RBI WSS",
]


def _rec(source: str) -> dict[str, Any]:
    return _SOURCES.setdefault(source, {
        "last_attempt_at": None,
        "last_success_at": None,
        "last_event_received_at": None,
        "success_count": 0,
        "failure_count": 0,
        "http_failure_count": 0,
        "parse_failure_count": 0,
        "consecutive_failures": 0,
        "events": deque(maxlen=_MAX_SAMPLES),  # (timestamp, event_count)
        "last_latency_ms": None,
        "latencies": deque(maxlen=_MAX_SAMPLES),  # successful-fetch latencies only
        "last_error": None,
    })


def record_fetch(
    source: str, *, success: bool, event_count: int = 0, failure_kind: FailureKind = None,
    latency_ms: float | None = None, error: str | None = None,
) -> None:
    """Called once per fetch attempt by each provider's ingestion path.
    event_count=0 on a successful fetch is a legitimate, common outcome
    (a quiet period) — it's recorded distinctly from a failed fetch so
    get_source_health can tell the two apart.

    latency_ms/error are optional (2026-08 spec: "latest error", "latency
    if available") — not every call site can measure both cheaply (RSS's
    per-feed loop can; the shared BaseProvider.fetch_and_normalize() wraps
    fetch_latest() so it can too), so both default to not-recorded rather
    than a fabricated 0/empty-string."""
    now = datetime.now(timezone.utc)
    rec = _rec(source)
    rec["last_attempt_at"] = now
    if latency_ms is not None:
        rec["last_latency_ms"] = latency_ms
    if success:
        rec["last_success_at"] = now
        rec["success_count"] += 1
        rec["consecutive_failures"] = 0
        rec["last_error"] = None
        if event_count > 0:
            rec["last_event_received_at"] = now
        rec["events"].append((now, event_count))
        if latency_ms is not None:
            rec["latencies"].append(latency_ms)
    else:
        rec["failure_count"] += 1
        rec["consecutive_failures"] += 1
        if error is not None:
            rec["last_error"] = error[:500]
        if failure_kind == "http":
            rec["http_failure_count"] += 1
        elif failure_kind == "parse":
            rec["parse_failure_count"] += 1


def _events_since(rec: dict, since: datetime) -> int:
    return sum(c for ts, c in rec["events"] if ts >= since)


def get_source_health(source: str, *, stale_after_hours: float = 6.0) -> dict[str, Any]:
    """HEALTHY / DEGRADED / STALE / FAILED / UNKNOWN.

    UNKNOWN — never observed at all (e.g. a source not yet wired in, or
      the process just started).
    FAILED — 3+ consecutive failed fetch attempts, or every attempt ever
      made has failed.
    STALE — fetches are succeeding, but it's been longer than
      stale_after_hours since the last one that returned any events at
      all could still count as HEALTHY if THIS check used last_event_
      received_at — deliberately uses last_success_at instead, because a
      source can be legitimately quiet (no real news that hour) without
      being broken; "zero events for a while" alone is not FAILED or
      STALE, only "the fetch itself stopped succeeding" is.
    DEGRADED — currently succeeding, but has at least one recent failure
      in its history (a partial/flaky pattern worth watching).
    HEALTHY — succeeding, no recent failures.
    """
    if source not in _SOURCES:
        return {
            "source": source, "status": "UNKNOWN",
            "last_attempt_at": None, "last_success_at": None, "last_event_received_at": None,
            "events_today": 0, "events_last_hour": 0,
            "success_count": 0, "failure_count": 0,
            "http_failure_count": 0, "parse_failure_count": 0,
            "consecutive_failures": 0, "stale_since": None,
            "latency_ms": None, "avg_latency_ms": None, "latest_error": None,
        }
    rec = _SOURCES[source]
    now = datetime.now(timezone.utc)
    last_success = rec["last_success_at"]
    consecutive = rec["consecutive_failures"]

    if last_success is None:
        status = "FAILED" if rec["last_attempt_at"] is not None else "UNKNOWN"
    elif consecutive >= 3:
        status = "FAILED"
    elif (now - last_success) > timedelta(hours=stale_after_hours):
        status = "STALE"
    elif consecutive > 0:
        status = "DEGRADED"
    else:
        status = "HEALTHY"

    stale_since = last_success if status == "STALE" else None
    latencies = rec["latencies"]
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else None

    return {
        "source": source,
        "status": status,
        "last_attempt_at": rec["last_attempt_at"].isoformat() if rec["last_attempt_at"] else None,
        "last_success_at": last_success.isoformat() if last_success else None,
        "last_event_received_at": rec["last_event_received_at"].isoformat() if rec["last_event_received_at"] else None,
        "events_today": _events_since(rec, now - timedelta(hours=24)),
        "events_last_hour": _events_since(rec, now - timedelta(hours=1)),
        "success_count": rec["success_count"],
        "failure_count": rec["failure_count"],
        "http_failure_count": rec["http_failure_count"],
        "parse_failure_count": rec["parse_failure_count"],
        "consecutive_failures": consecutive,
        "stale_since": stale_since.isoformat() if stale_since else None,
        "latency_ms": rec["last_latency_ms"],
        "avg_latency_ms": avg_latency,
        "latest_error": rec["last_error"],
    }


def get_all_source_health(sources: list[str] | None = None, *, stale_after_hours: float = 6.0) -> list[dict[str, Any]]:
    return [get_source_health(s, stale_after_hours=stale_after_hours) for s in (sources or KNOWN_SOURCES)]
