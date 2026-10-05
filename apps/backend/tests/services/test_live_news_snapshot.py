"""
Step 3.4H.3: live-news snapshot lifecycle (stale-while-revalidate, single flight, last known good, bounded cold start, background-only yfinance, absolute timestamps kept).
Model-free and network-free: feeds and yfinance are fakes with controllable behaviour. Budgets are small so the tests run in seconds; they are NOT the production values.
"""
from __future__ import annotations

import asyncio
import time
from collections import Counter

import pytest

from app.core.config import settings
from app.services import news_fetcher as NF
from app.services import request_deadline as RD
from app.services.ai_search import retrieval as RT

URLS = ["feed://a", "feed://b", "feed://c"]


def art(i: int, ts: float | None = None, src: str = "Wire") -> dict:
    return NF._normalize(f"Nifty and Sensex move on item {i} India market", f"India market summary {i}", src, ts if ts is not None else time.time(), f"https://x/{i}")


class Feeds:
    def __init__(self):
        self.calls: Counter = Counter()
        self.behaviour: dict = {}
        self.default = ("ok", 3)
        self.yf_calls = 0
        self.yf_behaviour = ("items", 0, 0.0)          # (kind, n items, sleep seconds)

    async def fetch(self, url, source):
        self.calls[url] += 1
        b = self.behaviour.get(url, self.default)
        if b[0] == "hang":
            await asyncio.sleep(60)
        if b[0] == "sleep":
            await asyncio.sleep(b[1])
            return [art(hash(url) % 1000 + k) for k in range(b[2])], None
        if b[0] == "err":
            return [], b[1]
        base = {"feed://a": 100, "feed://b": 200, "feed://c": 300}.get(url, 0)
        return [art(base + k) for k in range(b[1])], None

    def yf(self):
        self.yf_calls += 1
        kind, n, sl = self.yf_behaviour
        time.sleep(sl)
        return [art(900 + k, src="Yahoo") for k in range(n)]


@pytest.fixture
def feeds(monkeypatch):
    f = Feeds()
    monkeypatch.setattr(NF, "RSS_FEEDS", [(u, "Wire") for u in URLS])
    monkeypatch.setattr(NF, "_fetch_rss_status", f.fetch)
    monkeypatch.setattr(NF, "_sync_fetch_yfinance", f.yf)
    monkeypatch.setattr(settings, "live_news_cold_rss_cap_seconds", 1.0)
    monkeypatch.setattr(settings, "live_news_rss_publish_window_seconds", 0.4)
    monkeypatch.setattr(settings, "live_news_rss_max_seconds", 2.0)
    monkeypatch.setattr(settings, "live_news_yfinance_timeout_seconds", 0.6)
    monkeypatch.setattr(settings, "live_news_max_stale_seconds", 6 * 3600)
    NF._snapshot = {"items": [], "fetched_at": 0.0, "last_success_at": 0.0, "source_failures": {}, "consecutive_failures": 0, "last_error": None, "installed": False}
    NF._refresh_task = None
    NF._rss_event = None
    NF._yf_future = None
    yield f
    NF._refresh_task = None
    NF._yf_future = None


def run(coro):
    return asyncio.run(coro)


def seed(items, age_s: float):
    now = time.time()
    NF._snapshot = {"items": list(items), "fetched_at": now - age_s, "last_success_at": now - age_s, "source_failures": {}, "consecutive_failures": 0, "last_error": None, "installed": True}


async def settle():
    t = NF._refresh_task
    if t is not None:
        await asyncio.shield(t)


# ── fresh / stale / refresh running ─────────────────────────────────────────────────────────────────────────────────────────────

def test_fresh_snapshot_is_served_immediately_without_any_fetch(feeds):
    seed([art(1), art(2)], age_s=10)

    async def go():
        t = time.monotonic()
        out = await NF.get_live_news(limit=20)
        return out, time.monotonic() - t, NF.live_news_status()

    out, dt, status = run(go())
    assert len(out) == 2 and dt < 0.05 and sum(feeds.calls.values()) == 0 and status == "ok"


