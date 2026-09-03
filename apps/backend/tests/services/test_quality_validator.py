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


# ── P0-CD3-B: no_historical_forecast_collapse (2026-09-02) ──────────────────
# The exact live specimen CD3-A found (rbi-rate-pauses-banking-investors-
# historic, published 2026-08-08) — confirmed to match NONE of
# scan_recommendation_language's patterns, which is why this is a separate
# required check rather than another blacklisted phrase there.

def test_rbi_style_historical_forecast_collapse_blocks_publication():
    article = _clean_article(
        key_takeaway=(
            "Use policy-driven market dips to add to high-quality banking stocks, "
            "as they typically rebound and outperform over the next 3-6 months."
        )
    )
    passed, results, _ = validate(article, seo_score=70)
    assert passed is False
    assert results["no_historical_forecast_collapse"] is False
    assert "historical_forecast_collapse_violations" in results
    # And confirm the boundary this check exists to cover: the same
    # sentence does NOT trip the older, narrower recommendation-language
    # scan at all -- proving this is a genuinely new backstop, not a
    # duplicate of the existing one.
    assert results["no_recommendation_language"] is True


def test_historical_forecast_collapse_in_opportunities_blocks_publication():
    article = _clean_article(opportunities=[{
        "title": "Banking stocks historically rebound after a rate hold",
        "description": "Investors should add to positions given this pattern tends to repeat.",
    }])
    passed, results, _ = validate(article, seo_score=70)
    assert passed is False
    assert results["no_historical_forecast_collapse"] is False


def test_pure_retrospective_historical_statement_does_not_block_publication():
    """A real historical fact, reported as a fact, with no forward-looking
    instruction stitched onto it -- exactly what OUTPUT DISCIPLINE now
    asks historical articles to do instead of the collapse."""
    article = _clean_article(
        key_takeaway="Banking stocks rose 4.2% on average in the month after the 2020 and 2023 rate holds.",
    )
    passed, results, _ = validate(article, seo_score=70)
    assert passed is True
    assert results["no_historical_forecast_collapse"] is True


def test_forward_claim_without_historical_connector_does_not_block_publication():
    """Deliberately not a blanket future-tense regex: a forward-looking
    statement grounded in a real current event (no historical/habitual
    connector anywhere) must not be flagged."""
    article = _clean_article(
        key_takeaway="The RBI's guidance today points to easing pressure on bank funding costs over the next 2 months.",
    )
    passed, results, _ = validate(article, seo_score=70)
    assert passed is True
    assert results["no_historical_forecast_collapse"] is True
