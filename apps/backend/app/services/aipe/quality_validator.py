"""
Quality Validation Engine — every article must pass before publishing.

Checks (in order):
  1. has_headline          — required
  2. has_executive_summary — required
  3. has_key_takeaway      — required
  4. confidence_sufficient — score >= 0.65
  5. min_length            — what_happened >= 100 chars
  6. no_unfilled_placeholders — required
  7. has_companies         — at least 1 company affected
  8. has_opportunities     — at least 1 opportunity
  9. has_faqs              — at least 1 FAQ
 10. has_seo_fields        — seo_title + meta_description present
 11. seo_score_sufficient  — >= 60

Required checks (failure → do not publish): 1, 2, 3, 4, 5, 6
Soft checks (failure → lower quality_score but still publish): 7-11
"""
from __future__ import annotations

import re
from typing import Any

# Catches literal unfilled template placeholders the LLM sometimes echoes
# instead of resolving (e.g. "On [specific date], tensions escalated..." —
# a real generation the model produced despite never being given that
# bracket syntax anywhere in the prompt; it's a journalism-template pattern
# from training data, not something a prompt fix reliably prevents). This
# is a content-shaped safety net, not a prompt fix — deterministic
# detection at the gate that already blocks publication on quality failure,
# rather than trying to prevent every way an LLM might do this.
_PLACEHOLDER_RE = re.compile(r"\[[a-zA-Z][a-zA-Z0-9 ,'/-]{2,40}\]")
_PLACEHOLDER_FIELDS = ("headline", "executive_summary", "key_takeaway", "why_it_matters", "what_happened")
# opportunities/risks/faqs/what_to_watch_next are LLM-authored prose too, and
# were never checked here — a production sweep of 100 live articles found no
# leaks yet, but the gap is real (title/description/question/answer are the
# same free-text shape as the fields already covered above).
_PLACEHOLDER_LIST_FIELDS = ("opportunities", "risks", "faqs")
_PLACEHOLDER_LIST_TEXT_KEYS = ("title", "description", "question", "answer")


def _has_unfilled_placeholder(article: dict[str, Any]) -> bool:
    for field in _PLACEHOLDER_FIELDS:
        val = article.get(field)
        if isinstance(val, str) and _PLACEHOLDER_RE.search(val):
            return True
    for field in _PLACEHOLDER_LIST_FIELDS:
        for item in (article.get(field) or []):
            if not isinstance(item, dict):
                continue
            for key in _PLACEHOLDER_LIST_TEXT_KEYS:
                val = item.get(key)
                if isinstance(val, str) and _PLACEHOLDER_RE.search(val):
                    return True
    for item in (article.get("what_to_watch_next") or []):
        if isinstance(item, str) and _PLACEHOLDER_RE.search(item):
            return True
    return False


def validate(article: dict[str, Any], seo_score: int) -> tuple[bool, dict[str, Any], float]:
    """
    Returns (passed: bool, results: dict, quality_score: float 0-1).
    passed = True only when ALL required checks pass.
    """
    results: dict[str, Any] = {}
    passed_required = 0
    total_required = 6
    passed_soft = 0
    total_soft = 5

    # ── Required checks ───────────────────────────────────────────────────────
    results["has_headline"] = bool(article.get("headline"))
    results["has_executive_summary"] = bool(article.get("executive_summary"))
    results["has_key_takeaway"] = bool(article.get("key_takeaway"))
    results["confidence_sufficient"] = float(article.get("confidence_score") or 0) >= 0.65
    what_happened = article.get("what_happened") or ""
    results["min_length"] = len(what_happened) >= 100
    results["no_unfilled_placeholders"] = not _has_unfilled_placeholder(article)

    for check in ["has_headline", "has_executive_summary", "has_key_takeaway",
                  "confidence_sufficient", "min_length", "no_unfilled_placeholders"]:
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
