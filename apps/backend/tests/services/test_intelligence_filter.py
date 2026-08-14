"""
Regression suite — app.services.aipe.intelligence_filter, offline.
No DB, no network, no LLM.

Covers three fixes from the 2026-08-13 re-audit:
  1. should_generate_intelligence's urgency<6 gate used to be unconditional,
     rejecting a keyword-floor-elevated Critical/High event before
     filter_triage_batch's own rescue ever got a chance to save it.
  2. Two regex bugs in _HARD_YES_PATTERNS: a Cyrillic "о" (U+043E) in "ipо
     listing" that silently never matched the real ASCII string, and
     `\\bmerger|acquisition\\b...` parsing as `(\\bmerger)|(acquisition\\b...)`
     — "merger" alone hard-yes'd with no amount required (and no trailing
     boundary either), while "acquisition" alone required one.
  3. _FII_THRESHOLD_CR (=1000) was declared but never compared against
     anything — the old patterns only checked an amount was PRESENT, not
     that it met the ₹1000 Cr threshold.
"""
from __future__ import annotations

import pytest

from app.services.aipe.intelligence_filter import (
    _is_hard_yes,
    _fii_dii_exceeds_threshold,
    should_generate_intelligence,
)


# ── Fix 1: keyword-floor-elevated events bypass the raw urgency gate ────────
def test_low_urgency_critical_keyword_event_still_generates():
    # The exact real shape found live in the 2026-08 audit: urgency=1 (the
    # AI itself scored this low), but the headline contains "war", which
    # engine.py's keyword floor forces to Critical regardless of raw
    # urgency/importance. Before the fix, this was rejected here with
    # "Urgency too low (1 < 6)" before ever reaching the Critical/High
    # rescue in filter_triage_batch.
    event = {
        "headline": "From Gift Nifty to US-Iran war, crude oil prices surge overnight",
        "urgency": 1,
        "importance": 6,
        "market_impact": "medium",
        "is_structural": False,
    }
    ok, reason = should_generate_intelligence(event, source="triage")
    assert ok, f"Keyword-elevated Critical event still rejected: {reason}"
    assert "Critical" in reason or "Priority" in reason


def test_genuinely_low_priority_event_still_rejected():
    # Sanity check the fix isn't a blanket bypass — an event with low
    # urgency AND no Critical/High keyword match should still be rejected.
    event = {
        "headline": "Company X holds routine investor call",
        "urgency": 2,
        "importance": 3,
        "market_impact": "low",
        "is_structural": False,
    }
    ok, reason = should_generate_intelligence(event, source="triage")
    assert not ok, f"Genuinely low-priority event should still be rejected, got: {reason}"


# ── Fix 2a: Cyrillic "о" in "ipо listing" ────────────────────────────────────
def test_ipo_listing_ascii_matches():
    assert _is_hard_yes("company ipo listing surges premium above issue price by 40%")


# ── Fix 2b: merger/acquisition word-boundary + amount requirement ───────────
def test_merger_alone_no_longer_unconditional_hard_yes():
    # Before the fix, bare "merger" anywhere hard-yes'd with no amount
    # required at all (operator-precedence bug). Both alternatives now
    # require the same trailing rupee-crore amount clause.
    assert not _is_hard_yes("company announces merger with rival firm")


def test_merger_with_amount_still_hard_yes():
    assert _is_hard_yes("company announces merger worth rs 800 cr with rival firm")


def test_acquisition_with_amount_hard_yes():
    assert _is_hard_yes("company announces acquisition worth rs 500 cr")


def test_acquisition_without_amount_not_hard_yes():
    assert not _is_hard_yes("company announces acquisition of smaller rival")


# ── Fix 3: FII/DII threshold actually enforced ───────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("fii sold rs 500 cr worth of equities today", False),   # below ₹1000 Cr
    ("fii sold rs 999 cr worth of equities today", False),   # just below
    ("fii sold rs 1000 cr worth of equities today", True),   # exactly at threshold
    ("fii sold rs 1500 cr worth of equities today", True),   # above
    ("dii net buying at rs 3,200 crore", True),               # comma-formatted, above
    ("company reports strong quarterly results", False),      # no fii/dii mention at all
])
def test_fii_dii_threshold_enforcement(text, expected):
    assert _fii_dii_exceeds_threshold(text) == expected, f"{text!r} -> expected {expected}"


def test_fii_below_threshold_not_hard_yes_via_full_path():
    # End-to-end through _is_hard_yes, not just the helper directly.
    assert not _is_hard_yes("fii sold rs 200 cr worth of equities today")


def test_fii_above_threshold_is_hard_yes_via_full_path():
    assert _is_hard_yes("fii sold rs 2000 cr worth of equities today")


# ── Non-regression: existing hard-yes/hard-no behavior unaffected ───────────
def test_rbi_rate_decision_still_hard_yes():
    assert _is_hard_yes("rbi cuts repo rate by 25 bps in surprise monetary policy move")


def test_routine_agm_still_not_hard_yes():
    assert not _is_hard_yes("notice of annual general meeting to be held on august 31, 2026")
