"""Comparison cycle efficiency (2026-10-13): one scheduled run may only TRY a bounded number of candidate pairs, whatever the outcome, and does no work when every configured
model is cooling down. On 2026-10-12 the run counted only successful publications towards its cap, so with every provider exhausted it walked the whole pool: 474 internal AI Search
runs per run, twice a day, all degraded. Real test database for article rows; the LLM-facing publisher and the capacity check are faked, no network."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

import app.services.ai_service as ai
import app.services.ai_usage as U
import app.services.aipe.comparison_scheduler as cs
from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from sqlalchemy import delete

POOL = [(f"TSTA{i:02d}", f"TSTB{i:02d}") for i in range(40)]


@pytest.fixture(autouse=True)
def clean_usage(monkeypatch):
    U._skips.clear()
    U._queue.clear()
    U._search_queue.clear()
    yield
    U._skips.clear()


class Harness:
    """Drives run_comparison_cycle with a fixed candidate pool, a scripted publisher and a scripted capacity check."""

    def __init__(self, monkeypatch, results, capacity=lambda n: True):
        self.calls: list[tuple[str, str]] = []
        self.pool_loads = 0
        self.capacity_checks = 0
        self.operation_seen: list[str | None] = []
        results = list(results)

        async def fake_publish(db, a, b, name_a, name_b, sector=None):
            self.calls.append((a, b))
            self.operation_seen.append(U._operation.get())
            outcome = results[len(self.calls) - 1] if len(self.calls) - 1 < len(results) else results[-1]
            return {"slug": f"{a}-vs-{b}".lower()} if outcome else None

        async def fake_scores(db):
            self.pool_loads += 1
            return {}

        def fake_available():
            self.capacity_checks += 1
            return capacity(self.capacity_checks)

        monkeypatch.setattr(cs, "_CURATED_PAIRS", list(POOL))
        monkeypatch.setattr(cs, "_sector_derived_pairs", lambda scores: [])
        monkeypatch.setattr(cs, "_sector_engagement_scores", fake_scores)
        monkeypatch.setattr(cs, "publish_comparison_article", fake_publish)
        monkeypatch.setattr(ai, "any_provider_available", fake_available)

    async def run(self):
        await cs.run_comparison_cycle()
        return self


def skipped(op="comparison_cycle", outcome="skipped_no_capacity") -> int:
    return U._skips.get((op, "-", "-", outcome), 0)


# ── complete provider exhaustion ───────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_exhaustion_does_no_work_and_is_recorded(monkeypatch):
    h = await Harness(monkeypatch, [True], capacity=lambda n: False).run()
    assert h.calls == [] and h.pool_loads == 0                    # nothing generated, the candidate pool was not even loaded
    assert skipped() == 1 and h.capacity_checks == 1


@pytest.mark.asyncio
async def test_every_attempt_failing_stops_after_a_few_failures_not_after_the_whole_pool(monkeypatch):
    h = await Harness(monkeypatch, [False]).run()                  # providers look available but every generation fails (the 2026-10-12 shape)
    assert len(h.calls) == cs._MAX_CONSECUTIVE_FAILURES            # 3 tries, not 40 (not 474)
    assert len(h.calls) <= cs._MAX_ATTEMPTS_PER_CYCLE


@pytest.mark.asyncio
async def test_attempt_cap_holds_even_when_successes_keep_resetting_the_failure_streak(monkeypatch):
    # fail, fail, success, repeat: never three failures in a row, and never reaches 5 publications within 8 attempts
    h = await Harness(monkeypatch, [False, False, True] * 10).run()
    assert len(h.calls) == cs._MAX_ATTEMPTS_PER_CYCLE == 8
    published = sum(1 for i in range(len(h.calls)) if (i % 3) == 2)
    assert published == 2


# ── partial recovery ───────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_partial_recovery_continues_after_a_success_and_stops_at_the_publish_limit(monkeypatch):
    h = await Harness(monkeypatch, [False, False, True, True, True, True, True, True]).run()
    assert len(h.calls) == 7                                       # 2 failures, then 5 publications: the publish limit ends the run
    assert len(h.calls) <= cs._MAX_ATTEMPTS_PER_CYCLE


@pytest.mark.asyncio
async def test_two_failures_then_a_success_resets_the_streak(monkeypatch):
    h = await Harness(monkeypatch, [False, False, True, False, False, True, True]).run()
    assert len(h.calls) >= 7                                       # the streak never reached 3, so the run kept going


@pytest.mark.asyncio
async def test_capacity_that_disappears_mid_run_stops_the_run(monkeypatch):
    # checks: 1 = top of run, 2 = before attempt 1, 3 = before attempt 2 (providers now cooling down)
    h = await Harness(monkeypatch, [True], capacity=lambda n: n <= 2).run()
    assert len(h.calls) == 1
    assert skipped() == 1


# ── publication limit preserved ────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publication_limit_is_unchanged(monkeypatch):
    h = await Harness(monkeypatch, [True]).run()
    assert len(h.calls) == cs._MAX_PER_CYCLE == 5


# ── a fresh page is not an attempt ─────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pairs_whose_page_is_still_fresh_do_not_use_attempts(monkeypatch):
    fresh = POOL[:6]
    slugs = [f"{cs._slugify(a)}-vs-{cs._slugify(b)}" for a, b in fresh]
    ids = [f"pytest-cmp-{uuid.uuid4().hex[:8]}" for _ in fresh]
    async with AsyncSessionLocal() as db:
        for i, slug in zip(ids, slugs):
            db.add(IntelligenceArticle(id=i, slug=slug, headline="fresh comparison", article_type="comparison_intelligence", status="published",
                                       lifecycle_status="published", published_at=datetime.now(timezone.utc), last_updated=datetime.now(timezone.utc)))
        await db.commit()
    try:
        h = await Harness(monkeypatch, [False]).run()
        assert len(h.calls) == cs._MAX_CONSECUTIVE_FAILURES
        assert h.calls[0] == POOL[6]                               # the six fresh pairs were passed over without being tried
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id.in_(ids)))
            await db.commit()


# ── internal comparison activity stays apart from public AI Search ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_comparison_attempts_are_tagged_comparison_cycle_not_ai_search(monkeypatch):
    h = Harness(monkeypatch, [True])
    inner: list[str | None] = []

    async def publish_via_search(db, a, b, na, nb, sector=None):
        with U.search_request(10):                                 # what run_ai_search does for every in-process call
            inner.append(U._operation.get())
        return {"slug": "x"}

    monkeypatch.setattr(cs, "publish_comparison_article", publish_via_search)
    await h.run()
    assert inner and set(inner) == {"comparison_cycle"}


def test_public_requests_and_untagged_internal_callers_are_unchanged():
    with U.search_request(5):                                      # internal caller with no outer tag: as before
        assert U._operation.get() == "ai_search"
    with U.operation("comparison_cycle"):
        token = U._origin.set("api")                               # a user-facing request is always ai_search, even inside another tag
        try:
            with U.search_request(5):
                assert U._operation.get() == "ai_search"
        finally:
            U._origin.reset(token)
        assert U._operation.get() == "comparison_cycle"
    assert U._operation.get() is None
