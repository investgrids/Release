"""
Regression suite — fact_grounding validators, offline (no DB/network/LLM).

Built for the AI Article Pipeline fix (2026-08-10, Phase 1): catches the
three failure modes named in the approved spec — a boilerplate causal
reason reused across companies, a sentiment tag that contradicts a real
price move (the "-5.84% tagged neutral" example), and a draft event
described as finalized (or the reverse).
"""
from __future__ import annotations

from app.services.aipe.fact_grounding import (
    check_shared_causal_reasons,
    check_sentiment_magnitude_consistency,
    check_status_tense,
    validate_fact_grounding,
)


# ── Shared causal reasons ────────────────────────────────────────────────────

def test_identical_reason_across_two_companies_flagged():
    companies = [
        {"symbol": "BAJFINANCE", "reason": "Sector-wide risk-off sentiment amid regulatory uncertainty"},
        {"symbol": "ICICIBANK", "reason": "Sector-wide risk-off sentiment amid regulatory uncertainty"},
    ]
    errors = check_shared_causal_reasons(companies)
    assert len(errors) == 1
    assert "BAJFINANCE" in errors[0] and "ICICIBANK" in errors[0]


def test_genuinely_distinct_reasons_not_flagged():
    companies = [
        {"symbol": "BAJFINANCE", "reason": "Flexi Loan products directly targeted by the draft NBFC rule"},
        {"symbol": "ICICIBANK", "reason": "No direct revolving-credit NBFC exposure; broad sector caution only"},
    ]
    assert check_shared_causal_reasons(companies) == []


def test_single_company_never_flagged():
    companies = [{"symbol": "TCS", "reason": "Some reason"}]
    assert check_shared_causal_reasons(companies) == []


def test_companies_without_reason_ignored():
    companies = [{"symbol": "TCS"}, {"symbol": "INFY", "reason": ""}]
    assert check_shared_causal_reasons(companies) == []


# ── Sentiment/magnitude consistency against real price moves ────────────────

def test_large_negative_move_tagged_neutral_flagged():
    companies = [{"symbol": "SBIN", "impact": "neutral"}]
    price_moves = {"SBIN": -5.84}
    errors = check_sentiment_magnitude_consistency(companies, price_moves)
    assert len(errors) == 1
    assert "SBIN" in errors[0] and "neutral" in errors[0]


def test_small_move_tagged_neutral_not_flagged():
    companies = [{"symbol": "SBIN", "impact": "neutral"}]
    price_moves = {"SBIN": -0.4}
    assert check_sentiment_magnitude_consistency(companies, price_moves) == []


def test_direction_mismatch_positive_move_tagged_negative():
    companies = [{"symbol": "TCS", "impact": "negative"}]
    price_moves = {"TCS": 1.2}
    errors = check_sentiment_magnitude_consistency(companies, price_moves)
    assert len(errors) == 1
    assert "TCS" in errors[0]


def test_direction_mismatch_negative_move_tagged_positive():
    companies = [{"symbol": "INFY", "impact": "positive"}]
    price_moves = {"INFY": -1.5}
    errors = check_sentiment_magnitude_consistency(companies, price_moves)
    assert len(errors) == 1


def test_consistent_tags_not_flagged():
    companies = [
        {"symbol": "BAJFINANCE", "impact": "negative"},
        {"symbol": "TCS", "impact": "positive"},
        {"symbol": "SBIN", "impact": "neutral"},
    ]
    price_moves = {"BAJFINANCE": -5.84, "TCS": 1.1, "SBIN": 0.05}
    assert check_sentiment_magnitude_consistency(companies, price_moves) == []


def test_company_without_fetched_price_skipped_not_flagged():
    # No real quote data available for this symbol — must never be treated
    # as an error; that's a data-availability gap, not a fact violation.
    companies = [{"symbol": "UNLISTEDCO", "impact": "neutral"}]
    assert check_sentiment_magnitude_consistency(companies, {}) == []


# ── Status/tense consistency ─────────────────────────────────────────────────

def test_draft_event_described_as_finalized_flagged():
    source = "RBI proposed draft restrictions on revolving credit facilities for NBFCs"
    body = "The RBI has finalized new restrictions on NBFC revolving credit facilities."
    errors = check_status_tense(source, body)
    assert len(errors) == 1
    assert "STATUS_MISMATCH" in errors[0]


