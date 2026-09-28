"""
2026-09-28 incident — production refresh, 149/424 valuation pillars came
back None. Live re-fetch of a sample immediately after found real data for
28/30, confirming transient yfinance throttling during the ~58-minute batch
(not a real data gap). Fix: more per-symbol retry attempts with real
backoff, plus a sector-level second pass over any symbol that still had
nothing after the first sweep — mocked here, no live network calls.
"""
from __future__ import annotations

import time

import pytest
import yfinance as yf

from app.services.marketripple_score import valuation as v

# valuation.py does `import yfinance as yf` / `import time` LOCALLY inside
# its functions (not at module scope), so patches must land on the real
# yfinance/time module objects those local imports bind to — patching `v.yf`
# would have no effect.


class _FakeTicker:
    """Simulates a symbol whose `.info` returns empty for the first N
    calls, then real data — the exact shape of the observed throttling."""

    def __init__(self, fail_times: int, real: dict):
        self.fail_times = fail_times
        self.real = real
        self.calls = 0

    @property
    def info(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            return {}
        return self.real


def test_retries_more_than_the_old_single_1_5s_attempt(monkeypatch):
    """The old code gave up after 1 retry (2 total attempts). A symbol that
    only recovers on its 3rd attempt must still succeed now."""
    fake = _FakeTicker(fail_times=2, real={"trailingPE": 21.7, "priceToBook": 1.8, "returnOnEquity": None})
    monkeypatch.setattr(yf, "Ticker", lambda t: fake)
    monkeypatch.setattr(time, "sleep", lambda s: None)  # don't actually wait in tests

    result = v._fetch_valuation_snapshot_sync("RELIANCE")
    assert result == {"pe": 21.7, "pb": 1.8, "roe": None}
    assert fake.calls == 3


def test_gives_up_after_exhausting_all_retries_on_a_genuine_gap(monkeypatch):
    """A company with no real trailingPE/priceToBook at all (negative
    earnings, e.g.) must still correctly return None, not loop forever."""
    fake = _FakeTicker(fail_times=99, real={"trailingPE": 1.0, "priceToBook": 1.0, "returnOnEquity": None})
    monkeypatch.setattr(yf, "Ticker", lambda t: fake)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    result = v._fetch_valuation_snapshot_sync("ABFRL")
    assert result == {"pe": None, "pb": None, "roe": None}
    assert fake.calls == len(v._RETRY_BACKOFF_S) + 1


@pytest.mark.asyncio
async def test_prefetch_second_pass_recovers_stragglers_after_the_first_sweep(monkeypatch):
    """A symbol that came back empty on the sector's first pass (a
    correlated, sector-wide throttling window, not just its own bad luck)
    must be retried again after the whole sector's first sweep finishes."""
    calls: dict[str, int] = {}

    def fake_fetch(symbol: str) -> dict:
        calls[symbol] = calls.get(symbol, 0) + 1
        if symbol == "STRAGGLER" and calls[symbol] == 1:
            return {"pe": None, "pb": None, "roe": None}
        return {"pe": 20.0, "pb": 2.0, "roe": 0.15}

    monkeypatch.setattr(v, "_fetch_valuation_snapshot_sync", fake_fetch)

    async def no_sleep(_):
        return None
    import asyncio
    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    out = await v.prefetch_valuation_snapshots(["A", "STRAGGLER", "B"])
    assert out["STRAGGLER"] == {"pe": 20.0, "pb": 2.0, "roe": 0.15}
    assert calls["STRAGGLER"] == 2  # first pass + second-pass retry
    assert calls["A"] == 1  # never needed a retry
    assert calls["B"] == 1


@pytest.mark.asyncio
async def test_prefetch_no_second_pass_when_nothing_is_missing(monkeypatch):
    calls: dict[str, int] = {}

    def fake_fetch(symbol: str) -> dict:
        calls[symbol] = calls.get(symbol, 0) + 1
        return {"pe": 20.0, "pb": 2.0, "roe": 0.15}

    monkeypatch.setattr(v, "_fetch_valuation_snapshot_sync", fake_fetch)
    import asyncio

    async def no_sleep(_):
        return None
    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    await v.prefetch_valuation_snapshots(["A", "B"])
    assert calls == {"A": 1, "B": 1}
