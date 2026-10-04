"""
Baseline Step 1, deterministic stage: runs the REAL v3 pipeline for every question in questions.json with ONLY the three specialist LLM calls stubbed out.
Everything upstream of the model (decision intent, entities, ambiguity/short-circuit checks, routing, evidence retrieval, ui_mode) is the production code.
No paid or free-tier model call is made. Output: stage1_results.json (raw per-question record) next to this file.

Run from apps/backend:  PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/stage1_deterministic.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402

HERE = Path(__file__).parent
OUT = Path(os.environ.get("BASELINE_OUT_DIR") or HERE)   # a rerun writes elsewhere so the committed baseline is never overwritten
OUT.mkdir(parents=True, exist_ok=True)
TODAY = datetime(2026, 10, 4, tzinfo=timezone.utc)


def _age_days(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return round((TODAY - d).total_seconds() / 86400, 1)
    except Exception:
        return None


def _summarize_evidence(ev, symbols: list[str]) -> dict:
    def ev_row(e):
        syms = [c.get("symbol") for c in (e.get("companies") or []) if isinstance(c, dict)]
        d = e.get("event_date") or e.get("published_at")
        return {"title": (e.get("title") or "")[:110], "date": e.get("date"), "age_days": _age_days(d), "source": e.get("source"), "impact": e.get("impact_score"),
                "tagged_symbols": syms[:6], "about_query_company": bool(set(syms) & set(symbols)) if symbols else None}

    def news_row(n):
        return {"headline": (n.get("headline") or "")[:110], "published_at_raw": n.get("published_at"), "source": n.get("source")}

    return {
        "events": [ev_row(e) for e in ev.events],
        "news": [news_row(n) for n in ev.news],
        "policies": [{"title": (p.get("title") or "")[:110], "ministry": p.get("ministry"), "status": p.get("status"), "impact_score": p.get("impact_score")} for p in ev.policies],
        "announcements": [{"subject": (a.get("subject") or "")[:90], "category": a.get("category"), "date": a.get("announcement_date")} for a in (ev.announcements or [])],
        "results_announcements": len(ev.results_announcements or []),
        "historical": [{"title": (h.get("title") or h.get("event") or "")[:90], "similarity": h.get("similarity")} for h in (ev.similar_historical or [])],
        "sector_rows": [{"name": s.get("name"), "value": s.get("value")} for s in (ev.sector_rows or [])][:20],
        "valuation_symbols": sorted((ev.valuation or {}).keys()),
        "valuation": {k: {kk: v.get(kk) for kk in ("pe", "pb")} for k, v in (ev.valuation or {}).items()},
        "vix_level": ev.vix_level,
        "macro_indices": [i.get("name") for i in (ev.macro_indices or [])],
        "company_story": bool(ev.company_story),
        "context_lines": len(ev.context_lines or []),
        "context_chars": len(ev.to_context_text()),
        "development_count": ev.development_count,
        "source_count": ev.source_count,
    }


async def run_one(q: dict) -> dict:
    cap: dict = {}

    def make_stub(kind):
        async def stub(query, evidence, intent_data, entities):
            cap.update(kind=kind, evidence=evidence, intent=dict(intent_data), entities=entities)
            return ({"_degraded_reason": "stage1_stub"}, True)
        return stub

    P.comparison_specialist.run = make_stub("comparison")
    P.company_specialist.run = make_stub("company")
    P.sector_specialist.run = make_stub("sector")

    t0 = time.monotonic()
    final, stages = None, []
    async with AsyncSessionLocal() as db:
        async for stage, _label, payload in P._run_v3_steps(q["query"], db, None):
            stages.append(stage)
            if payload is not None:
                final = payload
    rec = {"id": q["id"], "type": q["type"], "query": q["query"], "stages": stages, "elapsed_s": round(time.monotonic() - t0, 2)}
    ents = cap.get("entities") or {}
    rec["short_circuit"] = None if cap else ((final or {}).get("degraded_reason") or (final or {}).get("type") or "unknown")
    rec["specialist"] = cap.get("kind")
    rec["ui_mode"] = (final or {}).get("ui_mode")
    rec["intent"] = (cap.get("intent") or {}).get("intent")
    rec["entities"] = {"companies": ents.get("companies"), "sectors": ents.get("sectors"), "policies": ents.get("policies")}
    if cap.get("evidence") is not None:
        rec["evidence"] = _summarize_evidence(cap["evidence"], [c for c in (ents.get("companies") or [])])
        rec["plan_kind"] = getattr(cap["evidence"], "plan_kind", None)          # present from Step 2 on
        rec["filter_report"] = getattr(cap["evidence"], "filter_report", None)
    return rec


async def main():
    qs = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))["questions"]
    out = []
    for q in qs:
        try:
            out.append(await run_one(q))
        except Exception as exc:  # a crash is itself a finding
            out.append({"id": q["id"], "type": q["type"], "query": q["query"], "crash": f"{type(exc).__name__}: {str(exc)[:300]}"})
        print(q["id"], out[-1].get("specialist"), out[-1].get("ui_mode"), out[-1].get("short_circuit"), out[-1].get("crash", ""), flush=True)
    (OUT / "stage1_results.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("wrote", OUT / "stage1_results.json")


if __name__ == "__main__":
    asyncio.run(main())
