"""
Step 3.4H.4: production-chain latency measurement. MEASUREMENT ONLY: no setting, prompt, provider order or reasoning parameter is changed; no OpenAI/Luna call.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4h/h4_production_chain.py

Four requests, each run exactly once, never retried:
  SR2, CC2, CR1   real end-to-end requests on the real provider chain (frozen wording from questions.json), under the route's request deadline (RD.scope(), the same call the HTTP routes make)
  SR2-slow        the same SR2 question with the FIRST specialist provider attempt replaced by a hang (no real quota is spent waiting); every later attempt uses the real chain
Records per request: retrieval (news snapshot state/latency, failures), classifier (invoked, latency, attempts), each specialist provider attempt (tier, model, start time, remaining budget at start, duration, outcome),
Gate A/B, assembly, total wall, remaining deadline at completion. Never records keys or headers; failure reasons are short codes.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent

from app.core.config import settings  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service as S  # noqa: E402
from app.services import news_fetcher as NF  # noqa: E402
from app.services import request_deadline as RD  # noqa: E402
from app.services.ai_search import cache as cache_mod  # noqa: E402
from app.services.ai_search import evidence as EV  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search import retrieval as RT  # noqa: E402
from app.services.ai_search.response_finalize import finalize_v3_response  # noqa: E402

QS = {q["id"]: q for q in json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]}
RSS_SOURCES = {"Google News", "Economic Times", "Moneycontrol", "Business Standard", "Livemint", "NDTV Profit"}
REC: dict = {}


def r3(x):
    return None if x is None else round(x, 3)


def rel():
    return r3(time.monotonic() - REC["t0"])


# ── instrumentation (wrappers only; behaviour is unchanged except the optional synthetic hang) ───────────────────────────────

_orig_attempt = S._attempt
_orig_call_provider = S._call_provider
_orig_cwf = S._call_with_fallback
_orig_classify = mp_mod._classify_market_pulse_llm
_orig_collect = EV.collect
_orig_live = RT.get_live_news


async def call_provider_w(*args, failure_log=None):
    if REC.get("slow") and args[5] > 10 and not REC.get("slow_done"):
        REC["slow_done"] = True
        REC["slow_injected_at"] = rel()
        await asyncio.sleep(3600)                      # a provider that never answers; the request deadline must cancel it
    return await _orig_call_provider(*args, failure_log=failure_log)


async def attempt_w(tier, provider, url, key, model, prompt, system, max_tokens, headers, failure_log):
    label = "classifier" if max_tokens <= 10 else "specialist"
    fl = failure_log if failure_log is not None else []
    n0 = len(fl)
    use, cap = RD.usable(), RD.attempt_cap()
    ent = {"call": label, "tier": tier, "model": model, "start_s": rel(), "remaining_at_start_s": r3(RD.remaining()), "usable_at_start_s": r3(use),
           "attempt_budget_s": r3(min(cap, use)) if use is not None and cap is not None else None, "synthetic_hang": False}
    if REC.get("slow") and label == "specialist" and not REC.get("slow_done"):
        ent["synthetic_hang"] = True
    t = time.monotonic()
    try:
        text, stop = await _orig_attempt(tier, provider, url, key, model, prompt, system, max_tokens, headers, fl)
    except asyncio.CancelledError:
        ent.update(duration_s=r3(time.monotonic() - t), outcome="cancelled_by_caller")
        REC["attempts"].append(ent)
        raise
    reasons = [x.get("reason") for x in fl[n0:]]
    if text:
        outcome = "success"
    elif "deadline" in reasons:
        outcome = "deadline_cancellation"
    elif "timeout" in reasons:
        outcome = "full_cap_timeout"
    else:
        outcome = "provider_failure" if reasons else "empty_response"
    ent.update(duration_s=r3(time.monotonic() - t), outcome=outcome, reasons=reasons, stop_chain=bool(stop))
    REC["attempts"].append(ent)
    return text, stop


async def cwf_w(prompt, system="", max_tokens=200, failure_log=None, *, priority):
    label = "classifier" if max_tokens <= 10 else "specialist_or_other"
    fl = failure_log if failure_log is not None else []
    t = time.monotonic()
    start = rel()
    text = await _orig_cwf(prompt, system, max_tokens, failure_log=fl, priority=priority)
    REC["chains"].append({"call": label, "max_tokens": max_tokens, "start_s": start, "duration_s": r3(time.monotonic() - t), "returned_text": bool(text),
                          "chain_reasons": [{"model": x.get("model"), "tier": x.get("provider"), "reason": x.get("reason")} for x in fl]})
    return text


async def classify_w(query):
    t = time.monotonic()
    REC["classifier"] = {"invoked": True, "start_s": rel()}
    verdict = await _orig_classify(query)
    REC["classifier"].update(duration_s=r3(time.monotonic() - t), verdict=verdict, sub_budget_s=settings.ai_search_classifier_budget_seconds)
    return verdict


async def collect_w(query, intent_data, entities, db):
    t = time.monotonic()
    b = await _orig_collect(query, intent_data, entities, db)
    REC["retrieval"] = {"ms": round((time.monotonic() - t) * 1000), "retrieval_failures": dict(getattr(b, "retrieval_failures", {}) or {}),
                        "events": len(b.events), "news": len(b.news), "policies": len(b.policies)}
    return b


async def live_w(limit=20):
    has, fresh = NF._usable_snapshot(time.time())
    state = "cold" if not has else ("fresh" if fresh else "stale")
    t = time.monotonic()
    out = await _orig_live(limit)
    REC["news"] = {"snapshot_state": state, "ms": round((time.monotonic() - t) * 1000, 1), "status": NF.live_news_status(), "items": len(out)}
    return out


S._attempt = attempt_w
S._call_provider = call_provider_w
S._call_with_fallback = cwf_w
mp_mod._call_with_fallback = cwf_w
mp_mod._classify_market_pulse_llm = classify_w
EV.collect = collect_w
RT.get_live_news = live_w


async def one(label: str, qid: str, slow: bool = False) -> dict:
    cache_mod._CACHE.clear()
    S._EXHAUSTED.clear() if slow else None             # the slow run must start from the same provider state a first request has; normal runs keep whatever state production would have
    REC.clear()
    REC.update(attempts=[], chains=[], t0=time.monotonic(), slow=slow, slow_done=False)
    q = QS[qid]["query"]
    out: dict = {"label": label, "question_id": qid, "synthetic_slow_first_specialist_attempt": slow}
    try:
        async with AsyncSessionLocal() as db:
            with RD.scope():
                raw, was_cached = await P.run_ai_search_v3(q, db, None)
                out["remaining_at_completion_s"] = r3(RD.remaining())
        wall = time.monotonic() - REC["t0"]
        res = finalize_v3_response(q, raw, x_admin_key=None, was_cached=was_cached)
        out.update(
            total_wall_s=r3(wall), cached=was_cached, specialist=res.get("specialist"), degraded_reason=res.get("degraded_reason"),
            answer_availability=res.get("answer_availability"), pipeline_timing_ms=raw.get("timing"),
            gate_a=(res.get("evidence_sufficiency") or {}).get("status") if isinstance(res.get("evidence_sufficiency"), dict) else None,
            gate_a_kind=(res.get("evidence_sufficiency") or {}).get("kind") if isinstance(res.get("evidence_sufficiency"), dict) else None,
            gate_b=res.get("answer_authorization"), synthesis_incomplete=res.get("synthesis_incomplete"))
    except Exception as exc:                                 # record, never retry
        out.update(total_wall_s=r3(time.monotonic() - REC["t0"]), error=type(exc).__name__)
    out.update(retrieval=REC.get("retrieval"), news=REC.get("news"), classifier=REC.get("classifier", {"invoked": False}), provider_attempts=REC["attempts"], provider_chains=REC["chains"],
               synthetic_injected_at_s=REC.get("slow_injected_at"))
    print(f"{label}: wall={out.get('total_wall_s')}s attempts={[(a['call'], a['model'], a['outcome'], a['duration_s']) for a in REC['attempts']]} "
          f"degraded={out.get('degraded_reason')} remaining_at_end={out.get('remaining_at_completion_s')}", flush=True)
    return out


async def main():
    keys = {k: bool(getattr(settings, k)) for k in ("groq_api_key", "openrouter_api_key", "mistral_api_key", "gemini_api_key")}
    cfg = {k: getattr(settings, k) for k in ("ai_search_total_budget_seconds", "ai_search_finalization_reserve_seconds", "ai_search_classifier_budget_seconds",
                                              "ai_search_min_provider_attempt_seconds", "ai_search_provider_attempt_cap_seconds")}
    print("provider keys present:", keys, "| budgets:", cfg, flush=True)
    runs = []
    for label, qid, slow in (("SR2", "SR2", False), ("CC2", "CC2", False), ("CR1", "CR1", False), ("SR2-slow-first-provider", "SR2", True)):
        runs.append(await one(label, qid, slow))
    bg = {}
    t = NF._refresh_task
    if t is not None:
        try:
            await asyncio.wait_for(asyncio.shield(t), timeout=30)
        except Exception as exc:
            bg["wait"] = type(exc).__name__
    snap = NF._snapshot
    non_rss = [a for a in snap["items"] if a.get("source") not in RSS_SOURCES]
    bg.update(snapshot_items=len(snap["items"]), source_failures=dict(snap["source_failures"]), consecutive_failures=snap["consecutive_failures"],
              items_from_sources_outside_the_RSS_feeds=len(non_rss), yfinance_thread_done=(NF._yf_future.done() if NF._yf_future is not None else None))
    (HERE / "h4_production_chain.json").write_text(json.dumps({"provider_keys_present": keys, "budgets": cfg, "background_news": bg, "runs": runs}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("background news:", bg, flush=True)

asyncio.run(main())
