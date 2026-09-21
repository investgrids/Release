"""
AEV2's deterministic recommendation-language gate (errata §10, item from
the "AEV2 implementation prerequisite" correction, 2026-09-21).

Real defect this closes: a raw, never-shown-to-user LLM response for a
production HDFC Bank query contained the literal phrase "solid buy
candidate" — caught only because that response also happened to fail
JSON parsing and fall back to the degraded path. Prompt instructions
("never say Buy/Sell/Hold...") are NOT sufficient on their own — this
gate is the deterministic backstop, applied to every AEV2 field that
carries generated prose, after parsing and before assembly, regardless
of whether the prompt was followed.

Reuses app.services.aipe.recommendation_language's proven, already-tested
pattern list (find_violations()) rather than inventing a second one —
same adversarial-case guarantees (buy vs buyback, short vs short-term)
that module already carries test coverage for. Adds exactly one AEV2-only
pattern on top: a bare "hold" check. recommendation_language.py's own
list has no such pattern (Article V2's opportunities[]/key_takeaway
fields didn't need one) — but AEV2 must also never say "Hold", matching
the original ai_search prompt-level instruction
(specialists/base.py::research_framing_rules: "never say Buy, Sell,
Hold..."). Word-boundary safe by construction: \\bhold\\b does not match
"shareholding" (no boundary between "e" and "h" in that word), tested
explicitly below.

Fields this gate is required to cover (spec): the direct conclusion, why-
it-matters analysis, risks/invalidation text, and follow-up question
text. Never applied to immutable source titles (evidence[] items quoting
a real event/news headline verbatim) — those may legitimately contain a
third party's own words.

Fail-closed, never regenerates: on a violation, the field's text is
replaced wholesale with a fixed, honest fallback string — never
reworded, never retried against the LLM a second time (this pipeline's
"zero additional LLM calls" constraint applies here too), never partially
edited to "sound safer." The caller is told a violation occurred
(`had_violation=True`) so it can log accordingly; the ORIGINAL text is
never surfaced anywhere past this gate, not even in a sanitized form.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.aipe.recommendation_language import find_violations

# AEV2-only addition — see module docstring for why this isn't in the
# shared recommendation_language.py pattern list.
_HOLD_PATTERN = re.compile(r"\bhold\b", re.IGNORECASE)

# One fallback per field kind — honest, not a filler platitude. Never
# claims a specific reason (that would itself be an unverified claim);
# just states plainly that the generated text didn't pass the check.
FALLBACK_TEXT = {
    "direct_conclusion": "A direct conclusion could not be shown for this query because the generated text did not pass the research-language check.",
    "why_it_matters": "An analysis could not be shown for this query because the generated text did not pass the research-language check.",
    "risk": "A risk statement could not be shown because the generated text did not pass the research-language check.",
    "invalidates_if": "An invalidation condition could not be shown because the generated text did not pass the research-language check.",
    "watch_for": "A watch-for condition could not be shown because the generated text did not pass the research-language check.",
    "follow_up": "This follow-up question could not be shown because its generated text did not pass the research-language check.",
}


@dataclass
class GateResult:
    text: str
    had_violation: bool
    violations: list[str]  # the matched phrases, for internal telemetry only — never shown to a user


def scan(text: str) -> list[str]:
    """Every violation found in `text`, combining the shared, proven
    pattern list with AEV2's one additional bare-"hold" check. Never
    called on an immutable source title (see module docstring)."""
    if not text:
        return []
    hits = list(find_violations(text))
    if _HOLD_PATTERN.search(text):
        hits.append("hold")
    return hits


def gate(field_kind: str, text: str) -> GateResult:
    """Scan `text`; on any violation, replace it wholesale with the
    field's fixed fallback string. Never reworded, never retried, never
    partially edited — the original text is discarded entirely, kept
    only in the returned `violations` list for internal-only telemetry
    (never logged verbatim, never surfaced to a user — see telemetry.py)."""
    violations = scan(text)
    if violations:
        fallback = FALLBACK_TEXT.get(field_kind, FALLBACK_TEXT["why_it_matters"])
        return GateResult(text=fallback, had_violation=True, violations=violations)
    return GateResult(text=text, had_violation=False, violations=[])
