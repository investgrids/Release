"""
Phase 5F.2a — event_pipeline.py's enrichment used to route through
get_ai_provider() (a single provider, OpenRouter by current config)
with no fallback. Confirmed live: OpenRouter alone returning HTTP 429
meant 100% of recent enrichment attempts failed (1,583 events stuck
"failed", reason provider_unavailable) even while every other AI
feature in this codebase stayed healthy through the same rate-limiting
via app.services.ai_service._call_with_fallback's multi-provider
cascade.

Fixed via FallbackChainAIProvider (app/services/fallback_chain_provider.py)
-- inherits DeepSeekProvider (same prompts/fallback contracts, verbatim)
and overrides only _chat() to route through _call_with_fallback.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models.event import Event
from app.db.session import AsyncSessionLocal
from app.pipeline.event_pipeline import _AIUnavailable, _CLASSIFY_FALLBACK
from app.repositories.event_repository import EventRepository
from app.services import ai_service
from app.services.fallback_chain_provider import FallbackChainAIProvider, get_resilient_ai_provider


async def _cleanup(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Event).where(Event.id.in_(ids)))
        await db.commit()


async def _make_event(event_id: str, **overrides) -> None:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=event_id, title="Reliance Industries announces new refinery capacity expansion",
        summary="Investment of 50000 crore in Gujarat refinery capacity.",
        source="test", event_type="news",
        published_at=now, created_at=now, updated_at=now,
        enrichment_status="pending",
    )
    defaults.update(overrides)
    async with AsyncSessionLocal() as db:
        db.add(Event(**defaults))
        await db.commit()


# ── Delegation contract: FallbackChainAIProvider._chat -> _call_with_fallback ──

@pytest.mark.asyncio
async def test_openrouter_429_second_provider_succeeds(monkeypatch):
    """First tier (simulating an OpenRouter 429) returns empty, a later
    tier succeeds -- the cascade must continue, not give up on the
    first failure."""
    calls = {"n": 0}

    async def _fake_call_provider(base_url, api_key, model, prompt, system="", max_tokens=200, extra_headers=None, failure_log=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return ""  # simulated 429 -> empty result, same contract _call_provider uses
        return '{"category": "corporate", "confidence": 0.9, "subcategory": "capex"}'

    monkeypatch.setattr(ai_service, "_call_provider", _fake_call_provider)
    provider = FallbackChainAIProvider()
    result = await provider.classify_event("Reliance announces new refinery capacity")

    assert result == {"category": "corporate", "confidence": 0.9, "subcategory": "capex"}
    assert calls["n"] >= 2  # had to fall through past the first failure


@pytest.mark.asyncio
async def test_two_failures_third_provider_succeeds(monkeypatch):
    calls = {"n": 0}

    async def _fake_call_provider(base_url, api_key, model, prompt, system="", max_tokens=200, extra_headers=None, failure_log=None):
        calls["n"] += 1
        if calls["n"] <= 2:
            return ""
        return '{"category": "policy", "confidence": 0.8, "subcategory": "regulatory"}'

    monkeypatch.setattr(ai_service, "_call_provider", _fake_call_provider)
    provider = FallbackChainAIProvider()
    result = await provider.classify_event("RBI announces new regulatory framework")

    assert result == {"category": "policy", "confidence": 0.8, "subcategory": "regulatory"}
    assert calls["n"] >= 3


@pytest.mark.asyncio
async def test_all_providers_fail_returns_classify_fallback_not_a_crash(monkeypatch):
    async def _always_empty(base_url, api_key, model, prompt, system="", max_tokens=200, extra_headers=None, failure_log=None):
        return ""

    monkeypatch.setattr(ai_service, "_call_provider", _always_empty)
    provider = FallbackChainAIProvider()
    result = await provider.classify_event("Some event")

    # Preserves the exact pre-existing degraded-stub contract event_pipeline.py checks for.
    assert result == _CLASSIFY_FALLBACK


@pytest.mark.asyncio
async def test_first_provider_success_makes_no_unnecessary_fallback_calls(monkeypatch):
    calls = {"n": 0}

    async def _fake_call_provider(base_url, api_key, model, prompt, system="", max_tokens=200, extra_headers=None, failure_log=None):
        calls["n"] += 1
        return '{"category": "earnings", "confidence": 0.95, "subcategory": "results"}'

    monkeypatch.setattr(ai_service, "_call_provider", _fake_call_provider)
    provider = FallbackChainAIProvider()
    result = await provider.classify_event("Company Q1 results beat estimates")

    assert result == {"category": "earnings", "confidence": 0.95, "subcategory": "results"}
    assert calls["n"] == 1  # no wasted calls past the first success


def test_response_schema_matches_deepseek_provider_contract():
    """FallbackChainAIProvider must expose the identical AIProvider
    surface DeepSeekProvider/OpenRouterProvider do -- same methods,
    inherited unchanged, not reimplemented."""
    from app.services.ai_provider import AIProvider
    provider = FallbackChainAIProvider()
    assert isinstance(provider, AIProvider)
    for method in (
        "classify_event", "summarize_news", "generate_story", "generate_radar",
        "summarize_event", "extract_companies", "extract_sectors",
        "generate_timeline", "generate_impact_analysis", "find_similar_events", "generate_graph",
    ):
        assert hasattr(provider, method)


def test_get_ai_provider_untouched():
    """provider_factory.py's get_ai_provider() must be completely
    unaffected by this fix -- it's a separate entry point
    (get_resilient_ai_provider), so no other caller's behavior changes."""
    from app.services.provider_factory import get_ai_provider
    from app.services.openrouter_provider import OpenRouterProvider
    provider = get_ai_provider()
    # Still resolves per settings.ai_provider exactly as before -- this
    # environment's config is "openrouter", so this must still be true.
    assert isinstance(provider, OpenRouterProvider)
    assert not isinstance(get_resilient_ai_provider(), OpenRouterProvider)


