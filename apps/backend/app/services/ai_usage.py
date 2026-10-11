"""
AI usage instrumentation: what was called, by which feature, with what outcome and (when the provider says so) how many tokens.

Design rules (see app/db/models/ai_usage.py for the table-level honesty rules):
  * Instrumentation can never break or slow an AI call: every public function swallows its own errors, writes are queued in memory and flushed in batches off the request path,
    and the queue is bounded (oldest entries are dropped and counted, never blocking the caller).
  * No prompts, questions, responses or keys are ever recorded.
  * Tokens are the provider's own `usage` numbers. When the provider reported none the row says "unknown" (NULL), never 0.
  * No retry behaviour is changed here; this module only observes.

Feature tagging uses context variables: a feature wraps its work in `operation("article_generation")` (or the AI Search pipeline wrapper does it for a search request), and every LLM
attempt made inside inherits the tag, including attempts made by concurrently gathered sub-tasks. Anything not explicitly tagged is labelled `other:<calling module>` so no consumer is invisible.
"""
from __future__ import annotations

import asyncio
import sys
import time
import uuid
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

log = structlog.get_logger(__name__)

# ── Retention / size bounds ─────────────────────────────────────────────────────────────────────────────────
ATTEMPT_RETENTION_DAYS = 14          # raw per-attempt rows; older days are rolled into ai_usage_daily, then deleted
SEARCH_LOG_RETENTION_DAYS = 180
MAX_RAW_ROWS = 300_000               # hard safety cap on raw rows (oldest rolled up and deleted beyond this)
QUEUE_MAX = 5_000                    # in-memory buffer; beyond this the oldest queued rows are dropped (and counted)
FLUSH_BATCH = 50

# ── Context ───────────────────────────────────────────────────────────────────────────────────────────────────
_operation: ContextVar[str | None] = ContextVar("ai_usage_operation", default=None)
_request_id: ContextVar[str | None] = ContextVar("ai_usage_request_id", default=None)
_origin: ContextVar[str] = ContextVar("ai_usage_origin", default="internal")
_call_ctx: ContextVar[dict | None] = ContextVar("ai_usage_call", default=None)
_search_acc: ContextVar[dict | None] = ContextVar("ai_usage_search_acc", default=None)
_op_stats: ContextVar[dict | None] = ContextVar("ai_usage_op_stats", default=None)

_queue: deque = deque(maxlen=QUEUE_MAX)
_skips: dict[tuple, int] = {}              # (operation, provider, model, outcome) -> count of work skipped without an HTTP attempt
_stats = {"queued": 0, "written": 0, "dropped": 0, "flush_errors": 0}
_MAX_CONSECUTIVE_FLUSH_FAILURES = 5     # a transient database error (e.g. SQLite write contention) requeues the rows; only a persistent failure drops them
_consecutive_failures = 0
_flush_task: asyncio.Task | None = None


def _safe_reset(var: ContextVar, token) -> None:
    """Reset a context variable; if the generator/stream that set it is closed from a different task (a client disconnecting mid-stream), the reset is simply skipped."""
    try:
        var.reset(token)
    except (ValueError, RuntimeError):
        pass


@contextmanager
def operation(name: str, request_id: str | None = None, track: bool = False):
    """Tag every LLM attempt made inside this block (and its child tasks) with a feature name. With track=True the block also counts its real HTTP attempts and its cooldown skips,
    readable through `scope_stats()` (used to tell "every provider was merely cooling down" from "providers were really tried and failed")."""
    t1 = _operation.set(name)
    t2 = _request_id.set(request_id) if request_id else None
    t3 = _op_stats.set({"attempts": 0, "skips": 0, "successes": 0}) if track else None
    try:
        yield
    finally:
        _safe_reset(_operation, t1)
        if t2 is not None:
            _safe_reset(_request_id, t2)
        if t3 is not None:
            _safe_reset(_op_stats, t3)


def scope_stats() -> dict | None:
    """Counters of the innermost tracked operation scope, or None when not inside one."""
    return _op_stats.get()


def cooldown_only() -> bool:
    """True when, inside a tracked scope, work was skipped for cooldown and NOTHING was really attempted: no provider was actually tried, so a failure here says nothing about the event."""
    st = _op_stats.get()
    return bool(st and st["attempts"] == 0 and st["skips"] > 0)


