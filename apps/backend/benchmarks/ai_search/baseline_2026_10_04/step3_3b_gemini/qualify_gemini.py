"""
Step 3.3b: Gemini-only qualification of CR2, EI1, CC1 through the REAL release/ai-answer-v2 pipeline, prompts, schema and finalizer, using the production Gemini credential injected by
`railway run`. Authorised scope: at most 3 specialist requests, no classifier call, no retry, no fallback to any other provider/model, not a production query and no production
infrastructure touched.

Isolation (how this stays clean and safe):
  * Before the app is imported, every environment variable except basic OS ones and GEMINI_API_KEY is deleted. The database, Redis, admin key, Groq/OpenRouter keys, JSON_LOGS and every other
    production value therefore never reach this process; the app falls back to the local `.env` for everything except the Gemini key.
  * The AI call is replaced by a wrapper that calls ONLY gemini-3.6-flash (the first Gemini model in the chain) with the app's own request shape and the app's own HTTP timeout. It never
    consults the cooldown table and never falls through to another model. A request beyond the cap is refused.
  * The market-pulse LLM classifier is switched off (the three routes are known); regex routing still runs.
  * The key is never printed, logged or written. Artifacts hold only response metadata, sanitized error text and the model's output.

Run (from the linked monorepo checkout):
  cd D:/IG-expansion && MSYS_NO_PATHCONV=1 railway run python "D:\\IG\\apps\\backend\\benchmarks\\ai_search\\baseline_2026_10_04\\step3_3b_gemini\\qualify_gemini.py"
"""
import os
import re
import sys

# ── isolate the environment BEFORE importing anything from the app ───────────────────────────
_KEEP = {"PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "COMPUTERNAME", "OS", "COMSPEC",
         "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS", "PYTHONIOENCODING", "PYTHONPATH", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "COMMONPROGRAMFILES", "USERNAME", "USERDOMAIN"}
_gemini_key = os.environ.get("GEMINI_API_KEY")
for _k in list(os.environ):
    if _k.upper() not in _KEEP:
        del os.environ[_k]
if _gemini_key:
    os.environ["GEMINI_API_KEY"] = _gemini_key
os.chdir("D:/IG/apps/backend")
sys.path.insert(0, "D:/IG/apps/backend")
sys.path.insert(0, "D:/IG/apps/backend/benchmarks/ai_search/baseline_2026_10_04/step3")

import asyncio  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service as S  # noqa: E402
from app.services.ai_search import entities as entities_mod  # noqa: E402
from app.services.ai_search import evidence as evidence_mod  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search.response_finalize import finalize_v3_response  # noqa: E402

import answer_checks as AC  # noqa: E402

HERE = Path("D:/IG/apps/backend/benchmarks/ai_search/baseline_2026_10_04/step3_3b_gemini")
MODEL = S._GEMINI_MODELS[0]
MAX_SPECIALIST_REQUESTS = 3
QS = {q["id"]: q for q in json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]}
ORDER = ["CR2", "EI1", "CC1"]
_REDACT = re.compile(r"[A-Za-z0-9_\-\.]{28,}")
_LIMIT_HEADER = re.compile(r"^(retry-after|x-ratelimit.*|ratelimit.*|x-should-retry)$", re.IGNORECASE)

state = {"requests": 0}
current: dict = {}


