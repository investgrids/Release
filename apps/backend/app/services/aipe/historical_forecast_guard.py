"""
Historical-Outcome Forecast-Collapse Guard — P0-CD3-B historical-outcome
containment (2026-09-02).

CD3-A's read-only audit found a live production specimen
(rbi-rate-pauses-banking-investors-historic, published 2026-08-08, never
regenerated) where a real historical outcome ("banking stocks typically
rebound after a rate hold") was silently converted, in the same sentence,
into unmarked forward-looking instruction: "Use policy-driven market
dips to add to high-quality banking stocks, as they typically rebound
and outperform over the next 3-6 months." Confirmed to match NONE of
recommendation_language.py's existing patterns — "add to X stocks"
contains neither "buy" nor "accumulate" nor any other blacklisted verb.

This is deliberately NOT another phrase added to that blacklist. An
endless enumeration (buy -> accumulate -> favor -> preferred -> add to
-> increase exposure -> ...) is not a real architecture — recommendation_
language.py's own sibling gap (comparison articles' "favor X over Y",
found in the same CD3-A audit) already proved that pattern doesn't
converge. Per the CD3-B decision, this is a producer-level SEMANTIC
guard instead: the failure shape is structural, not lexical.

The contract: historical evidence may authorize a retrospective
statement ("X rose/fell after Y in 2020") freely, in any tense, in any
field. It may NEVER, on its own, license a present-tense instruction or
forward expectation ("so add to X now", "expect X to outperform over the
next N months") — that requires separately identified CURRENT evidence,
which none of today's article types carry a field for. Until such a
field exists, ANY co-occurrence of a historical/habitual-pattern
connector ("historically", "typically", "tends to") with a forward-
looking action or expectation phrase ("add to", "expect to outperform",
"over the next N months") in the SAME SENTENCE of a high-risk field is
an unconditional violation — not a heuristic with a built-in exception,
because there is nothing yet for an exception to check against.

Deliberately NOT a blanket future-tense regex: "over the next 2 months"
or "should recover" alone, with no historical connector anywhere nearby,
is not flagged — plenty of legitimate forward-looking content (grounded
in a real current event, not a historical pattern) uses that phrasing.
Only the CO-OCCURRENCE with a historical/habitual connector in the same
sentence is the collapse this guard exists to catch.

Same scope as recommendation_language.py (key_takeaway + opportunities[]
— the fields whose entire purpose is MarketRipple's own forward-looking
conclusion), same fail-closed contract (reports violations, never
rewrites the article), for the same reason: silently sanitizing would
hide a real generation-policy failure instead of surfacing it.
"""
from __future__ import annotations

import re
from typing import Any

_HIGH_RISK_SCALAR_FIELDS: tuple[str, ...] = ("key_takeaway",)
_HIGH_RISK_LIST_FIELDS: dict[str, tuple[str, ...]] = {
    "opportunities": ("title", "description"),
}

# A historical/habitual-pattern connector — signals the sentence is
# describing what has happened before, not what is happening now.
_HISTORICAL_CONNECTOR = re.compile(
    r"\b("
    r"historically|typically|usually|"
    r"tend(?:s|ed)?\s+to|"
    r"in\s+(?:the\s+)?past(?:\s+cycles)?|"
    r"in\s+(?:similar\s+)?(?:past|prior)\s+events?|"
    r"based\s+on\s+past\s+performance|"
    r"has\s+historically|have\s+historically|"
    r"historical\s+pattern"
    r")\b",
    re.IGNORECASE,
)

# A forward-looking action or expectation phrase — on its own this is
# often legitimate (a real current event can license it); the violation
# is this co-occurring with _HISTORICAL_CONNECTOR in the same sentence.
_FORWARD_CLAIM = re.compile(
    r"\b("
    r"add\s+to|"
    r"increase\s+(?:your\s+)?exposure|"
    r"expect(?:s|ed)?\s+to|"
    r"should\s+(?:rebound|rise|fall|recover|outperform|underperform)|"
    r"will\s+(?:likely\s+)?(?:rebound|rise|fall|recover|outperform|underperform)|"
    r"(?:outperform|underperform|rebound|recover)\s+over\s+the\s+next|"
    r"over\s+the\s+next\s+\d+[\s-]*(?:day|week|month|year)s?"
    r")\b",
    re.IGNORECASE,
)


def _split_sentences(text: str) -> list[str]:
    # Deliberately simple — only needs to separate independent clauses
    # well enough to check same-sentence co-occurrence, not a real
    # sentence tokenizer.
    return re.split(r"(?<=[.!?])\s+", text)


def _find_collapse(text: str) -> list[str]:
    if not text:
        return []
    return [
        s.strip() for s in _split_sentences(text)
        if _HISTORICAL_CONNECTOR.search(s) and _FORWARD_CLAIM.search(s)
    ]


def scan_historical_forecast_collapse(article: dict[str, Any]) -> list[str]:
    """Scan the high-risk fields for a historical/habitual-pattern
    connector co-occurring with a forward-looking claim in the same
    sentence. Returns a list of violation strings (empty = clean).
    Read-only — never rewrites `article` in place."""
    errors: list[str] = []

    for field in _HIGH_RISK_SCALAR_FIELDS:
        val = article.get(field)
        if isinstance(val, str):
            for hit in _find_collapse(val):
                errors.append(f"HISTORICAL_FORECAST_COLLAPSE: {field} contains {hit!r}")

    for field, keys in _HIGH_RISK_LIST_FIELDS.items():
        for i, item in enumerate(article.get(field) or []):
            if not isinstance(item, dict):
                continue
            for key in keys:
                val = item.get(key)
                if isinstance(val, str):
                    for hit in _find_collapse(val):
                        errors.append(f"HISTORICAL_FORECAST_COLLAPSE: {field}[{i}].{key} contains {hit!r}")

    return errors
