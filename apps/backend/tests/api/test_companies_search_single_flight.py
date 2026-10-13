"""Company search cold-cache stampede (2026-10-13): after a restart, 26 simultaneous /api/companies/search requests each ran their own ~4.3 s classify_all_entities, held the
whole connection pool and timed out at the proxy. _get_qualified_master_entries is now single-flight per worker: concurrent callers on a cold or expired cache share one
classification, freshness is re-checked after the lock is acquired, waiters touch no database session, and failure / cancellation never leave the lock held or the cache
poisoned. The classification is faked with a counter and a delay except in the last test, which drives the real function against the test-scratch DB."""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

import app.api.companies as C
import app.services.company_identity.tiers as tiers
from app.services.company_identity.tiers import CoverageTier


class Untouchable:
    """A database session that must never be used: waiters hold no connection, so touching it is a failure."""
    def __getattr__(self, name):
        raise AssertionError(f"waiter used its database session ({name})")


def _row(symbol: str, tier=CoverageTier.A_INTELLIGENCE_RICH):
    return SimpleNamespace(symbol=symbol, company_name=f"{symbol} Ltd", tier=tier)


class Fake:
    def __init__(self, monkeypatch, rows=None, delay=0.15, fail_first=0):
        self.calls = 0
        self.rows = rows if rows is not None else [_row("ZZTESTA"), _row("ZZTESTB"), _row("ZZTESTC", CoverageTier.C_IDENTITY_ONLY)]
        self.delay, self.fail_first = delay, fail_first
        outer = self

        async def fake_classify(db, *, check_live_data=True, sample_limit=None):
            outer.calls += 1
            await asyncio.sleep(outer.delay)
            if outer.calls <= outer.fail_first:
                raise RuntimeError("database is locked")
            return outer.rows

        monkeypatch.setattr(tiers, "classify_all_entities", fake_classify)


@pytest.fixture(autouse=True)
def clean_cache():
    C._QUALIFIED_MASTER_CACHE.update({"data": None, "at": 0.0, "failed_at": None})
    C._QUALIFIED_MASTER_LOCK.update({"loop": None, "lock": None})
    yield
    C._QUALIFIED_MASTER_CACHE.update({"data": None, "at": 0.0, "failed_at": None})
    C._QUALIFIED_MASTER_LOCK.update({"loop": None, "lock": None})


def symbols(entries):
    return sorted(e["symbol"] for e in entries)


async def many(n=26, db_factory=Untouchable):
    return await asyncio.wait_for(asyncio.gather(*[C._get_qualified_master_entries(db_factory()) for _ in range(n)]), timeout=10)


# ── the stampede ────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_26_simultaneous_cold_cache_requests_share_one_classification(monkeypatch):
    f = Fake(monkeypatch)
    t0 = time.perf_counter()
    results = await many(26)
    elapsed = time.perf_counter() - t0
    assert f.calls == 1                                            # was 26
    assert all(r is results[0] for r in results)                   # everyone got the same entries
    assert symbols(results[0]) == ["ZZTESTA", "ZZTESTB"]          # Tier A only, same filtering as before
    assert elapsed < f.delay * 3                                   # one classification's latency, not 26 of them in series


@pytest.mark.asyncio
async def test_a_fresh_cache_needs_no_lock_and_no_classification(monkeypatch):
    f = Fake(monkeypatch)
    first = await C._get_qualified_master_entries(Untouchable())
    again = await many(26)
    assert f.calls == 1 and all(r is first for r in again)


@pytest.mark.asyncio
async def test_expiry_triggers_exactly_one_refill_for_concurrent_callers(monkeypatch):
    f = Fake(monkeypatch)
    await C._get_qualified_master_entries(Untouchable())
    C._QUALIFIED_MASTER_CACHE["at"] -= C._QUALIFIED_MASTER_TTL_S + 1     # the TTL passes
    f.rows = [_row("ZZTESTD")]
    results = await many(26)
    assert f.calls == 2                                            # initial fill + one refill
    assert all(symbols(r) == ["ZZTESTD"] for r in results)


@pytest.mark.asyncio
async def test_ttl_and_entry_shape_are_unchanged(monkeypatch):
    Fake(monkeypatch)
    assert C._QUALIFIED_MASTER_TTL_S == 600.0
    (entry, _) = sorted(await C._get_qualified_master_entries(Untouchable()), key=lambda e: e["symbol"]), None
    assert set(entry[0]) == {"symbol", "name", "sector", "industry", "cap", "aliases", "_sym_l", "_name_l", "_alias_l"}
    assert entry[0]["name"] == "ZZTESTA Ltd" and entry[0]["_sym_l"] == "zztesta"


