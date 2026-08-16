"""
Phase 5A.11 — AI Search date safety. The Phase 5A audit found the
earnings_preview intent's prompt overlay instructed the LLM to produce
a "results date" in its "timeline" field with zero backing data (no
trustworthy forward-looking earnings-date source exists anywhere in
this codebase, confirmed by audit) — a live hallucination risk, not a
hypothetical one. Fixed at the prompt level: the overlay now explicitly
forbids inventing/inferring a date and requires the honest fallback
"The next results date is not verified yet." when no sourced date is
present in the evidence context.
"""
from __future__ import annotations

from app.services.ai_search.enrichment import _intent_overlay


def test_earnings_preview_overlay_forbids_inventing_a_date():
    overlay = " ".join(_intent_overlay({"intent": "earnings_preview"}).split())   # normalize wrapped whitespace
    assert "not verified yet" in overlay
    assert "NEVER invent, infer, or estimate" in overlay


def test_earnings_preview_overlay_no_longer_demands_a_results_date_unconditionally():
    overlay = _intent_overlay({"intent": "earnings_preview"})
    # The old, unsafe instruction — literal demand for a date with no
    # conditioning on whether one is actually known — must be gone.
    assert '"timeline" must show: results date, pre-result window, post-result action.' not in overlay


def test_earnings_preview_overlay_still_covers_the_rest_of_its_original_guidance():
    """The date-safety fix must not have collateral-damaged the
    overlay's other, still-legitimate instructions (consensus
    expectations, miss/beat scenarios, etc.)."""
    overlay = _intent_overlay({"intent": "earnings_preview"})
    assert "consensus expectations" in overlay
    assert "beat vs miss thresholds" in overlay
    assert "pre-result window" in overlay
