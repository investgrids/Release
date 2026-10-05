# Step 3.4H.3 inspection: live-news cache reliability (no implementation)

Evidence: code read of `news_fetcher.py`, `news_worker.py`, `ingest_tasks.py`, `rss_provider.py`, `retrieval.py`, `scheduler`/`main.py`; `news_components.py` (one timed read of the public feeds, concurrent, from this machine); `news_db_probe.py` (local dev database). Zero provider calls; nothing in `app/` changed.

## 1. Where the 13 s comes from (measured, one run, local network)
| Component | Time | Items |
|---|---:|---:|
| yfinance news, 23 symbols **called one after another** in a thread | **11.6 s** | **0** |
| 10 RSS feeds (Google x4, ET, Moneycontrol x2, BS, Livemint, NDTV Profit), concurrent | 0.1 to 0.95 s each | 15 to 92 each |
Wall time for the cold aggregation is the slowest component: yfinance. The saved live-news snapshot (60 items) has publishers ET, Google News, NDTV Profit, Livemint, Business Standard: **none from yfinance**. So locally the synchronous penalty is almost entirely a fetch that contributes nothing. Caveat: this is this machine's network; what yfinance returns on Railway is unverified (a read-only production probe would settle it). `_sync_fetch_yfinance` swallows every error, so a failure looks like "0 items" and is invisible.

## 2. Is there already a reusable snapshot? Partly, and it is not equivalent
There are **two independent news systems fetching largely the same feeds every 15 minutes** (the source registry notes it as "duplicate fetch", audit finding #6).
| | `get_live_news` (what AI Search reads first) | `job_ingest_news` -> `news_articles` |
|---|---|---|
| Fetcher | `news_fetcher` (RSS x10 + yfinance x23) | `RSSProvider` (6 feeds; Google News has 1 query vs 4) + NSE |
| Storage | one in-process dict, `CACHE_TTL = 900` | SQLite table, survives restarts |
| Runs | on demand (first request after expiry pays) | in the backend process scheduler, every 15 min (`start_scheduler` in `main.py`) |
| Item time | relative string baked at fetch time ("9m ago") | `published_at` is **day-only** ("2026-10-04") or "—" (133 of the latest 3,000 local rows); `created_at` is a true ingest time |
| Company tags | none | 7% coverage |
| Read in AI Search | first, window 60 | fallback only, **ordered by impact score, no recency window** |
Reusing the persisted table as the live pool would need recency-aware selection and time-of-day precision it does not have, and would reopen retrieval ranking (frozen in 3.4G). Production freshness of the table is unverified (the local copy's newest row is 27.6 h old, so it says nothing about production). Conclusion: **not a drop-in snapshot. Outcome is "second-best plus a cold-start policy".**

## 3. Defects in the `get_live_news` lifecycle (all read from code)
1. **An empty result overwrites the snapshot.** If every source fails (or the process has no network for a moment), `clean = []` is stored with `ts = now`: the last good news is replaced by nothing, and nothing is retried for 15 minutes.
2. **No single flight.** Cache expiry with N concurrent requests starts N aggregations (each with 23 yfinance calls and 10 feeds). There is no lock.
3. **Nothing keeps it warm.** `workers/news_worker.run_news_worker`, which would call `get_live_news` every 15 minutes, is **dead code** (never started). The cache is filled only by whichever HTTP request happens to arrive after expiry (news endpoints or AI Search).
4. **Source timestamps are discarded.** `_ts` is stripped before caching; consumers receive only the relative label computed at fetch time. An item served 14 minutes later still says "9m ago". Any stale-while-revalidate that serves older snapshots would make this worse unless the label is derived at read time from retained epoch timestamps. (This is the same root as the tracked relative-date persistence defect: `news_worker` persists that string as `published_at`.)
5. **Cold boot is cold.** The cache is in-process; every Railway restart or deploy starts empty and the first request pays the full cost.
6. **yfinance runs in the default executor**, so it cannot be cancelled when the H.2b deadline fires; the thread keeps running its 23 calls (about 11 s) after the request has already failed closed.

## 4. Proposed design (for approval, not started)
- **Snapshot object**: items with retained epoch `ts` and a `fetched_at`, plus `last_success_at`, `last_error`, `consecutive_failures`. The relative `published_at` label is generated when served, never stored.
- **Fresh** (age under TTL): return immediately. **Stale but usable** (age under a max-stale limit, e.g. 6 h, a setting): return immediately and start **one** background refresh; concurrent callers share it. Beyond max-stale the snapshot is treated as absent: stale news never becomes permanent evidence, and each item keeps its own `ts` so selection and ranking can still reject old items.
- **No snapshot**: a bounded foreground fetch of **RSS only** (measured about 1 s; hard cap, for example 4 s, and never more than the request's remaining budget). A cut-off is a retrieval failure, not "no news".
- **Refresh success**: build the new list fully, then replace atomically. **Refresh failure or empty result**: keep the last known good snapshot, record the failure and age.
- **yfinance**: leaves the foreground path. It runs only inside the background refresh, with its own timeout, and its items merge into the next snapshot. Whether to keep it at all is a product question the production probe should answer (if it yields 0 items there too, it is cost without value).
- **Warm-up**: a scheduler job in the same process calls the refresh slightly inside the TTL, so ordinary requests normally never see expiry. Optionally seed a day-precision fallback from the last persisted rows at startup (marked lower precision); I would not do this in H.3.
- **Cancellation safety with H.2b**: requests wait on the shared refresh through `asyncio.shield`; otherwise one request's deadline cancel would cancel the refresh for everyone.
- Public signature of `get_live_news(limit)` and the item keys stay compatible; added fields only.

## 5. Model-free tests planned (fake slow feeds, no network)
Fresh cache; stale cache (returns in milliseconds, one background refresh started); stale while refresh running (no second refresh); cold cache with a healthy feed (bounded); cold cache with a hanging feed (bounded failure, retrieval failure not "no news"); refresh failure and empty result keep the last known good snapshot; 20 concurrent stale requests cause exactly one refresh; cancelled request does not cancel the shared refresh; stale item ages are computed at read time; beyond max-stale the snapshot is not served; the 11.6 s synchronous penalty is absent on the stale path (the check is the latency, not an improvement in degree).

## 6. Decisions needed
1. **yfinance news**: keep it as a background-only source, or drop it? Settling this properly needs one read-only production probe of what it returns there (no write, no provider call). Default if you say nothing: background-only, still bounded.
2. **Max-stale** default (I propose 6 h) and whether stale items older than a few hours should be excluded from AI Search evidence regardless of the snapshot's age (they already carry per-item timestamps).
3. **Scope**: H.3 as above only. The persisted-table-as-live-source idea and merging the two RSS systems are separate follow-ups.
