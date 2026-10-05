import asyncio, sys, time
sys.path.insert(0, ".")
from app.services import news_fetcher as NF


async def timed(name, coro):
    t = time.monotonic()
    try:
        r = await coro
        n = len(r)
    except Exception as e:
        n = f"ERR {type(e).__name__}"
    return name, round(time.monotonic() - t, 2), n


async def main():
    loop = asyncio.get_event_loop()
    t0 = time.monotonic()
    tasks = [timed("yfinance(sync x%d symbols)" % len(NF._YF_SYMBOLS), loop.run_in_executor(None, NF._sync_fetch_yfinance))]
    tasks += [timed(f"rss {src} {url[:60]}", NF._fetch_rss(url, src)) for url, src in NF.RSS_FEEDS]
    res = await asyncio.gather(*tasks)
    for name, s, n in sorted(res, key=lambda x: -x[1]):
        print(f"{s:6.2f}s  items={n}  {name}")
    print("wall (concurrent)", round(time.monotonic() - t0, 2))

asyncio.run(main())
