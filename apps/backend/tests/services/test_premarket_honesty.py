"""Premarket honesty: the stale-GIFT note states the real age, and market breadth is never scaled up from the tracked sample."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api import market


def test_gift_note_states_the_real_age():
    now = datetime.now(timezone.utc)
    assert "3 hours ago" in market._gift_stale_note(now - timedelta(hours=3))
    assert "1 hour ago" in market._gift_stale_note(now - timedelta(hours=1))
    assert "2 days ago" in market._gift_stale_note(now - timedelta(hours=39 + 10))      # past the 48h mark it switches to days
    assert "39 hours ago" in market._gift_stale_note(now - timedelta(hours=39))
    assert "unknown" in market._gift_stale_note(None)


def test_breadth_is_never_scaled_to_an_invented_universe():
    import inspect
    src = inspect.getsource(market)
    assert "* 1200" not in src and "1500 - est_advances" not in src and "Estimated from Nifty 500 sample" not in src


# ── stale-while-revalidate cache (the cold premarket wait) ────────────────────────────────────────

def test_expired_value_is_served_instantly_while_one_background_refresh_runs():
    import threading, time as _t
    market._cache.pop("t-swr", None)
    calls, gate = [], threading.Event()

    def slow_fn():
        calls.append(1)
        gate.wait(5)                                   # a slow refresh (the real one takes ~10 s)
        return "fresh"

    market._cache["t-swr"] = (_t.time() - 120, "old")  # past a 60 s TTL, well inside 4x
    t0 = _t.time()
    assert market._cached_sync("t-swr", 60, slow_fn) == "old"       # served immediately, not after the slow fetch
    assert _t.time() - t0 < 1.0
    assert market._cached_sync("t-swr", 60, slow_fn) == "old"       # a second caller during the refresh does not start another
    gate.set()
    for _ in range(50):
        if market._cache["t-swr"][1] == "fresh":
            break
        _t.sleep(0.05)
    assert market._cache["t-swr"][1] == "fresh" and len(calls) == 1
    assert market._cached_sync("t-swr", 60, lambda: "never") == "fresh"


def test_missing_or_very_old_values_still_block_for_a_real_fetch():
    import time as _t
    market._cache.pop("t-old", None)
    assert market._cached_sync("t-old", 60, lambda: "first") == "first"
    market._cache["t-old"] = (_t.time() - 60 * 5, "ancient")          # older than 4x TTL: not served
    assert market._cached_sync("t-old", 60, lambda: "refetched") == "refetched"


def test_keep_warm_job_is_registered_every_five_minutes():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.scheduler.scheduler import register_jobs
    sch = AsyncIOScheduler()
    register_jobs(sch)
    job = sch.get_job("keep_market_warm")
    assert job is not None and job.trigger.interval.total_seconds() == 300
