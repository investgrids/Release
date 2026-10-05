"""
CR1 model-free reassessment from the CURRENT pipeline (3.4G.1 ranking + 3.4G.2 visibility + 3.4G.3 cold-start fix). ZERO provider calls, no code change in the pipeline: this script only observes.
Answers: (1) what is the evidence journey for CR1 now; (2) is the recovered "Primed For Next Leg Of Growth" article enough MODEL-VISIBLE evidence for an outlook answer (titles only: facts that live only in its
summary do not count); (3) what is Gate A actually relying on (counterfactuals: remove Investor Presentation, remove all announcements, remove news).

  PYTHONIOENCODING=utf-8 PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4g_cr1/cr1_reassessment.py
Writes cr1_reassessment.json next to this file.
"""
from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
SNAP = HERE.parent / "step3_4g1" / "live_news_snapshot.json"

from sqlalchemy import or_, select, text  # noqa: E402

from app.api.companies import _NSE_UNIVERSE as UNIVERSE  # noqa: E402
from app.db.models.event import Event  # noqa: E402
from app.db.models_legacy import NewsArticle  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import ai_service as S  # noqa: E402
from app.services.ai_search import conclusion_scope as CSC  # noqa: E402
from app.services.ai_search import entities as EN  # noqa: E402
from app.services.ai_search import evidence as E  # noqa: E402
from app.services.ai_search import evidence_filter as EF  # noqa: E402
from app.services.ai_search import evidence_scope as scope  # noqa: E402
from app.services.ai_search import evidence_sufficiency as SUFF  # noqa: E402
from app.services.ai_search import retrieval as R  # noqa: E402
from app.services.ai_search.decision_intent import _detect_decision_intent as D  # noqa: E402
from app.services.ai_search.specialists import company as C  # noqa: E402

CALLS = []


async def _rec(*a, **k):
    CALLS.append(1)
    return ""


S._call_with_fallback = _rec
QUERY = "What is the outlook for Kotak Mahindra Bank?"
snap = json.loads(SNAP.read_text(encoding="utf-8"))


async def fake_live(limit=20):
    return list(snap[:limit])


R.get_live_news = fake_live


def row_info(kind, title, summary="", extra=None):
    d = {"kind": kind, "title": title, "tags": []}
    if scope.is_administrative(title, summary):
        d["tags"].append("administrative")
    if CSC._OPERATING.search(title):
        d["tags"].append("operating_result_term_in_title")
    d["tips"] = scope.is_tips_article(title, summary)
    d.update(extra or {})
    return d