async def gemini_only_call(prompt, system="", max_tokens=200, failure_log=None, *, priority):
    """Replaces the provider chain. One request to one Gemini model; refused beyond the cap; never retried; never falls through."""
    if max_tokens <= 10 or state["requests"] >= MAX_SPECIALIST_REQUESTS:
        current.setdefault("calls", []).append({"refused": "classifier-sized request" if max_tokens <= 10 else "cap reached", "max_tokens": max_tokens})
        return ""
    state["requests"] += 1
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    payload = {"model": MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0.4}      # the app's own request shape for this provider
    rec = {"provider": "gemini", "model": MODEL, "max_tokens": max_tokens, "prompt_chars": len(prompt) + len(system), "approx_input_tokens": round((len(prompt) + len(system)) / 4)}
    t0 = time.monotonic()
    out = ""
    try:
        async with httpx.AsyncClient(timeout=S._HTTP_TIMEOUT) as client:      # the app's own timeout (read 30 s), part of the production path
            r = await client.post(S._GEMINI_URL, json=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings.gemini_api_key}"})
        rec["latency_ms"] = round((time.monotonic() - t0) * 1000)
        rec["status"] = r.status_code
        rec["limit_headers"] = {k.lower(): v for k, v in r.headers.items() if _LIMIT_HEADER.match(k)}
        try:
            body = r.json()
        except Exception:
            body = {}
        if r.status_code != 200:
            err = body.get("error") if isinstance(body, dict) else None
            if isinstance(body, list) and body and isinstance(body[0], dict):
                err = body[0].get("error")
            err = err if isinstance(err, dict) else {"message": str(body)[:200]}
            rec["error"] = {"status": _REDACT.sub("<redacted>", str(err.get("status"))), "code": str(err.get("code")), "message": _REDACT.sub("<redacted>", str(err.get("message")))[:400]}
        else:
            ch = (body.get("choices") or [{}])[0]
            content = ((ch.get("message") or {}).get("content")) or ""
            usage = body.get("usage") or {}
            rec.update({"finish_reason": ch.get("finish_reason"), "output_chars": len(content), "usage": {k: v for k, v in usage.items() if isinstance(v, (int, float))},
                        "would_exceed_30s": rec["latency_ms"] / 1000 > S._HTTP_READ_TIMEOUT_S, "raw_output": content})
            out = S._strip_reasoning(content.strip()) if content else ""
    except Exception as exc:
        rec["latency_ms"] = round((time.monotonic() - t0) * 1000)
        rec["status"] = None
        rec["exception"] = type(exc).__name__ + ": " + _REDACT.sub("<redacted>", str(exc))[:140]
    current.setdefault("calls", []).append(rec)
    return out


async def _no_classifier(query: str) -> bool:
    return False


S._call_with_fallback = gemini_only_call
mp_mod._call_with_fallback = gemini_only_call
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
    spec = [c for c in rec["calls"] if "refused" not in c]
    rec["request_ok"] = bool(spec and spec[-1].get("status") == 200 and spec[-1].get("output_chars"))
    rec["response"] = res
    bundle = current.get("bundle")
    rec["evidence"] = AC.snapshot_evidence(bundle) if bundle is not None else None
    degraded = (res or {}).get("degraded_reason")
    rec["structured_parse_ok"] = bool(res and not res.get("synthesis_incomplete") and degraded not in ("capacity", "parse_failure"))
    rec["full_specialist_success"] = rec["request_ok"] and rec["structured_parse_ok"]
    return rec


async def main():
    print("gemini key present in this process:", bool(settings.gemini_api_key), "| model:", MODEL, "| other provider keys visible to the app:",
          {n: bool(getattr(settings, n, None)) for n in ("groq_api_key", "openrouter_api_key")}, "| is_production:", settings.is_production, flush=True)
    if not settings.gemini_api_key:
        print("no Gemini key reached the process; stopping")
        return
    out = {}
    for n, qid in enumerate(ORDER):
        out[qid] = await run(qid)
        r = out[qid]
        res = r.get("response") or {}
        c = [x for x in r["calls"] if "refused" not in x]
        print(qid, f'wall={r["wall_s"]}s request_ok={r["request_ok"]} parse_ok={r["structured_parse_ok"]} degraded={res.get("degraded_reason")} '
                   f'status={c[-1].get("status") if c else None} latency_ms={c[-1].get("latency_ms") if c else None} finish={c[-1].get("finish_reason") if c else None}', flush=True)
        (HERE / "gemini_qualification.json").write_text(json.dumps({"model": MODEL, "cap": MAX_SPECIALIST_REQUESTS, "specialist_requests_made": state["requests"], "results": out}, indent=2,
                                                                    ensure_ascii=False, default=str), encoding="utf-8")
        if n < len(ORDER) - 1:
            await asyncio.sleep(8)
    await asyncio.sleep(1.5)
    ok = sum(1 for r in out.values() if r["full_specialist_success"])
    print(f"GEMINI FULL SPECIALIST SUCCESSES: {ok}/3 | specialist requests made: {state['requests']} of cap {MAX_SPECIALIST_REQUESTS}")


if __name__ == "__main__":
    asyncio.run(main())
