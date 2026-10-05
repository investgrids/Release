"""
Step 3.4H.3: real-network latency check of the new live-news snapshot (public RSS feeds and yfinance reads only; no provider call).
  PYTHONIOENCODING=utf-8 PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4h/live_news_latency_check.py
Cold start (no snapshot) is what used to cost ~13 s (23 sequential yfinance calls); the stale path is the common case once warm.
"""
import asyncio
import sys
import time

sys.path.insert(0, ".")
from app.services import news_fetcher as NF


async def main():
    t = time.monotonic()
    out = await NF.get_live_news(limit=60)
    print(f"cold   : {time.monotonic() - t:5.2f} s  items={len(out)} status={NF.live_news_status()}", flush=True)
    t = time.monotonic()
    await NF._refresh_task            # let the background yfinance phase finish (it is bounded by its own timeout)
    print(f"background refresh finished {time.monotonic() - t:5.2f} s later; items={len(NF._snapshot['items'])} failures={NF._snapshot['source_failures']}", flush=True)
    NF._snapshot = {**NF._snapshot, "fetched_at": time.time() - 1000}      # past the 900 s TTL
    t = time.monotonic()
    out = await NF.get_live_news(limit=60)
    print(f"stale  : {time.monotonic() - t:5.3f} s  items={len(out)} status={NF.live_news_status()}", flush=True)
    await NF._refresh_task
    t = time.monotonic()
    out = await NF.get_live_news(limit=60)
    print(f"fresh  : {time.monotonic() - t:5.3f} s  items={len(out)} status={NF.live_news_status()} sample={out[0]['published_at'] if out else None}", flush=True)

asyncio.run(main())
