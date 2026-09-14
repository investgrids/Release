"""
Article V2-F1 correction (owner review, 2026-09-14) — a focused
integration regression for `_publish_new_article()`, the real V1
production article path that was refactored to call the new shared
`app/services/aipe/seo_metadata.py` builder instead of its own inline
JSON-LD block.

Every existing test touching this function mocks `_publish_new_article`
itself (see test_publisher_cycle_fanout.py / test_publisher_cycle_v2_
dispatch.py), so a wiring error in the new shared helper could pass the
whole suite undetected. This test does NOT mock `_publish_new_article`
-- only its external generation inputs (the LLM call, historical
context fetch, market snapshot fetch, validation, and the fire-and-
forget side effects that aren't what this test is about) -- so the real
canonical_url/json_ld/breadcrumb/schema-type/timestamp-consistency
behavior actually executes and is asserted against.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete

from app.db.models.intelligence_article import IntelligenceArticle
from app.db.session import AsyncSessionLocal
from app.services.aipe import publisher


def _triage_event(event_id: str, headline: str) -> dict:
    return {
        "event_id": event_id, "headline": headline, "title": headline,
        "urgency": 8, "importance": 7, "sectors": ["Banking"], "themes": ["credit growth"],
    }


def _fake_article_data(headline: str, slug: str, faqs: list[dict] | None = None) -> dict:
    return {
        "headline": headline, "slug": slug, "seo_title": headline[:65],
        "meta_description": "A real, grounded test description of this development.",
        "executive_summary": "A real fact happened today.", "key_takeaway": "A real fact happened today.",
        "why_it_matters": "This matters because of real, grounded context.",
        "what_happened": "A real fact happened today.",
        "companies_affected": [], "sectors_affected": [], "opportunities": [], "risks": [],
        "what_to_watch_next": [], "faqs": faqs or [], "confidence_score": 0.8,
        "_price_moves_grounding": {},
    }


async def _cleanup(article_ids: list[str]):
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IntelligenceArticle).where(IntelligenceArticle.id.in_(article_ids)))
        await db.commit()


@pytest.fixture(autouse=True)
def _mock_external_dependencies(monkeypatch):
    """Everything genuinely external to what this test verifies:
    the LLM call, DB-independent historical/market context fetches,
    validation outcomes, and the fire-and-forget post-publish side
    effects (sibling-linking, company-signal extraction, prediction
    storage, media job creation) -- none of these are what a JSON-LD/
    canonical_url wiring regression would touch."""
    monkeypatch.setattr(publisher, "fetch_historical_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(publisher, "get_latest_market_snapshot", AsyncMock(return_value={}))
    monkeypatch.setattr(publisher, "validate", lambda article, seo_score: (True, {"has_headline": True}, 90.0))
    monkeypatch.setattr(publisher, "validate_fact_grounding", lambda *a, **k: (True, []))
    monkeypatch.setattr(publisher, "_link_event_siblings", AsyncMock(return_value=None))
    monkeypatch.setattr("app.services.aipe.company_score_engine.extract_company_signals", AsyncMock(return_value=None))
    monkeypatch.setattr(publisher, "_store_article_predictions", AsyncMock(return_value=None))
    monkeypatch.setattr("app.services.media.image_worker.create_media_job", AsyncMock(return_value=None))


@pytest.mark.asyncio
async def test_publish_new_article_produces_correct_seo_metadata_end_to_end(monkeypatch):
    tag = uuid.uuid4().hex[:8]
    event_id = f"evt-seo-{tag}"
    headline = f"Test Co {tag} Wins Rs 500 Crore Order"
    slug = f"test-co-{tag}-wins-order"
    article_data = _fake_article_data(headline, slug)
    monkeypatch.setattr(publisher, "generate_intelligence_article", AsyncMock(return_value=dict(article_data)))

    triage_event = _triage_event(event_id, headline)
    before = datetime.now(timezone.utc)
    article_id = None
    try:
        async with AsyncSessionLocal() as db:
            article = await publisher._publish_new_article(
                db, triage_event, {"themes": [], "session": "live"}, "company_intelligence", f"story-{tag}",
            )
        assert article is not None
        article_id = article.id
        after = datetime.now(timezone.utc)

        # canonical_url — the final, non-redirecting path.
        assert article.canonical_url is not None
        assert article.canonical_url.endswith(f"/newsroom/article/{article.slug}")
        assert "/insights/" not in article.canonical_url

        # json_ld — schema type, breadcrumb, and timestamp consistency
        # with the real persisted published_at.
        jld = article.json_ld
        assert jld is not None
        assert jld["@type"] == "NewsArticle"  # company_intelligence is not in the evergreen exception list
        assert jld["headline"] == article.headline
        assert jld["mainEntityOfPage"] == article.canonical_url
        breadcrumb_items = jld["breadcrumb"]["itemListElement"]
        assert [b["name"] for b in breadcrumb_items] == ["MarketRipple", "Newsroom", article.headline]
        assert breadcrumb_items[-1]["item"] == article.canonical_url
        assert "mainEntity" not in jld  # no faqs in this specimen

        # SQLite round-trips DateTime columns as naive (a known, already-
        # documented app-wide footgun -- see app/api/insights.py's own
        # "tz-reattached UTC" comment for the established fix pattern);
        # published_at is genuinely UTC, just missing the marker after
        # db.refresh(), so reattach it before comparing.
        assert article.published_at is not None
        published_at_utc = article.published_at.replace(tzinfo=timezone.utc)
        assert jld["datePublished"] == published_at_utc.isoformat()
        assert jld["dateModified"] == published_at_utc.isoformat()
        assert before <= published_at_utc <= after
    finally:
        if article_id:
            await _cleanup([article_id])


@pytest.mark.asyncio
async def test_publish_new_article_with_faqs_upgrades_json_ld_type(monkeypatch):
    tag = uuid.uuid4().hex[:8]
    event_id = f"evt-seo-faq-{tag}"
    headline = f"Test Co {tag} Reports Results"
    slug = f"test-co-{tag}-reports-results"
    faqs = [{"question": "What happened?", "answer": "A real, grounded event."}]
    article_data = _fake_article_data(headline, slug, faqs=faqs)
    monkeypatch.setattr(publisher, "generate_intelligence_article", AsyncMock(return_value=dict(article_data)))

    triage_event = _triage_event(event_id, headline)
    article_id = None
    try:
        async with AsyncSessionLocal() as db:
            article = await publisher._publish_new_article(
                db, triage_event, {"themes": [], "session": "live"}, "company_intelligence", f"story-{tag}",
            )
        article_id = article.id
        jld = article.json_ld
        assert jld["@type"] == ["NewsArticle", "FAQPage"]
        assert jld["mainEntity"] == [
            {"@type": "Question", "name": "What happened?", "acceptedAnswer": {"@type": "Answer", "text": "A real, grounded event."}},
        ]
    finally:
        if article_id:
            await _cleanup([article_id])


@pytest.mark.asyncio
async def test_publish_new_article_evergreen_type_uses_plain_article_schema(monkeypatch):
    tag = uuid.uuid4().hex[:8]
    event_id = f"evt-seo-evergreen-{tag}"
    headline = f"How {tag} Works: An Explainer"
    slug = f"how-{tag}-works"
    article_data = _fake_article_data(headline, slug)
    monkeypatch.setattr(publisher, "generate_intelligence_article", AsyncMock(return_value=dict(article_data)))

    triage_event = _triage_event(event_id, headline)
    article_id = None
    try:
        async with AsyncSessionLocal() as db:
            article = await publisher._publish_new_article(
                db, triage_event, {"themes": [], "session": "live"}, "educational_intelligence", f"story-{tag}",
            )
        article_id = article.id
        assert article.json_ld["@type"] == "Article"
    finally:
        if article_id:
            await _cleanup([article_id])