def test_a_stale_snapshot_is_served_in_milliseconds_while_one_background_refresh_runs(feeds):
    feeds.default = ("sleep", 1.2, 3)                      # a slow feed: the old synchronous behaviour would have waited for it
    seed([art(1), art(2)], age_s=1000)                     # past the 900 s TTL, well inside max stale

    async def go():
        t = time.monotonic()
        out = await NF.get_live_news(limit=20)
        dt = time.monotonic() - t
        status = NF.live_news_status()
        await settle()
        return out, dt, status

    out, dt, status = run(go())
    assert dt < 0.1 and len(out) == 2 and status == "stale"      # the stale path does not pay for the refresh at all
    assert all(feeds.calls[u] == 1 for u in URLS)                # exactly one refresh happened in the background
    assert NF._snapshot["fetched_at"] > time.time() - 30 and len(NF._snapshot["items"]) >= 3     # and it replaced the snapshot


def test_stale_while_a_refresh_is_running_starts_no_second_refresh(feeds):
    feeds.default = ("sleep", 0.8, 3)
    seed([art(1)], age_s=1000)

    async def go():
        a = await NF.get_live_news()
        b = await NF.get_live_news()
        await settle()
        return a, b

    a, b = run(go())
    assert a and b and all(feeds.calls[u] == 1 for u in URLS)


def test_twenty_concurrent_stale_requests_cause_exactly_one_refresh(feeds):
    feeds.default = ("sleep", 0.6, 3)
    seed([art(1)], age_s=1000)

    async def go():
        t = time.monotonic()
        outs = await asyncio.gather(*[NF.get_live_news() for _ in range(20)])
        dt = time.monotonic() - t
        await settle()
        return outs, dt

    outs, dt = run(go())
    assert dt < 0.2 and all(len(o) == 1 for o in outs)
    assert all(feeds.calls[u] == 1 for u in URLS)


# ── cold start ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_cold_cache_with_healthy_feeds_is_bounded_and_ok(feeds):
    async def go():
        t = time.monotonic()
        out = await NF.get_live_news(limit=20)
        return out, time.monotonic() - t, NF.live_news_status()

    out, dt, status = run(go())
    assert out and dt < 0.5 and status == "ok"


def test_cold_cache_with_every_feed_hanging_is_a_bounded_timeout_not_empty_news(feeds):
    feeds.default = ("hang",)

    async def go():
        t = time.monotonic()
        out = await NF.get_live_news()
        dt = time.monotonic() - t
        status = NF.live_news_status()
        task_alive = NF._refresh_task is not None and not NF._refresh_task.done()
        NF._refresh_task.cancel()
        return out, dt, status, task_alive

    out, dt, status, task_alive = run(go())
    assert out == [] and status == "timeout" and 0.9 < dt < 1.4          # the cold cap (1 s), not the 60 s hang
    assert task_alive                                                     # the shared refresh was not cancelled by the waiter giving up


def test_cold_cache_with_one_hanging_feed_publishes_the_others_when_the_window_closes(feeds):
    feeds.behaviour = {"feed://b": ("hang",)}

    async def go():
        t = time.monotonic()
        out = await NF.get_live_news()
        dt = time.monotonic() - t
        NF._refresh_task.cancel()
        return out, dt

    out, dt = run(go())
    assert len(out) == 6 and 0.3 < dt < 0.9                              # 2 feeds x 3 items after the 0.4 s publish window; the hang did not hold the request


def test_cold_start_inherits_the_request_deadline(feeds):
    feeds.default = ("hang",)

    async def go():
        with RD.scope(total=1.5, reserve=1.2, min_attempt=0.1, attempt_cap=1.0):     # 0.3 s usable
            t = time.monotonic()
            out = await NF.get_live_news()
            dt = time.monotonic() - t
        NF._refresh_task.cancel()
        return out, dt, NF.live_news_status()

    out, dt, status = run(go())
    assert out == [] and status == "timeout" and dt < 0.6


def test_a_cancelled_cold_waiter_does_not_cancel_the_shared_refresh(feeds):
    feeds.default = ("sleep", 0.7, 3)

    async def go():
        waiter = asyncio.ensure_future(NF.get_live_news())
        await asyncio.sleep(0.1)
        task = NF._refresh_task
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert not task.done()
        await task
        return len(NF._snapshot["items"])

    assert run(go()) >= 3


