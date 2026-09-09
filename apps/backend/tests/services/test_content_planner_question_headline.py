"""
Regression suite — content_planner.plan_extra_angles' "question" angle
headline construction, offline.

Real incident (2026-09-09): a live, published headline read "Should I Buy
Tata Steel? Why Crude Oil Volatility and Geopolitical Tensions Are..." --
a grammatically incomplete fragment. Root cause: the old event_phrase
truncation cut at a hard character count then a WORD boundary, not a
CLAUSE boundary, and papered over the cut with "...". Fix: only truncate
at a genuine clause boundary (colon/semicolon/dash) within budget, and
fall back to a fixed, phrase-free, deterministic title (never another
speculative attempt) when no such boundary exists.

Remediation boundary (owner-locked): fix the title-generation defect only.
Preserve grounded entity identity, introduce no new facts/numbers, no new
recommendation/directional language, and keep the fallback fully
deterministic.
"""
from __future__ import annotations

from app.services.aipe.content_planner import _safe_event_phrase, plan_extra_angles

_TATA_STEEL = {"symbol": "TATASTEEL", "name": "Tata Steel", "impact": "positive"}


def _question_plans(plans):
    return [p for p in plans if p[2] == "question"]


def test_tata_steel_long_no_clause_boundary_headline_falls_back_not_truncated():
    """The real specimen: a headline long enough to need truncation, with
    no colon/semicolon/dash within the first 60 characters. Must NOT
    produce a "..."-terminated fragment -- must use the deterministic
    fallback instead."""
    primary_headline = (
        "Why Crude Oil Volatility and Geopolitical Tensions Are Reshaping "
        "Steel Demand and Margins This Quarter"
    )
    plans = plan_extra_angles(
        primary_article_type="sector_intelligence",
        primary_story_id="intel-crude-steel-20260909",
        primary_headline=primary_headline,
        companies_affected=[_TATA_STEEL],
        sectors_affected=[{"name": "Metals"}],
        primary_angle_entity=None,
    )
    questions = _question_plans(plans)
    assert len(questions) == 1
    question_text = questions[0][4]
    assert question_text == "Should I Buy Tata Steel? What Investors Need To Know"
    assert "..." not in question_text


def test_short_headline_under_cap_is_used_verbatim_no_truncation():
    primary_headline = "Tata Steel Announces Strong Quarterly Results"
    plans = plan_extra_angles(
        primary_article_type="sector_intelligence",
        primary_story_id="intel-tata-results-20260909",
        primary_headline=primary_headline,
        companies_affected=[_TATA_STEEL],
        sectors_affected=[{"name": "Metals"}],
        primary_angle_entity=None,
    )
    question_text = _question_plans(plans)[0][4]
    assert primary_headline in question_text
    assert "..." not in question_text


def test_long_headline_with_clause_boundary_within_budget_truncates_safely():
    """When a genuine clause boundary (colon here) exists within the
    length budget, truncating there is safe -- the result is a real,
    complete clause, not a fragment."""
    primary_headline = (
        "Tata Steel Q2 Results: Net Profit Jumps 40% On Strong Export Demand "
        "And Falling Input Costs Across All Major Product Lines"
    )
    phrase = _safe_event_phrase(primary_headline)
    assert phrase is not None
    assert phrase == "Tata Steel Q2 Results"
    assert "..." not in phrase


def test_empty_primary_headline_falls_back_never_produces_empty_or_malformed_title():
    plans = plan_extra_angles(
        primary_article_type="sector_intelligence",
        primary_story_id="intel-empty-headline-20260909",
        primary_headline="",
        companies_affected=[_TATA_STEEL],
        sectors_affected=[{"name": "Metals"}],
        primary_angle_entity=None,
    )
    question_text = _question_plans(plans)[0][4]
    assert question_text.strip() != ""
    assert question_text == "Should I Buy Tata Steel? What Investors Need To Know"


def test_whitespace_only_primary_headline_treated_as_empty():
    assert _safe_event_phrase("   \n\t  ") is None


