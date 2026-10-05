"""
Step 3.4C/3.4D: benchmark-only OpenAI path. CR2 -> EI1 -> CC1 through the REAL release/ai-answer-v2 pipeline (intent, entities, retrieval, Gate A, specialist prompts, schema, Gate B, finalizer).

Expected behaviour after Step 3.4A (this is the success criterion, NOT "3/3 model successes"):
  CR2  Gate A refuses (insufficient_evidence)           -> 0 OpenAI calls
  EI1  Gate A refuses (premise_check=not_established)   -> 0 OpenAI calls
  CC1  sufficient evidence for both companies           -> exactly 1 OpenAI specialist call

Isolation
  * Before the app is imported every environment variable except basic OS ones and the three OPENAI_BENCH_* variables is deleted: no production credential, database, Redis or admin key reaches this
    process. The app falls back to the local `.env` for settings; none of its provider keys is ever used because the AI call is replaced.
  * The AI call is replaced by a wrapper that talks ONLY to the dedicated OpenAI benchmark project (key OPENAI_BENCH_API_KEY, model OPENAI_BENCH_MODEL). It never consults the production provider chain, the
    cooldown table, or any other provider. No retries. Refused beyond the call cap. The market-pulse classifier is switched off (the routes are known).
  * The key is never printed, logged or written. Artifacts hold response metadata, classified error codes and the model output only. The exact model id is recorded in the artifact.
  * This is NOT added to the production fallback chain and nothing in app/ is modified.

Modes
  no key (or --dry)  Gate A preflight only: real retrieval, specialists replaced by a call counter that makes NO request. Reports each question's Gate A decision and how many calls WOULD be made.
                     If CC1 is not SUFFICIENT in this environment (e.g. market data unavailable) the live run must not be forced: restore a representative data environment first.
  with key           live run, cap OPENAI_BENCH_MAX_CALLS (default 2), stop on the first non-200.

Run (from apps/backend, PowerShell or bash; the key is set in the shell only, never in a committed file):
  $env:OPENAI_BENCH_API_KEY = "<new project-scoped key>"; $env:OPENAI_BENCH_MODEL = "gpt-6-luna"
  python benchmarks/ai_search/baseline_2026_10_04/step3_4c/qualify_openai.py            # live
  python benchmarks/ai_search/baseline_2026_10_04/step3_4c/qualify_openai.py --dry      # preflight only
"""
import os
import re
import sys

_KEEP = {"PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "COMPUTERNAME", "OS", "COMSPEC",
         "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS", "PYTHONIOENCODING", "PYTHONPATH", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "COMMONPROGRAMFILES", "USERNAME", "USERDOMAIN",
         "OPENAI_BENCH_API_KEY", "OPENAI_BENCH_MODEL", "OPENAI_BENCH_MAX_CALLS", "OPENAI_BENCH_QUESTIONS", "OPENAI_BENCH_OUT"}
for _k in list(os.environ):
    if _k.upper() not in _KEEP:
        del os.environ[_k]
_KEY = os.environ.pop("OPENAI_BENCH_API_KEY", "")          # held in a module variable only; removed from the environment so nothing else can read or inherit it
MODEL = os.environ.get("OPENAI_BENCH_MODEL", "gpt-6-luna")
MAX_CALLS = int(os.environ.get("OPENAI_BENCH_MAX_CALLS", "2"))
DRY = ("--dry" in sys.argv) or not _KEY
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "benchmarks", "ai_search", "baseline_2026_10_04", "step3"))

import asyncio  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import httpx  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service as S  # noqa: E402
from app.services.ai_search import answer_authorization as AA  # noqa: E402
from app.services.ai_search import entities as entities_mod  # noqa: E402
from app.services.ai_search import evidence as evidence_mod  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search.response_finalize import finalize_v3_response  # noqa: E402

import answer_checks as AC  # noqa: E402