def test_decided_event_described_as_pending_flagged():
    source = "RBI has decided to cut the repo rate by 25 bps, effective immediately"
    body = "RBI is considering a rate cut and may decide in the coming weeks."
    errors = check_status_tense(source, body)
    assert len(errors) == 1


def test_consistent_draft_language_not_flagged():
    source = "RBI proposed draft restrictions on NBFC revolving credit"
    body = "The RBI's draft proposal, if implemented, would restrict revolving credit products."
    assert check_status_tense(source, body) == []


def test_consistent_decided_language_not_flagged():
    source = "RBI cuts repo rate by 25 bps in surprise policy decision"
    body = "The RBI has finalized a 25 bps repo rate cut, effective immediately."
    assert check_status_tense(source, body) == []


def test_ambiguous_text_not_flagged():
    # Source mentions both draft and a related decided fact — genuinely
    # ambiguous, must not be treated as a clear-cut mismatch either way.
    source = "RBI proposed a draft NBFC rule; separately, RBI has already decided to hold the repo rate"
    body = "The draft proposal remains under consideration."
    assert check_status_tense(source, body) == []


# ── Combined gate ─────────────────────────────────────────────────────────────

def test_validate_fact_grounding_passes_clean_article():
    article = {
        "companies_affected": [
            {"symbol": "BAJFINANCE", "impact": "negative", "reason": "Flexi Loan products directly targeted"},
            {"symbol": "SBIN", "impact": "neutral", "reason": "No verified direct exposure"},
        ],
        "what_happened": "RBI proposed a draft rule restricting NBFC revolving credit facilities.",
        "why_it_matters": "The draft proposal, if finalized later, could affect lending margins.",
    }
    price_moves = {"BAJFINANCE": -5.84, "SBIN": 0.1}
    passed, errors = validate_fact_grounding(
        article, price_moves,
        source_headline="RBI proposes draft NBFC revolving credit restrictions",
        source_summary="Draft rule open for public feedback until August 28.",
    )
    assert passed is True
    assert errors == []


def test_total_fetch_failure_fails_closed_when_companies_present():
    # This is the bug the reviewer caught: on a total price-fetch failure
    # (fetch_price_moves() returns None, not {}), a company-bearing article
    # must NOT publish unchecked — that would silently reopen the exact
    # "-5.84% tagged neutral" bug on the days feeds are most likely to lag
    # (fast-moving/volatile sessions).
    article = {
        "companies_affected": [{"symbol": "SBIN", "impact": "neutral", "reason": "Broad market move"}],
        "what_happened": "Markets reacted to the policy announcement.",
        "why_it_matters": "Investors are watching for follow-through.",
    }
    passed, errors = validate_fact_grounding(
        article, None,
        source_headline="RBI holds repo rate steady",
        source_summary="No change from the previous policy.",
    )
    assert passed is False
    assert any("PRICE_DATA_UNAVAILABLE" in e for e in errors)


def test_total_fetch_failure_does_not_block_company_less_article():
    # A pure macro/policy piece with no companies has nothing to check
    # against real prices regardless of fetch status — must not be
    # penalized for a data outage that's irrelevant to it.
    article = {
        "companies_affected": [],
        "what_happened": "RBI held the repo rate steady at its policy meeting.",
        "why_it_matters": "No immediate market-wide shift expected.",
    }
    passed, errors = validate_fact_grounding(
        article, None,
        source_headline="RBI holds repo rate steady",
        source_summary="No change from the previous policy.",
    )
    assert passed is True
    assert errors == []


def test_validate_fact_grounding_fails_on_real_bug_combination():
    article = {
        "companies_affected": [
            {"symbol": "BAJFINANCE", "impact": "negative", "reason": "Sector-wide risk-off sentiment"},
            {"symbol": "SBIN", "impact": "neutral", "reason": "Sector-wide risk-off sentiment"},
        ],
        "what_happened": "The RBI has finalized new restrictions on NBFC revolving credit.",
        "why_it_matters": "This decision immediately impacts lenders.",
    }
    price_moves = {"BAJFINANCE": -5.84, "SBIN": -5.2}
    passed, errors = validate_fact_grounding(
        article, price_moves,
        source_headline="RBI proposed draft restrictions on NBFC revolving credit facilities",
        source_summary="Draft open for public feedback until August 28.",
    )
    assert passed is False
    # Shared reason + SBIN neutral-tagged-but-large-move + status mismatch
    assert len(errors) >= 3
