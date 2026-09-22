"""
app.services.quant.backfill — the price-bar ingestion guard (2026-09-22).

Real production defect this closes: a holiday session (2026-09-14,
Ganesh Chaturthi) reached production for all 49 tracked symbols because
nothing checked bar_date against the trading calendar before storing
it. The trading calendar (is_valid_nse_trading_session) is now the
authoritative gate; the stale-value shape is only ever a secondary
quarantine signal on an already-confirmed real trading date.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.price_bar import PriceBar
from app.services.quant import backfill


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def _bar(bar_date: date, close: float, *, open_: float | None = None, high: float | None = None,
         low: float | None = None, volume: int | None = 1000) -> dict:
    return {
        "bar_date": bar_date,
        "open": open_ if open_ is not None else close,
        "high": high if high is not None else close,
        "low": low if low is not None else close,
        "close": close,
        "volume": volume,
    }


# ── _reject_non_trading_sessions / the trading-calendar gate ────────────

def test_ganesh_chaturthi_bar_is_rejected():
    rows = [_bar(date(2026, 9, 14), 100.0, volume=0)]
    kept = backfill._reject_non_trading_sessions(rows, "TESTSYM")
    assert kept == []


def test_normal_weekday_bar_is_kept():
    rows = [_bar(date(2026, 9, 15), 100.0)]
    kept = backfill._reject_non_trading_sessions(rows, "TESTSYM")
    assert len(kept) == 1


def test_stale_carry_forward_shape_on_a_holiday_is_still_rejected_not_quarantined():
    """The trading calendar is authoritative -- a holiday bar that ALSO
    happens to look like a stale carry-forward is rejected outright by
    the calendar gate, never reaching quality classification at all
    (so it can never be quarantined as `stale_carry_forward` -- it's
    simply not stored)."""
    prev = _bar(date(2026, 9, 11), 100.0)
    holiday_bar = _bar(date(2026, 9, 14), 100.0, volume=0)  # flat, == prev close
    kept = backfill._reject_non_trading_sessions([prev, holiday_bar], "TESTSYM")
    assert [r["bar_date"] for r in kept] == [date(2026, 9, 11)]


# ── _classify_quality's stale-carry-forward secondary guard ─────────────

def test_stale_carry_forward_on_a_valid_session_is_quarantined_not_good():
    prev = _bar(date(2026, 9, 11), 100.0)
    flat_bar = _bar(date(2026, 9, 15), 100.0, volume=0)  # valid weekday, flat, == prev close
    classified = backfill._classify_quality([prev, flat_bar])
    assert classified[1]["data_quality"] == "stale_carry_forward"
    assert classified[1]["data_quality"] != "good"


def test_legitimate_thin_volume_bar_is_not_reclassified_as_stale_carry_forward():
    """A real, illiquid session with zero volume but genuine intraday
    movement (not flat, or not equal to the prior close) must stay
    `thin_volume`, not be quarantined as a carry-forward artifact."""
    prev = _bar(date(2026, 9, 11), 100.0)
    moved_but_illiquid = _bar(date(2026, 9, 15), 101.5, open_=100.0, high=102.0, low=99.5, volume=0)
    classified = backfill._classify_quality([prev, moved_but_illiquid])
    assert classified[1]["data_quality"] == "thin_volume"


def test_flat_zero_volume_bar_not_matching_prev_close_stays_thin_volume():
    prev = _bar(date(2026, 9, 11), 100.0)
    flat_different_close = _bar(date(2026, 9, 15), 105.0, volume=0)  # flat, but NOT == prev close
    classified = backfill._classify_quality([prev, flat_different_close])
    assert classified[1]["data_quality"] == "thin_volume"


# ── upsert_price_bars — the final choke point (defense in depth) ────────

async def test_upsert_never_stores_a_non_trading_session_row_even_if_pre_filter_is_bypassed(db_session):
    rows = [{**_bar(date(2026, 9, 14), 100.0, volume=0), "data_quality": "stale_carry_forward"}]
    inserted, updated = await backfill.upsert_price_bars(db_session, "TESTSYM", rows)
    assert (inserted, updated) == (0, 0)
    result = await db_session.execute(select(PriceBar).where(PriceBar.symbol == "TESTSYM"))
    assert result.scalars().all() == []


async def test_existing_good_row_cannot_be_overwritten_by_rejected_data(db_session):
    good_row = {**_bar(date(2026, 9, 11), 100.0), "data_quality": "good"}
    inserted, _ = await backfill.upsert_price_bars(db_session, "TESTSYM", [good_row])
    await db_session.commit()
    assert inserted == 1

    # A caller that (incorrectly) tries to upsert a holiday-dated row
    # for the SAME date range must not be able to touch the existing
    # good row for 2026-09-11 -- simulated here by attempting an upsert
    # for the rejected 2026-09-14 date only; the real 09-11 row must be
    # untouched regardless.
    rejected_row = {**_bar(date(2026, 9, 14), 999.0, volume=0), "data_quality": "stale_carry_forward"}
    await backfill.upsert_price_bars(db_session, "TESTSYM", [rejected_row])
    await db_session.commit()

    result = await db_session.execute(
        select(PriceBar).where(PriceBar.symbol == "TESTSYM", PriceBar.bar_date == date(2026, 9, 11))
    )
    row = result.scalar_one()
    assert row.close == 100.0
    assert row.data_quality == "good"


# ── shared validation function across every real caller ─────────────────

def test_backfill_and_daily_refresh_use_the_same_underlying_functions():
    from app.services.quant import refresh
    import inspect
    source = inspect.getsource(refresh)
    assert "backfill_universe" in source
    assert "from app.services.quant.backfill import backfill_universe" in source
    # refresh.py has no independent PriceBar-writing code of its own --
    # confirmed by absence, not just presence of the shared import.
    assert "PriceBar(" not in source


async def test_backfill_universe_calls_backfill_symbol_once_per_symbol(monkeypatch, db_session):
    calls: list[str] = []

    async def fake_backfill_symbol(db, symbol, period="5y"):
        calls.append(symbol)
        return {"symbol": symbol, "fetched": 0, "inserted": 0, "updated": 0, "ok": True}

    monkeypatch.setattr(backfill, "backfill_symbol", fake_backfill_symbol)
    symbols = ["AAA", "BBB", "CCC"]
    result = await backfill.backfill_universe(db_session, symbols, delay_sec=0)
    assert calls == symbols
    assert result["total_symbols"] == 3


# ── sanitized telemetry ──────────────────────────────────────────────────

def test_rejection_telemetry_contains_only_symbol_date_reason(monkeypatch):
    captured = {}

    def fake_info(event, **kwargs):
        captured["event"] = event
        captured["kwargs"] = kwargs

    monkeypatch.setattr(backfill.log, "info", fake_info)
    backfill._reject_non_trading_sessions([_bar(date(2026, 9, 14), 100.0, volume=0)], "TESTSYM")

    assert captured["event"] == "backfill.bar_rejected"
    assert set(captured["kwargs"].keys()) == {"symbol", "bar_date", "reason"}
    assert captured["kwargs"]["symbol"] == "TESTSYM"
    assert captured["kwargs"]["bar_date"] == "2026-09-14"
    assert captured["kwargs"]["reason"] == "non_trading_session"
    # Never the full row or a raw response payload.
    for value in captured["kwargs"].values():
        assert not isinstance(value, dict)
