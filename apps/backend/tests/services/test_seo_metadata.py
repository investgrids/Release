"""
Shared SEO metadata builder (Article V2-F1 Data Contract Completion,
2026-09-14) — regression tests.

`build_article_json_ld`/`build_canonical_url` were extracted verbatim
from `aipe/publisher.py::_publish_new_article()`'s own inline JSON-LD
block, the real production V1 article path. These tests pin the EXACT
original shape (breadcrumb, conditional schema_type, FAQPage handling,
canonical path) so the extraction is provably byte-for-byte equivalent,
not merely "close enough" — per the owner's own explicit requirement
that migrating V1's real production path must not change its output.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings
from app.services.aipe.seo_metadata import ArticleJsonLdInput, build_article_json_ld, build_canonical_url

_SITE = (settings.frontend_url or "https://www.marketripple.in").rstrip("/")


def test_build_canonical_url_uses_the_final_non_redirecting_path():
    url = build_canonical_url("some-headline-slug-abcd1234")
    assert url.endswith("/newsroom/article/some-headline-slug-abcd1234")
    assert "/insights/" not in url


def test_news_article_schema_type_for_a_regular_event_triggered_article():
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    result = build_article_json_ld(ArticleJsonLdInput(
        headline="Test Co Wins Order", slug="test-co-wins-order-abcd1234",
        article_type="company_intelligence", meta_description="A test description.",
        published_at=now, updated_at=now,
    ))
    assert result == {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Test Co Wins Order",
        "description": "A test description.",
        "datePublished": now.isoformat(),
        "dateModified": now.isoformat(),
        "author": {"@type": "Organization", "name": "MarketRipple AI Intelligence Engine"},
        "publisher": {"@type": "Organization", "name": "MarketRipple"},
        "mainEntityOfPage": f"{_SITE}/newsroom/article/test-co-wins-order-abcd1234",
        "breadcrumb": {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "MarketRipple", "item": _SITE},
                {"@type": "ListItem", "position": 2, "name": "Newsroom", "item": f"{_SITE}/newsroom"},
                {"@type": "ListItem", "position": 3, "name": "Test Co Wins Order", "item": f"{_SITE}/newsroom/article/test-co-wins-order-abcd1234"},
            ],
        },
    }


def test_evergreen_article_types_use_plain_article_schema_not_news_article():
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    for article_type in ("educational_intelligence", "comparison_intelligence", "historical_intelligence"):
        result = build_article_json_ld(ArticleJsonLdInput(
            headline="H", slug="s", article_type=article_type, meta_description=None,
            published_at=now,
        ))
        assert result["@type"] == "Article", f"{article_type} must use plain Article schema"


def test_faqs_present_upgrades_type_to_list_and_adds_main_entity():
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    faqs = [
        {"question": "Q1?", "answer": "A1."},
        {"question": "Q2?", "answer": "A2."},
    ]
    result = build_article_json_ld(ArticleJsonLdInput(
        headline="H", slug="s", article_type="company_intelligence", meta_description=None,
        published_at=now, faqs=faqs,
    ))
    assert result["@type"] == ["NewsArticle", "FAQPage"]
    assert result["mainEntity"] == [
        {"@type": "Question", "name": "Q1?", "acceptedAnswer": {"@type": "Answer", "text": "A1."}},
        {"@type": "Question", "name": "Q2?", "acceptedAnswer": {"@type": "Answer", "text": "A2."}},
    ]


def test_faqs_truncated_to_first_five():
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    faqs = [{"question": f"Q{i}?", "answer": f"A{i}."} for i in range(8)]
    result = build_article_json_ld(ArticleJsonLdInput(
        headline="H", slug="s", article_type="company_intelligence", meta_description=None,
        published_at=now, faqs=faqs,
    ))
    assert len(result["mainEntity"]) == 5


def test_no_faqs_leaves_type_as_a_plain_string_not_a_list():
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    result = build_article_json_ld(ArticleJsonLdInput(
        headline="H", slug="s", article_type="company_intelligence", meta_description=None,
        published_at=now,
    ))
    assert result["@type"] == "NewsArticle"
    assert "mainEntity" not in result


def test_missing_meta_description_becomes_empty_string_not_none():
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    result = build_article_json_ld(ArticleJsonLdInput(
        headline="H", slug="s", article_type="company_intelligence", meta_description=None,
        published_at=now,
    ))
    assert result["description"] == ""


def test_updated_at_defaults_to_published_at_when_omitted():
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    result = build_article_json_ld(ArticleJsonLdInput(
        headline="H", slug="s", article_type="company_intelligence", meta_description=None,
        published_at=now,
    ))
    assert result["dateModified"] == result["datePublished"] == now.isoformat()
