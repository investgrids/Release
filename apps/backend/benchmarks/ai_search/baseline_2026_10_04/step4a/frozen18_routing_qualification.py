"""
Step 4A: frozen-18 routing qualification (copy of the Step 3.4E script, output written into step4a/). ZERO provider calls: the market-pulse classifier is off, every specialist is replaced by a stub that only records its inputs, and the shared model
call (`ai_service._call_with_fallback`) is replaced by a recorder that must stay at zero. Intent, entities, routing, retrieval (real DB, RSS and market data), filters, premise, Gate A and conclusion
scope are the real code at the current commit. Writes frozen18_matrix.json / frozen18_matrix.md next to this file; the committed Step 4 baseline files are not touched.

Run from apps/backend:  PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4e/frozen18_deterministic.py
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent

from app.api.companies import _NSE_UNIVERSE  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service as S  # noqa: E402
from app.services.ai_search import conclusion_scope as scope_mod  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search.response_finalize import finalize_v3_response  # noqa: E402

PROVIDER_CALLS: list[str] = []


async def _recorder(*a, **k):
    PROVIDER_CALLS.append("call")
    return ""


async def _no_classifier(query: str) -> bool:
    return False


S._call_with_fallback = _recorder
mp_mod._call_with_fallback = _recorder
mp_mod._classify_market_pulse_llm = _no_classifier


def _entities_ok(exp: dict, got: dict) -> tuple[bool, str]:
    problems = []
    gc, gs, gp = set(got.get("companies") or []), {s.lower() for s in got.get("sectors") or []}, {p.lower() for p in got.get("policies") or []}
    if "companies" in exp and gc != set(exp["companies"]):
        problems.append(f"companies {sorted(gc)} != {exp['companies']}")
    if "companies" not in exp and gc:
        problems.append(f"unexpected companies {sorted(gc)}")
    if "sectors" in exp and gs != {s.lower() for s in exp["sectors"]}:
        problems.append(f"sectors {sorted(gs)} != {exp['sectors']}")
    if "sectors" not in exp and gs:
        problems.append(f"unexpected sectors {sorted(gs)}")
    if "policies" in exp and not {p.lower() for p in exp["policies"]} <= gp:
        problems.append(f"policies {sorted(gp)} missing {exp['policies']}")
    return (not problems, "; ".join(problems) or "as expected")


async def run_one(q: dict) -> dict:
    cap: dict = {"calls": 0}

    def make_stub(kind):
        async def stub(query, evidence, intent_data, entities):
            cap.update(calls=cap["calls"] + 1, kind=kind, evidence=evidence, entities=entities, intent=dict(intent_data))
            return ({"_degraded_reason": "capacity"}, True)
        return stub

    P.comparison_specialist.run = make_stub("comparison")
    P.company_specialist.run = make_stub("company")
    P.sector_specialist.run = make_stub("sector")
    t0 = time.monotonic()
    final = None
    stages = []
    async with AsyncSessionLocal() as db:
        async for stage, _label, payload in P._run_v3_steps(q["query"], db, None):
            stages.append(stage)
            if payload is not None:
                final = payload
    res = finalize_v3_response(q["query"], final, x_admin_key=None, was_cached=False) or {}
    suff = res.get("evidence_sufficiency") or {}
    ents = cap.get("entities") or {"companies": [], "sectors": [], "policies": []}
    ev = cap.get("evidence")
    if ev is None:      # Gate A refused before the specialist: entities come from the refusal response
        ents = {"companies": list((res.get("context_used") or {}).get("companies") or []), "sectors": [], "policies": []}
    scope = scope_mod.assess(q["query"], cap.get("intent"), ents, ev, _NSE_UNIVERSE) if ev is not None else None
    exp_route, exp_ents = q["expected_route"], q["expected_entities"]
    ui = res.get("ui_mode")
    ents_ok, ents_note = _entities_ok(exp_ents, {"companies": ents.get("companies"), "sectors": ents.get("sectors"), "policies": ents.get("policies")}) if ev is not None else (None, "n/a (refused before specialist)")
    kind = suff.get("kind")
    gate = suff.get("status")
    if res.get("degraded_reason") == "insufficient_evidence":
        outcome = "REFUSAL_GATE_A"
    elif kind == "not_gated":
        outcome = "NOT_GATED_EDUCATION_OR_GENERAL"
    elif scope and scope.get("partial"):
        outcome = "SUFFICIENT_PARTIAL_SCOPE"
    elif cap["calls"]:
        outcome = "SUFFICIENT"
    else:
        outcome = "NO_SPECIALIST_REACHED"
    return {
        "id": q["id"], "type": q["type"], "query": q["query"], "elapsed_s": round(time.monotonic() - t0, 1),
        "expected": {"specialist": exp_route["specialist"], "ui_mode": exp_route["ui_mode"]},
        "got": {"specialist": res.get("specialist"), "ui_mode": ui, "intent": res.get("intent")},
        "route_ui_ok": ui == exp_route["ui_mode"], "route_specialist_ok": res.get("specialist") == exp_route["specialist"],
        "entities": {"companies": ents.get("companies"), "sectors": ents.get("sectors"), "policies": ents.get("policies")}, "entities_ok": ents_ok, "entities_note": ents_note,
        "gate_a": {k: suff.get(k) for k in ("status", "kind", "required", "satisfied", "missing", "reason", "missing_entities")},
        "premise": (res.get("premise_check") or {}).get("status"),
        "conclusion_scope": ({k: scope.get(k) for k in ("requested", "authorized", "partial", "missing")} if scope else None),
        "would_call_model": cap["calls"] > 0, "outcome": outcome,
        "evidence": ({"events": len(ev.events), "news": len(ev.news), "announcements": len(ev.announcements or []), "policies": len(ev.policies), "valuation_symbols": sorted((ev.valuation or {}).keys()),
                      "sector_rows": len(ev.sector_rows or []), "vix": ev.vix_level, "context_lines": len(ev.context_lines or [])} if ev is not None else None),
        "answer_availability": (res.get("answer_availability") or {}).get("state"),
    }


async def main():
    qs = json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]
    rows = []
    for q in qs:
        r = await run_one(q)
        rows.append(r)
        print(r["id"], r["outcome"], "| ui", r["got"]["ui_mode"], "ok" if r["route_ui_ok"] else "DIFF", "| gate", r["gate_a"]["status"], r["gate_a"]["kind"], "| model?", r["would_call_model"], flush=True)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    out = {"commit": commit, "provider_calls_made": len(PROVIDER_CALLS), "n": len(rows), "results": rows}
    (HERE / "frozen18_matrix.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    lines = ["| ID | Type | UI mode (exp -> got) | Specialist (exp -> got) | Entities | Gate A | Premise | Conclusion scope | Model call | Outcome |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ga = r["gate_a"]
        sc = r["conclusion_scope"]
        lines.append(f"| {r['id']} | {r['type']} | {r['expected']['ui_mode']} -> {r['got']['ui_mode']}{'' if r['route_ui_ok'] else ' **DIFF**'} | {r['expected']['specialist']} -> {r['got']['specialist']}{'' if r['route_specialist_ok'] else ' (diff)'} | "
                     f"{'OK' if r['entities_ok'] else ('n/a' if r['entities_ok'] is None else 'DIFF: ' + r['entities_note'])} | {ga['status']}/{ga['kind']}{' missing ' + ','.join(ga['missing']) if ga['missing'] else ''} | {r['premise']} | "
                     f"{(sc['requested'] + ' -> ' + sc['authorized']) if sc and sc['requested'] != 'not_applicable' else '-'} | {'yes' if r['would_call_model'] else 'no'} | {r['outcome']} |")
    (HERE / "frozen18_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"commit {commit} | provider calls made: {len(PROVIDER_CALLS)}")


if __name__ == "__main__":
    asyncio.run(main())