def mark_api_request() -> None:
    """Called at the start of a user-facing AI Search route: the request counts as origin "api" (everything else that calls the pipeline in-process is "internal"). Set once per
    request task, no reset needed (the task ends with the request)."""
    try:
        _origin.set("api")
    except Exception:  # noqa: BLE001
        pass


@contextmanager
def origin(value: str):
    token = _origin.set(value)
    try:
        yield
    finally:
        _safe_reset(_origin, token)


def _caller_label() -> str:
    """Name of the first module outside the AI plumbing: used when a feature did not tag itself, so no consumer is invisible."""
    try:
        f = sys._getframe(3)
        for _ in range(14):
            mod = f.f_globals.get("__name__", "")
            if mod and not mod.startswith(("app.services.ai_service", "app.services.ai_usage", "app.services.fallback_chain_provider", "asyncio", "contextlib")):
                return ("other:" + ".".join(mod.split(".")[-2:]))[:48]
            f = f.f_back
            if f is None:
                break
    except Exception:  # noqa: BLE001
        pass
    return "other:unknown"


# ── Call / attempt recording (called from ai_service) ─────────────────────────────────────────────────────────

def begin_call():
    """Start of one fallback-chain call. Returns an opaque token for end_call(). Never raises."""
    try:
        ctx = {"id": uuid.uuid4().hex[:12], "n": 0, "op": _operation.get() or _caller_label()}
        acc = _search_acc.get()
        if acc is not None:
            acc["calls"] += 1
        return _call_ctx.set(ctx)
    except Exception:  # noqa: BLE001
        return None


def end_call(token) -> None:
    try:
        if token is not None:
            _safe_reset(_call_ctx, token)
    except Exception:  # noqa: BLE001
        pass


def begin_attempt(provider: str, model: str) -> dict:
    try:
        ctx = _call_ctx.get()
        if ctx is None:                                  # an attempt outside any tracked call (direct provider call): still recorded
            ctx = {"id": uuid.uuid4().hex[:12], "n": 0, "op": _operation.get() or _caller_label()}
        ctx["n"] += 1
        st = _op_stats.get()
        if st is not None:
            st["attempts"] += 1
        return {"ts": datetime.now(timezone.utc), "t0": time.monotonic(), "operation": ctx["op"], "call_id": ctx["id"], "attempt_no": ctx["n"],
                "request_id": _request_id.get(), "provider": provider, "model": (model or "")[:96], "outcome": "other", "http_status": None,
                "input_tokens": None, "output_tokens": None}
    except Exception:  # noqa: BLE001
        return {"_broken": True}


def set_outcome(att: dict, outcome: str, status: int | None = None) -> None:
    if att.get("_broken"):
        return
    att["outcome"] = outcome
    att["http_status"] = status


def set_usage(att: dict, usage: dict | None) -> None:
    """Provider-reported usage only. Anything the provider did not report stays None (unknown)."""
    if att.get("_broken") or not isinstance(usage, dict):
        return

    def num(*keys):
        for k in keys:
            v = usage.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0:
                return int(v)
        return None

    att["input_tokens"] = num("prompt_tokens", "input_tokens")
    att["output_tokens"] = num("completion_tokens", "output_tokens")


def finish_attempt(att: dict) -> None:
    try:
        if att.get("_broken"):
            return
        latency = int((time.monotonic() - att["t0"]) * 1000)
        known = att["input_tokens"] is not None and att["output_tokens"] is not None
        row = {"ts": att["ts"], "operation": att["operation"], "call_id": att["call_id"], "request_id": att["request_id"], "attempt_no": att["attempt_no"],
               "provider": att["provider"], "model": att["model"], "outcome": att["outcome"], "http_status": att["http_status"], "latency_ms": latency,
               "input_tokens": att["input_tokens"] if known else None, "output_tokens": att["output_tokens"] if known else None,
               "usage_source": "provider" if known else "unknown", "n": 1}
        _enqueue(row)
        st = _op_stats.get()
        if st is not None and att["outcome"] == "success":
            st["successes"] += 1
        acc = _search_acc.get()
        if acc is not None:
            acc["attempts"] += 1
            if known:
                acc["in"] = (acc["in"] or 0) + att["input_tokens"]
                acc["out"] = (acc["out"] or 0) + att["output_tokens"]
            elif att["outcome"] == "success":
                acc["unknown"] += 1
    except Exception:  # noqa: BLE001
        pass


