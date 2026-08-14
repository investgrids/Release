"""Shared word-boundary-safe keyword matching.

The single mechanism every classifier in this codebase should use instead
of writing its own bare `kw in text` check — that pattern silently false-
positives on short keywords: "rbi" matches inside "turbine" ("triveni
tuRBIne industries"), "ai" matches inside "maintain"/"chairman"/"again"/
"retail"/"captain", "ev" matches inside "event"/"revenue"/"seven"/"every",
"pli" matches inside "compliance". Confirmed concretely for all of these in
the 2026-08 event-coverage audit.

app.services.intelligence.engine.compute_priority already had this fixed
correctly (its own module comment documents the incident: a real Triveni
Turbine filing was misclassified Critical this way); content_planner.py's
article-type keyword lists had the identical bug, unfixed, using the same
underlying vocabulary for a different question (which article template,
not how important). Rather than force those two genuinely different
classification axes into one merged keyword list, both now share this one
matching mechanism so the bug class can't reappear independently in each.
"""
from __future__ import annotations

import re


def compile_keywords(keywords: list[str]) -> list[re.Pattern]:
    """Word-boundary-wrapped patterns. Callers should lowercase their input
    text before matching (this codebase's existing convention) rather than
    relying on re.IGNORECASE here."""
    return [re.compile(r"\b" + re.escape(kw) + r"\b") for kw in keywords]


def matches_any(patterns: list[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)
