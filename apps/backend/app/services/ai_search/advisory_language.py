"""
Shared, deterministic recommendation-language scanner — the one place
every real serving surface (safety_gate.py for the main V3 response,
market_pulse_safety.py for Market Pulse, refine_safety.py for Refine
Analysis) derives its "does this generated text contain advisory
language" check from, so the three can never independently drift.

Deliberately has NO dependency on the aev2/ package (a real coupling
found in review, 2026-09-21: safety_gate.py — which protects every
production route regardless of AEV2 mode and whose own docstring already
claimed to be "deliberately independent of AEV2" — imported its scan
function from aev2.language_gate, meaning a module load of safety_gate.py
transitively required the unfinished aev2/ package to exist at all. This
module is the fix: a neutral, standalone location none of the 3 callers
above need aev2/ for.

Wraps app.services.aipe.recommendation_language's proven, already-tested
pattern list (find_violations()) — same adversarial-case guarantees (buy
vs buyback, short vs short-term) that module already carries test
coverage for — plus one addition this codebase's various callers all
independently needed: a context-aware "hold" check.

Context-aware hold (2026-09-21, second pass): a bare `\\bhold\\b` check
(the AEV2-only precedent this replaces for non-AEV2 callers) is too
blunt — "RBI decided to hold rates", "prices may hold steady", and "the
company will hold its AGM" are all factual, non-advisory uses of the
same word that a bare-word ban would incorrectly degrade. Recommendation
language is a specific PHRASING ("should hold X", "hold rating",
"continue holding"), not the bare word — is_advisory_hold() below
matches only those phrasings, never the word in isolation.
"""
from __future__ import annotations

import re

from app.services.aipe.recommendation_language import find_violations

# Deliberately a POSITIVE allowlist of advisory-shaped phrasings, not a
# bare word + an exclusion list — a factual usage ("hold rates", "hold
# steady", "hold its AGM/meeting/election/talks") simply never matches
# any of these, so no separate exclusion list is needed to keep it safe.
# (?:\s+\w+){0,3} between "hold(ing)" and the noun tolerates real
# intervening words ("hold THEIR EXISTING position") — same fix pattern
# decision_intent.py already uses for filler-word tolerance elsewhere in
# this codebase; found live via an adversarial test case this session.
_ADVISORY_HOLD_PATTERNS = re.compile(
    r"\bshould\s+hold\b|"
    r"\b(?:continue|keep)\s+holding\b|"
    r"\bhold(?:ing)?\b(?:\s+\w+){0,3}\s+(?:stock|position|shares?)\b|"
    r"\bhold\s+on\s+to\b|"
    r"\bhold\s+(?:rating|recommendation|call)\b|"
    r"\b(?:is|as|remains?|stays?)\s+a\s+hold\b|"
    r"\brate[ds]?\s+(?:it|this)\s+(?:as\s+)?(?:a\s+)?hold\b|"
    r"\bhold\s+for\s+now\b|"
    r"\bwe\s+recommend\b(?:\s+\w+){0,3}\s+hold\b",
    re.IGNORECASE,
)


def is_advisory_hold(text: str) -> bool:
    """True only for phrasings that recommend holding a position — never
    for the bare word "hold" used factually (rates, prices, meetings,
    talks, elections). See module docstring for the adversarial cases
    this distinction is built against."""
    if not text:
        return False
    return bool(_ADVISORY_HOLD_PATTERNS.search(text))


def scan(text: str) -> list[str]:
    """Every violation found in `text` — the shared proven pattern list
    plus the context-aware hold check above. Never called on an
    immutable source title/label/market-data value; only on this
    platform's own generated prose."""
    if not text:
        return []
    hits = list(find_violations(text))
    if is_advisory_hold(text):
        hits.append("hold")
    return hits
