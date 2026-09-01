"""
Regression suite — quality_validator.py, offline (no DB/network/LLM).

P0-CD2 Generation Containment (2026-09-01): confirms
no_recommendation_language is wired in as a REQUIRED check (publish-blocking,
same severity as has_headline/confidence_sufficient/etc), not a soft one —
the CD2 authorization was explicit that prompt changes alone are
insufficient and this backstop must actually block publication.
"""
from __future__ import annotations

from app.services.aipe.quality_validator import validate


def _clean_article(**overrides):
    article = {
        "headline": "What RBI's Rate Hold Means For SBI, HDFC Bank Investors",
        "executive_summary": "RBI held rates steady. Investors should note the implications for lending margins.",
        "key_takeaway": "The evidence points to stable net interest margins for private banks this quarter.",
        "confidence_score": 0.8,
        "what_happened": "A" * 120,
        "companies_affected": [{"name": "SBI", "symbol": "SBIN"}],
        "opportunities": [{"title": "SBI's funding cost eases if the hold persists", "description": "Evidence-based read."}],
        "faqs": [{"question": "q", "answer": "a"}],
        "seo_title": "What RBI's Rate Hold Means For SBI, HDFC Bank Investors Today",
        "meta_description": "A" * 140,
    }
    article.update(overrides)
    return article


def test_clean_article_passes_all_required_checks():
    passed, results, _ = validate(_clean_article(), seo_score=70)
    assert passed is True
    assert results["no_recommendation_language"] is True


def test_recommendation_language_in_key_takeaway_blocks_publication():
    article = _clean_article(key_takeaway="Buy HDFC Bank now while the setup remains favorable.")
    passed, results, _ = validate(article, seo_score=70)
    assert passed is False
    assert results["no_recommendation_language"] is False
    assert "recommendation_language_violations" in results


def test_recommendation_language_in_opportunities_blocks_publication():
    article = _clean_article(opportunities=[{"title": "Accumulate SBI on every dip", "description": "x"}])
    passed, results, _ = validate(article, seo_score=70)
    assert passed is False
    assert results["no_recommendation_language"] is False


def test_recommendation_language_violation_does_not_affect_unrelated_fields():
    # A violation in one field must not somehow suppress the other required
    # checks from being evaluated correctly.
    article = _clean_article(key_takeaway="Buy HDFC Bank now.")
    passed, results, _ = validate(article, seo_score=70)
    assert results["has_headline"] is True
    assert results["has_key_takeaway"] is True  # non-empty string -- still "has" one, just an unsafe one
    assert results["confidence_sufficient"] is True


def test_buyback_fact_does_not_block_publication():
    article = _clean_article(opportunities=[{"title": "Company announced a share buyback", "description": "The board approved a buyback program."}])
    passed, results, _ = validate(article, seo_score=70)
    assert passed is True
    assert results["no_recommendation_language"] is True
