"""
Article V2 Phase P5 — run_aipe_cycle()'s mode-dispatch wiring. Proves the
one invariant P5-B's own deploy verification depends on: with the
default `v1` mode, production output is byte-identical to before this
phase existed (the V2 shadow orchestrator is never even called), and
with any other mode it IS called, with the same approved batch and a
real, correctly-populated v1_decisions map. Also proves a V2 shadow-path
exception can never take down the V1 cycle.
"""
from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.db.models.intelligence_article import IntelligenceArticle
from app.services.aipe import publisher


def _triage_event(event_id: str, headline: str = "Some headline") -> dict:
    return {"event_id": event_id, "headline": headline, "urgency": 8, "importance": 7, "sectors": [], "themes": [], "tickers": []}


def _run_with_mocks(triage_events, publish_side_effect):
    stack = ExitStack()
    stack.enter_context(patch("app.services.aipe.publisher.get_mie_context", new_callable=AsyncMock, return_value={"session": "closed", "themes": [], "mood": "neutral", "story": "", "story_hash": "x"}))
    stack.enter_context(patch("app.services.aipe.publisher.get_high_urgency_triage", new_callable=AsyncMock, return_value=triage_events))
    stack.enter_context(patch("app.services.aipe.publisher.filter_triage_batch", side_effect=lambda events, max_per_cycle: [(e, "approved") for e in events]))
    stack.enter_context(patch("app.services.aipe.publisher.count_today_articles", new_callable=AsyncMock, return_value=0))
    stack.enter_context(patch("app.services.aipe.publisher.get_today_story_ids", new_callable=AsyncMock, return_value=set()))
    stack.enter_context(patch("app.services.aipe.publisher.select_article_type", side_effect=lambda ev, mie: ("company_intelligence", f"story-{ev['event_id']}", "normal")))
    stack.enter_context(patch("app.services.aipe.publisher.find_duplicate", new_callable=AsyncMock, return_value=None))
    publish_mock = stack.enter_context(patch("app.services.aipe.publisher._publish_new_article", new_callable=AsyncMock, side_effect=publish_side_effect))
    stack.enter_context(patch("app.services.aipe.publisher.plan_extra_angles", return_value=[]))
    stack.enter_context(patch("app.services.aipe.publisher.run_continuous_update_cycle", new_callable=AsyncMock, return_value=0))
    stack.enter_context(patch("app.services.aipe.publisher._scheduled_article_due", new_callable=AsyncMock, return_value=False))
    stack.enter_context(patch("app.services.aipe.publisher.get_latest_market_snapshot", new_callable=AsyncMock, return_value={}))
    return stack, publish_mock


@pytest.fixture(autouse=True)
def _restore_setting():
    original = settings.article_pipeline_mode
    yield
    settings.article_pipeline_mode = original
    publisher._STATS["running"] = False


def _fake_article(event_id: str) -> IntelligenceArticle:
    return IntelligenceArticle(
        id=f"art-{event_id}", slug=f"art-{event_id}", article_type="company_intelligence",
        story_id=f"story-{event_id}", story_version=1, lifecycle_status="published",
        status="published", update_count=0, update_history=[],
        angle="primary", angle_entity=None, headline="Test headline",
        executive_summary="", key_takeaway="", why_it_matters="", what_happened="",
        companies_affected=[], sectors_affected=[],
    )


@pytest.mark.asyncio
async def test_v1_mode_never_calls_the_v2_shadow_orchestrator():
    settings.article_pipeline_mode = "v1"
    event_id = "evt-dispatch-v1"
    stack, _ = _run_with_mocks([_triage_event(event_id)], AsyncMock(return_value=_fake_article(event_id)))
    with stack, patch("app.services.article_v2.shadow_orchestrator.run_shadow_batch", new_callable=AsyncMock) as shadow_mock:
        await publisher.run_aipe_cycle()
    shadow_mock.assert_not_called()


@pytest.mark.asyncio
async def test_shadow_v2_mode_calls_the_orchestrator_with_the_same_approved_batch():
    settings.article_pipeline_mode = "shadow_v2"
    event_id = "evt-dispatch-shadow"
    triage_events = [_triage_event(event_id)]
    stack, _ = _run_with_mocks(triage_events, AsyncMock(return_value=_fake_article(event_id)))
    with stack, patch("app.services.article_v2.shadow_orchestrator.run_shadow_batch", new_callable=AsyncMock) as shadow_mock:
        await publisher.run_aipe_cycle()

    shadow_mock.assert_called_once()
    _, kwargs = shadow_mock.call_args
    assert [t for t, _ in kwargs["triage_events"]] == triage_events
    assert kwargs["v1_decisions"][event_id] == "created"
    assert kwargs["mode"].value == "shadow_v2"


@pytest.mark.asyncio
async def test_unknown_mode_falls_back_to_v1_and_never_calls_the_orchestrator():
    settings.article_pipeline_mode = "not-a-real-mode"
    event_id = "evt-dispatch-unknown"
    stack, _ = _run_with_mocks([_triage_event(event_id)], AsyncMock(return_value=_fake_article(event_id)))
    with stack, patch("app.services.article_v2.shadow_orchestrator.run_shadow_batch", new_callable=AsyncMock) as shadow_mock:
        await publisher.run_aipe_cycle()
    shadow_mock.assert_not_called()


@pytest.mark.asyncio
async def test_a_v2_shadow_exception_never_crashes_the_v1_cycle():
    settings.article_pipeline_mode = "shadow_v2"
    event_id = "evt-dispatch-crash"
    stack, publish_mock = _run_with_mocks([_triage_event(event_id)], AsyncMock(return_value=_fake_article(event_id)))
    with stack, patch(
        "app.services.article_v2.shadow_orchestrator.run_shadow_batch",
        new_callable=AsyncMock, side_effect=RuntimeError("boom"),
    ):
        await publisher.run_aipe_cycle()  # must not raise
    publish_mock.assert_called_once()  # V1's own work still completed


@pytest.mark.asyncio
async def test_v1_decisions_records_a_daily_cap_skip():
    settings.article_pipeline_mode = "shadow_v2"
    event_id = "evt-dispatch-cap"
    stack, _ = _run_with_mocks([_triage_event(event_id)], AsyncMock(return_value=None))
    with stack as _s:
        # Override count_today_articles to already be at/over the cap for a non-critical event.
        with patch("app.services.aipe.publisher.count_today_articles", new_callable=AsyncMock, return_value=publisher._MAX_PER_DAY):
            with patch("app.services.article_v2.shadow_orchestrator.run_shadow_batch", new_callable=AsyncMock) as shadow_mock:
                await publisher.run_aipe_cycle()

    shadow_mock.assert_called_once()
    _, kwargs = shadow_mock.call_args
    assert kwargs["v1_decisions"][event_id] == "skipped_daily_cap"
