"""
Step 3.4H.4 follow-up: zero-provider-call profile of evidence.collect for the CR1 question (company path), because the real H.4 request hit the 14 s retrieval cap.
Wraps every awaitable the company branch uses, times each, runs collect with NO deadline so the real duration is visible (bounded here by a 120 s wait_for).
  PYTHONIOENCODING=utf-8 PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4h/profile_collect_company.py [QID]
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.ai_search import entities as entities_mod  # noqa: E402
from app.services.ai_search import evidence as E  # noqa: E402
from app.services.ai_search import intent as intent_mod  # noqa: E402

QID = sys.argv[1] if len(sys.argv) > 1 else "CR1"
q = {x["id"]: x for x in json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]}[QID]["query"]
T: dict = {}


def wrap(obj, name, label=None):
    fn = getattr(obj, name, None)
    if fn is None:
        return
    label = label or name
    if asyncio.iscoroutinefunction(fn):
        async def w(*a, **k):
            t = time.monotonic()
            try:
                return await fn(*a, **k)
            finally:
                T[label] = T.get(label, 0) + (time.monotonic() - t)
    else:
        def w(*a, **k):
            t = time.monotonic()
            try:
                return fn(*a, **k)
            finally:
                T[label] = T.get(label, 0) + (time.monotonic() - t)
    setattr(obj, name, w)


for n in ["_search_events", "_search_news", "_search_policies", "get_sector_changes", "get_extended_indices", "find_similar_events", "read_themes", "get_intelligence_state",
          "_apply_clustering", "_fetch_vix_sync", "_fetch_valuation_sync", "get_recent_announcements", "build_development_context", "get_symbol_context"]:
    wrap(E, n)
import app.services.company_announcements_service as CA  # noqa: E402
import app.services.intelligence.engine as IE  # noqa: E402
import app.services.development_memory.ai_search_context as DM  # noqa: E402
wrap(CA, "get_recent_announcements", "CA.get_recent_announcements")
wrap(IE, "get_symbol_context", "IE.get_symbol_context")
wrap(DM, "build_development_context", "DM.build_development_context")


async def main():
    entities = entities_mod.extract_entities(q)
    intent_data = {"intent": "company_analysis"}
    print("query:", q, "| companies:", entities.get("companies"), flush=True)
    yf = None
    if "yf" in sys.argv[2:]:
        # simulate the live-news background refresh: the 23-symbol yfinance news fetch running in the default executor while the request's retrieval runs
        from app.services import news_fetcher as NF
        yf = asyncio.get_running_loop().run_in_executor(None, NF._sync_fetch_yfinance)
        print("concurrent yfinance news fetch started", flush=True)
    async with AsyncSessionLocal() as db:
        t = time.monotonic()
        try:
            b = await asyncio.wait_for(E.collect(q, intent_data, entities, db), timeout=120)
            print("TOTAL", round(time.monotonic() - t, 2), "s | events", len(b.events), "news", len(b.news), "failures", dict(b.retrieval_failures))
        except asyncio.TimeoutError:
            print("TOTAL > 120 s (timed out)")
    for k, v in sorted(T.items(), key=lambda x: -x[1]):
        print(f"{k:34s} {v:7.2f}s")

asyncio.run(main())
