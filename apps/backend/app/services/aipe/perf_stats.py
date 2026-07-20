"""
Shared, in-process performance counters for the AIPE pipeline stages —
feeds the Ops Dashboard's "Engine Performance" panel with real
cumulative-average timings rather than fabricated numbers. Same
"resets on deploy" pattern as publisher.py's _STATS.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

_TIMES: dict[str, list[float]] = {
    "validation": [], "campaign": [], "update": [],
}
_MAX_SAMPLES = 200  # bounded ring buffer per stage — avoids unbounded memory growth


def record(stage: str, seconds: float) -> None:
    bucket = _TIMES.setdefault(stage, [])
    bucket.append(seconds)
    if len(bucket) > _MAX_SAMPLES:
        del bucket[0]


@contextmanager
def timed(stage: str):
    start = time.monotonic()
    try:
        yield
    finally:
        record(stage, time.monotonic() - start)


def get_performance_stats() -> dict:
    def avg(stage: str) -> float:
        samples = _TIMES.get(stage) or []
        return round(sum(samples) / len(samples), 3) if samples else 0.0

    return {
        "avg_validation_time_s": avg("validation"),
        "avg_campaign_time_s":   avg("campaign"),
        "avg_update_time_s":     avg("update"),
    }


# ── Per-engine last-run tracking (Engine Health panel) ────────────────────────
# Lightweight — just the last-run/last-success timestamps and a rolling error
# count each named engine's own cycle function reports on exit. Not a
# replacement for each engine's own detailed stats (publisher.py's _STATS
# already has richer AIPE-specific numbers); this is the common denominator
# every engine can report so the dashboard can show one consistent table.

_ENGINE_RUNS: dict[str, dict] = {}
_ENGINE_LATENCIES: dict[str, list[float]] = {}


def mark_engine_run(engine: str, success: bool, error: str | None = None, duration_s: float | None = None) -> None:
    from datetime import datetime, timezone
    rec = _ENGINE_RUNS.setdefault(engine, {
        "last_run": None, "last_success": None, "errors_today": 0, "last_error": None,
        "runs_total": 0, "runs_success": 0,
    })
    now = datetime.now(timezone.utc)
    rec["last_run"] = now.isoformat()
    rec["runs_total"] += 1
    if success:
        rec["last_success"] = now.isoformat()
        rec["runs_success"] += 1
    else:
        rec["errors_today"] += 1
        rec["last_error"] = error
    if duration_s is not None:
        bucket = _ENGINE_LATENCIES.setdefault(engine, [])
        bucket.append(duration_s)
        if len(bucket) > _MAX_SAMPLES:
            del bucket[0]


def get_engine_runs() -> dict[str, dict]:
    return dict(_ENGINE_RUNS)


def get_engine_latency_s(engine: str) -> float | None:
    samples = _ENGINE_LATENCIES.get(engine) or []
    return round(sum(samples) / len(samples), 3) if samples else None
