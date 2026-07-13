"""
Quality Validation Engine — every article must pass before publishing.

Checks (in order):
  1. has_headline          — required
  2. has_executive_summary — required
  3. has_key_takeaway      — required
  4. confidence_sufficient — score >= 0.65
  5. min_length            — what_happened >= 100 chars
  6. has_companies         — at least 1 company affected
  7. has_opportunities     — at least 1 opportunity
  8. has_faqs              — at least 1 FAQ
  9. has_seo_fields        — seo_title + meta_description present
 10. seo_score_sufficient  — >= 60

Required checks (failure → do not publish): 1, 2, 3, 4, 5
Soft checks (failure → lower quality_score but still publish): 6-10
"""
from __future__ import annotations

from typing import Any


def validate(article: dict[str, Any], seo_score: int) -> tuple[bool, dict[str, Any], float]:
    """
    Returns (passed: bool, results: dict, quality_score: float 0-1).
    passed = True only when ALL required checks pass.
    """
    results: dict[str, Any] = {}
    passed_required = 0
    total_required = 5
    passed_soft = 0
    total_soft = 5

    # ── Required checks ───────────────────────────────────────────────────────
    results["has_headline"] = bool(article.get("headline"))
    results["has_executive_summary"] = bool(article.get("executive_summary"))
    results["has_key_takeaway"] = bool(article.get("key_takeaway"))
    results["confidence_sufficient"] = float(article.get("confidence_score") or 0) >= 0.65
    what_happened = article.get("what_happened") or ""
    results["min_length"] = len(what_happened) >= 100

    for check in ["has_headline", "has_executive_summary", "has_key_takeaway",
                  "confidence_sufficient", "min_length"]:
        if results[check]:
            passed_required += 1

    # ── Soft checks ───────────────────────────────────────────────────────────
    results["has_companies"] = len(article.get("companies_affected") or []) >= 1
    results["has_opportunities"] = len(article.get("opportunities") or []) >= 1
    results["has_faqs"] = len(article.get("faqs") or []) >= 1
    results["has_seo_fields"] = bool(article.get("seo_title")) and bool(article.get("meta_description"))
    results["seo_score_sufficient"] = seo_score >= 60

    for check in ["has_companies", "has_opportunities", "has_faqs",
                  "has_seo_fields", "seo_score_sufficient"]:
        if results[check]:
            passed_soft += 1

    passed = passed_required == total_required
    quality_score = round(
        (passed_required / total_required) * 0.7 +
        (passed_soft / total_soft) * 0.3,
        3,
    )
    return passed, results, quality_score
