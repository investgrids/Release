"""
Phase 5F.3 — Phase 5C's macro_rates package (US Treasury, Fed H.15,
RBI WSS) had zero source_health tracking and no scheduled job. Both
confirmed real gaps by Phase 5F's audit: a staleness/outage in any of
these 3 sources would have been exactly as invisible as BSE's
multi-day outage was before Phase 5D found it.

Fixed by wiring source_health.record_fetch() into each source module
and adding a scheduled job (job_macro_rates_sync, every 6h IST,
matching get_macro_rate_state's own TTL) that keeps the cache warm on
a fixed schedule instead of depending entirely on reactive traffic.
"""
from __future__ import annotations

import pytest

from app.services import source_health


def test_macro_rate_sources_are_known():
    for source in ("US Treasury", "Fed H.15", "RBI WSS"):
        assert source in source_health.KNOWN_SOURCES


@pytest.mark.asyncio
async def test_live_us_treasury_records_health():
    from app.services.macro_rates.us_treasury_source import get_us_treasury_state
    await get_us_treasury_state()
    health = source_health.get_source_health("US Treasury")
    assert health["status"] in ("HEALTHY", "DEGRADED", "FAILED")
    assert health["last_attempt_at"] is not None


@pytest.mark.asyncio
async def test_live_fed_h15_records_health():
    from app.services.macro_rates.fed_funds_source import get_fed_funds_rate
    await get_fed_funds_rate()
    health = source_health.get_source_health("Fed H.15")
    assert health["status"] in ("HEALTHY", "DEGRADED", "FAILED")
    assert health["last_attempt_at"] is not None


@pytest.mark.asyncio
async def test_live_rbi_wss_records_health():
    from app.services.macro_rates.rbi_wss_source import get_rbi_wss_state
    await get_rbi_wss_state()
    health = source_health.get_source_health("RBI WSS")
    assert health["status"] in ("HEALTHY", "DEGRADED", "FAILED")
    assert health["last_attempt_at"] is not None


@pytest.mark.asyncio
async def test_job_macro_rates_sync_populates_all_three_sources():
    """Real end-to-end: the actual scheduled job function, not just the
    individual source calls in isolation."""
    from app.tasks.daily_tasks import job_macro_rates_sync
    await job_macro_rates_sync()  # must not raise

    statuses = source_health.get_all_source_health(["US Treasury", "Fed H.15", "RBI WSS"])
    for s in statuses:
        assert s["status"] != "UNKNOWN"
        assert s["last_attempt_at"] is not None


def test_job_macro_rates_sync_is_scheduled():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.scheduler.scheduler import _IST, register_jobs

    scheduler = AsyncIOScheduler(timezone=_IST)
    register_jobs(scheduler)
    job = scheduler.get_job("macro_rates_sync")
    assert job is not None
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "3,9,15,21"
    assert str(job.trigger.timezone) == str(_IST)


@pytest.mark.asyncio
async def test_job_macro_rates_sync_never_raises_even_if_source_fails(monkeypatch):
    async def _boom():
        raise RuntimeError("simulated total outage")

    import app.services.macro_rates.service as service_mod
    monkeypatch.setattr(service_mod, "get_macro_rate_state", _boom)

    from app.tasks import daily_tasks
    await daily_tasks.job_macro_rates_sync()  # must not raise, matching every other scheduled job's contract
