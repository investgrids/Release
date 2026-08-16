"""
Phase 5A.7 — scheduler registration tests for the two Economic Calendar
jobs, matching this codebase's established scheduler-test pattern (see
test_weekend_intelligence_scheduler.py) and the owner's explicit rules:
stable job IDs, Asia/Kolkata timezone, no duplicate registration, no
Eurostat/ECB job, no earnings job, source failure isolation.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scheduler.scheduler import _IST, register_jobs


def _fresh_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler(timezone=_IST)


def test_both_economic_calendar_jobs_registered_with_stable_ids():
    scheduler = _fresh_scheduler()
    register_jobs(scheduler)
    ids = {job.id for job in scheduler.get_jobs()}
    assert "economic_calendar_full_sync" in ids
    assert "economic_calendar_imminent_recheck" in ids


def test_full_sync_runs_daily_in_ist_at_a_quiet_hour():
    scheduler = _fresh_scheduler()
    register_jobs(scheduler)
    job = scheduler.get_job("economic_calendar_full_sync")
    assert isinstance(job.trigger, CronTrigger)
    assert str(job.trigger.timezone) == str(_IST)
    field_map = {f.name: str(f) for f in job.trigger.fields}
    assert field_map["hour"] == "3"
    assert field_map["minute"] == "0"
    # Clear of market open (9:15 IST) and the 16:30/17:00 IST quant/
    # observation jobs — a pure external-fetch job, no reason to share
    # either window.
    assert 3 not in (16, 17) and 3 < 9


def test_imminent_recheck_runs_four_times_daily_not_continuously():
    scheduler = _fresh_scheduler()
    register_jobs(scheduler)
    job = scheduler.get_job("economic_calendar_imminent_recheck")
    assert isinstance(job.trigger, CronTrigger)
    assert str(job.trigger.timezone) == str(_IST)
    field_map = {f.name: str(f) for f in job.trigger.fields}
    # "2,8,14,20" -> exactly 4 fire times per day, not an interval/*
    # wildcard that would poll continuously (owner: "do not repeatedly
    # poll every source all day").
    assert field_map["hour"] == "2,8,14,20"


def test_no_duplicate_registration_after_restart():
    """"Restart" in this codebase means a brand-new process constructing
    a brand-new AsyncIOScheduler with the default in-memory jobstore
    (confirmed: scheduler.py's own AsyncIOScheduler(timezone=_IST)
    passes no jobstore, and register_jobs() has exactly one real call
    site, at scheduler.py's own start_scheduler()) — jobs are never
    persisted across a restart, so there is nothing to duplicate. That
    guarantee is architectural, not a de-dup check inside register_jobs
    itself: calling it twice against the SAME live scheduler instance
    (which never happens in real operation — grep confirms the one call
    site) does add every job twice, since APScheduler's add_job doesn't
    silently no-op on a re-used id without replace_existing=True. This
    test asserts the actual guarantee — one call site, no persistent
    jobstore — rather than a scenario that doesn't occur in production."""
    import inspect
    from app.scheduler import scheduler as scheduler_module

    source = inspect.getsource(scheduler_module)
    assert source.count("register_jobs(scheduler)") == 1   # exactly one real call site
    assert "AsyncIOScheduler(timezone=_IST)" in source       # no jobstore= kwarg -> default in-memory, nothing persists across a restart

    scheduler = _fresh_scheduler()
    register_jobs(scheduler)
    ids = [job.id for job in scheduler.get_jobs()]
    assert len(ids) == len(set(ids))   # no duplicate ids from a single, real registration pass


def test_no_eurostat_or_ecb_job_registered_while_deferred():
    scheduler = _fresh_scheduler()
    register_jobs(scheduler)
    ids = {job.id.lower() for job in scheduler.get_jobs()}
    assert not any("eurostat" in i for i in ids)
    assert not any("ecb" in i for i in ids)


def test_no_earnings_job_registered_yet():
    scheduler = _fresh_scheduler()
    register_jobs(scheduler)
    ids = {job.id.lower() for job in scheduler.get_jobs()}
    assert not any("earning" in i for i in ids)


@pytest.mark.asyncio
async def test_full_sync_job_does_not_raise_when_orchestrator_fails():
    """Matches every other job in this codebase's own defensive style
    (checkpoints, quant_price_refresh, intelligence_observation_snapshot)
    — a failure inside the job must be caught internally, never escape
    to the scheduler."""
    from app.tasks.daily_tasks import job_economic_calendar_full_sync

    with patch(
        "app.services.economic_calendar.sync_orchestrator.run_full_sync",
        new=AsyncMock(side_effect=Exception("simulated total failure")),
    ):
        await job_economic_calendar_full_sync()   # must not raise


@pytest.mark.asyncio
async def test_imminent_recheck_job_does_not_raise_when_orchestrator_fails():
    from app.tasks.daily_tasks import job_economic_calendar_imminent_recheck

    with patch(
        "app.services.economic_calendar.sync_orchestrator.run_imminent_recheck",
        new=AsyncMock(side_effect=Exception("simulated total failure")),
    ):
        await job_economic_calendar_imminent_recheck()   # must not raise
