"""
app/services/media/prompt_builder.py — real bug (user-reported): "same
image is coming for most of the articles." Confirmed live: 267 generated
hero images across the whole platform used only 10 distinct prompt
strings (one fixed sentence per category, no per-article detail, no
seed), and the top 2 alone accounted for 68% of every image ever
generated. Fixed with sector enrichment + a deterministic per-article
scene/seed derived from headline+article_id.
"""
from __future__ import annotations

from app.services.media.prompt_builder import build_prompt, STYLE_GUIDE_VERSION, STYLE_NAME


def test_same_article_reproduces_the_same_prompt_and_seed():
    """Regenerating the SAME article should look the same — determinism,
    not randomness, is the point."""
    p1, v1, s1, seed1 = build_prompt("RBI holds repo rate steady", "market_wrap", ["Banking"], "article-123")
    p2, v2, s2, seed2 = build_prompt("RBI holds repo rate steady", "market_wrap", ["Banking"], "article-123")
    assert p1 == p2
    assert seed1 == seed2
    assert v1 == STYLE_GUIDE_VERSION
    assert s1 == STYLE_NAME


def test_different_articles_in_the_same_category_get_different_prompts():
    """The exact reported bug — two different company-earnings articles
    (same 'company' subject bucket) must not collide on one identical
    sentence/seed anymore."""
    p1, _, _, seed1 = build_prompt("Zydus reports Q1 earnings", "company_intelligence", ["Pharma"], "article-a")
    p2, _, _, seed2 = build_prompt("TCS reports Q1 earnings", "company_intelligence", ["IT Services"], "article-b")
    assert p1 != p2
    assert seed1 != seed2


def test_two_articles_with_identical_headline_but_different_ids_still_diverge():
    """Even in the pathological case of an identical headline (e.g. two
    real articles that happen to share exact wording), the article_id
    component of the variation key must still separate them."""
    p1, _, _, seed1 = build_prompt("Quarterly results announced", "company_intelligence", [], "article-x")
    p2, _, _, seed2 = build_prompt("Quarterly results announced", "company_intelligence", [], "article-y")
    assert p1 != p2 or seed1 != seed2


def test_sector_is_folded_into_the_subject_when_present():
    prompt, *_ = build_prompt("Some company posts strong earnings", "company_intelligence", ["Automobiles"], "id-1")
    assert "Automobiles" in prompt


def test_no_sector_omits_the_representing_clause():
    prompt, *_ = build_prompt("Some company posts strong earnings", "company_intelligence", [], "id-1")
    assert "representing the" not in prompt


def test_category_rules_still_match_expected_subjects():
    rbi_prompt, *_ = build_prompt("RBI cuts repo rate by 25 bps", "policy_intelligence", [], "id-rbi")
    assert "reserve bank" in rbi_prompt.lower()

    oil_prompt, *_ = build_prompt("Crude oil prices spike on OPEC cut", "market_wrap", [], "id-oil")
    assert "oil rig" in oil_prompt.lower()

    ai_prompt, *_ = build_prompt("Semiconductor demand surges on AI boom", "sector_intelligence", [], "id-ai")
    assert "semiconductor" in ai_prompt.lower()


def test_unmatched_headline_falls_back_to_default_subject():
    prompt, *_ = build_prompt("A completely generic unrelated headline", "market_wrap", [], "id-default")
    assert "abstract financial market data visualization" in prompt.lower()


def test_seed_is_always_a_valid_non_negative_int_in_range():
    for i in range(20):
        _, _, _, seed = build_prompt(f"Headline number {i}", "market_wrap", [], f"id-{i}")
        assert isinstance(seed, int)
        assert 0 <= seed < 2**31
