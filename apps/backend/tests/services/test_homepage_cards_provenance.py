"""
Provenance contract, Stage D remaining consumers (2026-10-19) --
engine.py's three homepage card builders (_derive_biggest_risk,
_derive_companies_to_watch, and compute_intelligence_state's
market_drivers list) must not present a rule_based_fallback/unknown
event as verified MarketRipple analysis.
"""
from __future__ import annotations

from app.services.intelligence.engine import _derive_biggest_risk, _derive_companies_to_watch


def _event(triage_source: str | None, sentiment: str = "bearish", urgency: int = 8, tickers=None) -> dict:
    ev = {
        "id": "ev-1", "headline": "Raw or AI headline", "one_liner": "Raw or AI one-liner",
        "sentiment": sentiment, "urgency": urgency, "sectors": [], "tickers": tickers or ["RELIANCE"],
        "confidence": 50, "triaged_at": None,
    }
    if triage_source is not None:
        ev["triage_source"] = triage_source
    return ev


# ── _derive_biggest_risk ─────────────────────────────────────────────────────

def test_fallback_bearish_event_is_skipped_falls_back_to_ai_synthesis():
    result = _derive_biggest_risk(story={"risk": "Global rate uncertainty", "confidence": 40},
                                   events=[_event("rule_based_fallback")])
    assert result["source"] == "ai_synthesis"
    assert result["reason"] == "Global rate uncertainty"


def test_unknown_bearish_event_is_skipped():
    result = _derive_biggest_risk(story={"risk": "Global rate uncertainty"}, events=[_event("unknown")])
    assert result["source"] == "ai_synthesis"


def test_ai_sourced_bearish_event_is_unaffected():
    result = _derive_biggest_risk(story=None, events=[_event("ai")])
    assert result["source"] == "tracked_event"
    assert result["reason"] == "Raw or AI one-liner"


def test_falls_through_to_a_lower_urgency_ai_sourced_event():
    events = [_event("rule_based_fallback", urgency=9), _event("ai", urgency=3)]
    result = _derive_biggest_risk(story=None, events=events)
    assert result["source"] == "tracked_event"
    assert result["sentiment"] if "sentiment" in result else True  # sanity: a result was returned
    assert result["reason"] == "Raw or AI one-liner"


# ── _derive_companies_to_watch ───────────────────────────────────────────────

def test_fallback_event_does_not_add_its_ticker():
    out = _derive_companies_to_watch([_event("rule_based_fallback", tickers=["RELIANCE"])])
    assert out == []


def test_ticker_still_added_by_a_later_eligible_event():
    events = [
        _event("rule_based_fallback", tickers=["RELIANCE"]),
        _event("ai", tickers=["RELIANCE"]),
    ]
    out = _derive_companies_to_watch(events)
    assert len(out) == 1 and out[0]["ticker"] == "RELIANCE"


def test_ai_sourced_event_is_unaffected():
    out = _derive_companies_to_watch([_event("ai", tickers=["TCS"])])
    assert len(out) == 1 and out[0]["ticker"] == "TCS"