HERE = Path(__file__).parent
URL = "https://api.openai.com/v1/chat/completions"
HTTP_TIMEOUT_S = 120.0                      # harness-only; the production path's 30 s read timeout is recorded per call as would_exceed_30s
QS = {q["id"]: q for q in json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]}
# Step 3.4F: the question list and output name can be set from the environment (default stays CR2, EI1, CC1). A question with no recorded expectation is not scored as_expected.
ORDER = [q.strip() for q in os.environ.get("OPENAI_BENCH_QUESTIONS", "CR2,EI1,CC1").split(",") if q.strip()]
EXPECTED_CALLS = {"CR2": 0, "EI1": 0, "CC1": 1}
OUT_NAME = os.environ.get("OPENAI_BENCH_OUT", "openai_qualification.json")
_REDACT = re.compile(r"(?:sk|rk|pk)-[A-Za-z0-9_\-]{8,}|[A-Za-z0-9_\-\.]{32,}")
_LIMIT_HEADER = re.compile(r"^(retry-after|x-ratelimit.*|openai-processing-ms|x-request-id)$", re.IGNORECASE)

state = {"calls": 0, "stopped": None}
current: dict = {}


def classify_error(status: int | None, body: dict) -> str:
    """Classify from the actual OpenAI error code/type, never generically."""
    err = (body.get("error") if isinstance(body, dict) else None) or {}
    code, typ = str(err.get("code") or "").lower(), str(err.get("type") or "").lower()
    msg = str(err.get("message") or "").lower()
    if status == 401:
        return "AUTH_INVALID_KEY"
    if status == 404 or code == "model_not_found":
        return "MODEL_NOT_FOUND_OR_NOT_ENABLED_FOR_PROJECT"
    if code == "insufficient_quota" or typ == "insufficient_quota":
        return "CREDITS_OR_PROJECT_SPEND_LIMIT_EXHAUSTED"
    if "billing_hard_limit" in code or "hard limit" in msg or "spend limit" in msg or "budget" in msg:
        return "PROJECT_SPEND_LIMIT_REACHED"
    if status == 429 or code == "rate_limit_exceeded":
        return "RATE_LIMITED"
    if status == 400:
        return "BAD_REQUEST"
    return f"HTTP_{status}" if status else "NETWORK_OR_TIMEOUT"


