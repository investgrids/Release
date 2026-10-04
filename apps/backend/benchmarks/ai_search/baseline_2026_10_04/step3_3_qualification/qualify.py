"""
Step 3.3 provider qualification: CR2, EI1 and CC1 through the REAL pipeline + finalizer with the app's configured provider chain, using the real current specialist prompts and output
schema. Nothing is tuned, no provider is added, no prompt/retrieval/age filter is changed. No credential is read, printed or written.

What is captured per call (the wrapper only observes): kind, max_tokens, prompt length and an ESTIMATED input-token count (chars/4), ok, latency, output length, the per-model
failure log (reasons such as 429), the change in the service's cumulative token counter (total only; input/output are not exposed), the last provider reported, and the RAW output text.
The finish reason is not exposed by the AI service; truncation is inferred from whether the structured output parsed.

Hard gate: a "full specialist call" succeeds when the specialist-sized request returns output AND it parses into the structured contract. 0/3 -> stop, report provider capacity as the blocker.
Cap: MAX_PIPELINE_CALLS pipeline-level calls in total. One attempt per question.

Run from apps/backend:  PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_3_qualification/qualify.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "step3"))

from app.api.companies import _NSE_UNIVERSE  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service  # noqa: E402
from app.services.ai_search import entities as entities_mod  # noqa: E402
from app.services.ai_search import evidence as evidence_mod  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search.response_finalize import finalize_v3_response  # noqa: E402

import answer_checks as AC  # noqa: E402

QUESTION_IDS = ["CR2", "EI1", "CC1"]
MAX_PIPELINE_CALLS = 8
PAUSE_S = 25
QS = {q["id"]: q for q in json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]}

state = {"calls": 0}
current: dict = {}
_real_call = ai_service._call_with_fallback


async def observed_call(prompt, system="", max_tokens=200, failure_log=None, *, priority):
    kind = "classifier" if max_tokens <= 10 else "specialist"
    if state["calls"] >= MAX_PIPELINE_CALLS:
        current.setdefault("calls", []).append({"kind": kind, "skipped": "cap reached"})
        return ""
    state["calls"] += 1
    flog: list = []
    tokens_before = ai_service._AI_USAGE.get("tokens_total", 0)
    t0 = time.monotonic()
    out = await _real_call(prompt, system, max_tokens, flog, priority=priority)
    current.setdefault("calls", []).append({
        "kind": kind, "max_tokens": max_tokens, "prompt_chars": len(prompt) + len(system), "est_input_tokens": round((len(prompt) + len(system)) / 4),
        "ok": bool(out), "latency_ms": round((time.monotonic() - t0) * 1000), "output_chars": len(out or ""),
        "tokens_total_delta": ai_service._AI_USAGE.get("tokens_total", 0) - tokens_before,
        "last_provider": ai_service._AI_USAGE.get("last_provider") if out else None,
        "failure_log": flog, "raw_output": out if kind == "specialist" else (out or "")[:40],
    })
    return out


ai_service._call_with_fallback = observed_call
mp_mod._call_with_fallback = observed_call
_real_collect = evidence_mod.collect


async def stash_collect(query, intent_data, entities, db):
    bundle = await _real_collect(query, intent_data, entities, db)
    current["bundle"] = bundle
    return bundle


evidence_mod.collect = stash_collect
P.evidence_mod.collect = stash_collect


async def run(qid: str) -> dict:
    q = QS[qid]
    current.clear()
    ents = entities_mod.extract_entities(q["query"])
    rec = {"id": qid, "query": q["query"], "entities": {"companies": ents["companies"], "sectors": ents["sectors"], "policies": ents["policies"]}}
    t0 = time.monotonic()
    async with AsyncSessionLocal() as db:
        try:
            raw, was_cached = await P.run_ai_search_v3(q["query"], db, None)
            res = finalize_v3_response(q["query"], raw, x_admin_key=None, was_cached=was_cached)
        except Exception as exc:
            rec["crash"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            res = None
    rec["wall_s"] = round(time.monotonic() - t0, 2)
    rec["calls"] = current.get("calls", [])
    spec = [c for c in rec["calls"] if c["kind"] == "specialist" and "skipped" not in c]
    rec["specialist_call_ok"] = bool(spec and spec[-1]["ok"])
    rec["response"] = res
    bundle = current.get("bundle")
    rec["evidence"] = AC.snapshot_evidence(bundle) if bundle is not None else None
    degraded = (res or {}).get("degraded_reason")
    rec["structured_parse_ok"] = bool(res and not res.get("synthesis_incomplete") and degraded not in ("capacity", "parse_failure"))
    rec["full_specialist_success"] = rec["specialist_call_ok"] and rec["structured_parse_ok"]
    return rec


async def main():
    out = {}
    for n, qid in enumerate(QUESTION_IDS):
        out[qid] = await run(qid)
        r = out[qid]
        res = r.get("response") or {}
        print(qid, f'wall={r["wall_s"]}s specialist_call_ok={r["specialist_call_ok"]} parse_ok={r["structured_parse_ok"]} degraded={res.get("degraded_reason")} '
                   f'calls={[(c["kind"], c.get("ok"), c.get("latency_ms")) for c in r["calls"]]}', flush=True)
        (HERE / "qualification.json").write_text(json.dumps({"cap": MAX_PIPELINE_CALLS, "pipeline_calls_made": state["calls"], "results": out}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        if n < len(QUESTION_IDS) - 1:
            await asyncio.sleep(PAUSE_S)
    await asyncio.sleep(1.5)
    ok = sum(1 for r in out.values() if r["full_specialist_success"])
    print(f"FULL SPECIALIST SUCCESSES: {ok}/3 | pipeline calls made: {state['calls']} of cap {MAX_PIPELINE_CALLS}")


if __name__ == "__main__":
    asyncio.run(main())
