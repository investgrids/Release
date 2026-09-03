"""
Regression suite — historical_forecast_guard.py, offline (no DB/network/LLM).

P0-CD3-B historical-outcome containment (2026-09-02): a producer-level
semantic guard for the exact live specimen CD3-A found
(rbi-rate-pauses-banking-investors-historic) — a historical/habitual
connector co-occurring with a forward-looking claim in the same sentence,
never a blanket future-tense scan. See the module's own docstring for the
full rationale.
"""
from __future__ import annotations

from app.services.aipe.historical_forecast_guard import scan_historical_forecast_collapse


def _kt(text: str) -> dict:
    return {"key_takeaway": text}


def _opp(title: str = "", description: str = "") -> dict:
    return {"opportunities": [{"title": title, "description": description}]}


# ── Must flag ─────────────────────────────────────────────────────────────────

def test_exact_rbi_specimen_flagged():
    # The real, live production sentence CD3-A found -- verbatim.
    v = scan_historical_forecast_collapse(_kt(
        "Use policy-driven market dips to add to high-quality banking stocks, "
        "as they typically rebound and outperform over the next 3-6 months."
    ))
    assert v
    assert any("key_takeaway" in e for e in v)


def test_historically_plus_should_rebound_flagged():
    v = scan_historical_forecast_collapse(_kt(
        "Historically, defence stocks should rebound after a budget announcement like this one."
    ))
    assert v


def test_tends_to_plus_increase_exposure_flagged():
    v = scan_historical_forecast_collapse(_kt(
        "IT stocks tend to recover within a quarter, so investors should increase exposure now."
    ))
    assert v


def test_historical_pattern_plus_add_to_in_opportunities_flagged():
    v = scan_historical_forecast_collapse(_opp(
        title="Banking stocks historically rebound after a rate hold",
        description="Given this historical pattern, add to positions over the next few weeks.",
    ))
    assert any("opportunities" in e for e in v)


def test_based_on_past_performance_plus_expect_to_flagged():
    v = scan_historical_forecast_collapse(_kt(
        "Based on past performance, we expect to see a similar rally play out this time."
    ))
    assert v


# ── Must NOT flag ─────────────────────────────────────────────────────────────

def test_pure_retrospective_statement_not_flagged():
    v = scan_historical_forecast_collapse(_kt(
        "Banking stocks rose 4.2% on average in the month after the 2020 and 2023 rate holds."
    ))
    assert v == []


def test_pure_retrospective_statement_with_typically_alone_not_flagged():
    # "typically" alone, describing only the past, with no forward action
    # or expectation phrase anywhere -- not a collapse.
    v = scan_historical_forecast_collapse(_kt(
        "This type of announcement has typically been followed by a short-lived dip in the sector index."
    ))
    assert v == []


def test_forward_claim_without_historical_connector_not_flagged():
    # Deliberately not a blanket future-tense regex -- a forward statement
    # grounded in today's real event, no historical/habitual connector
    # anywhere in the sentence, must pass.
    v = scan_historical_forecast_collapse(_kt(
        "The RBI's guidance today points to easing pressure on bank funding costs over the next 2 months."
    ))
    assert v == []


def test_historical_connector_and_forward_claim_in_different_sentences_not_flagged():
    # Same field, but the historical observation and the forward-looking
    # statement are in separate sentences with the current-evidence
    # grounding stated explicitly -- this guard only catches same-sentence
    # co-occurrence, not any proximity anywhere in the field. (A stricter
    # cross-sentence check is a possible future tightening, not this pass.)
    v = scan_historical_forecast_collapse(_kt(
        "Banking stocks have historically rebounded after a rate hold. "
        "Today's RBI commentary specifically flagged easing NIM pressure, which supports a near-term recovery."
    ))
    assert v == []


def test_low_risk_fields_not_scanned():
    # what_happened/why_it_matters/executive_summary are narrative fields,
    # same scope boundary as recommendation_language.py -- only
    # key_takeaway/opportunities are the "MarketRipple's own conclusion"
    # fields this guard exists to protect.
    article = {
        "what_happened": (
            "Banking stocks typically rebound after a rate hold, and some analysts "
            "expect this pattern to repeat over the next few months."
        ),
        "key_takeaway": "The evidence shows a historical pattern investors should be aware of.",
    }
    v = scan_historical_forecast_collapse(article)
    assert v == []


def test_empty_and_missing_fields_do_not_raise():
    assert scan_historical_forecast_collapse({}) == []
    assert scan_historical_forecast_collapse({"key_takeaway": None, "opportunities": None}) == []
    assert scan_historical_forecast_collapse({"opportunities": ["not-a-dict"]}) == []
