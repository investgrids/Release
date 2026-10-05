"""
Step 3.4H.4 follow-up: zero-provider-call replay of the RETRIEVAL stage of the H.4 request sequence (SR2, CC2, CR1 in one process, in that order, using the pipeline's own intent/entity steps), with per-function timers,
to find why CR1 retrieval ran into the 14 s cap in the real H.4 run while taking about 4 s alone.
  PYTHONIOENCODING=utf-8 PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4h/profile_collect_sequence.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import news_fetcher as NF  # noqa: E402
from app.services.ai_search import entities as entities_mod  # noqa: E402
from app.services.ai_search import evidence as E  # noqa: E402
from app.services.ai_search import intent as intent_mod  # noqa: E402
from app.services.ai_search.decision_intent import _detect_decision_intent  # noqa: E402

QS = {x["id"]: x for x in json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]}
T: dict = {}


def wrap(obj, name, label):
    fn = getattr(obj, name, None)
    if fn is None:
        return

    def rec(t):
        T[label] = T.get(label, 0) + (time.monotonic() - t)
    if asyncio.iscoroutinefunction(fn):
        async def w(*a, **k):
            t = time.monotonic()
            try:
                return await fn(*a, **k)
            finally:
                rec(t)
    else:
        def w(*a, **k):
            t = time.monotonic()
            try:
                return fn(*a, **k)
            finally:
                rec(t)
    setattr(obj, name, w)


for n in ["_search_events", "_search_news", "_search_policies", "get_sector_changes", "get_extended_indices", "find_similar_events", "read_themes", "get_intelligence_state",
          "_apply_clustering", "_fetch_vix_sync", "_fetch_valuation_sync", "get_recent_announcements", "build_development_context", "get_symbol_context"]:
    wrap(E, n, n)
import app.services.company_announcements_service as CA  # noqa: E402
import app.services.intelligence.engine as IE  # noqa: E402
import app.services.development_memory.ai_search_context as DM  # noqa: E402
wrap(CA, "get_recent_announcements", "CA.get_recent_announcements")
wrap(IE, "get_symbol_context", "IE.get_symbol_context")
wrap(DM, "build_development_context", "DM.build_development_context")
for _n in ("_find_relevant_development", "reconcile_development", "find_similar_developments_context"):
    wrap(DM, _n, "DM." + _n)


async def main():
    for qid in (sys.argv[1].split(",") if len(sys.argv) > 1 else ("SR2", "CC2", "CR1")):
        q = QS[qid]["query"]
        entities = entities_mod.extract_entities(q)
        intent_data = _detect_decision_intent(q)
        is_cmp, holding, target = intent_mod.resolve_comparison(q, intent_data, entities)
        if is_cmp and holding and target:
            intent_data["is_comparison"] = True
            intent_data["holding"], intent_data["target"] = holding, target
        T.clear()
        async with AsyncSessionLocal() as db:
            t = time.monotonic()
            try:
                b = await asyncio.wait_for(E.collect(q, intent_data, entities, db), timeout=45)
                print(f"{qid}: collect {time.monotonic() - t:5.2f} s events={len(b.events)} news={len(b.news)} failures={dict(b.retrieval_failures)}", flush=True)
            except asyncio.TimeoutError:
                print(f"{qid}: collect TIMED OUT at 45 s", flush=True)
        for k, v in sorted(T.items(), key=lambda x: -x[1]):
            print(f"      {k:32s} {v:6.2f}s", flush=True)
    t = NF._refresh_task
    if t is not None:
        await asyncio.wait_for(asyncio.shield(t), timeout=30)

asyncio.run(main())
