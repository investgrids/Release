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

Reuses advisory_language.py's shared scan() (2026-09-21, third pass —
previously duplicated its own bare "hold" check independently, one of
three near-identical copies found in review alongside safety_gate.py and
market_pulse_safety.py; all three now derive from the one shared,
context-aware implementation). That module wraps
app.services.aipe.recommendation_language's proven, already-tested
pattern list (find_violations()) — same adversarial-case guarantees (buy
vs buyback, short vs short-term) — plus a context-aware "hold" check:
AEV2 must never say "Hold" as a recommendation (matching the original
ai_search prompt-level instruction, specialists/base.py::
research_framing_rules: "never say Buy, Sell, Hold..."), but a bare-word
ban would also degrade a legitimate mention of the RBI holding rates or
a company holding its AGM — see advisory_language.py's own docstring for
the adversarial cases this is built against.

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

from dataclasses import dataclass

from app.services.ai_search.advisory_language import scan as _shared_scan

# One fallback per field kind — honest, not a filler platitude. Never
# claims a specific reason (that would itself be an unverified claim);
# just states plainly that the generated text didn't pass the check.
FALLBACK_TEXT = {
    "direct_conclusion": "A direct conclusion could not be shown for this query because the generated text did not pass the research-language check.",
    "direct_comparison": "A direct comparison could not be shown for this query because the generated text did not pass the research-language check.",
    "what_happened": "A summary of what happened could not be shown because the generated text did not pass the research-language check.",
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
    """Thin wrapper over advisory_language.scan() — kept as its own named
    function here (rather than importing that one directly at call sites)
    so AEV2 code has one stable, AEV2-scoped entry point regardless of
    where the shared implementation lives. Never called on an immutable
    source title (see module docstring)."""
    return _shared_scan(text)


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
