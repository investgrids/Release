"""
Unit tests for aev2_benchmark.py's pure scoring functions (2026-09-23).

Real bug this benchmark's own first run found in itself: score_degraded_
honesty required a top-level `degraded_reason` on every synthesis_
incomplete=True response, but Market Pulse's degraded state carries none
of the research shape's vocabulary at all (no investment_verdict, no
degraded_reason — see market_pulse.py's own docstring) — every
correctly-routed, honestly-degraded market_pulse response in the first
60-query run was flagged as a false "degraded honesty" failure. These
tests pin the fix directly.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from aev2_benchmark import score_advisory_safety, score_degraded_honesty, score_routing  # noqa: E402


def test_routing_pass_when_ui_mode_matches():
    result = {"ui_mode": "direct_company_research"}
    assert score_routing("direct_company_research", result)["pass"] is True


def test_routing_fail_when_ui_mode_differs():
    result = {"ui_mode": "portfolio_review"}
    scored = score_routing("switch_analysis", result)
    assert scored["pass"] is False
    assert "expected='switch_analysis'" in scored["detail"]


def test_routing_fail_distinguishes_early_shell_from_a_wrong_ui_mode():
    result = {"ui_mode": None, "degraded_reason": "unsupported_entity"}
    scored = score_routing("event_impact", result)
    assert scored["pass"] is False
    assert "early degraded shell" in scored["detail"]


def test_degraded_honesty_not_applicable_when_synthesis_succeeded():
    result = {"synthesis_incomplete": False}
    assert score_degraded_honesty(result) is None


def test_degraded_honesty_market_pulse_passes_without_degraded_reason():
    """The exact real bug this benchmark's own first run found: a
    correctly-degraded market_pulse response has no degraded_reason at
    all, and must not be scored a failure for lacking one."""
    result = {"type": "market_pulse", "synthesis_incomplete": True}
    scored = score_degraded_honesty(result)
    assert scored["pass"] is True


def test_degraded_honesty_research_shape_requires_degraded_reason():
    result = {"synthesis_incomplete": True, "investment_verdict": {}, "answer": {}}
    scored = score_degraded_honesty(result)
    assert scored["pass"] is False
    assert any("degraded_reason is missing" in issue for issue in scored["issues"])


def test_degraded_honesty_fails_on_a_fabricated_rating():
    result = {
        "synthesis_incomplete": True, "degraded_reason": "capacity",
        "investment_verdict": {"rating": "Positive"}, "answer": {},
    }
    scored = score_degraded_honesty(result)
    assert scored["pass"] is False
    assert any("rating='Positive'" in issue for issue in scored["issues"])


def test_degraded_honesty_passes_on_a_genuinely_honest_degraded_shape():
    result = {
        "synthesis_incomplete": True, "degraded_reason": "capacity",
        "investment_verdict": {"rating": "Not Applicable", "confidence": None, "top_picks": []},
        "answer": {"confidence": None},
    }
    scored = score_degraded_honesty(result)
    assert scored["pass"] is True
    assert scored["issues"] == []


def test_advisory_safety_reuses_the_real_safety_gate_function():
    # A clean response with no banned recommendation-language pattern.
    result = {"answer": {"bottom_line": "Reliance reported strong quarterly results."}}
    scored = score_advisory_safety(result)
    assert scored["pass"] is True


def test_advisory_safety_catches_a_real_violation():
    result = {"answer": {"bottom_line": "You should buy this stock immediately."}}
    scored = score_advisory_safety(result)
    assert scored["pass"] is False
    assert scored["violated_field"] is not None