def note_skip(provider: str, model: str) -> None:
    """A (provider, model) skipped because it is cooling down: not an HTTP attempt, so counted in aggregate rather than as rows."""
    try:
        ctx = _call_ctx.get()
        op = (ctx or {}).get("op") or _operation.get() or _caller_label()
        key = (op, provider, (model or "")[:96], "skipped_cooldown")
        _skips[key] = _skips.get(key, 0) + 1
        st = _op_stats.get()
        if st is not None:
            st["skips"] += 1
    except Exception:  # noqa: BLE001
        pass


def note_skipped_work(operation_name: str, reason: str, n: int = 1) -> None:
    """Whole units of work skipped on purpose (e.g. an enrichment tick with no eligible provider). Recorded separately from attempted and failed work, as outcome "skipped_<reason>"."""
    try:
        key = (operation_name[:48], "-", "-", ("skipped_" + reason)[:24])
        _skips[key] = _skips.get(key, 0) + n
    except Exception:  # noqa: BLE001
        pass


def _enqueue(row: dict) -> None:
    if len(_queue) == _queue.maxlen:
        _stats["dropped"] += 1
    _queue.append(row)
    _stats["queued"] += 1
    if len(_queue) >= FLUSH_BATCH:
        _kick_flush()


def _kick_flush() -> None:
    global _flush_task
    try:
        if _flush_task is not None and not _flush_task.done():
            return
        _flush_task = asyncio.get_running_loop().create_task(flush_pending())
    except RuntimeError:                                  # no running loop (sync context): the scheduled flush picks it up
        pass


# ── AI Search request recording ───────────────────────────────────────────────────────────────────────────────

def new_search_accumulator() -> dict:
    return {"calls": 0, "attempts": 0, "in": None, "out": None, "unknown": 0}


@contextmanager
def search_request(query_len: int):
    """Wrap one AI Search request. Yields a recorder; call `rec.finish(...)` exactly once in a finally block."""
    rid = uuid.uuid4().hex[:16]
    acc = new_search_accumulator()
    t_acc = _search_acc.set(acc)
    t_op = _operation.set("ai_search")
    t_rid = _request_id.set(rid)
    t0 = time.monotonic()
    state: dict[str, Any] = {"done": False}

    def finish(outcome: str, degraded_reason: str | None = None, specialist: str | None = None, cache_hit: bool | None = None) -> None:
        if state["done"]:
            return
        state["done"] = True
        try:
            _enqueue_search({"ts": datetime.now(timezone.utc), "request_id": rid, "origin": _origin.get(), "outcome": outcome, "degraded_reason": (degraded_reason or None) and str(degraded_reason)[:48],
                             "specialist": (specialist or None) and str(specialist)[:24], "cache_hit": cache_hit, "latency_ms": int((time.monotonic() - t0) * 1000), "query_len": query_len,
                             "llm_calls": acc["calls"], "llm_attempts": acc["attempts"], "input_tokens": acc["in"], "output_tokens": acc["out"], "tokens_unknown_attempts": acc["unknown"]})
        except Exception:  # noqa: BLE001
            pass

    try:
        yield finish
    finally:
        _safe_reset(_search_acc, t_acc)
        _safe_reset(_operation, t_op)
        _safe_reset(_request_id, t_rid)


_search_queue: deque = deque(maxlen=QUEUE_MAX)


def _enqueue_search(row: dict) -> None:
    _search_queue.append(row)
    _kick_flush()


# ── Flush ─────────────────────────────────────────────────────────────────────────────────────────────────────