async def main():
    ents = EN.extract_entities(QUERY)
    it = D(QUERY)
    sym = ents["companies"][0]
    out: dict = {"query": QUERY, "entities": {k: ents.get(k) for k in ("companies", "sectors", "policies")}}
    async with AsyncSessionLocal() as db:
        await db.execute(text("select 1"))
        b = await E.collect(QUERY, it, ents, db)
        b.prompt_kind = "company"
        plan = EF.plan_for(QUERY, it, ents)
        out["plan"] = {"kind": plan.kind, "events": plan.events, "news": plan.news, "age_key": plan.age_key}
        out["retrieval_failures"] = dict(b.retrieval_failures)

        # ── universe: what exists about Kotak anywhere we hold data ───────────────────────────────────────────────────────────
        u: dict = {}
        ev_tag = (await db.execute(select(Event).where(Event.companies.ilike(f'%"symbol": "{sym}"%')))).scalars().all()
        u["events_tagged_to_symbol"] = len(ev_tag)
        ev_name = (await db.execute(select(Event).where(or_(Event.title.ilike("%Kotak Mahindra%"), Event.summary.ilike("%Kotak Mahindra%"))).order_by(Event.event_date.desc()).limit(40))).scalars().all()
        u["events_mentioning_kotak_by_name"] = [{"title": e.title[:110], "tagged": sym in str(e.companies), "date": str(e.event_date or e.published_at)[:10], "source": e.source,
                                                 "single_company_filing": not scope.eligible_for_company(scope.normalize("event", {"title": e.title, "summary": e.summary or "", "companies": e.companies or []}), sym, UNIVERSE)[0]} for e in ev_name]
        nw_db = (await db.execute(select(NewsArticle).where(or_(NewsArticle.headline.ilike("%Kotak Mahindra%"), NewsArticle.summary.ilike("%Kotak Mahindra%"))).limit(40))).scalars().all()
        u["db_news_mentioning_kotak"] = [{"headline": n.headline[:110], "published_at": n.published_at, "age_days": EF.age_days(n.published_at)} for n in nw_db]
        feed = [{"rank": i + 1, "headline": a["headline"], "summary": (a.get("summary") or "")[:220], "published_at": a.get("published_at")} for i, a in enumerate(snap)
                if "kotak" in (a.get("headline", "") + " " + a.get("summary", "")).lower()]
        for f in feed:
            n = {"id": "x", "headline": f["headline"], "summary": f["summary"], "published_at": f["published_at"], "impact_score": 5.0}
            bb = E.EvidenceBundle()
            bb.news = [n]
            rep = EF.filter_bundle(bb, plan, QUERY, ents)["news"]
            f["filter_fate"] = "kept" if bb.news else next((k.replace("dropped_", "") for k, v in rep.items() if k.startswith("dropped_") and v), "dropped")
        u["live_feed_items_mentioning_kotak"] = feed
        from app.services.company_announcements_service import get_recent_announcements
        allann = await get_recent_announcements(sym, limit=400)
        u["announcements_total_in_db"] = len(allann)
        u["announcements_all"] = [{"subject": a["subject"][:110], "category": a.get("category"), "date": (a.get("announcement_date") or "")[:10], "description": (a.get("description") or "")[:140],
                                  "ai_summary": (a.get("ai_summary") or "")[:140]} for a in allann]
        out["universe"] = u

        # ── bundle + ranking + prompt ─────────────────────────────────────────────────────────────────────────────────────────
        out["bundle"] = {
            "events": [row_info("event", e["title"], e.get("summary", "")) for e in b.events],
            "news": [row_info("news", n["headline"], n.get("summary", ""), {"summary_NOT_visible_to_model": (n.get("summary") or "")[:220], "published_at": n.get("published_at"), "source": n.get("source")}) for n in b.news],
            "announcements": [row_info("announcement", a["subject"], a.get("description") or "", {"category": a.get("category"), "date": (a.get("announcement_date") or "")[:10]}) for a in b.announcements],
            "context_lines_full_text": list(b.context_lines),
            "rank_trace": b.rank_trace,
            "index": [{"id": i["id"], "kind": i["kind"], "title": (i["title"] or "")[:140]} for i in b.index()],
        }
        prompt = C.build_prompt(QUERY, b, it, ents)
        i = prompt.index("DB Events:")
        j = prompt.index("PRIORITY ORDER")
        out["model_visible_evidence_section"] = prompt[i:j]

        # ── what Gate A relies on ────────────────────────────────────────────────────────────────────────────────────────────
        base = SUFF.assess(QUERY, it, ents, b, UNIVERSE)
        counted = []
        for it_ in SUFF._items(b):
            ok = (not (it_["kind"] == "policy" or scope.is_tips_article(it_["title"], it_["summary"]) or scope.is_administrative(it_["title"], it_["summary"])) and
                  (it_.get("symbol") == sym or scope.eligible_for_company(it_, sym, UNIVERSE)[0]))
            counted.append({"kind": it_["kind"], "title": it_["title"][:110], "counts_as_company_evidence": bool(ok), "administrative": scope.is_administrative(it_["title"], it_["summary"])})
        out["gate_a"] = {"status": base["status"], "satisfied": base["satisfied"], "context": base["context"], "items": counted}

        def variant(mod):
            bc = copy.copy(b)
            bc.events, bc.news, bc.announcements, bc.policies = list(b.events), list(b.news), list(b.announcements), list(b.policies)
            mod(bc)
            r = SUFF.assess(QUERY, it, ents, bc, UNIVERSE)
            return {"status": r["status"], "context": r["context"]}

        out["gate_a_counterfactuals"] = {
            "without_Investor_Presentation": variant(lambda x: setattr(x, "announcements", [a for a in x.announcements if "investor presentation" not in (a.get("subject") or "").lower()])),
            "without_all_announcements": variant(lambda x: setattr(x, "announcements", [])),
            "without_news": variant(lambda x: setattr(x, "news", [])),
            "only_the_Primed_for_growth_headline": variant(lambda x: (setattr(x, "announcements", []), setattr(x, "news", [n for n in x.news if "primed" in n["headline"].lower()]))),
            "only_General_Updates_and_wrap_news": variant(lambda x: (setattr(x, "announcements", [a for a in x.announcements if "general updates" in (a.get("subject") or "").lower()]),
                                                                  setattr(x, "news", [n for n in x.news if "primed" not in n["headline"].lower()]))),
            "nothing_at_all": variant(lambda x: (setattr(x, "announcements", []), setattr(x, "news", []), setattr(x, "events", []))),
        }
    out["provider_calls_made"] = len(CALLS)
    (HERE / "cr1_reassessment.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print("done; provider calls:", len(CALLS))


asyncio.run(main())
