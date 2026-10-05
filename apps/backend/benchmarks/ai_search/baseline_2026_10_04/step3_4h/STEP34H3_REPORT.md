# Step 3.4H.3 report: live-news snapshot reliability (implemented, model-free)

Zero provider calls. Nothing pushed or deployed. Retrieval ranking, the news candidate window, persisted `news_articles` and the two-RSS-system duplication are untouched. H.4 not started.

## What changed
- `news_fetcher.py`: `get_live_news(limit)` keeps its signature and never raises. Behind it is a snapshot lifecycle:
  - **fresh** (age under the 15 min TTL): served immediately.
  - **stale** (older than TTL, younger than `live_news_max_stale_seconds` = 6 h): served immediately, and **one** background refresh is started or joined (single flight).
  - **no snapshot or older than max stale**: a bounded foreground wait for the first RSS publish, `min(live_news_cold_rss_cap_seconds = 4 s, request_deadline.usable())`. A cut-off or total failure returns `[]` with `live_news_status()` = `timeout` / `failed`; a feed set that answered with nothing relevant is `empty`.
- **Refresh semantics**: all feeds run concurrently; whatever has answered when the publish window (3 s) closes is published, later feeds merge in as they finish (hard limit 12 s). **Partial success publishes** (a broken source no longer freezes the cache) and the failures are recorded per source. **Zero usable result with errors keeps the last known good snapshot** and counts a failure. A successful empty result installs as empty (distinct from a failure). The snapshot is replaced by one assignment.
- **yfinance is background-only**: a separate phase after RSS is published, bounded by `live_news_yfinance_timeout_seconds` (20 s). It only adds to an already published snapshot, can never delay it, and a still-running yfinance thread is never stacked.
- **Absolute timestamps kept**: items keep epoch `_ts`; the relative label ("9m ago") is derived when served, and `published_ts` (epoch) is added to served items. Snapshot age is not article age; no article-age cutoff was added.
- **Cancellation/lifecycle**: waiters wait on an `Event`, not on the refresh task, so a cancelled or timed-out request never cancels the shared refresh. A finished or failed refresh task is cleared and never counts as "already running"; a task bound to a closed event loop is ignored.
- **H.2b interaction**: the cold wait is capped by the request's usable budget. In `retrieval._search_news`, when the live feed ended `failed`/`timeout` **and** nothing else was found (including the database fallback), it raises `LiveNewsUnavailable`, which the existing `_guarded` records as a retrieval failure. A legitimate empty feed, a stale snapshot, or database rows are returned as before.
- **Warm-up**: scheduler job `refresh_live_news` every 600 s (inside the TTL) calls `refresh_live_news()`; the in-process scheduler shares the cache with the API.
- `get_cached_article` reads the snapshot (served form). `_fetch_rss` keeps its signature; `_fetch_rss_status` returns (items, error) so an exception is never mistaken for an empty feed.
- New settings (provisional): max stale 6 h, cold cap 4 s, publish window 3 s, feed hard limit 12 s, yfinance timeout 20 s, warm-up 600 s.

## Verification
- `test_live_news_snapshot.py`: 23 tests, fake feeds, no network. Fresh; stale returns in milliseconds with one background refresh; stale-while-refreshing starts no second refresh; 20 concurrent stale requests give exactly one refresh; cold healthy; cold with every feed hanging is a bounded timeout (task not cancelled) and not empty news; cold with one hanging feed publishes the rest after the window; cold start inherits the request deadline; cancelled waiter leaves the refresh running; total failure keeps last known good; exception vs legitimate empty; **partial-source success with a hanging yfinance**; **yfinance cannot delay publication and merges later**; yfinance threads not stacked; failed task never blocks the next refresh; **time progression** (same absolute timestamp, label 1m -> 21m -> 2h); beyond max stale not served; retrieval raises/returns correctly; job registered; public signatures unchanged.
- Mutation checks: overwriting last known good on failure (2 tests fail), serving beyond max stale (1), no single flight (2), stacking yfinance threads (1), not deriving the label at read time (1).
- **Real feeds, same machine as the 13 s profile** (`live_news_latency_check.py`): cold start **1.97 s** (60 items, was about 13 s); background refresh finished 10.3 s later; stale path **under 1 ms**; fresh path under 1 ms; label "9m ago".
- AI Search + deadline + provider + news-snapshot selection: 788 passed, 3 xfailed (live-engine tests excluded as before).

## Pre-existing failures found (not caused here, not touched)
- `test_ingest_news_shared_fetch.py` (2 tests): fails identically at commit 6319bd7, before the 3.4H changes.
- `test_weekend_intelligence_scheduler.py::test_recurring_job_count_increased_by_exactly_two`: asserts 30 jobs; the registry already had 32 before this change (33 with the new job). I did not bump it, because that would hide two unexplained earlier additions.

## Debt and notes
- A cold request still pays up to the first publish window (about 2 s measured); the background yfinance thread (about 10 s, 0 items on this machine) still occupies an executor thread each refresh. yfinance's real yield in production is unmeasured; the removal decision stays with H.4 or a read-only source-quality probe.
- A background refresh started after a process restart has nothing to serve for the first cold requests; the first one after boot waits up to the cold cap.
- The persisted-table-as-live-source and RSS-system consolidation remain separate architecture debt.
- Public items now carry `published_ts` and a correct relative label; `news_worker.py` (dead code) still persists the label as `published_at`.

## Next
H.4: measure the real provider chain (retrieval with warm/stale news, classifier latency and fallback count, specialist attempts, Gate B and assembly, total), including one deliberately slow first provider; then tune the provisional 24/2/3/8/14 s budgets.
