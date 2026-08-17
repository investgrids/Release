"""
Scheduler registration tests — brief §33. Confirms the exact new jobs,
their trigger config (day_of_week/timezone), that the total job count
only changed by the expected +2, that no Monday-finalization job exists
yet, and that a checkpoint failure can't propagate out of the scheduled
function (it must be caught internally, matching every other job in
this codebase's own defensive style).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scheduler.scheduler import _IST, register_jobs


def _fresh_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler(timezone=_IST)


def test_exactly_two_new_weekend_checkpoint_jobs_registered():
    scheduler = _fresh_scheduler()
    register_jobs(scheduler)
    ids = {job.id for job in scheduler.get_jobs()}
    assert "weekend_intelligence_checkpoint_morning" in ids
    assert "weekend_intelligence_checkpoint_evening" in ids


def test_recurring_job_count_increased_by_exactly_two():
    """register_jobs() alone (this test's scope) registers only the
    RECURRING jobs — 21 per the Phase 1 architecture audit's count,
    confirmed again here before this change. The one-time boot/repair
    jobs (9 more) are registered separately by start_scheduler(), not by
    register_jobs(), and aren't this test's concern — a real full boot's
    log (captured live while applying this phase's schema patch) showed
    scheduler.jobs_registered count=32, i.e. the pre-existing 30 (21+9)
    plus these 2 new ones, which is the number to trust for "total jobs
    on a real boot," not this narrower register_jobs()-only count.

    Phase 2B §4 added one more recurring job (quant_price_refresh,
    16:30 IST) — 21 + 2 (weekend checkpoints) + 1 (quant refresh) = 24.
    This test's own name ("increased by exactly two") describes the
    Weekend Intelligence phase's own delta and is intentionally left
    as-is; the assertion below is the number that must stay accurate.
    24 -> 25: Phase 2E.1 added job_intelligence_observation_snapshot
    (5:00 PM IST, CompanyIntelligenceObservation collection).
    25 -> 27: Phase 5A.7 added job_economic_calendar_full_sync (3:00 AM
    IST) and job_economic_calendar_imminent_recheck (every 6h IST).
    27 -> 28: Phase 5F.3 added job_macro_rates_sync (every 6h IST,
    3/9/15/21:15) — Phase 5C's macro_rates package had no scheduled job
    at all before this, relying entirely on reactive traffic to keep
    its 6h-TTL cache warm."""
    scheduler = _fresh_scheduler()
    register_jobs(scheduler)
    assert len(scheduler.get_jobs()) == 28


def test_checkpoint_jobs_are_weekend_only_and_ist():
    scheduler = _fresh_scheduler()
    register_jobs(scheduler)
    morning = scheduler.get_job("weekend_intelligence_checkpoint_morning")
    evening = scheduler.get_job("weekend_intelligence_checkpoint_evening")

    for job in (morning, evening):
        assert isinstance(job.trigger, CronTrigger)
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields["day_of_week"] == "sat,sun"
        assert str(job.trigger.timezone) == str(_IST)

    assert fields_hour(morning) == "9"
    assert fields_hour(evening) == "18"


def fields_hour(job) -> str:
    return str(next(f for f in job.trigger.fields if f.name == "hour"))


def test_no_monday_finalization_job_exists_yet():
    """brief §23: 'Do NOT add Monday finalization yet' — this is Phase
    1C's job."""
    scheduler = _fresh_scheduler()
    register_jobs(scheduler)
    ids = {job.id.lower() for job in scheduler.get_jobs()}
    assert not any("monday" in job_id for job_id in ids)


def test_no_other_existing_job_ids_were_removed():
    """Spot-checks a handful of pre-existing Phase-0/1A job ids are still
    present, unmodified by this change — Phase 1B only ever ADDS jobs."""
    scheduler = _fresh_scheduler()
    register_jobs(scheduler)
    ids = {job.id for job in scheduler.get_jobs()}
    for expected in ("daily_opportunities", "mie_refresh", "aipe_publish_cycle", "ingest_news"):
        assert expected in ids


@pytest.mark.asyncio
async def test_checkpoint_cycle_failure_does_not_raise():
    """brief §33: 'checkpoint failure does not crash scheduler' — the
    scheduled entry point must swallow a failure internally, exactly
    like every other job in this codebase (see price_monitor.py's own
    per-instrument try/except)."""
    from app.services.weekend_intelligence import checkpoints

    with patch(
        "app.services.weekend_intelligence.checkpoints.run_checkpoint",
        side_effect=Exception("simulated DB outage"),
    ):
        await checkpoints.run_weekend_checkpoint_cycle()  # must not raise
