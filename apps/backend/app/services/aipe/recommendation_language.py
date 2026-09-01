"""
Recommendation Language Validator — P0-CD2 Generation Containment (2026-09-01).

Deterministic, field/context-aware scan for MarketRipple-authored
investment-instruction language in generated articles. content_templates.py's
prompt changes are the first line of defense; this is the required backstop
the CD2 authorization explicitly asked for — prompt instructions alone were
already proven insufficient once (P0-D: the exact instructions that asked
"What to do: Watch? Buy? Sell? Wait?" were producing exactly that language on
every call, not drifting into it occasionally).

Field-aware, not blanket: only the fields whose entire purpose is stating
MarketRipple's own forward-looking conclusion — opportunities[] and
key_takeaway, the "highest-risk generated fields" the authorization named —
are held to the strict policy. Narrative/explanatory fields (what_happened,
why_it_matters, executive_summary, faqs[].answer) are NOT scanned here: they
are legitimately allowed to report facts that use these same words in a
non-instructional sense ("the company announced a share buyback", "analyst X
rated the stock Strong Buy") — see the adversarial test suite for the exact
cases this module must not reject.

Fail-closed, not fail-soft: this module never rewrites or strips an unsafe
phrase to make it "sound safer" — it only reports violations. The caller
(quality_validator.py's required check) decides not to publish. Silently
sanitizing would hide a real generation-policy failure instead of surfacing
it, which is exactly the failure mode the CD2 authorization said to avoid.
"""
from __future__ import annotations

import re
from typing import Any

# The fields whose entire purpose is MarketRipple's own forward-looking
# conclusion. ANY match here is a violation, including text that reads like
# an attributed quote — a field that exists to state MarketRipple's own
# opportunity/takeaway has no legitimate reason to contain someone else's
# buy/sell language either; a real attribution belongs in why_it_matters
# (unscanned), not here.
_HIGH_RISK_SCALAR_FIELDS: tuple[str, ...] = ("key_takeaway",)
_HIGH_RISK_LIST_FIELDS: dict[str, tuple[str, ...]] = {
    "opportunities": ("title", "description"),
}

# Word-boundary regexes, deliberately narrow to avoid the exact adversarial
# false-positive cases named in the CD2 authorization (e.g. "buy" must never
# match inside "buyback"; "short" must never match "short-term").
_PATTERNS: list[re.Pattern[str]] = [re.compile(p, re.IGNORECASE) for p in [
    r"\bbuy\b(?!\s*-?\s*back)",                                   # "buy" but not "buyback"/"buy-back"
    r"\bsell\b",
    r"(?:^|\bconsider\s+|\binvestors?\s+should\s+)short(?:ing)?\s+(?!term\b)\w",  # "Short XYZ", not "short term"/"short-term"
    r"\baccumulat(?:e|ing)\b",
    r"\breduc(?:e|ing)\b.{0,20}\b(position|stake|holding|weight(?:age)?)\b",
    r"\bexit(?:ing)?\b.{0,20}\b(position|stake|holding)\b",
    r"\b(?:enter|initiate|take)\s+a\s+position\b",
    r"\benter(?:ing)?\s+(?:the\s+stock|now)\b",
    r"\btarget\s+price\b",
    r"\bstop[\s-]?loss\b",
    r"\bbook(?:ing)?\s+profits?\b",
    r"\boverweight\b",
    r"\bunderweight\b",
    r"\bdip[\s-]?buy(?:ing)?\b",
    r"\bswing[\s-]?buy\b",
    r"\bconsider\s+buying\b",
    r"\binvestors?\s+should\s+buy\b",
    r"\bgood\s+entry\s+point\b",
    r"\bpotential\s+entry\b",
    r"\ba\s+buying\s+opportunity\b",
    r"\bstrong\s+buy\b",
    r"\blikely\s+winner\b",
    r"\blikely\s+loser\b",
]]


def _find_violations(text: str) -> list[str]:
    if not text:
        return []
    return [m.group(0) for pat in _PATTERNS if (m := pat.search(text))]


def scan_recommendation_language(article: dict[str, Any]) -> list[str]:
    """Scan the high-risk fields of a generated article for MarketRipple-
    authored recommendation language. Returns a list of violation strings
    (empty = clean). Read-only — never rewrites `article` in place."""
    errors: list[str] = []

    for field in _HIGH_RISK_SCALAR_FIELDS:
        val = article.get(field)
        if isinstance(val, str):
            for hit in _find_violations(val):
                errors.append(f"RECOMMENDATION_LANGUAGE: {field} contains {hit!r}")

    for field, keys in _HIGH_RISK_LIST_FIELDS.items():
        for i, item in enumerate(article.get(field) or []):
            if not isinstance(item, dict):
                continue
            for key in keys:
                val = item.get(key)
                if isinstance(val, str):
                    for hit in _find_violations(val):
                        errors.append(f"RECOMMENDATION_LANGUAGE: {field}[{i}].{key} contains {hit!r}")

    return errors
