"""
Retrieval re-check of the frozen 18 questions after the evidence-scope and claim-source changes. Makes NO model call: the market-pulse LLM classifier is switched to "no" and the three
specialists are replaced by a stub that records the evidence bundle and returns a capacity-degraded marker. Everything else (intent, entities, routing, retrieval, filters, premise, finalizer)
is the real code.

Writes, next to this file:
  stage1_results.json / stage2_results.json   same shapes the frozen build_report.py reads (so the frozen route / entities / evidence rules score this run unchanged)
  recheck.json                                per-question bundle snapshot, irrelevance check, premise, index

Run from apps/backend:
  PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step4_scope/retrieval_recheck.py
  BASELINE_OUT_DIR=<this dir> python benchmarks/ai_search/baseline_2026_10_04/build_report.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "step3"))

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search.response_finalize import finalize_v3_response  # noqa: E402

import answer_checks as AC  # noqa: E402
import stage1_deterministic as S1  # noqa: E402  (for _summarize_evidence only)


async def _no_classifier(query: str) -> bool:
    return False


mp_mod._classify_market_pulse_llm = _no_classifier   # regex detection still runs; the LLM fallback does not


async def run_one(q: dict) -> tuple[dict, dict, dict]:
    cap: dict = {}

    def make_stub(kind):
        async def stub(query, evidence, intent_data, entities):
            cap.update(kind=kind, evidence=evidence, intent=dict(intent_data), entities=entities)
            return ({"_degraded_reason": "capacity"}, True)
        return stub

    P.comparison_specialist.run = make_stub("comparison")
    P.company_specialist.run = make_stub("company")
    P.sector_specialist.run = make_stub("sector")

    t0 = time.monotonic()
    final = None
    async with AsyncSessionLocal() as db:
        async for _stage, _label, payload in P._run_v3_steps(q["query"], db, None):
            if payload is not None:
                final = payload
    elapsed = round(time.monotonic() - t0, 2)
    res = finalize_v3_response(q["query"], final, x_admin_key=None, was_cached=False)
    ents = cap.get("entities") or {}
    bundle = cap.get("evidence")

    s1 = {"id": q["id"], "type": q["type"], "query": q["query"], "elapsed_s": elapsed, "short_circuit": None if cap else ((final or {}).get("degraded_reason") or "unknown"),
          "specialist": cap.get("kind"), "ui_mode": (final or {}).get("ui_mode"), "intent": (cap.get("intent") or {}).get("intent"),
          "entities": {"companies": ents.get("companies"), "sectors": ents.get("sectors"), "policies": ents.get("policies")}}
    rec = {"id": q["id"], "plan_kind": None}
    if bundle is not None:
        s1["evidence"] = S1._summarize_evidence(bundle, [c for c in (ents.get("companies") or [])])
        s1["plan_kind"] = bundle.plan_kind
        s1["filter_report"] = bundle.filter_report
        snap = AC.snapshot_evidence(bundle)
        rec = {"id": q["id"], "plan_kind": bundle.plan_kind, "premise": bundle.premise, "irrelevance": AC.bundle_irrelevance(snap, ents.get("companies") or [], ents.get("sectors") or []),
               "evidence_total": AC.evidence_total(snap), "snapshot": snap}
    shown_events = len((res or {}).get("related_events") or [])
    s2 = {"id": q["id"], "type": q["type"], "query": q["query"], "latency_s": elapsed, "model_calls": [], "model_call_count": 0, "skipped_by_circuit": None, "cap_hit": False,
          "synthesis_incomplete": (res or {}).get("synthesis_incomplete"), "degraded_reason": (res or {}).get("degraded_reason"), "answer_availability": (res or {}).get("answer_availability"),
          "summary": ((res or {}).get("answer") or {}).get("summary"), "fabricated_when_degraded": False,
          "attribution": {"checked": True, "related_events_shown": shown_events, "news_shown": len((res or {}).get("news") or [])}}
    return s1, s2, rec


async def main():
    qs = json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]
    s1s, s2s, recs = [], [], []
    for q in qs:
        s1, s2, rec = await run_one(q)
        s1s.append(s1)
        s2s.append(s2)
        recs.append(rec)
        print(q["id"], s1.get("specialist"), s1.get("ui_mode"), s1.get("short_circuit"), "| bundle items:", rec.get("evidence_total"), "| irrelevant:", len((rec.get("irrelevance") or {}).get("irrelevant_items", [])), flush=True)
    (HERE / "stage1_results.json").write_text(json.dumps(s1s, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (HERE / "stage2_results.json").write_text(json.dumps({"state": {"calls": 0, "circuit_open": False}, "results": s2s}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (HERE / "recheck.json").write_text(json.dumps(recs, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("model calls made by this script: 0 (classifier disabled, specialists stubbed)")


if __name__ == "__main__":
    asyncio.run(main())