async def flush_pending(max_rows: int = 2000) -> int:
    """Write queued rows. Never raises; on a database error the rows are dropped and counted (instrumentation must not accumulate unbounded memory or break callers)."""
    from sqlalchemy import insert
    from app.db.models.ai_usage import AISearchRequestLog, AIUsageAttempt
    from app.db.session import AsyncSessionLocal

    rows = []
    while _queue and len(rows) < max_rows:
        rows.append(_queue.popleft())
    skip_rows = []
    if _skips:
        now = datetime.now(timezone.utc)
        for (op, provider, model, outcome), n in list(_skips.items()):
            skip_rows.append({"ts": now, "operation": op, "call_id": None, "request_id": None, "attempt_no": None, "provider": provider, "model": model, "outcome": outcome,
                              "http_status": None, "latency_ms": None, "input_tokens": None, "output_tokens": None, "usage_source": "unknown", "n": n})
        _skips.clear()
    searches = []
    while _search_queue and len(searches) < max_rows:
        searches.append(_search_queue.popleft())
    if not (rows or skip_rows or searches):
        return 0
    try:
        async with AsyncSessionLocal() as db:
            if rows or skip_rows:
                await db.execute(insert(AIUsageAttempt), rows + skip_rows)
            if searches:
                await db.execute(insert(AISearchRequestLog), searches)
            await db.commit()
        _stats["written"] += len(rows) + len(skip_rows) + len(searches)
        global _consecutive_failures
        _consecutive_failures = 0
        return len(rows) + len(skip_rows) + len(searches)
    except Exception as exc:  # noqa: BLE001
        _stats["flush_errors"] += 1
        _consecutive_failures += 1
        if _consecutive_failures <= _MAX_CONSECUTIVE_FLUSH_FAILURES:
            _queue.extendleft(reversed(rows))                 # keep them for the next flush (still bounded by the queue's maxlen)
            _search_queue.extendleft(reversed(searches))
            for r in skip_rows:
                key = (r["operation"], r["provider"], r["model"], r["outcome"])
                _skips[key] = _skips.get(key, 0) + r["n"]
            log.warning("ai_usage.flush_failed_will_retry", error=str(exc)[:160], rows=len(rows) + len(skip_rows) + len(searches), consecutive=_consecutive_failures)
        else:
            _stats["dropped"] += len(rows) + len(skip_rows) + len(searches)
            log.warning("ai_usage.flush_failed_dropped", error=str(exc)[:160], dropped=len(rows) + len(skip_rows) + len(searches))
        return 0


# ── Retention: roll up, then prune ────────────────────────────────────────────────────────────────────────────

def _naive_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


async def rollup_and_prune(db, now: datetime | None = None) -> dict:
    """Aggregate raw attempt rows older than the retention window into ai_usage_daily (adding to any existing row), delete them, enforce the hard row cap, and prune the search log.
    One transaction: a failure leaves everything as it was."""
    from sqlalchemy import delete, func, select
    from app.db.models.ai_usage import AISearchRequestLog, AIUsageAttempt, AIUsageDaily

    now = now or datetime.now(timezone.utc)
    cutoff = _naive_utc(now) - timedelta(days=ATTEMPT_RETENTION_DAYS)
    out = {"rolled_up_rows": 0, "deleted_raw": 0, "deleted_by_cap": 0, "deleted_search_rows": 0}

    async def _roll(where) -> int:
        rows = (await db.execute(select(AIUsageAttempt).where(where))).scalars().all()
        agg: dict[tuple, dict] = {}
        for r in rows:
            ts = r.ts
            day = (ts.date() if isinstance(ts, datetime) else datetime.fromisoformat(str(ts)).date()).isoformat()
            a = agg.setdefault((day, r.operation, r.provider, r.model, r.outcome), {"attempts": 0, "in": 0, "out": 0, "with_usage": 0, "lat": 0.0})
            a["attempts"] += r.n or 1
            a["lat"] += float(r.latency_ms or 0) * (r.n or 1)
            if r.input_tokens is not None and r.output_tokens is not None:
                a["in"] += r.input_tokens
                a["out"] += r.output_tokens
                a["with_usage"] += 1
        for (day, op, prov, model, outcome), a in agg.items():
            existing = (await db.execute(select(AIUsageDaily).where(AIUsageDaily.day == day, AIUsageDaily.operation == op, AIUsageDaily.provider == prov,
                                                                       AIUsageDaily.model == model, AIUsageDaily.outcome == outcome))).scalars().first()
            if existing:
                existing.attempts += a["attempts"]
                existing.input_tokens += a["in"]
                existing.output_tokens += a["out"]
                existing.attempts_with_usage += a["with_usage"]
                existing.latency_ms_sum += a["lat"]
            else:
                db.add(AIUsageDaily(day=day, operation=op, provider=prov, model=model, outcome=outcome, attempts=a["attempts"], input_tokens=a["in"], output_tokens=a["out"],
                                    attempts_with_usage=a["with_usage"], latency_ms_sum=a["lat"]))
        ids = [r.id for r in rows]
        for i in range(0, len(ids), 500):
            await db.execute(delete(AIUsageAttempt).where(AIUsageAttempt.id.in_(ids[i:i + 500])))
        return len(rows)

    n = await _roll(AIUsageAttempt.ts < cutoff)
    out["rolled_up_rows"] = out["deleted_raw"] = n
    total = (await db.execute(select(func.count()).select_from(AIUsageAttempt))).scalar_one()
    if total > MAX_RAW_ROWS:
        threshold_id = (await db.execute(select(AIUsageAttempt.id).order_by(AIUsageAttempt.id.desc()).offset(MAX_RAW_ROWS).limit(1))).scalar_one_or_none()
        if threshold_id is not None:
            out["deleted_by_cap"] = await _roll(AIUsageAttempt.id <= threshold_id)
    sc = _naive_utc(now) - timedelta(days=SEARCH_LOG_RETENTION_DAYS)
    res = await db.execute(delete(AISearchRequestLog).where(AISearchRequestLog.ts < sc))
    out["deleted_search_rows"] = res.rowcount or 0
    await db.commit()
    return out


