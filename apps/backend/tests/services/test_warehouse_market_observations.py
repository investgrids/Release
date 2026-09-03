"""
Phase 1B Batch 1D — scheduler-wiring verification (owner instruction,
2026-08-23: "Verify one real scheduled cycle end-to-end. Not just manual
invocation... no duplicate rows... source failures persisted honestly").

capture_market_observations_if_due() is gated to NSE regular trading
hours ("live" session) — since tests run whenever CI/a developer runs
them, not necessarily during real market hours, these tests explicitly
monkeypatch _bucket_now() to simulate a live session. This is a labeled
test scenario, not a claim about real market data — the underlying
capture calls the SAME real fetchers as production (yfinance, NSE
scrapes, GIFT Nifty), so whatever real values those return right now are
what gets persisted; only the SESSION GATE is simulated, never the data.

The real (non-simulated) off-hours gate itself is verified separately —
see the module's own git history / the live verification run performed
directly against the real scheduler entrypoint
(app.services.intelligence.price_monitor.run_price_monitor_cycle) on a
real weekend, which correctly captured zero rows.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select, func

from app.db.models.market_observation import MarketObservation
from app.db.session import AsyncSessionLocal
from app.services.warehouse import market_observations as mo
from app.services.warehouse.source_registry_seed import seed_source_registry


def _fake_bucket_now(observation_time: datetime, market_date: date, session: str, bucket_key: str):
    def _inner():
        return observation_time, market_date, session, bucket_key
    return _inner


async def _cleanup(observation_time: datetime) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(MarketObservation).where(MarketObservation.observation_time == observation_time))
        await db.commit()


@pytest.mark.asyncio
async def test_scheduled_capture_persists_real_rows_when_gate_is_live(monkeypatch):
    """Simulated live session (labeled synthetic — see module docstring),
    real fetchers, real persistence."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    bucket_key = f"test-{now.isoformat()}"
    monkeypatch.setattr(mo, "_bucket_now", _fake_bucket_now(now, now.date(), "live", bucket_key))
    monkeypatch.setattr(mo, "_last_captured_bucket", None)

    try:
        async with AsyncSessionLocal() as db:
            # capture_market_observations_if_due() writes real, hardcoded
            # production source_ids (e.g. "yfinance_india_vix") -- self-
            # contained against a genuinely isolated test DB only if those
            # rows actually exist here; seed_source_registry() is upsert-
            # based, safe to call even when real rows already exist.
            await seed_source_registry(db)
            result = await mo.capture_market_observations_if_due(db)

        assert result["skipped"] is False
        # Not a hardcoded count (Batch 3, 2026-08-23) — the number of
        # wired metrics has grown and will keep growing; assert internal
        # consistency instead.
        assert result["capture_attempts"] > 20, "Batch 3 added well beyond the original 20 metrics"
        assert result["successful_metric_rows"] + result["source_failure_rows"] == result["capture_attempts"]
        assert result["duplicate_suppressed"] == 0

        async with AsyncSessionLocal() as db:
            count = (await db.execute(
                select(func.count()).select_from(MarketObservation).where(MarketObservation.observation_time == now)
            )).scalar()
        assert count == result["capture_attempts"], "one row per wired metric must be persisted for this exact bucket"
    finally:
        await _cleanup(now)


@pytest.mark.asyncio
async def test_second_call_in_same_bucket_is_suppressed_not_duplicated(monkeypatch):
    """The literal owner requirement: scheduler restart/overlap within
    the same 15-minute bucket must not create duplicate rows."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    bucket_key = f"test-dup-{now.isoformat()}"
    monkeypatch.setattr(mo, "_bucket_now", _fake_bucket_now(now, now.date(), "live", bucket_key))
    monkeypatch.setattr(mo, "_last_captured_bucket", None)

    try:
        async with AsyncSessionLocal() as db:
            await seed_source_registry(db)
            first = await mo.capture_market_observations_if_due(db)
        assert first["skipped"] is False
        first_count = first["capture_attempts"]

        # Simulate a restart: reset the in-process guard, same bucket_now.
        monkeypatch.setattr(mo, "_last_captured_bucket", None)

        async with AsyncSessionLocal() as db:
            second = await mo.capture_market_observations_if_due(db)
        assert second["skipped"] is True
        assert second["skip_reason"] == "already_captured_this_bucket_db"
        # duplicate_suppressed is the REAL existing row count for this
        # bucket, not a hardcoded metric count (Batch 3, 2026-08-23).
        assert second["duplicate_suppressed"] == first_count
        assert second["capture_attempts"] == 0, "must not re-fetch at all once the DB confirms this bucket is already captured"

        async with AsyncSessionLocal() as db:
            count = (await db.execute(
                select(func.count()).select_from(MarketObservation).where(MarketObservation.observation_time == now)
            )).scalar()
        assert count == first_count, "still exactly the first cycle's row count — the second call must not have added any"
    finally:
        await _cleanup(now)


@pytest.mark.asyncio
async def test_in_process_guard_skips_without_a_db_round_trip(monkeypatch):
    """The cheap fast path — same bucket_key twice in a row, guard
    already set, no DB query needed at all."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    bucket_key = f"test-guard-{now.isoformat()}"
    monkeypatch.setattr(mo, "_bucket_now", _fake_bucket_now(now, now.date(), "live", bucket_key))
    monkeypatch.setattr(mo, "_last_captured_bucket", bucket_key)  # pretend already captured this boot

    async with AsyncSessionLocal() as db:
        result = await mo.capture_market_observations_if_due(db)
    assert result["skipped"] is True
    assert result["skip_reason"] == "already_captured_this_bucket_inprocess"


def test_no_api_route_imports_the_capture_functions():
    """Owner requirement: 'no page request is responsible for
    persistence.' Structural guard, not just a manual grep — fails loudly
    if a future change wires persistence into a request path."""
    import ast
    import pathlib

    api_dir = pathlib.Path(__file__).resolve().parents[2] / "app" / "api"
    offending: list[str] = []
    for path in api_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "capture_market_observations" in text:
            offending.append(str(path))
    assert offending == [], f"capture_market_observations must never be imported from an API route file: {offending}"
