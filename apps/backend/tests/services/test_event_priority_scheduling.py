"""Phase 2 (2026-10-13): urgency-aware event enrichment selection and per-stage failure diagnostics, behind settings flags. Real test-scratch DB (see conftest.py), injectable `now`,
no network. Eligibility, the two lanes, the guaranteed backlog slot and retry/backoff are unchanged; only the order inside a lane changes, and only with the flag on."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

import app.services.ai_service as ai
import app.services.ai_usage as U
from app.core.config import settings
from app.db.models.event import Event
from app.db.models.intelligence import EventTriage
from app.db.session import AsyncSessionLocal
from app.pipeline import event_pipeline as ep
from app.repositories.event_repository import EventRepository
from tests.services.test_event_pipeline_r1_integrity import _FakeAIProvider, _cleanup as _cleanup_events, _fetch, _run_with_fake_provider, _tag

_INTERVAL = 300
PREFIX = "pytest-prio-"


def _now(force_backlog: bool, urgent_first: bool | None = None) -> datetime:
    """A UTC time whose bucket has (bucket % 4 == 0) == force_backlog and, when given, ((bucket // 4) % 2 == 0) == urgent_first."""
    base = datetime(2026, 10, 13, 6, 0, 0, tzinfo=timezone.utc)
    bucket = int(base.timestamp() // _INTERVAL)
    for off in range(0, 64):
        b = bucket + off
        if ((b % 4) == 0) != force_backlog:
            continue
        if urgent_first is not None and (((b // 4) % 2) == 0) != urgent_first:
            continue
        return datetime.fromtimestamp(b * _INTERVAL + 7, tz=timezone.utc)
    raise AssertionError("no bucket found")


@pytest.fixture
def prio(monkeypatch):
    monkeypatch.setattr(settings, "event_enrichment_priority_enabled", True, raising=False)
    monkeypatch.setattr(settings, "event_enrichment_urgent_threshold", 7, raising=False)
    monkeypatch.setattr(settings, "event_enrichment_aging_hours", 6, raising=False)


async def mk(made: list[str], name: str, *, age_h: float, now: datetime, urgency: int | None = None, status="pending", retry_count=0, next_retry_at=None) -> str:
    eid = f"{PREFIX}{name}-{uuid.uuid4().hex[:6]}"
    created = now - timedelta(hours=age_h)
    async with AsyncSessionLocal() as db:
        db.add(Event(id=eid, title=name, summary="x", source="test", event_type="news", published_at=created, created_at=created, updated_at=created,
                     enrichment_status=status, retry_count=retry_count, next_retry_at=next_retry_at))
        if urgency is not None:
            db.add(EventTriage(id=f"t-{eid}", event_id=eid, source="news", headline=name, urgency=urgency))
        await db.commit()
    made.append(eid)
    return eid


async def pick(now: datetime, limit: int, made: list[str]) -> list[str]:
    async with AsyncSessionLocal() as db:
        rows = await EventRepository(db).get_pending_enrichment(limit=limit, now=now)
    return [e.id for e in rows if e.id in made]


async def purge(made: list[str]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(EventTriage).where(EventTriage.event_id.in_(made)))
        await db.execute(delete(Event).where(Event.id.in_(made)))
        await db.commit()


# ── flag off: unchanged FIFO ─────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_flag_off_keeps_plain_fifo_and_ignores_urgency(monkeypatch):
    monkeypatch.setattr(settings, "event_enrichment_priority_enabled", False, raising=False)
    made: list[str] = []
    now = _now(False)
    try:
        old_normal = await mk(made, "old-normal", age_h=5, now=now, urgency=3)
        new_urgent = await mk(made, "new-urgent", age_h=1, now=now, urgency=9)
        assert await pick(now, 1000, made) == [old_normal, new_urgent]
    finally:
        await purge(made)


# ── flag on: ordering ─────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_urgent_recent_first_then_aged_normal_then_new_normal(prio):
    made: list[str] = []
    now = _now(False)
    try:
        new_normal = await mk(made, "new-normal", age_h=1, now=now, urgency=3)
        aged_normal = await mk(made, "aged-normal", age_h=8, now=now, urgency=4)
        urgent_new = await mk(made, "urgent-new", age_h=0.5, now=now, urgency=8)
        no_triage = await mk(made, "no-triage", age_h=0.2, now=now, urgency=None)
        assert await pick(now, 1000, made) == [urgent_new, aged_normal, new_normal, no_triage]   # FIFO inside the "new normal" group: no_triage is newest
    finally:
        await purge(made)


@pytest.mark.asyncio
async def test_urgency_uses_the_highest_triage_row_and_threshold_is_inclusive(prio):
    made: list[str] = []
    now = _now(False)
    try:
        a = await mk(made, "six", age_h=2, now=now, urgency=6)
        b = await mk(made, "seven", age_h=1, now=now, urgency=7)
        c = await mk(made, "two-rows", age_h=0.5, now=now, urgency=2)
        async with AsyncSessionLocal() as db:                              # a second, higher triage row for the same event
            db.add(EventTriage(id=f"t2-{c}", event_id=c, source="news", headline="x", urgency=9))
            await db.commit()
        assert await pick(now, 1000, made) == [b, c, a] or await pick(now, 1000, made) == [c, b, a]   # both urgent, FIFO between them is by eligibility time
        assert (await pick(now, 1000, made))[-1] == a
    finally:
        await purge(made)


@pytest.mark.asyncio
async def test_normal_events_are_not_starved_by_a_stream_of_new_normals(prio):
    made: list[str] = []
    now = _now(False)
    try:
        waiting = await mk(made, "waiting-7h", age_h=7, now=now, urgency=2)
        fresh_many = [await mk(made, f"new-{i}", age_h=0.1 * (i + 1), now=now, urgency=2) for i in range(6)]
        first = (await pick(now, 3, made))
        assert first[0] == waiting and set(first[1:]) <= set(fresh_many)
    finally:
        await purge(made)


# ── the guaranteed overdue share is preserved ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_guaranteed_backlog_slot_survives_an_urgent_flood(prio):
    made: list[str] = []
    now = _now(True)
    try:
        overdue = await mk(made, "overdue", age_h=40, now=now, urgency=2)
        flood = [await mk(made, f"urgent-{i}", age_h=1 + i * 0.1, now=now, urgency=9) for i in range(5)]
        got = await pick(now, 3, made)
        assert overdue in got and len(got) == 3 and all(g in flood or g == overdue for g in got)
    finally:
        await purge(made)


@pytest.mark.asyncio
async def test_backlog_guarantee_alternates_between_urgent_first_and_oldest_first(prio):
    made: list[str] = []
    try:
        t_urgent = _now(True, urgent_first=True)
        t_oldest = _now(True, urgent_first=False)
        oldest_normal = await mk(made, "oldest-normal", age_h=90, now=t_urgent, urgency=2)
        newer_urgent = await mk(made, "newer-urgent", age_h=30, now=t_urgent, urgency=9)
        assert (await pick(t_urgent, 1, made)) == [newer_urgent]                # urgent-first turn
        # on the oldest-first turn the same data yields the oldest overdue row; rebuild ages relative to that time
        await purge(made); made.clear()
        oldest_normal = await mk(made, "oldest-normal", age_h=90, now=t_oldest, urgency=2)
        newer_urgent = await mk(made, "newer-urgent", age_h=30, now=t_oldest, urgency=9)
        assert (await pick(t_oldest, 1, made)) == [oldest_normal]               # oldest-first turn: urgent overdue events cannot starve ordinary ones
    finally:
        await purge(made)


@pytest.mark.asyncio
async def test_work_conserving_when_one_lane_is_empty(prio):
    made: list[str] = []
    now = _now(False)
    try:
        backlog_only = [await mk(made, f"b{i}", age_h=30 + i, now=now, urgency=2) for i in range(3)]
        assert len(await pick(now, 3, made)) == 3                                # no fresh events at all: backlog drains at full capacity
        assert set(await pick(now, 3, made)) == set(backlog_only)
    finally:
        await purge(made)


# ── retry eligibility and permanence are untouched ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retry_eligibility_is_not_changed_by_urgency(prio):
    made: list[str] = []
    now = _now(False)
    try:
        waiting = await mk(made, "urgent-waiting-backoff", age_h=2, now=now, urgency=10, status="failed", retry_count=2, next_retry_at=now + timedelta(minutes=30))
        due = await mk(made, "urgent-due", age_h=2, now=now, urgency=10, status="failed", retry_count=2, next_retry_at=now - timedelta(minutes=1))
        spent = await mk(made, "urgent-spent", age_h=2, now=now, urgency=10, status="failed", retry_count=ep._MAX_ENRICHMENT_RETRIES, next_retry_at=None)
        perm = await mk(made, "urgent-permanent", age_h=2, now=now, urgency=10, status="failed_permanent", retry_count=5)
        got = await pick(now, 1000, made)
        assert got == [due] and waiting not in got and spent not in got and perm not in got
    finally:
        await purge(made)


@pytest.mark.asyncio
async def test_selection_is_stateless_and_repeatable_after_a_restart(prio):
    made: list[str] = []
    now = _now(True, urgent_first=True)
    try:
        for i in range(4):
            await mk(made, f"u{i}", age_h=1 + i, now=now, urgency=8)
        for i in range(3):
            await mk(made, f"o{i}", age_h=30 + i, now=now, urgency=3)
        first = await pick(now, 3, made)
        again = await pick(now, 3, made)                                          # a fresh process asking the same question at the same wall-clock bucket
        assert first == again and len(set(first)) == 3
    finally:
        await purge(made)


# ── diagnostics: per-stage attribution and capacity deferral vs genuine failure ───────────────────────────────────────────

class _FailAt(_FakeAIProvider):
    def __init__(self, stage, exc):
        super().__init__()
        self.stage, self.exc = stage, exc

    async def summarize_event(self, title, text, source):
        if self.stage == "summarize":
            raise self.exc
        return await super().summarize_event(title, text, source)

    async def generate_timeline(self, title, text, event_type):
        if self.stage == "timeline":
            raise self.exc
        return await super().generate_timeline(title, text, event_type)


async def _seed_event() -> str:
    eid = f"test-prio-diag-{uuid.uuid4()}"
    async with AsyncSessionLocal() as db:
        db.add(Event(id=eid, title=f"{_tag()} diag", source="Test", enrichment_status="pending", retry_count=0, created_at=datetime.now(timezone.utc)))
        await db.commit()
    return eid


@pytest.fixture(autouse=False)
def usage_clean():
    ai._EXHAUSTED.clear(); U._queue.clear(); U._search_queue.clear(); U._skips.clear()
    yield
    ai._EXHAUSTED.clear()


@pytest.mark.asyncio
async def test_failure_is_attributed_to_the_stage_that_failed(monkeypatch, usage_clean):
    import httpx
    events = []
    monkeypatch.setattr(ep.logger, "info", lambda event, *a, **kw: events.append((event, kw)))
    eid = await _seed_event()
    try:
        ok = await _run_with_fake_provider(eid, _FailAt("timeline", httpx.ConnectError("x")), monkeypatch)
        assert ok is False
        att = [kw for ev, kw in events if ev == "event_enrichment.attempt"]
        assert len(att) == 1
        assert att[0]["failed_stage"] == "timeline"
        assert att[0]["stages_done"] == ["classify", "summarize", "extract_companies_sectors", "impact_analysis"]
        assert att[0]["outcome"] == "failed" and att[0]["retry_before"] == 0 and att[0]["retry_after"] == 1
        assert ep.last_outcome.get() == "failed"
        assert (await _fetch(eid)).retry_count == 1                                # retry accounting unchanged
    finally:
        await _cleanup_events([eid])


@pytest.mark.asyncio
async def test_cooldown_only_is_reported_as_deferral_and_keeps_the_retry_budget(monkeypatch, usage_clean):
    import httpx
    events = []
    monkeypatch.setattr(ep.logger, "info", lambda event, *a, **kw: events.append((event, kw)))

    class _Cool(_FailAt):
        async def summarize_event(self, title, text, source):
            U.note_skip("groq", "m")                                                  # the chain skipped a cooling-down model and tried nothing
            raise httpx.ConnectError("all cooling down")

    eid = await _seed_event()
    try:
        assert await _run_with_fake_provider(eid, _Cool("summarize", None), monkeypatch) is False
        att = [kw for ev, kw in events if ev == "event_enrichment.attempt"][0]
        assert att["outcome"] == "deferred_capacity" and att["reason"] == "provider_cooldown" and att["failed_stage"] == "summarize"
        assert att["retry_after"] == 0 and ep.last_outcome.get() == "deferred_capacity"
        assert (await _fetch(eid)).retry_count == 0
    finally:
        await _cleanup_events([eid])


@pytest.mark.asyncio
async def test_success_is_logged_with_every_completed_stage_and_diagnostics_can_be_switched_off(monkeypatch, usage_clean):
    events = []
    monkeypatch.setattr(ep.logger, "info", lambda event, *a, **kw: events.append((event, kw)))
    eid = await _seed_event()
    try:
        assert await _run_with_fake_provider(eid, _FakeAIProvider(), monkeypatch) is True
        att = [kw for ev, kw in events if ev == "event_enrichment.attempt"][0]
        assert att["outcome"] == "done" and att["failed_stage"] is None
        assert att["stages_done"] == ["classify", "summarize", "extract_companies_sectors", "impact_analysis", "timeline", "similar_events", "graph"]
        assert ep.last_outcome.get() == "done"
    finally:
        await _cleanup_events([eid])
    events.clear()
    monkeypatch.setattr(settings, "event_enrichment_stage_diagnostics_enabled", False, raising=False)
    eid = await _seed_event()
    try:
        assert await _run_with_fake_provider(eid, _FakeAIProvider(), monkeypatch) is True
        assert not [1 for ev, _ in events if ev == "event_enrichment.attempt"] and ep.last_outcome.get() == "done"
    finally:
        await _cleanup_events([eid])