# ── last known good, partial success, empty vs failure ─────────────────────────────────────────────────────────────────────────

def test_a_total_refresh_failure_keeps_the_last_known_good_snapshot_and_records_it(feeds):
    feeds.default = ("err", "ConnectError")
    seed([art(1), art(2)], age_s=1000)

    async def go():
        out = await NF.get_live_news()
        await settle()
        again = await NF.get_live_news()
        return out, again

    out, again = run(go())
    assert [a["headline"] for a in again] == [a["headline"] for a in out] and len(again) == 2        # nothing was replaced by nothing
    assert NF._snapshot["consecutive_failures"] == 1 and NF._snapshot["source_failures"] and NF._snapshot["last_error"] == "ConnectError"


def test_an_exception_is_never_confused_with_a_legitimate_empty_result(feeds):
    feeds.default = ("ok", 0)                              # every feed answered and had nothing

    async def go():
        out = await NF.get_live_news()
        return out, NF.live_news_status()

    out, status = run(go())
    assert out == [] and status == "empty" and NF._snapshot["installed"] is True and NF._snapshot["source_failures"] == {}


def test_partial_source_success_becomes_the_new_snapshot_and_records_the_failures(feeds):
    feeds.behaviour = {"feed://a": ("ok", 3), "feed://b": ("err", "HTTPStatusError"), "feed://c": ("ok", 0)}
    feeds.yf_behaviour = ("items", 0, 5.0)                 # yfinance hangs

    async def go():
        t = time.monotonic()
        out = await NF.get_live_news()
        dt = time.monotonic() - t
        await settle()
        return out, dt

    out, dt = run(go())
    assert len(out) == 3 and dt < 0.5                                     # RSS published without waiting for yfinance
    assert NF._snapshot["source_failures"].get("feed://b") == "HTTPStatusError"
    assert NF._snapshot["source_failures"].get("yfinance") == "timeout"   # the background phase gave up after its own bound
    assert len(NF._snapshot["items"]) == 3 and NF._snapshot["consecutive_failures"] == 0


def test_background_yfinance_cannot_delay_publication_and_merges_when_it_returns(feeds):
    feeds.yf_behaviour = ("items", 2, 0.3)

    async def go():
        t = time.monotonic()
        out = await NF.get_live_news()
        dt = time.monotonic() - t
        before = len(NF._snapshot["items"])
        await settle()
        return out, dt, before, len(NF._snapshot["items"])

    out, dt, before, after = run(go())
    assert dt < 0.3 and len(out) == 9 and before == 9                    # published from RSS alone
    assert after == 11                                                    # yfinance items joined the already-published snapshot


def test_a_still_running_yfinance_thread_is_never_stacked(feeds):
    feeds.yf_behaviour = ("items", 0, 1.2)

    async def go():
        await NF.get_live_news()
        await settle()                                       # first refresh: yfinance timed out (0.6 s), thread still running (1.2 s)
        assert NF._yf_future is not None and not NF._yf_future.done()
        _ensure = NF._ensure_refresh()
        await _ensure[0]
        return feeds.yf_calls

    assert run(go()) == 1                                    # the second refresh skipped yfinance instead of starting another thread
    time.sleep(0.8)


def test_a_failed_refresh_task_never_blocks_the_next_refresh(feeds, monkeypatch):
    boom = {"n": 0}
    real = NF._aggregate

    def exploding(batches):
        boom["n"] += 1
        if boom["n"] == 1:
            raise RuntimeError("boom")
        return real(batches)
    monkeypatch.setattr(NF, "_aggregate", exploding)

    async def go():
        t1, _ = NF._ensure_refresh()
        with pytest.raises(RuntimeError):
            await t1
        await asyncio.sleep(0)
        assert NF._refresh_task is None                      # a failed task is not "refresh already running"
        t2, _ = NF._ensure_refresh()
        assert t2 is not t1
        await t2
        return len(NF._snapshot["items"])

    assert run(go()) >= 3