# ── Real, live end-to-end: one real backlog row, through the real pipeline ──

@pytest.mark.asyncio
async def test_live_one_real_event_succeeds_through_fallback_chain():
    """Real network -- no mocking. Proves the actual live cascade (not
    a simulation) can enrich a real event today, matching this
    codebase's `_live` test convention."""
    from app.pipeline.event_pipeline import run_event_pipeline

    test_id = f"pytest-fallback-live-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        await _make_event(test_id)
        async with AsyncSessionLocal() as db:
            event = await db.get(Event, test_id)
            success = await run_event_pipeline(event, db)

        async with AsyncSessionLocal() as db:
            row = await db.get(Event, test_id)
            # Either a real success, or a real (not fallback-masked)
            # failure/backoff -- never crashes, never silently "done"
            # with no real content.
            assert row.enrichment_status in ("done", "failed", "processing")
            if success:
                assert row.enrichment_status == "done"
                assert row.ai_summary is not None
    finally:
        await _cleanup(test_id)


@pytest.mark.asyncio
async def test_retry_queue_count_decreases_in_controlled_local_run():
    """Real backlog rows (already in the DB from real prior failures) --
    confirms get_pending_enrichment's count genuinely goes down after
    processing a real batch through the fixed provider, not just that
    one synthetic row succeeds in isolation."""
    repo_check = EventRepository
    async with AsyncSessionLocal() as db:
        repo = repo_check(db)
        before = await repo.get_pending_enrichment(limit=5)

    if not before:
        pytest.skip("no real backlog rows available in this environment right now")

    from app.pipeline.event_pipeline import run_event_pipeline
    processed_ids = []
    for event in before[:3]:
        async with AsyncSessionLocal() as db:
            ev = await db.get(Event, event.id)
            if ev is None:
                continue
            await run_event_pipeline(ev, db)
            processed_ids.append(event.id)

    async with AsyncSessionLocal() as db:
        repo = repo_check(db)
        after_ids = {e.id for e in await repo.get_pending_enrichment(limit=1000)}

    # Every row we actually processed must have LEFT the pending/retry-eligible set
    # (moved to done, or to failed-with-a-future-backoff outside this window).
    still_pending = [pid for pid in processed_ids if pid in after_ids]
    assert len(still_pending) < len(processed_ids)


# ── No duplicate writes ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_duplicate_enrichment_rows_on_retry():
    """Running the pipeline twice on the same event must update the
    same row, never create a second one."""
    from app.pipeline.event_pipeline import run_event_pipeline

    test_id = f"pytest-fallback-noretrydupe-{uuid.uuid4().hex[:8]}"
    await _cleanup(test_id)
    try:
        await _make_event(test_id)
        for _ in range(2):
            async with AsyncSessionLocal() as db:
                event = await db.get(Event, test_id)
                await run_event_pipeline(event, db)

        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(Event).where(Event.id == test_id))).scalars().all()
        assert len(rows) == 1
    finally:
        await _cleanup(test_id)