async def openai_only_call(prompt, system="", max_tokens=200, failure_log=None, *, priority):
    """Replaces the provider chain: one request to the benchmark model. Refused beyond the cap and after any failure; never retried; never falls through."""
    if max_tokens <= 10:
        current.setdefault("calls", []).append({"refused": "classifier-sized request", "max_tokens": max_tokens})
        return ""
    rec = {"provider": "openai-benchmark-project", "model": MODEL, "max_completion_tokens": max_tokens, "prompt_chars": len(prompt) + len(system),
           "approx_input_tokens": round((len(prompt) + len(system)) / 4)}
    if DRY:
        rec["dry_run_would_call"] = True
        current.setdefault("calls", []).append(rec)
        return ""
    if state["calls"] >= MAX_CALLS or state["stopped"]:
        rec["refused"] = "cap reached" if state["calls"] >= MAX_CALLS else f"stopped after {state['stopped']}"
        current.setdefault("calls", []).append(rec)
        return ""
    state["calls"] += 1
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    payload = {"model": MODEL, "messages": messages, "max_completion_tokens": max_tokens}
    t0 = time.monotonic()
    out = ""
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
            r = await client.post(URL, json=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {_KEY}"})
        rec["latency_ms"] = round((time.monotonic() - t0) * 1000)
        rec["status"] = r.status_code
        rec["limit_headers"] = {k.lower(): v for k, v in r.headers.items() if _LIMIT_HEADER.match(k)}
        try:
            body = r.json()
        except Exception:
            body = {}
        if r.status_code != 200:
            err = (body.get("error") if isinstance(body, dict) else None) or {}
            rec["classification"] = classify_error(r.status_code, body)
            rec["error"] = {"type": str(err.get("type")), "code": str(err.get("code")), "message": _REDACT.sub("<redacted>", str(err.get("message")))[:400]}
            state["stopped"] = rec["classification"]
        else:
            ch = (body.get("choices") or [{}])[0]
            content = ((ch.get("message") or {}).get("content")) or ""
            usage = body.get("usage") or {}
            rec.update({"response_model": body.get("model"), "finish_reason": ch.get("finish_reason"), "output_chars": len(content),
                        "usage": {k: v for k, v in usage.items() if isinstance(v, (int, float))}, "reasoning_tokens": ((usage.get("completion_tokens_details") or {}).get("reasoning_tokens")),
                        "would_exceed_30s": rec["latency_ms"] / 1000 > S._HTTP_READ_TIMEOUT_S, "raw_output": content})
            out = S._strip_reasoning(content.strip()) if content else ""
    except Exception as exc:
        rec["latency_ms"] = round((time.monotonic() - t0) * 1000)
        rec["status"] = None
        rec["classification"] = "NETWORK_OR_TIMEOUT"
        rec["exception"] = type(exc).__name__ + ": " + _REDACT.sub("<redacted>", str(exc))[:140]
        state["stopped"] = rec["classification"]
    current.setdefault("calls", []).append(rec)
    return out


async def _no_classifier(query: str) -> bool:
    return False


S._call_with_fallback = openai_only_call
mp_mod._call_with_fallback = openai_only_call
mp_mod._classify_market_pulse_llm = _no_classifier
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
    AA.REJECTED_GENERATIONS.clear()
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
    real = [c for c in rec["calls"] if "refused" not in c]
    rec["model_calls"] = len(real)
    rec["expected_model_calls"] = EXPECTED_CALLS.get(qid)
    rec["call_count_as_expected"] = (len(real) == EXPECTED_CALLS[qid]) if qid in EXPECTED_CALLS else None
    rec["response"] = res
    r = res or {}
    rec["gate_a"] = r.get("evidence_sufficiency")
    rec["premise_check"] = r.get("premise_check")
    rec["gate_b"] = r.get("answer_authorization")
    rec["claim_validation"] = r.get("claim_validation")
    rec["claim_sources"] = r.get("claim_sources")
    rec["degraded_reason"] = r.get("degraded_reason")
    rec["rejected_generation"] = [{"reasons": g["reasons"], "generation": g["generation"]} for g in AA.REJECTED_GENERATIONS]
    bundle = current.get("bundle")
    rec["evidence"] = AC.snapshot_evidence(bundle) if bundle is not None else None
    if real and not DRY:
        c = real[-1]
        rec["model_result"] = {"status": c.get("status"), "classification": c.get("classification"), "finish_reason": c.get("finish_reason"), "latency_ms": c.get("latency_ms"),
                               "usage": c.get("usage"), "reasoning_tokens": c.get("reasoning_tokens"), "would_exceed_30s": c.get("would_exceed_30s")}
    rec["outcome"] = ("deterministic_refusal" if r.get("degraded_reason") == "insufficient_evidence" else
                      "generation_rejected_by_gate_b" if r.get("degraded_reason") == "claims_not_authorized" else
                      "generation_authorized" if (real and not r.get("synthesis_incomplete")) else
                      "model_unavailable_or_unparsed" if real else "no_model_call")
    return rec


async def main():
    print("mode:", "DRY (Gate A preflight, no request will be made)" if DRY else "LIVE", "| model:", MODEL, "| key present:", bool(_KEY), "| call cap:", MAX_CALLS, flush=True)
    out = {}
    for n, qid in enumerate(ORDER):
        out[qid] = await run(qid)
        r = out[qid]
        ga = r.get("gate_a") or {}
        print(qid, f'outcome={r["outcome"]} gate_a={ga.get("status")}/{ga.get("kind")} model_calls={r["model_calls"]} (would_call={sum(1 for c in r["calls"] if c.get("dry_run_would_call"))}) '
                   f'expected={r["expected_model_calls"]} as_expected={r["call_count_as_expected"] or DRY}', flush=True)
        (HERE / ("openai_preflight.json" if DRY else OUT_NAME)).write_text(
            json.dumps({"mode": "dry" if DRY else "live", "model": MODEL, "cap": MAX_CALLS, "model_requests_made": state["calls"], "stopped": state["stopped"], "results": out}, indent=2,
                       ensure_ascii=False, default=str), encoding="utf-8")
        if not DRY and n < len(ORDER) - 1:
            await asyncio.sleep(2)
    if DRY:
        for qid, r in out.items():
            would = sum(1 for c in r["calls"] if c.get("dry_run_would_call"))
            print(f"{qid} PREFLIGHT:", f"would make {would} call(s)" if would else "NO CALL (Gate A refused or no specialist reached)")
    print(f"model requests made: {state['calls']} | stopped: {state['stopped']}")


if __name__ == "__main__":
    asyncio.run(main())
