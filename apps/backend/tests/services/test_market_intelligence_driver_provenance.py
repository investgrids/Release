"""
Provenance contract, Stage D remaining consumers (2026-10-19) --
market_intelligence_service.py::_verified_drivers_for() must not present a
rule_based_fallback/unknown event's one_liner as a checkable "driver".
Falls through to the existing tier 2/3 (theme/momentum) or the existing
empty-list "no verified driver identified" behavior.
"""
from __future__ import annotations

from app.services.market_intelligence_service import _verified_drivers_for


def _event(triage_source: str, urgency: int = 8) -> dict:
    return {
        "tickers": ["RELIANCE"], "one_liner": "Raw or AI headline about Reliance",
        "headline": "Reliance headline", "id": "ev-1", "urgency": urgency,
        "triage_source": triage_source,
    }


def test_fallback_sourced_event_produces_no_driver():
    drivers = _verified_drivers_for("RELIANCE", 1.5, themes=[], events=[_event("rule_based_fallback")])
    assert drivers == []


def test_unknown_provenance_event_produces_no_driver():
    drivers = _verified_drivers_for("RELIANCE", 1.5, themes=[], events=[_event("unknown")])
    assert drivers == []


def test_ai_sourced_event_is_unaffected():
    drivers = _verified_drivers_for("RELIANCE", 1.5, themes=[], events=[_event("ai")])
    assert len(drivers) == 1
    assert drivers[0]["evidence"] == "Raw or AI headline about Reliance"


def test_falls_through_to_a_later_eligible_event_for_the_same_ticker():
    events = [_event("rule_based_fallback", urgency=9), _event("ai", urgency=3)]
    drivers = _verified_drivers_for("RELIANCE", 1.5, themes=[], events=events)
    assert len(drivers) == 1, "the fallback event must be skipped, the AI event must still produce a driver"


def test_missing_triage_source_key_is_treated_as_eligible():
    event = {"tickers": ["RELIANCE"], "one_liner": "No key at all", "headline": "h", "id": "ev-1", "urgency": 5}
    drivers = _verified_drivers_for("RELIANCE", 1.5, themes=[], events=[event])
    assert len(drivers) == 1