# ── Pricing (estimates only; unknown stays unknown) ───────────────────────────────────────────────────────────

# USD per 1M tokens (input, output). A model appears here ONLY when its rate is documented for the account actually used. Free-tier accounts are 0.0 with basis "free_tier".
# Everything not listed is unpriced: cost is reported as unknown for it, never guessed.
_FREE = (0.0, 0.0, "free_tier")
PRICES: dict[tuple[str, str], tuple[float, float, str]] = {
    ("requesty", "google/gemma-4-31b-it"): (0.0, 0.0, "requesty_list_price"),
}
_FREE_PROVIDERS = ("groq", "gemini", "openrouter", "mistral")        # the keys in use are free-tier accounts (see the provider audit); a paid plan must be added to PRICES explicitly


def price_for(provider: str, model: str) -> tuple[float, float, str] | None:
    p = PRICES.get((provider, model))
    if p:
        return p
    if provider in _FREE_PROVIDERS and (provider != "openrouter" or model.endswith(":free")):
        return _FREE
    return None


# ── Report ────────────────────────────────────────────────────────────────────────────────────────────────────

MAX_REPORT_HOURS = ATTEMPT_RETENTION_DAYS * 24      # raw attempt rows only exist for this long; older history lives in ai_usage_daily


async def usage_report(db, hours: int = 24, now: datetime | None = None) -> dict:
    """Per-feature and per-model usage for the last `hours` (clamped to the raw retention window). Computed with SQL aggregation, so cost depends on the number of distinct
    feature/provider/model/outcome groups, never on how many raw rows there are. Counts are exact for what was recorded; tokens are the provider-reported ones only (attempts whose usage
    is unknown are counted beside them); cost covers only attempts with known tokens and a documented price."""
    from sqlalchemy import and_, case, func, select
    from app.db.models.ai_usage import AISearchRequestLog, AIUsageAttempt as A

    hours = max(1, min(int(hours), MAX_REPORT_HOURS))
    now = now or datetime.now(timezone.utc)
    start = _naive_utc(now) - timedelta(hours=hours)
    known = and_(A.input_tokens.is_not(None), A.output_tokens.is_not(None))
    groups = (await db.execute(
        select(A.operation, A.provider, A.model, A.outcome, func.coalesce(func.sum(A.n), 0),
               func.coalesce(func.sum(case((known, A.input_tokens), else_=0)), 0), func.coalesce(func.sum(case((known, A.output_tokens), else_=0)), 0),
               func.coalesce(func.sum(case((known, A.n), else_=0)), 0))
        .where(A.ts >= start).group_by(A.operation, A.provider, A.model, A.outcome))).all()
    calls = dict((await db.execute(select(A.operation, func.count(func.distinct(A.call_id))).where(A.ts >= start, A.call_id.is_not(None)).group_by(A.operation))).all())
    calls_ok = dict((await db.execute(select(A.operation, func.count(func.distinct(A.call_id))).where(A.ts >= start, A.call_id.is_not(None), A.outcome == "success").group_by(A.operation))).all())

    features: dict[str, dict] = {}
    models: dict[tuple, dict] = {}
    for op, prov, model, outcome, n, tin, tout, nknown in groups:
        f = features.setdefault(op, {"attempts": 0, "successes": 0, "failures": {}, "skipped": {}, "input_tokens": 0, "output_tokens": 0, "attempts_with_usage": 0,
                                     "success_attempts_unknown_usage": 0, "cost_usd": 0.0, "cost_covered_attempts": 0, "cost_unpriced_attempts": 0})
        if outcome.startswith("skipped_"):
            f["skipped"][outcome] = f["skipped"].get(outcome, 0) + n
            continue
        m = models.setdefault((prov, model), {"attempts": 0, "successes": 0, "failures": 0, "input_tokens": 0, "output_tokens": 0, "attempts_with_usage": 0,
                                              "success_attempts_unknown_usage": 0, "cost_usd": 0.0, "cost_covered_attempts": 0})
        f["attempts"] += n
        m["attempts"] += n
        if outcome == "success":
            f["successes"] += n
            m["successes"] += n
            f["success_attempts_unknown_usage"] += n - nknown
            m["success_attempts_unknown_usage"] += n - nknown
        else:
            f["failures"][outcome] = f["failures"].get(outcome, 0) + n
            m["failures"] += n
        for d in (f, m):
            d["input_tokens"] += tin
            d["output_tokens"] += tout
            d["attempts_with_usage"] += nknown
        if nknown:
            pr = price_for(prov, model)
            if pr:
                c = (tin * pr[0] + tout * pr[1]) / 1e6
                for d in (f, m):
                    d["cost_usd"] += c
                    d["cost_covered_attempts"] += nknown
            else:
                f["cost_unpriced_attempts"] += nknown

    feat_out = {}
    for op, f in sorted(features.items()):
        c, ok = calls.get(op, 0), calls_ok.get(op, 0)
        feat_out[op] = {**f, "calls": c, "calls_succeeded": ok, "call_success_rate": round(ok / c, 3) if c else None,
                        "attempt_success_rate": round(f["successes"] / f["attempts"], 3) if f["attempts"] else None,
                        "skipped_total": sum(f["skipped"].values()), "cost_usd": round(f["cost_usd"], 6),
                        "cost_note": "covers only attempts with provider-reported tokens and a documented price"}
    model_out = [{"provider": p, "model": mo, **v, "cost_usd": round(v["cost_usd"], 6)} for (p, mo), v in sorted(models.items(), key=lambda kv: -kv[1]["attempts"])]

    S = AISearchRequestLog
    srows = (await db.execute(
        select(S.origin, func.count(), func.coalesce(func.sum(case((S.outcome == "answered", 1), else_=0)), 0), func.coalesce(func.sum(case((S.outcome == "degraded", 1), else_=0)), 0),
               func.coalesce(func.sum(case((S.outcome == "error", 1), else_=0)), 0), func.coalesce(func.sum(case((S.cache_hit.is_(True), 1), else_=0)), 0),
               func.coalesce(func.sum(S.llm_calls), 0), func.coalesce(func.sum(S.llm_attempts), 0), func.sum(S.input_tokens), func.sum(S.output_tokens),
               func.coalesce(func.sum(case((S.tokens_unknown_attempts > 0, 1), else_=0)), 0), func.avg(S.latency_ms))
        .where(S.ts >= start).group_by(S.origin))).all()
    reasons = (await db.execute(select(S.origin, S.degraded_reason, func.count()).where(S.ts >= start, S.degraded_reason.is_not(None)).group_by(S.origin, S.degraded_reason))).all()

    def block(origin_name: str) -> dict:
        rs = [r for r in srows if r[0] == origin_name]
        tot = lambda i: sum((r[i] or 0) for r in rs)
        n = tot(1)
        in_known = [r[8] for r in rs if r[8] is not None]
        out_known = [r[9] for r in rs if r[9] is not None]
        deg: dict[str, int] = {}
        for o, reason, cnt in reasons:
            if o == origin_name:
                deg[reason] = deg.get(reason, 0) + cnt
        return {"requests": n, "answered": tot(2), "degraded": tot(3), "error": tot(4), "cache_hits": tot(5), "llm_calls": tot(6), "llm_attempts": tot(7),
                "input_tokens_known": sum(in_known) if in_known else None, "output_tokens_known": sum(out_known) if out_known else None, "requests_with_unknown_tokens": tot(10),
                "degraded_reasons": deg, "avg_latency_ms": round(sum((r[11] or 0) * r[1] for r in rs) / n) if n else None}

    return {"window_hours": hours, "from_utc": start.isoformat(), "to_utc": _naive_utc(now).isoformat(),
            "ai_search": {"user_requests": block("api"), "internal_pipeline_calls": block("internal")},
            "features": feat_out, "models": model_out, "recorder": {**_stats, "queued_now": len(_queue)},
            "gaps": ["Tokens are provider-reported only; attempts without usage are counted in *_unknown_usage, never as zero.",
                     "Skipped work (cooldown skips, ticks skipped for no capacity) is counted per feature under `skipped`; it is not an attempt and not a failure.",
                     "Models without a documented price are excluded from cost (cost_unpriced_attempts)."]}


def _count(items) -> dict:
    out: dict[str, int] = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out
