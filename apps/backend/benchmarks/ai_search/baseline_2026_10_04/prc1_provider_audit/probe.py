"""
PRC-1 capacity probe. DIAGNOSTIC ONLY: no provider, prompt, retry-policy or production change. Fresh process, one provider/model at a time, NOT through the fallback chain, so no
cooldown state from other runs can contaminate it.

Per model, the SAME content in progressively more realistic sizes (the real CR2 specialist prompt, truncated for the smaller steps):
  S1 tiny (like the classifier) | S2 ~500 input tokens, out 64 | S3 ~1,000 input, out 128 | S4a full prompt, out 256 | S4b full prompt, out 512 | S5a full, out 2048 | S5b full, out = real MAX_TOKENS
The model's sequence STOPS at its first failure (a 429 is never retried) and a later step runs only if the previous one succeeded.

Captured per request (safe metadata only): provider/model, step, requested max_tokens, approximate input size, HTTP status, latency, response headers that describe limits
(retry-after, x-ratelimit-*, ratelimit-*), the sanitized provider error (type/code/message, truncated, with long tokens and org ids redacted), and on success the returned usage and finish
reason. Request headers, keys and payload bodies are never recorded.

Classification (never inferred from "429" alone): AVAILABLE, REQUEST_LIMITED, RATE_LIMITED, QUOTA_EXHAUSTED, CONFIGURATION_ERROR, UNKNOWN_429, plus TRANSIENT_ERROR / OUTPUT_EMPTY.

Run from apps/backend:  PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/prc1_provider_audit/probe.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, ".")
HERE = Path(__file__).parent

from app.core.config import settings  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service as S  # noqa: E402
from app.services.ai_search import entities as entities_mod  # noqa: E402
from app.services.ai_search import evidence as evidence_mod  # noqa: E402
from app.services.ai_search.decision_intent import _detect_decision_intent  # noqa: E402
from app.services.ai_search.specialists import company  # noqa: E402

QUERY = "How is 3M India doing as a business?"          # CR2, the real specialist prompt
MAX_REQUESTS = 60
GAP_S = 3.0
APP_READ_TIMEOUT_S = S._HTTP_READ_TIMEOUT_S              # the app's own read timeout, for the "would the app have timed out" flag
_REDACT_LONG = re.compile(r"[A-Za-z0-9_\-\.]{28,}")
_REDACT_ORG = re.compile(r"org_[A-Za-z0-9]+")
_LIMIT_HEADER = re.compile(r"^(retry-after|x-ratelimit.*|ratelimit.*|x-should-retry)$", re.IGNORECASE)


def sanitize(text: str) -> str:
    return _REDACT_LONG.sub("<redacted>", _REDACT_ORG.sub("org_<redacted>", text or ""))[:400]


async def real_prompt() -> tuple[str, str, int]:
    ents = entities_mod.extract_entities(QUERY)
    intent = _detect_decision_intent(QUERY)
    async with AsyncSessionLocal() as db:
        bundle = await evidence_mod.collect(QUERY, intent, ents, db)
    return company.build_prompt(QUERY, bundle, intent, ents), company.SPECIALIST_SYSTEM, company.MAX_TOKENS


ONLY = [m.strip() for m in os.environ.get("PRC1_ONLY", "").split(",") if m.strip()]          # restrict a re-run to named models
RESULTS_FILE = os.environ.get("PRC1_RESULTS", "probe_results.json")


def is_reasoning(model: str) -> bool:
    """Models the app calls with a reasoning_effort: they spend max_tokens on hidden reasoning BEFORE any visible answer, so a 5-token request returns finish_reason=length with empty
    content. That is a property of the request budget, not a capacity signal; their ladder therefore uses larger output allowances."""
    return model in S._GROQ_REASONING_EFFORT


def models() -> list[tuple[str, str, str]]:
    out = []
    if settings.groq_api_key:
        out += [("groq", S._GROQ_URL, m) for m in S._GROQ_HIGH + S._GROQ_FAST]
    if settings.openrouter_api_key:
        out += [("openrouter", S._OR_URL, m) for m in S._OR_HIGH_QUALITY + S._OR_SMALL]
    if settings.gemini_api_key:
        out += [("gemini", S._GEMINI_URL, m) for m in S._GEMINI_MODELS]
    return [t for t in out if not ONLY or t[2] in ONLY]


def key_for(provider: str) -> str:
    return {"groq": settings.groq_api_key, "openrouter": settings.openrouter_api_key, "gemini": settings.gemini_api_key}[provider]


async def one_request(client: httpx.AsyncClient, provider: str, url: str, model: str, prompt: str, system: str, max_tokens: int) -> dict:
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key_for(provider)}"}
    if provider == "openrouter":
        headers.update({"HTTP-Referer": settings.frontend_url or "https://investgrids.com", "X-Title": "InvestGrids Market Intelligence"})
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.4}
    if url == S._GROQ_URL and model in S._GROQ_REASONING_EFFORT:
        payload["reasoning_effort"] = S._GROQ_REASONING_EFFORT[model]
    rec = {"max_tokens": max_tokens, "approx_input_tokens": round((len(prompt) + len(system)) / 4)}
    t0 = time.monotonic()
    try:
        r = await client.post(url, json=payload, headers=headers)
        rec["latency_ms"] = round((time.monotonic() - t0) * 1000)
        rec["status"] = r.status_code
        rec["limit_headers"] = {k.lower(): v for k, v in r.headers.items() if _LIMIT_HEADER.match(k)}
        try:
            body = r.json()
        except Exception:
            body = {}
        if r.status_code != 200:
            err = body.get("error") if isinstance(body, dict) else None
            err = err if isinstance(err, dict) else {"message": str(body)[:200]}
            rec["error"] = {"type": sanitize(str(err.get("type"))), "code": sanitize(str(err.get("code"))), "message": sanitize(str(err.get("message")))}
            meta = err.get("metadata")
            if isinstance(meta, dict):
                rec["error"]["metadata_headers"] = {k: sanitize(str(v)) for k, v in (meta.get("headers") or {}).items()} if isinstance(meta.get("headers"), dict) else None
        else:
            ch = (body.get("choices") or [{}])[0]
            content = ((ch.get("message") or {}).get("content")) or ""
            usage = body.get("usage") or {}
            rec.update({"finish_reason": ch.get("finish_reason"), "output_chars": len(content), "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                        "total_tokens": usage.get("total_tokens"), "would_exceed_app_read_timeout": rec["latency_ms"] / 1000 > APP_READ_TIMEOUT_S})
            rec["empty_content"] = not content.strip()
    except Exception as exc:
        rec["latency_ms"] = round((time.monotonic() - t0) * 1000)
        rec["status"] = None
        rec["exception"] = type(exc).__name__ + ": " + sanitize(str(exc))[:120]
    return rec


_QUOTA = re.compile(r"per[- ]day|daily|free-models-per-day|quota|add \d+ credits|credits|billing|exceeded your current", re.IGNORECASE)
_SIZE = re.compile(r"request too large|too large|context length|maximum context|tokens per minute|\btpm\b|requested\s+\d+", re.IGNORECASE)
_RATE = re.compile(r"rate limit|per minute|requests per minute|try again in|too many requests", re.IGNORECASE)


def classify(steps: list[dict]) -> tuple[str, str]:
    """(state, evidence). Never AVAILABLE unless the real-size request succeeded, never QUOTA_EXHAUSTED without explicit provider text."""
    last = steps[-1]
    if last["status"] == 200 and not last.get("empty_content") and last["step"] == "S5b":
        return "AVAILABLE", "the real specialist prompt with the real max_tokens succeeded"
    if last["status"] == 200 and last.get("empty_content"):
        return "OUTPUT_EMPTY", f"HTTP 200 but no content (finish_reason={last.get('finish_reason')}); likely output budget consumed before any answer"
    if last["status"] == 200:
        return "INCOMPLETE", "sequence stopped before the real-size request"
    text = " ".join([str((last.get("error") or {}).get("message")), str((last.get("error") or {}).get("code")), json.dumps(last.get("limit_headers") or {}),
                     json.dumps((last.get("error") or {}).get("metadata_headers") or {})])
    prior_ok = any(s["status"] == 200 for s in steps[:-1])
    m = re.search(r"\((TPM|TPD|RPM|RPD)\): Limit (\d+), Used (\d+), Requested (\d+)", text)
    if last["status"] == 429 and m:
        kind, limit, used, requested = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        detail = f"{kind} limit {limit}, used {used}, requested {requested}, remaining {max(limit - used, 0)}"
        if requested > limit:
            return "REQUEST_LIMITED", f"a single request ({requested}) exceeds the {kind} limit ({limit}): {detail}"
        if kind in ("TPD", "RPD"):
            return "QUOTA_EXHAUSTED", f"provider reports the daily {kind} allowance is used up: {detail}"
        return "RATE_LIMITED", f"provider reports the per-minute {kind} window is full (recoverable): {detail}"
    if last["status"] in (401, 403, 404) or (last["status"] == 400 and re.search(r"model|invalid|not found|does not exist|decommission", text, re.IGNORECASE)):
        return "CONFIGURATION_ERROR", f"HTTP {last['status']}: {(last.get('error') or {}).get('message')}"
    if last["status"] == 413 or (last["status"] == 429 and prior_ok and _SIZE.search(text)):
        return "REQUEST_LIMITED", f"HTTP {last['status']} after smaller requests succeeded; provider text names a size/token limit: {(last.get('error') or {}).get('message')}"
    if last["status"] == 429 and _QUOTA.search(text):
        return "QUOTA_EXHAUSTED", f"provider text names a daily/quota/credit limit: {(last.get('error') or {}).get('message')}"
    if last["status"] == 429 and _RATE.search(text):
        return "RATE_LIMITED", f"provider reports a recoverable rate window: {(last.get('error') or {}).get('message')} headers={last.get('limit_headers')}"
    if last["status"] == 429:
        return "UNKNOWN_429", f"429 with no distinguishing text. error={last.get('error')} headers={last.get('limit_headers')}"
    return "TRANSIENT_ERROR", f"status={last['status']} exception={last.get('exception')} error={last.get('error')}"


async def main():
    prompt, system, real_max = await real_prompt()
    plain = [("S1", "Reply with the single word OK.", "", 5), ("S2", prompt[:2000], system, 64), ("S3", prompt[:4000], system, 128), ("S4a", prompt, system, 256),
             ("S4b", prompt, system, 512), ("S5a", prompt, system, 2048), ("S5b", prompt, system, real_max)]
    reasoning = [("S1", "Reply with the single word OK.", "", 5), ("S1b", "Reply with the single word OK.", "", 512), ("S2", prompt[:2000], system, 512), ("S3", prompt[:4000], system, 768),
                 ("S4a", prompt, system, 1024), ("S4b", prompt, system, 2048), ("S5a", prompt, system, 4096), ("S5b", prompt, system, real_max)]
    results, made = {}, 0
    timeout = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for provider, url, model in models():
            seq: list[dict] = []
            for name, p, sysmsg, mx in (reasoning if is_reasoning(model) else plain):
                if made >= MAX_REQUESTS:
                    break
                rec = await one_request(client, provider, url, model, p, sysmsg, mx)
                rec["step"] = name
                seq.append(rec)
                made += 1
                print(f"{provider:10} {model[:44]:44} {name:3} status={rec['status']} {rec.get('latency_ms')}ms "
                      f"{'finish=' + str(rec.get('finish_reason')) if rec['status'] == 200 else (rec.get('error') or {}).get('message', rec.get('exception', ''))[:90]}", flush=True)
                if name == "S1" and is_reasoning(model) and rec["status"] == 200 and rec.get("empty_content"):
                    rec["note"] = "empty at 5 tokens is expected for a reasoning model (budget spent on hidden reasoning); continuing with a realistic budget"
                    await asyncio.sleep(GAP_S)
                    continue
                if rec["status"] != 200 or rec.get("empty_content"):
                    break
                await asyncio.sleep(GAP_S)
            state, ev = classify(seq)
            results[f"{provider}:{model}"] = {"state": state, "evidence": ev, "steps": seq}
            print(f"   => {state}: {ev[:160]}", flush=True)
            (HERE / RESULTS_FILE).write_text(json.dumps({"requests_made": made, "real_prompt_approx_input_tokens": round((len(prompt) + len(system)) / 4), "real_max_tokens": real_max,
                                                                  "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
            await asyncio.sleep(2.0)
    print("requests made:", made)


if __name__ == "__main__":
    asyncio.run(main())
