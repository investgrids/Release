"""
advisory_language.py — the shared, AEV2-independent recommendation-
language scanner every real serving surface (safety_gate.py,
market_pulse_safety.py, refine_safety.py) derives from.

Context-aware "hold" (2026-09-21, third pass): a bare `\\bhold\\b` ban —
the original AEV2-only precedent — falsely degrades legitimate factual
prose ("RBI decided to hold rates", "prices may hold steady", "the
company will hold its AGM"). Only specific advisory PHRASINGS are
blocked, never the bare word. These are the exact adversarial cases
named in review.
"""
from __future__ import annotations

import pytest

from app.services.ai_search.advisory_language import is_advisory_hold, scan


# ── Factual "hold" usage must never be flagged ──────────────────────────────

@pytest.mark.parametrize("text", [
    "RBI decided to hold rates.",
    "The RBI is expected to hold rates steady at its next MPC meeting.",
    "Prices may hold steady amid mixed global cues.",
    "The company will hold its AGM next month.",
    "The board will hold a meeting to discuss the merger.",
    "Talks between the two companies will hold in New Delhi next week.",
])
def test_factual_hold_usage_never_flagged(text):
    assert is_advisory_hold(text) is False
    assert scan(text) == []


# ── Advisory "hold" phrasings must be caught ────────────────────────────────

@pytest.mark.parametrize("text", [
    "You should hold BEL.",
    "Investors should hold their current positions.",
    "Continue holding the stock for now.",
    "Keep holding your shares until the next earnings call.",
    "This is a hold recommendation.",
    "Our hold rating remains unchanged.",
    "We rate this stock as a hold.",
    "We recommend investors hold their existing position.",
    "Hold on to the stock for the next quarter.",
])
def test_advisory_hold_phrasings_are_flagged(text):
    assert is_advisory_hold(text) is True
    assert "hold" in scan(text)


# ── The shared scan() still catches everything recommendation_language.py
# already proved (buy/sell/etc.) — this module adds hold, it doesn't
# replace the existing coverage. ────────────────────────────────────────────

def test_scan_still_catches_non_hold_advisory_language():
    assert scan("This stock is a solid buy candidate.") != []
    assert scan("Investors should sell this position immediately.") != []


def test_scan_does_not_flag_buyback_or_short_term_adversarial_cases():
    """Same adversarial guarantees recommendation_language.py already
    carries test coverage for — scan() must not weaken them."""
    assert scan("The company announced a share buyback program.") == []
    assert scan("This is a short-term headwind, not a structural one.") == []


def test_scan_empty_text_returns_empty_list():
    assert scan("") == []
    assert scan(None) == []  # type: ignore[arg-type]
