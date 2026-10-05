"""
Step 3.4G.1: frozen-18 model-free selection snapshot. ZERO provider calls (classifier off, specialists stubbed, ai_service call replaced by a recorder that must stay at 0).

Run once BEFORE and once AFTER the retrieval-ranking change, same live-news snapshot (live_news_snapshot.json, taken on the first run) so the comparison is not confounded by the live feed moving.
The snapshot emulates the real function in its usual warm-cache state: it returns snapshot[:limit], so the old code (limit=20) sees the newest 20 and the new code (limit=60) sees all 60.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4g1/frozen18_selection.py <label>     # label: before | after
Writes selection_<label>.json next to this file.
"""
from __future__ import annotations

import asyncio
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
LABEL = sys.argv[1] if len(sys.argv) > 1 else "run"

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service as S  # noqa: E402
from app.services import news_fetcher as NF  # noqa: E402
from app.services.ai_search import conclusion_scope as CSC  # noqa: E402
from app.services.ai_search import evidence as evidence_mod  # noqa: E402
from app.services.ai_search import evidence_filter as EF  # noqa: E402
from app.services.ai_search import evidence_scope as scope  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search import retrieval as R  # noqa: E402
from app.services.ai_search.response_finalize import finalize_v3_response  # noqa: E402

CALLS: list = []


async def _recorder(*a, **k):
    CALLS.append(1)
    return ""


async def _no_cls(q):
    return False


S._call_with_fallback = _recorder
mp_mod._call_with_fallback = _recorder
mp_mod._classify_market_pulse_llm = _no_cls

SNAP = HERE / "live_news_snapshot.json"
_snapshot: list = []


async def _frozen_live_news(limit: int = 20):
    return list(_snapshot[:limit])


_OUTLOOK = re.compile(r"(?<![a-z])(?:outlook|guidance|forecast|expect\w*|demand|slow\w*|weak\w*|recover\w*|growth|headwinds?|tailwinds?|pressure|crash\w*|rall\w*|surge\w*|jump\w*|fall\w*|decline\w*)(?![a-z])", re.I)
_RATE = re.compile(r"(?<![a-z])(?:repo|rate cut|rate hike|rate decision|mpc|monetary|policy rate|interest rate|rates?|yields?|inflation)(?![a-z])", re.I)


def tags(title: str, summary: str = "") -> list[str]:
    t = []
    if scope.is_administrative(title, summary):
        t.append("administrative")
    if CSC._OPERATING.search(title):
        t.append("operating_result")
    if _OUTLOOK.search(title):
        t.append("outlook_demand")
    if _RATE.search(title):
        t.append("rate_policy")
    return t


def jaccard(a: str, b: str) -> float:
    wa, wb = set(EF.content_words(a)), set(EF.content_words(b))
    return len(wa & wb) / max(1, len(wa | wb))


def dup_pairs(titles: list[str], thr: float = 0.5) -> int:
    return sum(1 for i in range(len(titles)) for j in range(i + 1, len(titles)) if jaccard(titles[i], titles[j]) >= thr)


def prompt_for(kind, query, evidence, intent_data, entities):
    from app.services.ai_search.specialists import company as C, comparison as K, sector as SE
    return {"company": C.build_prompt, "comparison": K.build_prompt, "sector": SE.build_prompt}[kind](query, evidence, intent_data, entities)


