"""Shared AI Search usage instrumentation.

This is the metrics contract consumed by the Ops Dashboard's "AI Search"
engine card and `ai_search_metrics` block (app/api/publishing.py::ops_overview,
surfaced on apps/web/app/admin/operations/page.tsx). It was originally V2-route
-only (`_SEARCH_STATS` living inside app/api/ai_search.py, incremented only by
`POST /api/ai/search`'s handler) — relocated here as part of the 6G Cutover
Gate so V2, V3-JSON (`/search/v3`), and V3-SSE (`/search/stream`) all report
into the same counters. Ops visibility must reflect real traffic regardless of
which pipeline implementation — or which `NEXT_PUBLIC_AI_SEARCH_V3` flag state
— actually served each request; it must not silently go blind the moment
traffic shifts between routes.
"""
from __future__ import annotations

from datetime import datetime, timezone

_STATS: dict = {
    "total": 0, "cache_hits": 0, "errors": 0, "timeouts": 0,
    "latency_ms_total": 0.0,
    "last_query_at": None, "last_success_at": None, "last_error_at": None, "last_error": None,
}


def record_query() -> None:
    """Call once per incoming request, before cache/pipeline dispatch."""
    _STATS["total"] += 1
    _STATS["last_query_at"] = datetime.now(timezone.utc).isoformat()


def record_cache_hit() -> None:
    """Call when a request was served from cache (in-process, Redis, or the
    V3 pipeline's own internal cache) without invoking the LLM pipeline."""
    _STATS["cache_hits"] += 1
    _STATS["last_success_at"] = _STATS["last_query_at"]


def record_success(latency_ms: float) -> None:
    """Call when a non-cached request completed the pipeline successfully."""
    _STATS["latency_ms_total"] += latency_ms
    _STATS["last_success_at"] = datetime.now(timezone.utc).isoformat()


def record_error(exc: Exception) -> None:
    """Call when a request raised. Timeout detection matches the original
    V2-only logic verbatim: substring match on the exception message, or a
    genuine TimeoutError instance."""
    _STATS["errors"] += 1
    _STATS["last_error_at"] = datetime.now(timezone.utc).isoformat()
    _STATS["last_error"] = str(exc)[:200]
    if "timeout" in str(exc).lower() or isinstance(exc, TimeoutError):
        _STATS["timeouts"] += 1


def get_stats() -> dict:
    resolved = _STATS["total"] - _STATS["cache_hits"]
    return {
        "total_today":     int(_STATS["total"]),
        "cache_hits":      int(_STATS["cache_hits"]),
        "errors":          int(_STATS["errors"]),
        "timeouts":        int(_STATS["timeouts"]),
        "avg_response_ms": round(_STATS["latency_ms_total"] / resolved, 0) if resolved > 0 else 0.0,
        "success_rate":    round((resolved - _STATS["errors"]) / resolved * 100, 1) if resolved > 0 else None,
        "last_query_at":   _STATS["last_query_at"],
        "last_success_at": _STATS["last_success_at"],
        "last_error_at":   _STATS["last_error_at"],
        "last_error":      _STATS["last_error"],
    }


def _reset_for_tests() -> None:
    """Test-only helper -- resets module-level state between test cases."""
    _STATS.update({
        "total": 0, "cache_hits": 0, "errors": 0, "timeouts": 0,
        "latency_ms_total": 0.0,
        "last_query_at": None, "last_success_at": None, "last_error_at": None, "last_error": None,
    })
