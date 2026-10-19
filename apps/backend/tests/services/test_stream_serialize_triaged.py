"""
Provenance contract, Stage D (2026-10-19) -- api/stream.py's
_serialize_triaged() manually allowlists fields for the live SSE push;
triage_source needs its own explicit addition (the chokepoint fix in
engine.py doesn't reach this boundary, since TriagedEvent is broadcast
in-process, not read from read_top_events()).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.api.stream import _serialize_triaged
from app.services.intelligence.event_bus import RawEvent, TriagedEvent


def _triaged(triage_source: str) -> TriagedEvent:
    return TriagedEvent(
        raw=RawEvent(id="x1", headline="Test headline", summary="s", source="news", origin="Test"),
        urgency=7, importance=6, confidence=5, sentiment="neutral", horizon="short",
        market_impact="medium", is_structural=False, direction="sideways",
        one_liner="Test one-liner", triage_source=triage_source,
        themes=[], sectors=[], tickers=[], broadcast=True, refresh_homepage=False,
    )


def test_triage_source_is_included_in_the_sse_payload():
    payload = json.loads(_serialize_triaged(_triaged("rule_based_fallback")))
    assert payload["triage_source"] == "rule_based_fallback"


def test_existing_fields_are_unchanged_for_an_ai_sourced_event():
    payload = json.loads(_serialize_triaged(_triaged("ai")))
    assert payload["one_liner"] == "Test one-liner"
    assert payload["headline"] == "Test headline"
    assert payload["urgency"] == 7
    assert payload["triage_source"] == "ai"