async def run_one(q: dict, prev_titles: dict) -> dict:
    stash: dict = {}
    real_collect = evidence_mod.collect

    async def stash_collect(query, intent_data, entities, db):
        b = await real_collect(query, intent_data, entities, db)
        stash.update(bundle=b, intent=dict(intent_data), entities=entities)
        return b

    P.evidence_mod.collect = stash_collect
    called = {"n": 0}

    def make_stub(kind):
        async def stub(query, evidence, intent_data, entities):
            called["n"] += 1
            return ({"_degraded_reason": "capacity"}, True)
        return stub

    P.comparison_specialist.run = make_stub("comparison")
    P.company_specialist.run = make_stub("company")
    P.sector_specialist.run = make_stub("sector")
    final = None
    async with AsyncSessionLocal() as db:
        async for _s, _l, payload in P._run_v3_steps(q["query"], db, None):
            if payload is not None:
                final = payload
    P.evidence_mod.collect = real_collect
    res = finalize_v3_response(q["query"], final, x_admin_key=None, was_cached=False) or {}
    b = stash.get("bundle")
    entities = stash.get("entities") or {}
    spec, kind = P._route_specialist(q["query"], stash.get("intent") or {}, entities)
    prompt = prompt_for(kind, q["query"], b, stash.get("intent") or {}, entities) if b is not None else ""
    suff = res.get("evidence_sufficiency") or {}

    def items(rows, tkey, dkey, kindname):
        out = []
        for r in rows:
            title = r.get(tkey) or ""
            age = EF.age_days(r.get(dkey), None) if dkey != "event" else EF._event_age(r, None)
            out.append({"id": str(r.get("id")), "title": title, "age_days": None if age is None else round(age, 1), "tags": tags(title, r.get("summary") or r.get("description") or ""),
                        "in_prompt": (title.strip()[:60] in prompt) if title else False, "impact": r.get("impact_score")})
        return out

    ev = items(b.events, "title", "event", "event") if b is not None else []
    nw = items(b.news, "headline", "published_at", "news") if b is not None else []
    an = items(b.announcements or [], "subject", "announcement_date", "announcement") if b is not None else []
    allt = [x["title"] for x in ev + nw + an]
    ages = [x["age_days"] for x in ev + nw + an if x["age_days"] is not None]
    return {"id": q["id"], "type": q["type"], "query": q["query"], "ui_mode": res.get("ui_mode"), "specialist": res.get("specialist"), "entities": {k: entities.get(k) for k in ("companies", "sectors", "policies")},
            "gate_a": {k: suff.get(k) for k in ("status", "kind", "missing")}, "would_call_model": called["n"] > 0, "premise": (res.get("premise_check") or {}).get("status"),
            "counts": {"events": len(ev), "news": len(nw), "announcements": len(an)}, "events": ev, "news": nw, "announcements": an, "index_ids": [i["id"] for i in b.index()] if b is not None else [],
            "duplicate_pairs": dup_pairs(allt), "freshness_median_days": round(statistics.median(ages), 1) if ages else None, "freshness_max_days": max(ages) if ages else None,
            "tag_counts": {t: sum(1 for x in ev + nw + an if t in x["tags"]) for t in ("administrative", "operating_result", "outlook_demand", "rate_policy")},
            "alignment": ({"index_ids": sorted(i["id"] for i in b.index()), "markers_in_prompt": sorted(set(re.findall(r"\[([ENPAC]\d{1,3})\]", prompt))), "prompt_kind": getattr(b, "prompt_kind", None),
                           "index_not_in_prompt": sorted({i["id"] for i in b.index()} - set(re.findall(r"\[([ENPAC]\d{1,3})\]", prompt))),
                           "prompt_not_in_index": sorted(set(re.findall(r"\[([ENPAC]\d{1,3})\]", prompt)) - {i["id"] for i in b.index()}), "prompt_chars": len(prompt), "composition_contract_count": prompt.count(__import__("app.services.ai_search.schema", fromlist=["COMPOSITION_RULES"]).COMPOSITION_RULES)} if b is not None else None),
            "rank_trace": getattr(b, "rank_trace", None) if b is not None else None,
            "filter_report": getattr(b, "filter_report", None) if b is not None else None}


async def main():
    global _snapshot
    if SNAP.exists():
        _snapshot = json.loads(SNAP.read_text(encoding="utf-8"))
    else:
        live = await NF.get_live_news(limit=60) or []
        _snapshot = live
        SNAP.write_text(json.dumps(live, indent=1, ensure_ascii=False), encoding="utf-8")
    R.get_live_news = _frozen_live_news
    NF.get_live_news = _frozen_live_news
    qs = json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]
    rows = []
    for q in qs:
        r = await run_one(q, {})
        rows.append(r)
        print(r["id"], r["ui_mode"], "| gate", r["gate_a"]["status"], r["gate_a"]["kind"], "| counts", r["counts"], "| dups", r["duplicate_pairs"], "| median age", r["freshness_median_days"], flush=True)
    (HERE / f"selection_{LABEL}.json").write_text(json.dumps({"label": LABEL, "provider_calls_made": len(CALLS), "snapshot_items": len(_snapshot), "results": rows}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("provider calls:", len(CALLS), "| snapshot items:", len(_snapshot))


if __name__ == "__main__":
    asyncio.run(main())
