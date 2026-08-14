"""
Regression suite — app.services.coverage_engine.classify_article /
article_classification_counts / coverage_vs_publishing_summary (Phase 12,
2026-08 audit).

Verifies the operational-reporting distinction the task required: "total
articles published" must never be silently read as "material events
covered." classify_article's category boundaries are checked against the
real publisher.py call-site semantics confirmed by reading the code
directly (comparison_intelligence, historical_intelligence,
trigger_type="high_urgency_triage" only from the real triage-selection
path, morning_intelligence/market_wrap excluded from EVENT_TRIGGERED
despite sharing that trigger_type, evergreen educational topics with a
synthetic trigger_event_id).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.db.models.intelligence_article import IntelligenceArticle
from app.services import coverage_engine


def test_classify_article_comparison_wins_even_if_evergreen():
    assert coverage_engine.classify_article("comparison_intelligence", None, True) == "COMPARISON"


def test_classify_article_historical_wins_even_if_evergreen_and_no_trigger():
    assert coverage_engine.classify_article("historical_intelligence", None, True) == "HISTORICAL"


def test_classify_article_event_triggered_for_real_triage_selection():
    assert coverage_engine.classify_article("company_intelligence", "high_urgency_triage", False) == "EVENT_TRIGGERED"


def test_classify_article_scheduled_digest_excluded_despite_trigger_type():
    # morning_intelligence/market_wrap carry trigger_type="high_urgency_triage"
    # too (publisher.py tags them with whatever triage event was mid-cycle),
    # but they are scheduled daily summaries, not "this event got covered."
    assert coverage_engine.classify_article("morning_intelligence", "high_urgency_triage", False) != "EVENT_TRIGGERED"
    assert coverage_engine.classify_article("market_wrap", "high_urgency_triage", False) != "EVENT_TRIGGERED"


def test_classify_article_evergreen_without_real_trigger():
    # educational_intelligence evergreen topics use a synthetic
    # trigger_event_id ("evergreen-{slug}") and never set trigger_type.
    assert coverage_engine.classify_article("educational_intelligence", None, True) == "EVERGREEN"


def test_classify_article_other_fallback():
    assert coverage_engine.classify_article("live_signal", None, False) == "OTHER"


async def _cleanup(*ids: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id.in_(ids)))
        await db.commit()


@pytest.mark.asyncio
async def test_article_classification_counts_against_real_db():
    now = datetime.now(timezone.utc)
    event_triggered_id = f"pytest-article-event-{uuid.uuid4().hex[:8]}"
    evergreen_id = f"pytest-article-evergreen-{uuid.uuid4().hex[:8]}"
    draft_id = f"pytest-article-draft-{uuid.uuid4().hex[:8]}"  # must be excluded (status != published)
    ids = [event_triggered_id, evergreen_id, draft_id]
    await _cleanup(*ids)
    try:
        async with AsyncSessionLocal() as db:
            db.add(IntelligenceArticle(
                id=event_triggered_id, headline="Test event-triggered article",
                article_type="company_intelligence", status="published",
                lifecycle_status="published", trigger_type="high_urgency_triage",
                trigger_event_id="pytest-source-event-1", is_evergreen=False,
                created_at=now,
            ))
            db.add(IntelligenceArticle(
                id=evergreen_id, headline="Test evergreen educational article",
                article_type="educational_intelligence", status="published",
                lifecycle_status="published", trigger_event_id="evergreen-test-topic",
                is_evergreen=True, created_at=now,
            ))
            db.add(IntelligenceArticle(
                id=draft_id, headline="Test draft article (should be excluded)",
                article_type="company_intelligence", status="draft",
                lifecycle_status="generated", is_evergreen=False, created_at=now,
            ))
            await db.commit()

            result = await coverage_engine.article_classification_counts(db, hours=1)
            assert result["total_articles_published"] >= 2
            assert result["by_category"]["EVENT_TRIGGERED"] >= 1
            assert result["by_category"]["EVERGREEN"] >= 1
            assert "possibly_truncated" in result

            summary = await coverage_engine.coverage_vs_publishing_summary(db, hours=1)
            assert summary["total_articles_published"] == result["total_articles_published"]
            assert summary["event_triggered_articles_published"] == result["by_category"]["EVENT_TRIGGERED"]
            assert "material_events_covered" in summary
    finally:
        await _cleanup(*ids)