def test_fallback_never_introduces_a_number_not_in_the_original_headline():
    """The fallback template is fixed text -- confirm it contains no
    digits at all, so it can never smuggle in an unsupported numeric
    claim regardless of what the (discarded) primary headline said."""
    primary_headline = "Company Reports 340% Surge In Something Extremely Long And Unrelated To Any Clause Boundary Whatsoever"
    plans = plan_extra_angles(
        primary_article_type="sector_intelligence",
        primary_story_id="intel-numeric-20260909",
        primary_headline=primary_headline,
        companies_affected=[_TATA_STEEL],
        sectors_affected=[{"name": "Metals"}],
        primary_angle_entity=None,
    )
    question_text = _question_plans(plans)[0][4]
    assert not any(ch.isdigit() for ch in question_text), (
        f"fallback title must never contain digits not present in the original grounded headline: {question_text!r}"
    )


def test_two_companies_each_get_their_own_correctly_scoped_entity_no_leakage():
    """Wrong-company/entity leakage guard: with two companies in the same
    event, each question angle's company name/symbol must match ITS OWN
    entity, never the other one's."""
    company_a = {"symbol": "TATASTEEL", "name": "Tata Steel", "impact": "positive"}
    company_b = {"symbol": "JSWSTEEL", "name": "JSW Steel", "impact": "negative"}
    plans = plan_extra_angles(
        primary_article_type="sector_intelligence",
        primary_story_id="intel-steel-sector-20260909",
        primary_headline="Steel Sector Update",
        companies_affected=[company_a, company_b],
        sectors_affected=[{"name": "Metals"}],
        primary_angle_entity=None,
        max_questions=2,
    )
    questions = _question_plans(plans)
    assert len(questions) == 2
    by_entity = {q[3]: q[4] for q in questions}
    assert "Tata Steel" in by_entity["TATASTEEL"]
    assert "JSW Steel" not in by_entity["TATASTEEL"]
    assert "JSW Steel" in by_entity["JSWSTEEL"]
    assert "Tata Steel" not in by_entity["JSWSTEEL"]


def test_negative_impact_fallback_uses_sell_framing_not_buy():
    primary_headline = (
        "A Very Long Primary Headline With No Clause Boundary Whatsoever That "
        "Exceeds The Safe Truncation Budget By A Wide Margin For Sure"
    )
    plans = plan_extra_angles(
        primary_article_type="sector_intelligence",
        primary_story_id="intel-negative-20260909",
        primary_headline=primary_headline,
        companies_affected=[{"symbol": "TATASTEEL", "name": "Tata Steel", "impact": "negative"}],
        sectors_affected=[{"name": "Metals"}],
        primary_angle_entity=None,
    )
    question_text = _question_plans(plans)[0][4]
    assert question_text == "Should I Sell Tata Steel? What Investors Need To Know"


def test_neutral_impact_fallback_uses_neutral_framing():
    primary_headline = (
        "A Very Long Primary Headline With No Clause Boundary Whatsoever That "
        "Exceeds The Safe Truncation Budget By A Wide Margin For Sure"
    )
    plans = plan_extra_angles(
        primary_article_type="sector_intelligence",
        primary_story_id="intel-neutral-20260909",
        primary_headline=primary_headline,
        companies_affected=[{"symbol": "TATASTEEL", "name": "Tata Steel", "impact": "neutral"}],
        sectors_affected=[{"name": "Metals"}],
        primary_angle_entity=None,
    )
    question_text = _question_plans(plans)[0][4]
    assert question_text == "What Does This Mean For Tata Steel? What Investors Need To Know"


def test_safe_event_phrase_never_returns_a_string_ending_in_ellipsis():
    """Direct guard on the helper itself -- whatever it returns (real
    prefix or None), it must never re-introduce the old "..." pattern."""
    long_no_boundary = "word " * 30
    result = _safe_event_phrase(long_no_boundary)
    if result is not None:
        assert not result.endswith("...")


def test_safe_event_phrase_boundary_candidate_too_short_falls_back_to_none():
    """A clause boundary that exists but leaves too short a prefix (e.g.
    right near the start) must not be used -- a 5-character 'phrase' is
    noise, not a real clause."""
    primary_headline = "Hi: " + ("x" * 100)
    assert _safe_event_phrase(primary_headline) is None
