"""Capacity protection (2026-10-11): an event whose failure was only provider cooldown keeps its retry budget, enrichment ticks are skipped when no provider can be tried, scheduled market
articles do not start (or duplicate) when nothing can be tried, and all of it is recorded as skipped work. Event tests use the same fake provider + real DB-backed Event rows as
test_event_pipeline_r1_integrity.py; no network."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

import app.services.ai_service as ai
import app.services.ai_usage as U
from app.db.models.event import Event
from app.db.session import AsyncSessionLocal
from app.pipeline.event_pipeline import _MAX_ENRICHMENT_RETRIES
from app.repositories.event_repository import EventRepository
from app.services.measurement_semantics import IntegrityStatus
from tests.services.test_event_pipeline_r1_integrity import _FakeAIProvider, _cleanup, _fetch, _run_with_fake_provider, _tag

FALLBACK = {"integrity_status": IntegrityStatus.FALLBACK.value}


@pytest.fixture(autouse=True)
def clean_usage_state():
    ai._EXHAUSTED.clear()
    U._queue.clear(); U._search_queue.clear(); U._skips.clear()
    yield
    ai._EXHAUSTED.clear()


def real_failed_attempt():
    a = U.begin_attempt("groq", "m")
    U.set_outcome(a, "rate_limited", 429)
    U.finish_attempt(a)


class _AI(_FakeAIProvider):
    """classify_event fails like an unavailable provider, after doing whatever 'real work' the scenario describes."""
    def __init__(self, skips=0, attempts=0):
        super().__init__()
        self.skips, self.attempts = skips, attempts

    async def classify_event(self, text):
        for _ in range(self.skips):
            U.note_skip("groq", "m")                     # a cooling-down model skipped by the chain
        for _ in range(self.attempts):
            real_failed_attempt()                        # a real HTTP attempt that failed
        return dict(FALLBACK)


async def _seed(retry_count: int) -> str:
    import uuid
    eid = f"test-cap-{uuid.uuid4()}"
    async with AsyncSessionLocal() as db:
        db.add(Event(id=eid, title=f"{_tag()} capacity test event", source="Test", enrichment_status="failed" if retry_count else "pending", retry_count=retry_count,
                     created_at=datetime.now(timezone.utc)))
        await db.commit()
    return eid


async def _run(retry_count: int, provider: _AI, monkeypatch) -> Event:
    eid = await _seed(retry_count)
    try:
        assert await _run_with_fake_provider(eid, provider, monkeypatch) is False
        return await _fetch(eid)
    finally:
        await _cleanup([eid])


# ── events: cooldown-only does not consume a retry ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cooldown_only_failure_keeps_the_retry_budget(monkeypatch):
    ev = await _run(2, _AI(skips=5), monkeypatch)
    assert ev.retry_count == 2                                                    # unchanged, not 3
    assert ev.enrichment_status == "failed" and ev.last_failure_reason == "provider_cooldown"
    assert ev.next_retry_at is not None                                           # still scheduled for another attempt
    assert sum(n for (op, _p, _m, out), n in U._skips.items() if op == "event_enrichment" and out == "skipped_cooldown_event") == 1


@pytest.mark.asyncio
async def test_cooldown_only_never_graduates_an_event_to_failed_permanent(monkeypatch):
    cooldown = await _run(_MAX_ENRICHMENT_RETRIES - 1, _AI(skips=3), monkeypatch)
    assert cooldown.enrichment_status == "failed" and cooldown.retry_count == _MAX_ENRICHMENT_RETRIES - 1
    genuine = await _run(_MAX_ENRICHMENT_RETRIES - 1, _AI(attempts=1), monkeypatch)       # the same position, but with a real failed attempt: unchanged historical behaviour
    assert genuine.enrichment_status == "failed_permanent" and genuine.retry_count == _MAX_ENRICHMENT_RETRIES


@pytest.mark.asyncio
async def test_mixed_cooldown_and_genuine_failure_still_consumes_a_retry(monkeypatch):
    ev = await _run(1, _AI(skips=4, attempts=1), monkeypatch)
    assert ev.retry_count == 2 and ev.last_failure_reason == "provider_unavailable"


@pytest.mark.asyncio
async def test_genuine_failure_and_no_signal_failure_are_counted_exactly_as_before(monkeypatch):
    assert (await _run(0, _AI(attempts=2), monkeypatch)).retry_count == 1
    assert (await _run(0, _AI(), monkeypatch)).retry_count == 1                   # nothing attempted and nothing skipped (e.g. no key at all): not a cooldown, counted


@pytest.mark.asyncio
async def test_cooldown_only_event_stays_eligible_for_retry(monkeypatch):
    eid = await _seed(2)
    try:
        await _run_with_fake_provider(eid, _AI(skips=2), monkeypatch)
        ev = await _fetch(eid)
        due = ev.next_retry_at if ev.next_retry_at.tzinfo else ev.next_retry_at.replace(tzinfo=timezone.utc)
        async with AsyncSessionLocal() as db:
            eligible = await EventRepository(db).get_pending_enrichment(limit=500, now=due + timedelta(minutes=1))
        assert eid in [e.id for e in eligible]
    finally:
        await _cleanup([eid])


# ── capacity check and enrichment ticks ───────────────────────────────────────────────────────────────────────

def test_any_provider_available_reflects_keys_and_cooldowns(monkeypatch):
    for name in ("groq_api_key", "openrouter_api_key", "mistral_api_key", "gemini_api_key", "requesty_api_key"):
        monkeypatch.setattr(ai.settings, name, "", raising=False)
    assert ai.any_provider_available() is False                                   # nothing configured
    monkeypatch.setattr(ai.settings, "groq_api_key", "k", raising=False)
    assert ai.any_provider_available() is True
    models = list(ai._GROQ_HIGH) + list(ai._GROQ_FAST)
    for m in models[:-1]:
        ai._mark_exhausted("groq", m, "rate_limit")
    assert ai.any_provider_available() is True                                    # one model still free
    ai._mark_exhausted("groq", models[-1], "rate_limit")
    assert ai.any_provider_available() is False                                   # every configured model cooling down
    ai._clear_exhaustion("groq")
    assert ai.any_provider_available() is True


def test_capacity_check_fails_open_if_it_errors(monkeypatch):
    monkeypatch.setattr(ai, "_build_tiers", lambda h: (_ for _ in ()).throw(RuntimeError("boom")))
    assert ai.any_provider_available() is True                                    # never block work because the check itself broke


@pytest.mark.asyncio
async def test_enrichment_tick_is_skipped_and_recorded_when_no_provider_is_available(monkeypatch):
    from app.tasks.ingest_tasks import job_enrich_events
    pending = AsyncMock(return_value=[])
    monkeypatch.setattr(EventRepository, "get_pending_enrichment", pending)
    monkeypatch.setattr(ai, "any_provider_available", lambda: False)
    await job_enrich_events()
    pending.assert_not_awaited()                                                  # no event was even picked up: retry state of every event is untouched
    assert U._skips[("event_enrichment", "-", "-", "skipped_no_capacity")] == 1
    monkeypatch.setattr(ai, "any_provider_available", lambda: True)
    await job_enrich_events()
    pending.assert_awaited_once()                                                 # with capacity the tick runs exactly as before
    assert U._skips[("event_enrichment", "-", "-", "skipped_no_capacity")] == 1


# ── scheduled market articles: no run when nothing can be tried, never a duplicate ─────────────────────────────

SCHED = {"_article_type": "market_wrap", "headline": "Market wrap for the day", "event_id": "sched-evt-1"}


def _cycle(today_story_ids, capacity: bool):
    from tests.services.test_publisher_cycle_skip_states import _run_with_mocks
    article = SimpleNamespace(status="published", id="art-1")
    stack, publish = _run_with_mocks([], AsyncMock(return_value=article), today_story_ids=today_story_ids)
    start, complete = AsyncMock(return_value=SimpleNamespace(id="run-1")), AsyncMock()
    stack.enter_context(patch("app.services.aipe.publisher._scheduled_article_due", new_callable=AsyncMock, return_value=True))
    stack.enter_context(patch("app.services.aipe.publisher._build_scheduled_event", new_callable=AsyncMock, return_value=dict(SCHED)))
    stack.enter_context(patch("app.services.aipe.publisher.start_candidate_run", start))
    stack.enter_context(patch("app.services.aipe.publisher.complete_candidate_run", complete))
    stack.enter_context(patch("app.services.ai_service.any_provider_available", lambda: capacity))
    return stack, publish, start, complete


@pytest.mark.asyncio
async def test_scheduled_article_does_not_start_when_no_provider_is_available():
    from app.services.aipe import publisher
    stack, publish, start, complete = _cycle(set(), capacity=False)
    with stack:
        await publisher.run_aipe_cycle()
    publish.assert_not_awaited(); start.assert_not_awaited(); complete.assert_not_awaited()      # nothing generated, nothing recorded as a failed run
    assert U._skips[("scheduled_market_article", "-", "-", "skipped_no_capacity")] == 1


@pytest.mark.asyncio
async def test_scheduled_article_publishes_once_and_a_second_cycle_cannot_duplicate_it():
    from app.services.aipe import publisher
    stack, publish, start, complete = _cycle(set(), capacity=True)
    with stack:
        await publisher.run_aipe_cycle()
    assert publish.await_count == 1 and start.await_count == 1
    assert complete.await_args.kwargs["terminal_status"] == "PUBLISHED"
    story_id = publish.await_args.args[4]                                         # the story id the first cycle generated
    stack2, publish2, start2, _ = _cycle({story_id}, capacity=True)               # the next cycle sees today's story id as already generated
    with stack2:
        await publisher.run_aipe_cycle()
    publish2.assert_not_awaited(); start2.assert_not_awaited()


def test_scheduled_capacity_skip_is_logged_at_most_every_30_minutes_per_story(monkeypatch):
    from app.services.aipe import publisher
    publisher._SKIP_LOG_AT.clear()
    fake_log = MagicMock()
    monkeypatch.setattr(publisher, "log", fake_log)
    monkeypatch.setattr(ai, "any_provider_available", lambda: False)
    for _ in range(50):
        assert publisher._scheduled_capacity_available("market_wrap", "wrap-x") is False
    assert fake_log.info.call_count == 1                                          # 50 skipped cycles, one log line
    assert U._skips[("scheduled_market_article", "-", "-", "skipped_no_capacity")] == 50   # but every skip is counted


# ── APScheduler: no duplicate execution ────────────────────────────────────────────────────────────────────────

def test_scheduler_has_no_duplicate_jobs_and_single_instance_guards():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from app.scheduler.scheduler import register_jobs
    sch = AsyncIOScheduler()
    register_jobs(sch)
    jobs = sch.get_jobs()
    ids = [j.id for j in jobs]
    assert len(ids) == len(set(ids))                                              # every job registered once
    import collections
    per_func = collections.defaultdict(list)
    for j in jobs:
        per_func[j.func.__name__].append(str(j.trigger))
    intentionally_twice = {"run_comparison_cycle", "run_weekend_checkpoint_cycle"}       # the same cycle at two times of day (distinct cron triggers), unchanged by this work
    for name, triggers in per_func.items():
        if len(triggers) > 1:
            assert name in intentionally_twice and len(set(triggers)) == len(triggers), f"{name} is scheduled more than once without being intended"
    by = {j.id: j for j in jobs}
    for jid in ("enrich_events", "aipe_publish_cycle", "ai_usage_flush", "ai_usage_daily", "keep_market_warm"):
        assert by[jid].max_instances == 1 and by[jid].coalesce is True, jid       # a slow run is never overlapped by the next tick, and missed ticks collapse into one
