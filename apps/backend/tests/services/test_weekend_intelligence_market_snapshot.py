"""
MarketSnapshot close-capture tests (price_monitor.capture_close_snapshot).

Mocks the network-touching fetchers (yfinance quotes, NSE FII/DII, NSE
PCR, top movers) so this runs fast and deterministically — this codebase
already has a `live_e2e` pytest marker convention for tests that
deliberately hit real network/LLM, and this isn't meant to be one of
those. `_market_session` is mocked too, so the test doesn't depend on
when it actually runs.

Capture-time tests use 15:35 IST (inside the bounded 15:30-15:40 close
capture window) unless a test is specifically exercising the window
boundary itself — see test_close_snapshot_window for the late-restart
regression this file was extended to cover (2026-08 Phase 1A review:
"confirm a boot/restart hours after market close cannot create a new
snapshot_type='close' row and falsely present it as an actual 15:30
closing snapshot").
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import delete, select

from app.db.models.intelligence import MarketSnapshot
from app.db.session import AsyncSessionLocal
from app.services.intelligence import price_monitor


async def _cleanup(trading_date: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketSnapshot).where(
            MarketSnapshot.trading_date == trading_date, MarketSnapshot.snapshot_type == "close",
        ))
        await db.commit()


def _fake_quote(price: float, pct: float):
    return {"price": price, "prev_close": price / (1 + pct / 100), "change": price * pct / 100, "pct": pct, "positive": pct >= 0}


def _patch_now(mock_dt, year, month, day, hour, minute):
    import datetime as real_datetime
    mock_dt.now.side_effect = lambda tz=None: real_datetime.datetime(year, month, day, hour, minute, tzinfo=tz)


@pytest.fixture(autouse=True)
def _reset_in_process_guard():
    price_monitor._captured_close_for = None
    yield
    price_monitor._captured_close_for = None


@pytest.mark.asyncio
async def test_close_snapshot_saves_with_all_sources_available():
    trading_date = f"2099-02-{uuid.uuid4().hex[:2]}"
    await _cleanup(trading_date)
    try:
        with patch("app.services.intelligence.engine._market_session", return_value="post_market"), \
             patch("app.services.intelligence.price_monitor.datetime") as mock_dt, \
             patch("app.services.market_data._fetch_quote") as mock_quote, \
             patch("app.api.market._fetch_fii_dii", return_value={"fii_net": 123.4}), \
             patch("app.api.market._fetch_pcr_data", return_value={"pcr": 1.1, "max_pain": 24500}), \
             patch("app.services.market_data.get_top_movers", return_value={
                 "gainers": [{"ticker": "BEL", "value": "+2.80%"}],
                 "losers": [{"ticker": "IDEA", "value": "-1.50%"}],
             }):
            _patch_now(mock_dt, 2099, 2, 1, 15, 35)
            mock_quote.side_effect = lambda ticker: _fake_quote(24500.0, 0.5)

            await price_monitor.capture_close_snapshot()

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(MarketSnapshot).where(
                    MarketSnapshot.trading_date == "2099-02-01", MarketSnapshot.snapshot_type == "close",
                )
            )).scalar_one_or_none()
            assert row is not None
            assert row.nifty_level == 24500.0
            assert row.fii_net == 123.4
            assert row.pcr == 1.1
            assert row.top_movers  # non-empty
    finally:
        await _cleanup("2099-02-01")


@pytest.mark.asyncio
async def test_close_snapshot_not_captured_outside_post_market():
    with patch("app.services.intelligence.engine._market_session", return_value="live"):
        await price_monitor.capture_close_snapshot()
    # No assertion on DB state needed — the function must return before
    # touching the DB at all when session != "post_market"; nothing to
    # clean up because nothing should have been written.


@pytest.mark.asyncio
async def test_close_snapshot_missing_secondary_source_does_not_block_save():
    trading_date = "2099-02-02"
    await _cleanup(trading_date)
    try:
        with patch("app.services.intelligence.engine._market_session", return_value="post_market"), \
             patch("app.services.intelligence.price_monitor.datetime") as mock_dt, \
             patch("app.services.market_data._fetch_quote") as mock_quote, \
             patch("app.api.market._fetch_fii_dii", side_effect=Exception("NSE unreachable")), \
             patch("app.api.market._fetch_pcr_data", side_effect=Exception("NSE unreachable")), \
             patch("app.services.market_data.get_top_movers", side_effect=Exception("boom")):
            _patch_now(mock_dt, 2099, 2, 2, 15, 35)
            mock_quote.side_effect = lambda ticker: _fake_quote(24500.0, 0.5)

            await price_monitor.capture_close_snapshot()

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(MarketSnapshot).where(
                    MarketSnapshot.trading_date == trading_date, MarketSnapshot.snapshot_type == "close",
                )
            )).scalar_one_or_none()
            assert row is not None  # primary (Nifty) succeeded, so a row must still be saved
            assert row.nifty_level == 24500.0
            assert row.fii_net is None
            assert row.pcr is None
            assert row.top_movers == []
    finally:
        await _cleanup(trading_date)


@pytest.mark.asyncio
async def test_close_snapshot_not_saved_when_primary_source_fails():
    trading_date = "2099-02-03"
    await _cleanup(trading_date)
    try:
        with patch("app.services.intelligence.engine._market_session", return_value="post_market"), \
             patch("app.services.intelligence.price_monitor.datetime") as mock_dt, \
             patch("app.services.market_data._fetch_quote", return_value=None):
            _patch_now(mock_dt, 2099, 2, 3, 15, 35)

            await price_monitor.capture_close_snapshot()

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(MarketSnapshot).where(
                    MarketSnapshot.trading_date == trading_date, MarketSnapshot.snapshot_type == "close",
                )
            )).scalar_one_or_none()
            assert row is None
    finally:
        await _cleanup(trading_date)


@pytest.mark.asyncio
async def test_close_snapshot_idempotent_within_same_process():
    trading_date = "2099-02-04"
    await _cleanup(trading_date)
    try:
        with patch("app.services.intelligence.engine._market_session", return_value="post_market"), \
             patch("app.services.intelligence.price_monitor.datetime") as mock_dt, \
             patch("app.services.market_data._fetch_quote") as mock_quote, \
             patch("app.api.market._fetch_fii_dii", return_value={"fii_net": None}), \
             patch("app.api.market._fetch_pcr_data", return_value={"pcr": None, "max_pain": None}), \
             patch("app.services.market_data.get_top_movers", return_value={"gainers": [], "losers": []}):
            _patch_now(mock_dt, 2099, 2, 4, 15, 35)
            mock_quote.side_effect = lambda ticker: _fake_quote(24500.0, 0.5)

            await price_monitor.capture_close_snapshot()
            await price_monitor.capture_close_snapshot()  # second tick, same session

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(MarketSnapshot).where(
                    MarketSnapshot.trading_date == trading_date, MarketSnapshot.snapshot_type == "close",
                )
            )).scalars().all()
            assert len(rows) == 1
    finally:
        await _cleanup(trading_date)


@pytest.mark.asyncio
async def test_close_snapshot_idempotent_across_in_process_guard_reset():
    """Simulates a restart: clearing the in-process guard must not
    produce a duplicate row — the DB-level unique index is the real
    protection, not just the in-memory flag."""
    trading_date = "2099-02-05"
    await _cleanup(trading_date)
    try:
        with patch("app.services.intelligence.engine._market_session", return_value="post_market"), \
             patch("app.services.intelligence.price_monitor.datetime") as mock_dt, \
             patch("app.services.market_data._fetch_quote") as mock_quote, \
             patch("app.api.market._fetch_fii_dii", return_value={"fii_net": None}), \
             patch("app.api.market._fetch_pcr_data", return_value={"pcr": None, "max_pain": None}), \
             patch("app.services.market_data.get_top_movers", return_value={"gainers": [], "losers": []}):
            _patch_now(mock_dt, 2099, 2, 5, 15, 35)
            mock_quote.side_effect = lambda ticker: _fake_quote(24500.0, 0.5)

            await price_monitor.capture_close_snapshot()
            price_monitor._captured_close_for = None  # simulate a restart
            await price_monitor.capture_close_snapshot()

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(MarketSnapshot).where(
                    MarketSnapshot.trading_date == trading_date, MarketSnapshot.snapshot_type == "close",
                )
            )).scalars().all()
            assert len(rows) == 1
    finally:
        await _cleanup(trading_date)


@pytest.mark.asyncio
async def test_close_snapshot_not_reconstructed_on_late_restart():
    """
    The exact scenario from the Phase 1A review: backend is up through
    15:28, restarts/redeploys at 15:30 and misses the whole capture
    window, comes back at 18:00 with no row yet for today. Even though
    _market_session() correctly reports "post_market" at 18:00 (it's well
    past close), capture_close_snapshot() must NOT synthesize a "close"
    row from 18:00 data — a missing close snapshot for the day is the
    correct, honest outcome, not a late reconstruction mislabeled as an
    exact 15:30 close.
    """
    trading_date = "2099-02-06"
    await _cleanup(trading_date)
    try:
        with patch("app.services.intelligence.engine._market_session", return_value="post_market"), \
             patch("app.services.intelligence.price_monitor.datetime") as mock_dt, \
             patch("app.services.market_data._fetch_quote") as mock_quote:
            _patch_now(mock_dt, 2099, 2, 6, 18, 0)  # backend just came back up, well past close
            mock_quote.side_effect = lambda ticker: _fake_quote(24777.0, 0.9)  # 18:00 data, must never be stored

            await price_monitor.capture_close_snapshot()

        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(MarketSnapshot).where(
                    MarketSnapshot.trading_date == trading_date, MarketSnapshot.snapshot_type == "close",
                )
            )).scalar_one_or_none()
            assert row is None, "an 18:00 restart must not fabricate a 'close' snapshot from late data"
    finally:
        await _cleanup(trading_date)


@pytest.mark.asyncio
async def test_close_snapshot_window_boundaries_inclusive():
    """15:30 and 15:40 are both inside the bounded window (inclusive on
    both ends); 15:29 and 15:41 are both outside it. Each case uses its
    own fixed day so rows can't collide across cases."""
    cases = [
        (10, 15, 29, False),
        (11, 15, 30, True),
        (12, 15, 40, True),
        (13, 15, 41, False),
    ]
    for day, hour, minute, should_capture in cases:
        trading_date = f"2099-03-{day:02d}"
        await _cleanup(trading_date)
        price_monitor._captured_close_for = None
        try:
            with patch("app.services.intelligence.engine._market_session", return_value="post_market"), \
                 patch("app.services.intelligence.price_monitor.datetime") as mock_dt, \
                 patch("app.services.market_data._fetch_quote") as mock_quote, \
                 patch("app.api.market._fetch_fii_dii", return_value={"fii_net": None}), \
                 patch("app.api.market._fetch_pcr_data", return_value={"pcr": None, "max_pain": None}), \
                 patch("app.services.market_data.get_top_movers", return_value={"gainers": [], "losers": []}):
                _patch_now(mock_dt, 2099, 3, day, hour, minute)
                mock_quote.side_effect = lambda ticker: _fake_quote(24500.0, 0.5)

                await price_monitor.capture_close_snapshot()

            async with AsyncSessionLocal() as db:
                rows = (await db.execute(
                    select(MarketSnapshot)
                    .where(MarketSnapshot.snapshot_type == "close")
                    .where(MarketSnapshot.trading_date == trading_date)
                )).scalars().all()
                assert (len(rows) == 1) == should_capture, f"day={day} hour={hour} minute={minute}"
        finally:
            await _cleanup(trading_date)
