"""
Baseline Step 1, live stage: the REAL run_ai_search_v3 + finalize_v3_response (the two functions every route calls) for each question, with every model call counted and capped.

Caps (cost + provider quota control; local keys share free-tier quotas with production):
  MAX_MODEL_CALLS        hard cap on pipeline-level model calls across the whole run (classifier + specialist). Beyond it a call returns "" (a capacity failure) and the question is marked cap_hit.
  CIRCUIT_AFTER          after this many CONSECUTIVE specialist calls that end capacity-degraded, further specialist and classifier calls are skipped (marked skipped_by_circuit) so a dead
                         provider chain is not hammered. Skipped questions' answer-level checks stay UNVERIFIED, never PASS.
No retries. One attempt per question.

Run from apps/backend:  PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/stage2_live.py
Output: stage2_results.json
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service  # noqa: E402
from app.services.ai_search import evidence as evidence_mod  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search.response_finalize import finalize_v3_response  # noqa: E402

HERE = Path(__file__).parent
OUT = Path(os.environ.get("BASELINE_OUT_DIR") or HERE)
OUT.mkdir(parents=True, exist_ok=True)
MAX_MODEL_CALLS = 30
CIRCUIT_AFTER = 3

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
    current.setdefault("model_calls", []).append({"kind": kind, "ok": bool(out), "ms": round((time.monotonic() - t0) * 1000), "provider": ai_service._AI_USAGE.get("last_provider") if out else None,
                                                  "max_tokens": max_tokens})
    return out


ai_service._call_with_fallback = counted_call
mp_mod._call_with_fallback = counted_call

_real_collect = evidence_mod.collect


async def stash_collect(query, intent_data, entities, db):
    bundle = await _real_collect(query, intent_data, entities, db)
    current["evidence_obj"] = bundle
    return bundle


evidence_mod.collect = stash_collect
P.evidence_mod.collect = stash_collect

_NUM = re.compile(r"(?<![\w.])[-+]?\d[\d,]*\.?\d*%?")
TEXT_FIELDS = ("summary", "bottom_line", "what_happened", "why_it_happened", "immediate_impact", "medium_term", "long_term", "what_priced_in")


def _answer_text(res: dict) -> str:
    a = res.get("answer") or {}
    parts = [str(a.get(k) or "") for k in TEXT_FIELDS]
    parts += [str(x) for x in (a.get("risks") or [])] + [str(x) for x in (a.get("opportunities") or [])]
    for d in res.get("key_drivers") or []:
        parts.append(json.dumps(d, ensure_ascii=False) if isinstance(d, dict) else str(d))
    for c in res.get("companies") or []:
        parts.append(str(c.get("reason") or "") + " " + str(c.get("why_it_matters") or ""))
    ai = res.get("ai_conclusion") or {}
    parts += [str(v) for v in ai.values() if isinstance(v, str)]
    return "\n".join(parts)


def _norm(tok: str) -> str:
    return tok.replace(",", "").rstrip(".").lstrip("+").rstrip("%")


def _evidence_text(ev, query: str) -> str:
    chunks = [query, ev.to_context_text()]
    for e in ev.events:
        chunks += [str(e.get("title")), str(e.get("summary")), str(e.get("date"))]
    for n in ev.news:
        chunks += [str(n.get("headline")), str(n.get("summary")), str(n.get("published_at"))]
    for p in ev.policies:
        chunks += [str(p.get("title")), str(p.get("summary"))]
    for a in ev.announcements or []:
        chunks += [str(a.get("subject")), str(a.get("announcement_date"))]
    chunks.append(json.dumps(ev.valuation, default=str))
    chunks.append(json.dumps(ev.sector_rows, default=str))
    chunks.append(json.dumps(ev.macro_indices, default=str))
    chunks.append(str(ev.vix_level))
    chunks.append(json.dumps(ev.similar_historical, default=str))
    return " ".join(chunks)


def unsupported_numbers(res: dict, ev, query: str) -> list[str]:
    """Numbers (2+ digits, or decimals, or percentages) in the generated text that appear nowhere in the query or the retrieved evidence. Years 2000-2035 are ignored.
    Heuristic: a flag is a candidate for manual review, not a verdict."""
    if ev is None:
        return []
    hay = _norm(_evidence_text(ev, query))
    hay_nums = {_norm(t) for t in _NUM.findall(_evidence_text(ev, query))}
    out = []
    for tok in _NUM.findall(_answer_text(res)):
        n = _norm(tok)
        if not n or n in ("-", "+"):
            continue
        if re.fullmatch(r"\d{4}", n) and 2000 <= int(n) <= 2035:
            continue
        if "." not in n and len(n) < 2 and not tok.endswith("%"):
            continue
        if n in hay_nums or n in hay:
            continue
        out.append(tok)
    return sorted(set(out))


def attribution_check(res: dict, ev) -> dict:
    if ev is None:
        return {"checked": False}
    have = set(ev.to_source_ids())
    claimed = set(res.get("source_attribution") or [])
    cites = set(res.get("citations") or [])
    news_sources = {n.get("source") for n in ev.news}
    return {"checked": True, "attribution_ids_not_in_evidence": sorted(claimed - have), "citations_not_in_news_sources": sorted(c for c in cites if c not in news_sources),
            "related_events_shown": len(res.get("related_events") or []), "news_shown": len(res.get("news") or [])}


def consistency(res: dict) -> dict:
    iv = res.get("investment_verdict") or {}
    de = res.get("decision_engine_v2") or {}
    ac = res.get("ai_conclusion") or {}
    ev2 = iv.get("engine_verdict") or {}
    return {"investment_verdict.rating": iv.get("rating"), "investment_verdict.direction": iv.get("direction"), "engine_verdict.rating": ev2.get("rating"),
            "decision_engine_v2.verdict_scale": de.get("verdict_scale"), "answer.sentiment": (res.get("answer") or {}).get("sentiment"),
            "answer.confidence": (res.get("answer") or {}).get("confidence"), "confidence_data.score": (res.get("confidence_data") or {}).get("score"),
            "opportunity_score": iv.get("opportunity_score"),
            "companies": [{"symbol": c.get("symbol"), "impact_score": c.get("impact_score"), "impact_type": c.get("impact_type")} for c in (res.get("companies") or [])][:6]}


async def run_one(q: dict) -> dict:
    current.clear()
    t0 = time.monotonic()
    rec = {"id": q["id"], "type": q["type"], "query": q["query"]}
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
    if res is None:
        return rec
    ev = current.get("evidence_obj")
    a = res.get("answer") or {}
    rec.update({
        "ui_mode": res.get("ui_mode"), "specialist": res.get("specialist"), "type_field": res.get("type"), "cached": was_cached,
        "synthesis_incomplete": res.get("synthesis_incomplete"), "degraded_reason": res.get("degraded_reason"), "answer_availability": res.get("answer_availability"),
        "summary": a.get("summary"), "bottom_line": a.get("bottom_line"), "confidence": a.get("confidence"), "sources_count": a.get("sources_count"),
        "full_text_excerpt": _answer_text(res)[:2500],
        "unsupported_numbers": unsupported_numbers(res, ev, q["query"]) if not res.get("synthesis_incomplete") else None,
        "attribution": attribution_check(res, ev), "consistency": consistency(res), "timing": res.get("timing"),
        "validation": res.get("validation"),
        "fabricated_when_degraded": bool(res.get("synthesis_incomplete") and ((res.get("investment_verdict") or {}).get("rating") not in (None, "Not Applicable") or a.get("confidence") is not None
                                                                              or (res.get("companies") or []) or (res.get("investment_verdict") or {}).get("top_picks"))),
    })
    # specialist-level capacity circuit breaker
    if res.get("degraded_reason") in ("capacity", "parse_failure"):
        state["consecutive_capacity"] += 1
        if state["consecutive_capacity"] >= CIRCUIT_AFTER:
            state["circuit_open"] = True
    elif res.get("synthesis_incomplete") is False:
        state["consecutive_capacity"] = 0
    return rec


async def main():
    qs = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))["questions"]
    out = []
    for q in qs:
        out.append(await run_one(q))
        r = out[-1]
        print(r["id"], f'{r["latency_s"]}s calls={r["model_call_count"]}', r.get("ui_mode"), "incomplete=", r.get("synthesis_incomplete"), r.get("degraded_reason"), r.get("crash", ""), flush=True)
        (OUT / "stage2_results.json").write_text(json.dumps({"state": state, "results": out}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("total pipeline-level model calls:", state["calls"], "circuit_open:", state["circuit_open"])


if __name__ == "__main__":
    asyncio.run(main())
