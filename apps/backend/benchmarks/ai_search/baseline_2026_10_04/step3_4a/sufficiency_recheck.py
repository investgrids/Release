"""
Step 3.4A gate-ON recheck of the frozen 18 questions. NO model call: the market-pulse LLM classifier is switched off and the three specialists are replaced by a stub that only counts calls.
Intent, entities, routing, retrieval, filters, premise, Gate A and the finalizer are the real code. For each question this records Gate A's decision and whether a specialist was reached.

Run from apps/backend:
  PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4a/sufficiency_recheck.py
Writes sufficiency_recheck.json and per_question_table.md next to this file.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search.response_finalize import finalize_v3_response  # noqa: E402


async def _no_classifier(query: str) -> bool:
    return False


mp_mod._classify_market_pulse_llm = _no_classifier


async def run_one(q: dict) -> dict:
    cap = {"calls": 0}

    def make_stub(kind):
        async def stub(query, evidence, intent_data, entities):
            cap["calls"] += 1
            cap["kind"] = kind
            return ({"_degraded_reason": "capacity"}, True)
        return stub

    P.comparison_specialist.run = make_stub("comparison")
    P.company_specialist.run = make_stub("company")
    P.sector_specialist.run = make_stub("sector")

    final = None
    stages = []
    async with AsyncSessionLocal() as db:
        async for stage, _label, payload in P._run_v3_steps(q["query"], db, None):
            stages.append(stage)
            if payload is not None:
                final = payload
    res = finalize_v3_response(q["query"], final, x_admin_key=None, was_cached=False)
    suff = (res or {}).get("evidence_sufficiency") or {}
    return {"id": q["id"], "type": q["type"], "query": q["query"], "specialist_called": cap["calls"] > 0, "specialist_calls": cap["calls"], "stages": stages,
            "degraded_reason": (res or {}).get("degraded_reason"), "gate_a": {k: suff.get(k) for k in ("status", "kind", "required", "satisfied", "missing", "reason", "missing_entities")} if suff else None,
            "premise_check": (res or {}).get("premise_check"), "public_title": (res or {}).get("public_title"), "rating": ((res or {}).get("investment_verdict") or {}).get("rating"),
            "confidence": ((res or {}).get("answer") or {}).get("confidence"), "summary": ((res or {}).get("answer") or {}).get("summary")}


async def main():
    qs = json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]
    rows = []
    for q in qs:
        r = await run_one(q)
        rows.append(r)
        print(r["id"], "| specialist_called:", r["specialist_called"], "| gate A:", (r["gate_a"] or {}).get("status"), (r["gate_a"] or {}).get("kind"), "| missing:", (r["gate_a"] or {}).get("missing"), flush=True)
    (HERE / "sufficiency_recheck.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    lines = ["| ID | Type | Gate A | Kind | Missing | Specialist reached | Verdict shown |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        g = r["gate_a"] or {}
        lines.append(f"| {r['id']} | {r['type']} | {g.get('status') or 'n/a'} | {g.get('kind') or ''} | {', '.join(g.get('missing') or []) or '-'} | {'yes' if r['specialist_called'] else 'NO'} | "
                     f"{'none (Not Applicable)' if r['rating'] in (None, 'Not Applicable') else r['rating']} |")
    (HERE / "per_question_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("model calls made by this script: 0 (classifier disabled, specialists stubbed)")


if __name__ == "__main__":
    asyncio.run(main())
