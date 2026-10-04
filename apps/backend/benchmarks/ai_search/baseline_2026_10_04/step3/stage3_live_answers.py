"""
Step 3 live-answer validation gate. Runs the frozen 18 questions through the REAL pipeline + finalizer with whatever model providers the app is configured with, under a strict
call cap, SAVES every actual answer together with the evidence snapshot it was generated from, then applies answer_checks.py. Nothing here loosens retrieval or the age filter.

Caps: MAX_MODEL_CALLS pipeline-level model calls in total (classifier + specialist each count, retries count); one attempt per question; a second pass only for questions that
ended capacity-degraded and only while budget remains. CIRCUIT_AFTER consecutive capacity-degraded answers stops further model calls (those questions stay UNVERIFIED).
No credentials are read, printed or written by this script; it uses the app's own configured chain.

Run from apps/backend:  PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3/stage3_live_answers.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service  # noqa: E402
from app.services.ai_search import entities as entities_mod  # noqa: E402
from app.services.ai_search import evidence as evidence_mod  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search.response_finalize import finalize_v3_response  # noqa: E402
from app.api.companies import _NSE_UNIVERSE  # noqa: E402

import answer_checks as AC  # noqa: E402

HERE = Path(__file__).parent
OUT = Path(os.environ.get("STEP3_OUT_DIR") or HERE)
OUT.mkdir(parents=True, exist_ok=True)
QUESTIONS = json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]
MAX_MODEL_CALLS = int(os.environ.get("STEP3_MAX_CALLS", "40"))
CIRCUIT_AFTER = 3
PAUSE_S = float(os.environ.get("STEP3_PAUSE_S", "5"))
PROD = "https://backend-production-78042.up.railway.app"

state = {"calls": 0, "consecutive_capacity": 0, "circuit_open": False}
current: dict = {}
_real_call = ai_service._call_with_fallback


async def counted_call(prompt, system="", max_tokens=200, failure_log=None, *, priority):
    kind = "classifier" if max_tokens <= 10 else "specialist"
    if state["circuit_open"]:
        current.setdefault("skipped", []).append(kind)
        return ""
    if state["calls"] >= MAX_MODEL_CALLS:
        current["cap_hit"] = True
        return ""
    state["calls"] += 1
    t0 = time.monotonic()
    out = await _real_call(prompt, system, max_tokens, failure_log, priority=priority)
    current.setdefault("model_calls", []).append({"kind": kind, "ok": bool(out), "ms": round((time.monotonic() - t0) * 1000), "max_tokens": max_tokens,
                                                  "usage": dict(ai_service._AI_USAGE) if out else None, "output_chars": len(out or "")})
    return out


ai_service._call_with_fallback = counted_call
mp_mod._call_with_fallback = counted_call
_real_collect = evidence_mod.collect


async def stash_collect(query, intent_data, entities, db):
    bundle = await _real_collect(query, intent_data, entities, db)
    current["bundle"] = bundle
    return bundle


evidence_mod.collect = stash_collect
P.evidence_mod.collect = stash_collect


def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def published_scores(symbols: list[str]) -> dict:
    """Read-only GETs of what the product currently publishes for these companies (banks: filing-backed score; others: live score if publishable)."""
    out = {}
    for s in symbols:
        fs = _get(f"{PROD}/api/filing-score/{s}")
        if fs and fs.get("state") == "scored":
            out[s] = {"score": fs.get("score"), "band": fs.get("rating"), "source": "filing-backed bank score"}
            continue
        live = _get(f"{PROD}/api/companies/{s}/marketripple-score")
        if live and live.get("score") is not None and live.get("publishable"):
            out[s] = {"score": live.get("score"), "band": live.get("rating"), "source": "live score"}
        else:
            out[s] = {"score": None, "band": None, "source": "no published score"}
    return out


async def run_one(q: dict, attempt: int) -> dict:
    current.clear()
    rec = {"id": q["id"], "type": q["type"], "query": q["query"], "attempt": attempt}
    ents = entities_mod.extract_entities(q["query"])
    rec["entities"] = {"companies": ents["companies"], "sectors": ents["sectors"], "policies": ents["policies"]}
    t0 = time.monotonic()
    async with AsyncSessionLocal() as db:
        try:
            raw, was_cached = await P.run_ai_search_v3(q["query"], db, None)
            res = finalize_v3_response(q["query"], raw, x_admin_key=None, was_cached=was_cached)
        except Exception as exc:
            rec["crash"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            res = None
    rec["latency_s"] = round(time.monotonic() - t0, 2)
    rec["model_calls"] = current.get("model_calls", [])
    rec["model_call_count"] = len(rec["model_calls"])
    rec["skipped_by_circuit"] = current.get("skipped")
    rec["cap_hit"] = bool(current.get("cap_hit"))
    bundle = current.get("bundle")
    rec["evidence"] = AC.snapshot_evidence(bundle) if bundle is not None else None
    rec["response"] = res
    return rec


def check_record(rec: dict, q: dict) -> dict:
    """Automatic answer-level checks. UNVERIFIED when no real answer exists."""
    res, ev = rec.get("response"), rec.get("evidence")
    if not res or ev is None or res.get("synthesis_incomplete"):
        return {"answer_exists": False, "reason": (res or {}).get("degraded_reason") or rec.get("crash") or "no response"}
    resolved, sectors = rec["entities"]["companies"], rec["entities"]["sectors"]
    claims = AC.claim_checks(res, ev, q["query"], resolved, sectors, _NSE_UNIVERSE)
    window = 45 if q["tags"] and "event_in_query" in q["tags"] else 90
    pub = published_scores(resolved) if resolved else {}
    cmp_rank = AC.comparison_rank_check(res, pub, ev.get("valuation")) if q["type"] == "company_comparison" else None
    return {
        "answer_exists": True,
        "unsupported_numbers": AC.unsupported_numbers(res, ev, q["query"]),
        "claims": {"total": len(claims), "supported": sum(c["status"] == "supported" for c in claims), "ineligible_only": [c for c in claims if c["status"] == "ineligible_only"],
                   "unsupported": [c for c in claims if c["status"] == "unsupported"]},
        "recency": AC.recency_claims(claims, ev, window),
        "citations": AC.citation_check(res, ev),
        "insufficient_evidence": AC.insufficient_evidence_check(res, ev, q["query"], _NSE_UNIVERSE, resolved),
        "score_refs": AC.score_reference_check(res, pub),
        "comparison_rank": cmp_rank,
        "evidence_total": AC.evidence_total(ev),
    }


async def main():
    results: dict[str, dict] = {}
    t_start = time.monotonic()
    for q in QUESTIONS:
        results[q["id"]] = await run_one(q, 1)
        r = results[q["id"]]
        res = r.get("response") or {}
        if res.get("degraded_reason") in ("capacity", "parse_failure"):
            state["consecutive_capacity"] += 1
            if state["consecutive_capacity"] >= CIRCUIT_AFTER:
                state["circuit_open"] = True
        elif res and not res.get("synthesis_incomplete"):
            state["consecutive_capacity"] = 0
        print(q["id"], f'{r["latency_s"]}s calls={r["model_call_count"]} incomplete={res.get("synthesis_incomplete")} reason={res.get("degraded_reason")} ev={AC.evidence_total(r["evidence"]) if r.get("evidence") else None}', flush=True)
        (OUT / "answers.json").write_text(json.dumps({"state": state, "results": results}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        if r["model_call_count"]:
            await asyncio.sleep(PAUSE_S)
    # second pass: only capacity-degraded, only while budget remains and the circuit is closed
    retry = [q for q in QUESTIONS if (results[q["id"]].get("response") or {}).get("degraded_reason") in ("capacity", "parse_failure")]
    if retry and not state["circuit_open"] and state["calls"] < MAX_MODEL_CALLS - 1:
        print("retry pass:", [q["id"] for q in retry], flush=True)
        for q in retry:
            if state["calls"] >= MAX_MODEL_CALLS - 1 or state["circuit_open"]:
                break
            results[q["id"]] = await run_one(q, 2)
            r = results[q["id"]]
            print(q["id"], "(retry)", f'calls={r["model_call_count"]} incomplete={(r.get("response") or {}).get("synthesis_incomplete")}', flush=True)
            await asyncio.sleep(PAUSE_S)
    await asyncio.sleep(1.5)     # let fire-and-forget local prediction writes finish
    checks = {q["id"]: check_record(results[q["id"]], q) for q in QUESTIONS}
    (OUT / "answers.json").write_text(json.dumps({"state": state, "elapsed_s": round(time.monotonic() - t_start, 1), "results": results}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (OUT / "auto_checks.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("total pipeline-level model calls:", state["calls"], "| circuit_open:", state["circuit_open"], "| answers produced:", sum(1 for c in checks.values() if c["answer_exists"]), "of", len(checks))


if __name__ == "__main__":
    asyncio.run(main())
