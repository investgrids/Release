"""
Regression suite — Intelligence Priority Queue (_compute_priority), offline.

No DB, no network, no LLM — pure function calls. Exists because a live
production audit (2026-08-10) found this function classifying 8 of 9
sampled Critical/High events as false positives: a naive `"rbi" in text`
substring check promoted every Triveni Turbine filing to Critical purely
because "Turbine" contains "rbi", and the "results"/"earnings" keyword
floor was firing on ordinary board-meeting boilerplate. This suite pins
down both the bug that shipped and the fix, so neither regresses.

Two kinds of case here, deliberately:
  - Cases with realistic urgency/importance (what the AI triage would
    actually assign) that should land High/Critical on the BASE score
    alone — the keyword floor is a safety net, not the primary mechanism.
  - Cases with the LOWER urgency/importance actually observed in the
    audit's real routine filings (urgency=8, importance=5 — the exact
    values Triveni Turbine scored), isolating whether the keyword floor
    itself is doing the right thing.
"""
from __future__ import annotations

import pytest

from app.services.intelligence.engine import _compute_priority


# ── The exact bug: a company name containing "rbi" as a substring ───────────
TURBINE_CASES = [
    'Triveni Turbine Limited has informed the Exchange regarding a press release dated August 10, 2026, titled "Investors  brief for Q1 FY27".',
    "Triveni Turbine Limited has informed the Exchange regarding Outcome of Board Meeting held on August 10, 2026 regarding Issuance of Corporate Guarantees.",
]


@pytest.mark.parametrize("headline", TURBINE_CASES)
def test_turbine_substring_no_longer_triggers_rbi_floor(headline):
    # Real observed production values for these exact filings.
    score, tier = _compute_priority(8, 5, None, headline)
    assert tier != "Critical", f"'Turbine' should not match the RBI keyword floor (got {score}/{tier})"
    # Base score from urgency=8, importance=5 alone is 65 (Medium) — the
    # keyword floor should have zero effect here, not just avoid Critical.
    assert score == 65
    assert tier == "Medium"


# ── Routine filings — weak keywords suppressed, tier stays low ──────────────
ROUTINE_CASES = [
    ("Board Meeting to be held on 11-Aug-2026 to consider routine matters", 8, 5),
    ("ANTARCTICA LIMITED has informed the Exchange about Board Meeting to be held on 17-Aug-2026 to inter-alia consider and approve the Unaudited Financial results", 8, 5),
    ("To consider and approve the financial results for the period ended Jun 30, 2026 and other business matters", 8, 5),
    ("Notice of Annual General Meeting to be held on August 31, 2026", 6, 5),
]


@pytest.mark.parametrize("headline,urgency,importance", ROUTINE_CASES)
def test_routine_filings_stay_low_or_medium(headline, urgency, importance):
    score, tier = _compute_priority(urgency, importance, None, headline)
    assert tier in ("Low", "Medium"), f"Routine filing wrongly elevated to {tier} ({score}): {headline!r}"


# ── Strong/specific keywords still elevate, even with routine framing ───────
def test_acquisition_elevates_even_when_routine_flagged():
    headline = "Board Meeting held to consider and approve the acquisition of XYZ Ltd"
    score, tier = _compute_priority(5, 5, None, headline)  # base would be 50 (Low) alone
    assert tier in ("High", "Critical"), f"Real acquisition signal suppressed by routine framing ({score}/{tier})"


def test_rbi_rate_decision_is_critical():
    score, tier = _compute_priority(9, 8, None, "RBI cuts repo rate by 25 bps in surprise monetary policy decision")
    assert tier == "Critical"


def test_rbi_circular_still_elevates():
    # Deliberately generous — any real RBI-sourced communication gets
    # visibility, since RBI mentions are rare and specific (unlike
    # "results"), so under-covering is the worse failure mode here.
    score, tier = _compute_priority(5, 5, None, "RBI issues circular on NBFC lending norms")
    assert tier in ("High", "Critical")


def test_sebi_regulatory_action_elevates():
    score, tier = _compute_priority(5, 5, None, "SEBI bars XYZ Ltd promoters from trading in regulatory crackdown")
    assert tier in ("High", "Critical")


def test_major_earnings_surprise_via_real_urgency():
    # Not routine-filing text (no board meeting/AGM framing) — a real
    # earnings beat headline, with the high urgency/importance the AI
    # triage would realistically assign to a genuine surprise.
    score, tier = _compute_priority(9, 8, None, "Company XYZ profit jumps 45%, results beat estimates significantly")
    assert tier in ("High", "Critical")


def test_major_acquisition_via_real_urgency():
    score, tier = _compute_priority(9, 8, None, "Company XYZ announces acquisition of ABC Ltd for $500M")
    assert tier in ("High", "Critical")


def test_regulatory_shock_via_real_urgency():
    score, tier = _compute_priority(9, 8, None, "SEBI orders halt in trading of XYZ Ltd shares pending investigation")
    assert tier in ("High", "Critical")


# ── Existing hard-critical keywords still work with word boundaries ─────────
@pytest.mark.parametrize("headline", [
    "Union Budget 2026: Key highlights for investors",
    "War fears grip markets as tensions escalate",
    "Federal Reserve holds rates steady, signals caution",
    "US Fed minutes show hawkish tilt",
])
def test_existing_critical_keywords_unaffected_by_word_boundary_fix(headline):
    score, tier = _compute_priority(4, 4, None, headline)
    assert tier == "Critical", f"Word-boundary fix broke an existing real match: {headline!r} -> {tier}"


# ── Keywords must not match as a substring anywhere else ────────────────────
@pytest.mark.parametrize("headline,forbidden_keyword", [
    ("Triveni Turbine Limited announces new plant", "rbi"),        # Turbine contains rbi
    ("Superbike sales rally on festive demand", "rbi"),            # Superbike contains rbi
    ("Software exports rise 12% for IT majors", "war"),            # Software contains war... actually check
])
def test_no_substring_false_positives(headline, forbidden_keyword):
    score, tier = _compute_priority(5, 5, None, headline)
    assert tier != "Critical", f"{forbidden_keyword!r} substring false-positive still present: {headline!r} -> {score}/{tier}"
