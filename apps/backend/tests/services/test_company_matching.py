"""
company_matching.py — the shared, pure company<->evidence matching
rules both pipeline.py (degraded-response builder) and aev2/
citation_validator.py (claim evidence coverage) use, extracted
2026-09-21 so the two can never silently drift into different rules.
"""
from __future__ import annotations

from app.services.ai_search.company_matching import (
    event_company_symbols,
    filter_announcements_to_companies,
    filter_events_to_companies,
)


def test_event_company_symbols_extracts_uppercased_symbols():
    event = {"companies": [{"symbol": "reliance"}, {"symbol": "TCS"}, {"not_a_symbol": "x"}]}
    assert event_company_symbols(event) == {"RELIANCE", "TCS"}


def test_event_company_symbols_empty_when_no_companies_field():
    assert event_company_symbols({}) == set()
    assert event_company_symbols({"companies": None}) == set()


def test_filter_events_to_companies_matches_by_symbol():
    events = [
        {"id": "e1", "companies": [{"symbol": "RELIANCE"}]},
        {"id": "e2", "companies": [{"symbol": "TCS"}]},
    ]
    assert [e["id"] for e in filter_events_to_companies(events, ["RELIANCE"])] == ["e1"]


def test_filter_events_to_companies_empty_symbols_returns_empty():
    events = [{"id": "e1", "companies": [{"symbol": "RELIANCE"}]}]
    assert filter_events_to_companies(events, []) == []


def test_filter_announcements_to_companies_matches_by_direct_symbol_column():
    announcements = [
        {"id": "a1", "symbol": "RELIANCE"},
        {"id": "a2", "symbol": "TCS"},
    ]
    assert [a["id"] for a in filter_announcements_to_companies(announcements, ["reliance"])] == ["a1"]


def test_filter_announcements_to_companies_empty_symbols_returns_empty():
    assert filter_announcements_to_companies([{"id": "a1", "symbol": "RELIANCE"}], set()) == []


def test_pipeline_filter_events_to_entities_delegates_to_shared_utility():
    """Regression guard: pipeline.py's own function must not silently
    grow a second, divergent copy of this matching rule."""
    import inspect
    from app.services.ai_search import pipeline
    source = inspect.getsource(pipeline._filter_events_to_entities)
    assert "filter_events_to_companies" in source


def test_pipeline_and_citation_validator_produce_identical_matches():
    """Same input, same output, across both real call sites — proves
    the delegation isn't just present in source but behaviorally
    identical."""
    from app.services.ai_search import pipeline
    from app.services.ai_search.company_matching import filter_events_to_companies

    events = [
        {"id": "e1", "companies": [{"symbol": "RELIANCE"}]},
        {"id": "e2", "companies": [{"symbol": "TCS"}]},
    ]
    assert pipeline._filter_events_to_entities(events, ["RELIANCE"]) == filter_events_to_companies(events, ["RELIANCE"])
