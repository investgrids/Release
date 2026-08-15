"""
Evidence normalization tests — pure functions over in-memory model
instances, no DB access needed (SQLAlchemy model instances can be
constructed without a session). Covers: correct source_type/source_id,
timestamp selection precedence, score_kind classification, and honest
handling of missing/null fields (never fabricated).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.db.models.company_announcements import CompanyAnnouncement
from app.db.models.company_signal import AICompanySignal
from app.db.models.event import Event, GovernmentPolicy
from app.db.models.opportunity import Opportunity
from app.db.models_legacy import NewsArticle
from app.services.weekend_intelligence.evidence import (
    DETERMINISTIC,
    HEURISTIC,
    LLM_SELF_RATED,
    UNKNOWN,
    normalize_announcement,
    normalize_company_signal,
    normalize_event,
    normalize_news,
    normalize_opportunity,
    normalize_policy,
)

_T1 = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
_T2 = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)


def test_normalize_event_prefers_event_date_over_published_at():
    row = Event(id="evt-1", title="Test event", event_date=_T1, published_at=_T2,
                companies=["RELIANCE"], sectors=["Energy"], confidence=72.0)
    item = normalize_event(row)
    assert item.source_type == "event"
    assert item.source_id == "evt-1"
    assert item.observed_at == _T1
    assert item.companies == ["RELIANCE"]
    assert item.score_kind == DETERMINISTIC


def test_normalize_event_falls_back_to_published_at_when_event_date_missing():
    row = Event(id="evt-2", title="Test event 2", event_date=None, published_at=_T2)
    item = normalize_event(row)
    assert item.observed_at == _T2


def test_normalize_event_carries_priority_tier_when_supplied():
    row = Event(id="evt-3", title="Critical event", published_at=_T2)
    item = normalize_event(row, priority_tier="Critical")
    assert item.impact_strength == "Critical"


def test_normalize_event_no_tier_when_not_supplied():
    row = Event(id="evt-4", title="Untriaged event", published_at=_T2)
    item = normalize_event(row)
    assert item.impact_strength is None


def test_normalize_policy_uses_created_at_and_has_no_score():
    row = GovernmentPolicy(id=1, external_id="ext-1", title="RBI notice", created_at=_T1)
    item = normalize_policy(row)
    assert item.source_type == "policy"
    assert item.source_id == "1"
    assert item.observed_at == _T1
    assert item.confidence is None
    assert item.score_kind == UNKNOWN


def test_normalize_announcement_uses_real_announcement_date():
    row = CompanyAnnouncement(
        id="ann-1", symbol="TCS", subject="Board meeting outcome",
        announcement_date=_T1, ingested_at=_T2,
        impact_score=8, sentiment="bullish", is_high_impact=True,
    )
    item = normalize_announcement(row)
    assert item.observed_at == _T1
    assert item.companies == ["TCS"]
    assert item.direction == "bullish"
    assert item.impact_strength == "high"
    assert item.confidence == 0.8
    assert item.score_kind == LLM_SELF_RATED


def test_normalize_announcement_falls_back_to_ingested_at():
    row = CompanyAnnouncement(id="ann-2", subject="Filing", announcement_date=None, ingested_at=_T2)
    item = normalize_announcement(row)
    assert item.observed_at == _T2
    assert item.impact_strength is None  # is_high_impact defaults False


def test_normalize_news_parses_iso_published_at():
    row = NewsArticle(id="news-1", headline="Headline", summary="s", source="ET",
                       published_at="2026-08-14T10:00:00+00:00", companies=[], impact_score=7.5,
                       created_at=_T2)
    item = normalize_news(row)
    assert item.observed_at == _T1
    assert item.score_kind == HEURISTIC


def test_normalize_news_falls_back_to_created_at_on_unparseable_string():
    row = NewsArticle(id="news-2", headline="Headline", summary="s", source="RSS",
                       published_at="3 hours ago", companies=[], impact_score=6.5,
                       created_at=_T2)
    item = normalize_news(row)
    assert item.observed_at == _T2


def test_normalize_company_signal_article_sourced_is_llm_self_rated():
    row = AICompanySignal(source_type="article", source_id="art-1", symbol="INFY",
                           sector="IT", signed_magnitude=45.0, confidence=0.8,
                           signal_at=_T1)
    item = normalize_company_signal(row)
    assert item.score_kind == LLM_SELF_RATED
    assert item.direction == "positive"
    assert item.source_id == "article:art-1"


def test_normalize_company_signal_opportunity_sourced_is_heuristic():
    row = AICompanySignal(source_type="opportunity", source_id="opp-1", symbol="HDFCBANK",
                           signed_magnitude=-10.0, confidence=0.6, signal_at=_T1)
    item = normalize_company_signal(row)
    assert item.score_kind == HEURISTIC
    assert item.direction == "negative"


def test_normalize_opportunity_uses_created_at_not_updated_at():
    row = Opportunity(id=1, slug="test-opp", title="Test Opportunity",
                       opportunity_score=90.0, confidence=0.8, sectors=["Banking"],
                       created_at=_T1, updated_at=_T2)
    item = normalize_opportunity(row)
    assert item.observed_at == _T1
    assert item.score_kind == HEURISTIC
    assert item.sectors == ["Banking"]
