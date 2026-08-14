"""
Regression suite — content_planner.select_article_type's keyword matching,
offline. No DB, no network, no LLM.

Companion to test_priority_engine.py, which pins the same fix for
app.services.intelligence.engine.compute_priority (the importance-tier
classifier). This file exists because content_planner.py's article-TYPE
classifier used the identical vocabulary with a bare `kw in text` substring
check — its own, separate, unfixed instance of the same bug class, only
caught in the 2026-08-13 re-audit. Concretely verified false positives
before the fix: "ai" matched inside "maintain"/"chairman"/"again"/"retail"/
"captain"; "ev" matched inside "event"/"revenue"/"seven"/"every"; "pli"
matched inside "compliance"; "rbi" matched inside "turbine".
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.services.aipe.content_planner import select_article_type, _IST


def _event(headline: str, urgency: int = 5, importance: int = 5, sectors=None, companies=None):
    return {
        "event_id": "test-event-001",
        "headline": headline,
        "urgency": urgency,
        "importance": importance,
        "sectors": sectors or [],
        "tickers": companies or [],
        "is_structural": False,
    }


# Freezes the two independent wall-clock checks select_article_type does
# before ever reaching keyword matching (_session()'s pre_market check, and
# a SEPARATE raw _ist_now() post-3:30pm check right after it) — otherwise
# these tests are time-of-day-dependent and fail identically whenever run
# after 3:30pm IST (confirmed: this is exactly what happened on first run).
# Both patched to a fixed mid-session Tuesday 11:00 IST for every test here.
@pytest.fixture(autouse=True)
def _force_live_session(monkeypatch):
    fixed_now = datetime(2026, 8, 11, 11, 0, tzinfo=_IST)  # Tuesday, 11:00 IST
    monkeypatch.setattr("app.services.aipe.content_planner._session", lambda: "live")
    monkeypatch.setattr("app.services.aipe.content_planner._ist_now", lambda: fixed_now)


# ── Keywords must NOT match as substrings of unrelated real words ───────────
FALSE_POSITIVE_CASES = [
    ("Triveni Turbine Industries wins export order worth Rs 45 crore", "policy_intelligence", "rbi-in-turbine"),
    ("Company management said it will maintain guidance for FY26", "theme_intelligence", "ai-in-maintain"),
    ("New chairman appointed to lead the board", "theme_intelligence", "ai-in-chairman"),
    ("Company profit rose again this quarter on strong demand", "theme_intelligence", "ai-in-again"),
    ("Strong retail demand seen ahead of festive season", "theme_intelligence", "ai-in-retail"),
    ("Captain of industry speaks on economic outlook", "theme_intelligence", "ai-in-captain"),
    ("Annual investor event scheduled for next month", "theme_intelligence", "ev-in-event"),
    ("Company revenue increased sharply in the quarter", "theme_intelligence", "ev-in-revenue"),
    ("Seven companies affected by the new regulation", "theme_intelligence", "ev-in-seven"),
    ("Every company in the sector saw gains today", "theme_intelligence", "ev-in-every"),
    ("Company flags compliance issue with SEBI norms", "theme_intelligence", "pli-in-compliance"),
]


@pytest.mark.parametrize("headline,forbidden_type,label", FALSE_POSITIVE_CASES)
def test_keyword_does_not_false_positive_on_substring(headline, forbidden_type, label):
    article_type, story_id, priority = select_article_type(_event(headline))
    assert article_type != forbidden_type, (
        f"[{label}] false-positive substring match still present: "
        f"{headline!r} -> {article_type} (story_id={story_id})"
    )


# ── The same keywords must still match on real word boundaries ──────────────
REAL_MATCH_CASES = [
    ("RBI cuts repo rate by 25 bps in surprise monetary policy move", "policy_intelligence"),
    ("Government unveils new AI Infrastructure push in Union Budget", "policy_intelligence"),  # "budget" hits policy first, by design (policy checked before theme)
    ("EV sales surge 40% year-on-year across major manufacturers", "theme_intelligence"),
    ("Government announces new PLI scheme for semiconductor makers", "theme_intelligence"),
]


@pytest.mark.parametrize("headline,expected_type", REAL_MATCH_CASES)
def test_keyword_still_matches_real_word_boundary(headline, expected_type):
    article_type, story_id, priority = select_article_type(_event(headline))
    assert article_type == expected_type, (
        f"Word-boundary fix broke a real match: {headline!r} -> {article_type}, expected {expected_type}"
    )


def test_ai_theme_matches_on_its_own_word():
    # "AI" as a standalone word (not inside a longer token) must still match
    # _THEME_KW — this is the real, intended trigger the false-positive
    # tests above are protecting, not disabling.
    article_type, _, _ = select_article_type(_event("AI Infrastructure theme gains momentum among investors"))
    assert article_type == "theme_intelligence"
