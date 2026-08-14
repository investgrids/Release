"""
Regression suite — app.api.stocks._related_events_for_symbol (Phase 13,
2026-08 audit: the company page's "Recent Events" list carried no id/slug
at all before this, so it could never link back to /events/[slug] even
though the events themselves are indexable pages).
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.stocks import _related_events_for_symbol


def _fake_event(id_: str, title: str, companies, slug: str | None = None):
    return SimpleNamespace(
        id=id_, title=title, companies=companies, slug=slug,
        published_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def test_matched_event_carries_real_id_and_slug():
    events = [_fake_event("evt-1", "TCS wins large deal", [{"symbol": "TCS"}], slug="tcs-wins-large-deal")]
    result = _related_events_for_symbol(events, "TCS")
    assert len(result) == 1
    assert result[0].id == "evt-1"
    assert result[0].slug == "tcs-wins-large-deal"


def test_event_with_no_slug_still_carries_id():
    events = [_fake_event("evt-2", "TCS quarterly results", [{"symbol": "TCS"}], slug=None)]
    result = _related_events_for_symbol(events, "TCS")
    assert result[0].id == "evt-2"
    assert result[0].slug == ""


def test_matches_string_company_entries_too():
    events = [_fake_event("evt-3", "Infosys announcement", ["INFY"])]
    result = _related_events_for_symbol(events, "INFY")
    assert len(result) == 1
    assert result[0].id == "evt-3"


def test_non_matching_symbol_excluded():
    events = [_fake_event("evt-4", "Reliance results", [{"symbol": "RELIANCE"}])]
    result = _related_events_for_symbol(events, "TCS")
    assert result == []


def test_respects_limit():
    events = [_fake_event(f"evt-{i}", f"TCS event {i}", [{"symbol": "TCS"}]) for i in range(10)]
    result = _related_events_for_symbol(events, "TCS", limit=4)
    assert len(result) == 4
