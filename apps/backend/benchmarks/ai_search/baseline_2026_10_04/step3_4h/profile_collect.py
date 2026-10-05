import asyncio, json, sys, time
sys.path.insert(0, ".")
from pathlib import Path
from app.db.session import AsyncSessionLocal
from app.services.ai_search import evidence as E

QS = {q["id"]: q for q in json.loads(Path("benchmarks/ai_search/baseline_2026_10_04/questions.json").read_text(encoding="utf-8"))["questions"]}
q = QS["SR2"]["query"]
T = {}


def wrap(name):
    fn = getattr(E, name, None)
    if fn is None:
        return
    if asyncio.iscoroutinefunction(fn):
        async def w(*a, **k):
            t = time.monotonic()
            try:
                return await fn(*a, **k)
            finally:
                T[name] = T.get(name, 0) + (time.monotonic() - t)
    else:
        def w(*a, **k):
            t = time.monotonic()
            try:
                return fn(*a, **k)
            finally:
                T[name] = T.get(name, 0) + (time.monotonic() - t)
    setattr(E, name, w)


for n in ["_search_events", "_search_news", "_search_policies", "get_sector_changes", "get_extended_indices", "find_similar_events", "read_themes", "get_intelligence_state",
          "_apply_clustering", "_fetch_vix_sync", "_fetch_valuation_sync", "get_recent_announcements", "build_development_context"]:
    wrap(n)


async def main():
    async with AsyncSessionLocal() as db:
        t = time.monotonic()
        b = await E.collect(q, {"intent": "sector_analysis"}, {"companies": [], "sectors": ["it"], "policies": []}, db)
        total = time.monotonic() - t
    print("TOTAL", round(total, 2), "events", len(b.events), "news", len(b.news))
    for k, v in sorted(T.items(), key=lambda x: -x[1]):
        print(f"{k:28s} {v:6.2f}s")

asyncio.run(main())