# ── failure ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_failure_is_attempted_once_not_26_times_and_recovers(monkeypatch):
    f = Fake(monkeypatch, fail_first=1)
    results = await many(26)
    assert f.calls == 1 and all(r == [] for r in results)          # no previous data: honest empty, as before
    assert C._QUALIFIED_MASTER_CACHE["data"] is None               # the failure was NOT cached as if it were a result
    assert await C._get_qualified_master_entries(Untouchable()) == [] and f.calls == 1     # inside the backoff nothing retries
    C._QUALIFIED_MASTER_CACHE["failed_at"] -= C._QUALIFIED_MASTER_FAILURE_BACKOFF_S + 1     # the backoff passes
    recovered = await many(26)
    assert f.calls == 2 and all(symbols(r) == ["ZZTESTA", "ZZTESTB"] for r in recovered)
    assert C._QUALIFIED_MASTER_CACHE["failed_at"] is None


@pytest.mark.asyncio
async def test_refresh_failure_keeps_serving_the_previous_entries(monkeypatch):
    f = Fake(monkeypatch)
    good = await C._get_qualified_master_entries(Untouchable())
    C._QUALIFIED_MASTER_CACHE["at"] -= C._QUALIFIED_MASTER_TTL_S + 1
    f.fail_first = 99
    results = await many(10)
    assert f.calls == 2 and all(r is good for r in results)        # stale-on-error, one attempt


# ── cancellation ────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancelled_refill_leader_releases_the_lock_and_waiters_continue(monkeypatch):
    f = Fake(monkeypatch, delay=0.4)
    leader = asyncio.create_task(C._get_qualified_master_entries(Untouchable()))
    await asyncio.sleep(0.05)                                      # the leader holds the lock and is mid-classification
    waiters = [asyncio.create_task(C._get_qualified_master_entries(Untouchable())) for _ in range(10)]
    await asyncio.sleep(0.05)
    leader.cancel()
    with pytest.raises(asyncio.CancelledError):
        await leader
    results = await asyncio.wait_for(asyncio.gather(*waiters), timeout=5)    # nobody is stranded
    assert f.calls == 2                                            # the cancelled attempt + exactly one new leader for all 10 waiters
    assert all(symbols(r) == ["ZZTESTA", "ZZTESTB"] for r in results)
    assert not C._qualified_master_lock().locked()
    assert C._QUALIFIED_MASTER_CACHE["failed_at"] is None          # cancellation is not a failure


@pytest.mark.asyncio
async def test_a_cancelled_waiter_does_not_disturb_the_others(monkeypatch):
    f = Fake(monkeypatch, delay=0.3)
    tasks = [asyncio.create_task(C._get_qualified_master_entries(Untouchable())) for _ in range(8)]
    await asyncio.sleep(0.05)
    tasks[4].cancel()
    done = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5)
    assert isinstance(done[4], asyncio.CancelledError)
    assert f.calls == 1 and all(symbols(r) == ["ZZTESTA", "ZZTESTB"] for i, r in enumerate(done) if i != 4)
    assert not C._qualified_master_lock().locked()


@pytest.mark.asyncio
async def test_lock_is_per_event_loop():
    first = C._qualified_master_lock()
    assert C._qualified_master_lock() is first
    C._QUALIFIED_MASTER_LOCK["loop"] = object()                    # as if the cache outlived another loop (e.g. between tests)
    assert C._qualified_master_lock() is not first


# ── contract ────────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_endpoint_response_contract_is_unchanged(monkeypatch):
    Fake(monkeypatch)
    out = await C.search_companies(q="ZZTESTA", sector="", cap="", limit=20, db=Untouchable())
    assert set(out) == {"count", "companies"} and out["count"] == 1
    assert set(out["companies"][0]) == {"symbol", "name", "sector", "industry", "cap"}
    assert out["companies"][0]["symbol"] == "ZZTESTA"
    static = await C.search_companies(q="RELIANCE", sector="", cap="", limit=5, db=Untouchable())
    assert static["count"] >= 1 and static["companies"][0]["symbol"].startswith("RELIANCE")


# ── real classification and real connection pool ─────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_real_classification_uses_one_pool_connection_not_26(monkeypatch):
    from app.db.session import AsyncSessionLocal, engine
    real = tiers.classify_all_entities
    state = {"calls": 0, "peak": 0}

    async def counting(db, **kw):
        state["calls"] += 1
        out = await real(db, **kw)
        await asyncio.sleep(0.2)                                   # keep the work in flight so the callers genuinely overlap
        return out

    monkeypatch.setattr(tiers, "classify_all_entities", counting)
    sampler_on = True

    async def sampler():
        while sampler_on:
            state["peak"] = max(state["peak"], engine.pool.checkedout())
            await asyncio.sleep(0.005)

    async def one():
        async with AsyncSessionLocal() as db:
            return await C._get_qualified_master_entries(db)

    s = asyncio.create_task(sampler())
    results = await asyncio.wait_for(asyncio.gather(*[one() for _ in range(26)]), timeout=30)
    sampler_on = False
    await s
    assert state["calls"] == 1
    assert all(r is results[0] for r in results)
    assert state["peak"] <= 1
