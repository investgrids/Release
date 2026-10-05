"""
Step 3.4G: model-free evidence trace for CR1, SR2 and MP1. ZERO provider calls (classifier off, specialists stubbed, ai_service call replaced by a recorder that must stay at zero).

For every item that exists in the upstream universe it records the full journey:
  exists upstream -> retrieved (rank within the retrieval limit) -> filter verdict (the REAL filter_bundle run on that single item, with the reason) -> in the final bundle (rank)
  -> index id (what claim_sources may cite) -> VISIBLE IN THE PROMPT (the real specialist prompt is built and searched) -> position in the prompt -> used in the previous live answer (3.4F artifact)
plus semantic tags (administrative / operating-result / outlook-demand / rate-policy / tips / company-or-sector-eligible) so findings generalise beyond these three strings.

Run from apps/backend:  PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4g/evidence_trace.py
Writes evidence_trace.json and evidence_trace.md next to this file.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
PREV = HERE.parent / "step3_4c" / "openai_3_4f_run2.json"

from app.api.companies import _NSE_UNIVERSE as UNIVERSE  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service as S  # noqa: E402
from app.services.ai_search import conclusion_scope as CSC  # noqa: E402
from app.services.ai_search import entities as entities_mod  # noqa: E402
from app.services.ai_search import evidence as evidence_mod  # noqa: E402
from app.services.ai_search import evidence_filter as EF  # noqa: E402
from app.services.ai_search import evidence_scope as scope  # noqa: E402
from app.services.ai_search import intent as intent_mod  # noqa: E402
from app.services.ai_search import market_pulse as mp_mod  # noqa: E402
from app.services.ai_search import pipeline as P  # noqa: E402
from app.services.ai_search import retrieval as R  # noqa: E402
from app.services.ai_search.decision_intent import _detect_decision_intent  # noqa: E402
from app.services.ai_search.evidence import EvidenceBundle  # noqa: E402

CALLS: list = []


async def _recorder(*a, **k):
    CALLS.append(1)
    return ""


async def _no_cls(q):
    return False


S._call_with_fallback = _recorder
mp_mod._call_with_fallback = _recorder
mp_mod._classify_market_pulse_llm = _no_cls

QUESTIONS = {"CR1": "What is the outlook for Kotak Mahindra Bank?", "SR2": "What is the outlook for the IT services sector?", "MP1": "What happens to Indian banks if the RBI cuts the repo rate?"}

_OUTLOOK = re.compile(r"(?<![a-z])(?:outlook|guidance|forecast|expect\w*|demand|slow\w*|weak\w*|recover\w*|growth|headwinds?|tailwinds?|pressure|crash\w*|rall\w*|surge\w*|jump\w*|fall\w*|decline\w*)(?![a-z])", re.I)
_RATE = re.compile(r"(?<![a-z])(?:repo|rate cut|rate hike|rate decision|mpc|monetary|policy rate|interest rate|rates?|yields?|inflation)(?![a-z])", re.I)


def tags(title: str, summary: str = "", kind: str = "") -> list[str]:
    t = []
    if scope.is_tips_article(title, summary):
        t.append("tips")
    if scope.is_administrative(title, summary):
        t.append("administrative")
    if CSC._OPERATING.search(title):
        t.append("operating_result")
    if _OUTLOOK.search(title):
        t.append("outlook_demand")
    if _RATE.search(title):
        t.append("rate_policy")
    return t


def fate_event(e: dict, plan, query, entities) -> str:
    b = EvidenceBundle()
    b.events = [dict(e)]
    rep = EF.filter_bundle(b, plan, query, entities)["events"]
    if b.events:
        return "kept"
    return next((k.replace("dropped_", "") for k, v in rep.items() if k.startswith("dropped_") and v), "dropped")


def fate_news(n: dict, plan, query, entities) -> str:
    b = EvidenceBundle()
    b.news = [dict(n)]
    rep = EF.filter_bundle(b, plan, query, entities)["news"]
    if b.news:
        return "kept"
    return next((k.replace("dropped_", "") for k, v in rep.items() if k.startswith("dropped_") and v), "dropped")


def fate_ann(a: dict, plan, query, entities) -> str:
    b = EvidenceBundle()
    b.announcements = [dict(a)]
    EF.filter_bundle(b, plan, query, entities)
    return "kept" if b.announcements else "stale"


def prompt_for(kind: str, query, evidence, intent_data, entities) -> str:
    from app.services.ai_search.specialists import company as C, comparison as K, sector as SE
    return {"company": C.build_prompt, "comparison": K.build_prompt, "sector": SE.build_prompt}[kind](query, evidence, intent_data, entities)


def where_in_prompt(prompt: str, text: str) -> dict:
    key = (text or "").strip()[:60]
    i = prompt.find(key) if key else -1
    return {"visible": i >= 0, "char_offset": i if i >= 0 else None, "pct_through_prompt": round(100 * i / max(1, len(prompt))) if i >= 0 else None}


async def trace(qid: str, query: str, prev: dict) -> dict:
    entities = entities_mod.extract_entities(query)
    intent_data = _detect_decision_intent(query)
    plan = EF.plan_for(query, intent_data, entities)
    specialist, spec_kind = P._route_specialist(query, intent_data, entities)
    out: dict = {"id": qid, "query": query, "entities": {k: entities.get(k) for k in ("companies", "sectors", "policies")}, "plan": {"kind": plan.kind, "events": plan.events, "news": plan.news, "age_key": plan.age_key},
                 "specialist": spec_kind, "limits": {"event_retrieval": 30, "news_retrieval": 20, "bundle_events_cap": 10}}
    async with AsyncSessionLocal() as db:
        bundle = await evidence_mod.collect(query, intent_data, entities, db)
        prompt = prompt_for(spec_kind, query, bundle, intent_data, entities)
        out["prompt_chars"] = len(prompt)
        index = bundle.index()
        prev_resp = prev.get("response") or {}
        prev_cited = {c.get("claim"): c.get("sources") for c in prev_resp.get("claim_sources") or []}
        prev_index = {i["id"]: i for i in (prev.get("evidence") or {}).get("index", [])}
        prev_used_titles = set()
        for sources in prev_cited.values():
            for sid in sources or []:
                if sid in prev_index:
                    prev_used_titles.add((prev_index[sid].get("title") or "")[:60])
        final_titles = {}
        for kind, rows, key in (("event", bundle.events, "title"), ("news", bundle.news, "headline"), ("announcement", bundle.announcements or [], "subject")):
            for rank, r in enumerate(rows, 1):
                final_titles[(kind, str(r.get("id")))] = rank

        # ── universe + retrieved + fate ───────────────────────────────────────────────────────────────────────────────────────────
        symbols = [c for c in (entities.get("companies") or []) if c]
        items: list[dict] = []
        # events
        if plan.events == "tagged":
            uni_ev = []
            for sym in symbols[:3]:
                uni_ev += await R._search_events(db, query, limit=500, entities={"companies": [sym]}, tagged_only=True)
        elif plan.events == "words":
            uni_ev = await R._search_events(db, query, limit=500, entities=entities, terms=EF.topic_search_terms(query, entities) or None)
        else:
            uni_ev = []
        retrieved_ids = {}
        for rank, e in enumerate(uni_ev, 1):
            retrieved_ids[str(e["id"])] = rank
        for rank, e in enumerate(uni_ev, 1):
            f = fate_event(e, plan, query, entities)
            items.append({"kind": "event", "id": e["id"], "title": e["title"], "date": str(e.get("event_date") or e.get("published_at") or e.get("date")), "impact_score": e.get("impact_score"),
                          "retrieval_rank_by_impact": rank, "within_retrieval_limit": rank <= 30, "filter_fate": f, "tags": tags(e["title"], e.get("summary", ""), "event"),
                          "bundle_rank": final_titles.get(("event", str(e["id"]))), "summary": (e.get("summary") or "")[:140]})
        # news (live feed universe)
        try:
            live = await R.get_live_news(limit=200) or []
        except Exception:
            live = []
        for rank, a in enumerate(live, 1):
            n = {"id": a["id"], "headline": a["headline"], "summary": (a.get("summary") or "")[:200], "source": a.get("source", ""), "published_at": a.get("published_at", ""), "impact_score": float(a.get("impact_score", 5.0))}
            ets = EF.company_terms(symbols) if plan.news == "entity" else (EF.topic_search_terms(query, entities) or None)
            matched = True
            if ets is not None:
                low = (n["headline"] + " " + n["summary"]).lower()
                matched = any(re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low) for t in ets) if plan.news == "entity" else any(w in low for w in ets)
            if not matched:
                continue
            f = fate_news(n, plan, query, entities)
            items.append({"kind": "news", "id": n["id"], "title": n["headline"], "date": str(n["published_at"]), "impact_score": n["impact_score"], "retrieval_rank_by_impact": rank, "within_retrieval_limit": rank <= 20,
                          "filter_fate": f, "tags": tags(n["headline"], n["summary"], "news"), "bundle_rank": final_titles.get(("news", str(n["id"]))), "summary": n["summary"][:140]})
        # announcements (company questions): recency order, limit 5 (general single company) or 8
        from app.services.company_announcements_service import get_recent_announcements
        for sym in symbols[:2]:
            allrows = await get_recent_announcements(sym, limit=400)
            limit_used = 5 if (intent_data.get("intent") == "general" and not intent_data.get("is_comparison") and len(symbols) == 1) else 8
            for rank, a in enumerate(allrows, 1):
                a2 = {**a, "symbol": sym}
                f = fate_ann(a2, plan, query, entities) if rank <= limit_used else "not_retrieved"
                title = a.get("subject") or ""
                items.append({"kind": "announcement", "id": a["id"], "title": title, "date": a.get("announcement_date"), "category": a.get("category"), "retrieval_rank_by_recency": rank, "within_retrieval_limit": rank <= limit_used,
                              "limit_used": limit_used, "filter_fate": f, "tags": tags(title, a.get("description") or "", "announcement") + ((["category_result"] if any(k in (a.get("category") or "").lower() for k in ("result", "financial")) else [])),
                              "bundle_rank": final_titles.get(("announcement", str(a["id"]))), "summary": (a.get("description") or "")[:140]})
        # ── prompt visibility + previous-answer use ────────────────────────────────────────────────────────────────────────────────
        idx_by_ref = {}
        for ix in index:
            idx_by_ref[(ix["kind"], ix["ref"].split(":", 1)[1])] = ix["id"]
        for it in items:
            it["index_id"] = idx_by_ref.get((it["kind"], str(it["id"])))
            it.update({"prompt_" + k: v for k, v in where_in_prompt(prompt, it["title"]).items()})
            it["used_in_previous_live_answer"] = (it["title"] or "")[:60] in prev_used_titles
        out["items"] = items
        out["bundle"] = {"events": len(bundle.events), "news": len(bundle.news), "announcements": len(bundle.announcements or []), "policies": len(bundle.policies), "context_lines": len(bundle.context_lines)}
        out["index_ids"] = [i["id"] for i in index]
        out["index_visible_in_prompt"] = {ix["id"]: where_in_prompt(prompt, ix["title"] or "")["visible"] for ix in index}
        out["historical"] = [{"title": h.get("title") or h.get("event"), "similarity": h.get("similarity"), "date": h.get("date")} for h in (bundle.similar_historical or [])]
        out["prompt_event_slice"], out["prompt_news_slice"] = ("events[:5]", "news[:5]") if spec_kind == "company" else (("events[:6]", "none") if spec_kind == "sector" else ("events[:4]", "news[:4]"))
        out["prev_cited_claims"] = {k: v for k, v in prev_cited.items()}
        out["prev_used_titles"] = sorted(prev_used_titles)
    return out


async def main():
    prev_all = json.loads(PREV.read_text(encoding="utf-8"))["results"]
    res = {}
    for qid, q in QUESTIONS.items():
        res[qid] = await trace(qid, q, prev_all[qid])
        print(qid, "items traced:", len(res[qid]["items"]), "| bundle", res[qid]["bundle"], "| prompt chars", res[qid]["prompt_chars"], flush=True)
    (HERE / "evidence_trace.json").write_text(json.dumps({"provider_calls_made": len(CALLS), "results": res}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("provider calls made:", len(CALLS))


if __name__ == "__main__":
    asyncio.run(main())
