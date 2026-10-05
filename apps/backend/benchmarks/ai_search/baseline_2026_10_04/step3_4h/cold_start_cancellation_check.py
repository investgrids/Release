"""
Step 3 closure check (zero provider calls): when the request deadline cancels CR1 retrieval during the historical-retrieval cold start, is that work lost (every company request would then time out forever),
or does it complete/warm up anyway? Runs collect for CR1 under the same 14 s retrieval cap the pipeline applies, three times in one process, with the inner historical calls timed.
  PYTHONIOENCODING=utf-8 PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4h/cold_start_cancellation_check.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
HERE = Path(__file__).parent
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services import request_deadline as RD  # noqa: E402
from app.services.ai_search import entities as entities_mod  # noqa: E402
from app.services.ai_search import evidence as E  # noqa: E402
from app.services.ai_search import intent as intent_mod  # noqa: E402
from app.services.ai_search.decision_intent import _detect_decision_intent  # noqa: E402
import app.services.development_memory.historical_retrieval as HR  # noqa: E402

q = {x["id"]: x for x in json.loads((HERE.parent / "questions.json").read_text(encoding="utf-8"))["questions"]}["CR1"]["query"]
EVENTS: list = []


def wrap(obj, name):
    fn = getattr(obj, name)
    if asyncio.iscoroutinefunction(fn):
        async def w(*a, **k):
            t = time.monotonic()
            EVENTS.append(f"  > {name} start")
            try:
                return await fn(*a, **k)
            except asyncio.CancelledError:
                EVENTS.append(f"  ! {name} CANCELLED after {time.monotonic() - t:.2f}s")
                raise
            finally:
                EVENTS.append(f"  < {name} end {time.monotonic() - t:.2f}s")
        setattr(obj, name, w)


for n in ("get_verified_historical_events", "_real_interest_rate_trend", "find_similar_events"):
    wrap(HR, n)


async def main():
    entities = entities_mod.extract_entities(q)
    intent_data = _detect_decision_intent(q)
    is_cmp, holding, target = intent_mod.resolve_comparison(q, intent_data, entities)
    for i in (1, 2, 3):
        EVENTS.clear()
        async with AsyncSessionLocal() as db:
            t = time.monotonic()
            try:
                with RD.scope():          # the same deadline scope the HTTP routes set; the pipeline's retrieval cap is the 14 s wait_for
                    await asyncio.wait_for(E.collect(q, intent_data, entities, db), timeout=14)
                print(f"run {i}: completed in {time.monotonic() - t:.2f}s", flush=True)
            except asyncio.TimeoutError:
                print(f"run {i}: CUT OFF at {time.monotonic() - t:.2f}s", flush=True)
        for e in EVENTS:
            print(e, flush=True)
        await asyncio.sleep(1)

asyncio.run(main())