# ── timestamps ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_relative_label_is_derived_at_serve_time_and_the_absolute_timestamp_never_changes(feeds, monkeypatch):
    t0 = 1_800_000_000.0
    monkeypatch.setattr(NF.time, "time", lambda: t0)
    item = art(1, ts=t0 - 60)                                # published one minute before it was cached
    seed([item], age_s=0)
    NF._snapshot["fetched_at"] = t0
    first = run(NF.get_live_news())[0]
    assert first["published_at"] == "1m ago" and first["published_ts"] == t0 - 60 and "_ts" not in first
    monkeypatch.setattr(NF.time, "time", lambda: t0 + 20 * 60)
    NF._snapshot["fetched_at"] = t0 + 20 * 60 - 10           # keep it fresh so no refresh is involved
    later = run(NF.get_live_news())[0]
    assert later["published_ts"] == first["published_ts"] and later["published_at"] == "21m ago"
    monkeypatch.setattr(NF.time, "time", lambda: t0 + 2 * 3600)
    NF._snapshot["fetched_at"] = t0 + 2 * 3600 - 10
    much_later = run(NF.get_live_news())[0]
    assert much_later["published_ts"] == first["published_ts"] and much_later["published_at"] == "2h ago"


def test_a_snapshot_older_than_max_stale_is_treated_as_absent_not_served(feeds):
    feeds.default = ("err", "ConnectError")
    seed([art(1)], age_s=7 * 3600)

    async def go():
        out = await NF.get_live_news()
        return out, NF.live_news_status()

    out, status = run(go())
    assert out == [] and status in ("failed", "timeout")     # a cache-availability limit, enforced; item ages are untouched by it


def test_get_cached_article_returns_the_served_form(feeds):
    it = art(7)
    seed([it], age_s=1)
    got = NF.get_cached_article(it["id"])
    assert got["headline"] == it["headline"] and "_ts" not in got and got["published_ts"] == it["_ts"]
    assert NF.get_cached_article("missing") is None


# ── AI Search retrieval: infrastructure failure is not "no news" ─────────────────────────────────────────────────────────────────

class _Db:
    async def execute(self, *a, **k):
        raise AssertionError("no database access expected for this query")


class _EmptyDb:
    async def execute(self, *a, **k):
        class _R:
            def scalars(self):
                return self

            def all(self):
                return []
        return _R()


def test_retrieval_raises_when_the_live_feed_is_unavailable_and_nothing_else_was_found(feeds):
    feeds.default = ("hang",)

    async def go():
        try:
            return await RT._search_news(_Db(), "the", limit=8, entities=None, entity_terms=None, live_window=60)
        finally:
            if NF._refresh_task is not None:
                NF._refresh_task.cancel()

    with pytest.raises(NF.LiveNewsUnavailable):
        run(go())


def test_retrieval_returns_empty_for_a_legitimate_empty_feed_without_raising(feeds):
    feeds.default = ("ok", 0)
    assert run(RT._search_news(_Db(), "the", limit=8, entities=None, entity_terms=None, live_window=60)) == []


def test_retrieval_serves_a_stale_snapshot_normally(feeds):
    seed([art(1)], age_s=1000)
    feeds.default = ("sleep", 0.5, 3)

    async def go():
        out = await RT._search_news(_EmptyDb(), "Nifty Sensex market", limit=8, entities=None, entity_terms=None, live_window=60)
        await settle()
        return out

    assert len(run(go())) == 1


# ── plumbing ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_warmup_job_is_registered_inside_the_ttl():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.scheduler.scheduler import register_jobs
    sched = AsyncIOScheduler()
    register_jobs(sched)
    job = next(j for j in sched.get_jobs() if j.id == "refresh_live_news")
    assert settings.live_news_warmup_interval_seconds < NF.CACHE_TTL and job.trigger.interval.total_seconds() == settings.live_news_warmup_interval_seconds


def test_the_public_contract_is_unchanged(feeds):
    import inspect
    assert list(inspect.signature(NF.get_live_news).parameters) == ["limit"]
    assert list(inspect.signature(NF._fetch_rss).parameters) == ["url", "source"]
