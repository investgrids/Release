"""
Regression suite — Tier 1: routing & entity-extraction, offline.

No DB, no network, no LLM — pure function calls against
_detect_decision_intent() and _match_companies(), the two functions that
decide which engine (Investment Verdict / Decision / AI Recommendation) a
query reaches at all. Runs in milliseconds and should gate every commit.

This tier exists because most of the real bugs found in this codebase's
Phase 2 push were routing gaps, not engine-logic bugs: a query would
silently fall to the ungrounded general path because a regex missed a
natural phrasing, not because the engine computing the answer was wrong.
A broad, cheap sweep across many phrasings catches exactly that class of
bug, before it ever needs a live LLM call to surface.

Tier 2 (tests/services/test_ai_search_engines_live.py) covers whether the
engines that DO get reached produce correct, non-fabricated output — this
tier only covers whether they get reached in the first place.
"""
from __future__ import annotations

import pytest

from app.services.ai_search_service import _detect_decision_intent, _match_companies


# ── Investment Verdict — single-entity queries that should reach the
# Investment Verdict Engine (i.e. NOT list_picks, since that's a different
# response shape entirely). ────────────────────────────────────────────────
INVESTMENT_VERDICT_QUERIES = [
    "Should I buy Reliance?",
    "Should I hold TCS?",
    "Should I sell SBI?",
]


@pytest.mark.parametrize("query", INVESTMENT_VERDICT_QUERIES)
def test_investment_verdict_routing(query):
    d = _detect_decision_intent(query)
    assert d["intent"] != "list_picks", f"{query!r} misrouted to list_picks"
    companies = _match_companies(query.lower())
    assert companies, f"{query!r} resolved zero real companies"


# ── Decision — genuine two-entity queries that must set is_comparison=True
# for the Decision Engine to run at all. Each of these phrasings was found
# broken at least once during this codebase's Phase 2 push (see the
# published audit report, §11) and fixed — this list is what verifies the
# fix holds. ─────────────────────────────────────────────────────────────
DECISION_QUERIES = [
    "HDFC or ICICI?",
    "Compare Infosys and TCS",
    "Switch from SBI to Axis",
    "Move investment from Reliance to ONGC",
]


@pytest.mark.parametrize("query", DECISION_QUERIES)
def test_decision_routing(query):
    d = _detect_decision_intent(query)
    assert d["is_comparison"] is True, (
        f"{query!r} did not set is_comparison — the Decision Engine will never run for it"
    )
    assert d.get("holding") and d.get("target"), f"{query!r} missing holding/target text"
    # Both sides must resolve to real, tradeable NSE symbols — this is the
    # check that would have caught the ITC-in-"switch" word-boundary bug.
    holding_syms = _match_companies((d["holding"] or "").lower())
    target_syms  = _match_companies((d["target"] or "").lower())
    assert holding_syms, f"{query!r}: holding text {d['holding']!r} resolved no real company"
    assert target_syms,  f"{query!r}: target text {d['target']!r} resolved no real company"


# ── Recommendations — queries that should reach the AI Recommendation
# Engine (intent == list_picks). "Pharma stocks" / "Power companies" are
# deliberately marked xfail: bare "<sector> stocks/companies" with no
# best/top/count qualifier does NOT currently route to list_picks (falls to
# the ungrounded general path instead) — a real, known, deliberately
# deferred gap, not a silent pass. See the audit report §11's "explicitly
# deferred" list. Flip to a plain assertion if this is ever fixed. ─────────
RECOMMENDATION_QUERIES_SUPPORTED = [
    "Best defence companies",
    "Top banking stocks",
]
RECOMMENDATION_QUERIES_KNOWN_GAP = [
    "Pharma stocks",
    "Power companies",
]


@pytest.mark.parametrize("query", RECOMMENDATION_QUERIES_SUPPORTED)
def test_recommendation_routing(query):
    d = _detect_decision_intent(query)
    assert d["intent"] == "list_picks", f"{query!r} routed to {d['intent']!r}, expected list_picks"
    assert d.get("pick_count", 0) >= 1


@pytest.mark.parametrize("query", RECOMMENDATION_QUERIES_KNOWN_GAP)
@pytest.mark.xfail(reason="bare '<sector> stocks/companies' with no best/top/count qualifier "
                           "isn't recognized as list_picks — deliberately deferred, see audit §11",
                    strict=True)
def test_recommendation_routing_known_gap(query):
    d = _detect_decision_intent(query)
    assert d["intent"] == "list_picks"


# ── Edge cases — must degrade honestly (no crash, no fabricated ticker),
# not necessarily route anywhere in particular. ─────────────────────────────
def test_edge_case_unknown_company():
    d = _detect_decision_intent("Should I buy XZQPLM?")
    assert d["intent"] == "buy"
    assert _match_companies("xzqplm") == [], "an unknown ticker must not resolve to a real company"


def test_edge_case_ambiguous_company():
    # "Tata" alone is a business house, not one specific listed entity —
    # correct behavior is to resolve nothing rather than guess.
    assert _match_companies("should i buy tata?") == [], (
        "an ambiguous business-house name must not silently resolve to one guessed company"
    )


def test_edge_case_typo():
    # Known, explicitly deferred gap (see audit §11) — typo tolerance needs
    # fuzzy matching or an LLM classifier, out of scope for a regex fix.
    # This test documents today's real (degraded but non-crashing) behavior
    # rather than silently passing either way.
    d = _detect_decision_intent("shoud i buy relaince ryt now")
    assert d["intent"] == "general"  # doesn't crash; just doesn't route specially
    assert _match_companies("shoud i buy relaince ryt now") == []


def test_edge_case_empty_query():
    d = _detect_decision_intent("")
    assert d["intent"] == "general"
    assert d["is_comparison"] is False
    assert _match_companies("") == []


def test_edge_case_multiple_companies():
    # A query naming several real companies without a clean 2-entity
    # switch/compare structure should still resolve every real company it
    # names via the robust full-text matcher, even though is_comparison may
    # reasonably stay False (this isn't a clean A-vs-B decision).
    companies = _match_companies("what about reliance, tcs, hdfc bank and infosys")
    for expected in ("RELIANCE", "TCS", "HDFCBANK", "INFY"):
        assert expected in companies, f"multi-company query missed {expected}"


def test_edge_case_word_boundary_false_positives():
    """
    Regression test for the specific word-boundary bug found live this
    session: short tickers/aliases matching inside unrelated words.
    "switch" contains "itc", "recent" contains "rec", "policy" contains
    "lic" — none of ITC / RECLTD / LICI are actually mentioned.
    """
    assert "ITC" not in _match_companies("switch from sbi to axis bank")
    assert "RECLTD" not in _match_companies("given the recent rbi policy changes")
    assert "LICI" not in _match_companies("given the recent rbi policy changes")
