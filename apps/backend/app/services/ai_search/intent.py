"""
Deterministic comparison detection — no LLM call, per the approved Phase 1A/1B
fix. V2's own `_detect_decision_intent` (ai_search_service.py:544) already
extracts holding/target via its own regex and sets `is_comparison = bool(holding)
and bool(target)` — but the benchmark proved this misses real comparison
phrasings (verified live: 6 of 13 "Company Comparison" category questions in
the Golden 200 run were misrouted to the company specialist because V2's
extraction never resolved a holding/target pair for phrasings like "Between
X and Y, which is the safer bet?" or "X and Y — which has less debt?").

This module is a second, broader opinion: it (a) recognizes many more
comparison-shaped phrasings via pattern matching, and (b) when V2's own
holding/target extraction comes up empty, falls back to our own entity
extraction (entities.py, which has fuzzy-matching and the expanded 34-company
universe V2's simple regex extraction doesn't benefit from) to identify which
two real companies are being compared. A query only needs ONE of these two
signals (V2's own is_comparison OR this module's) to route to the comparison
specialist — see pipeline.py's _route_specialist.
"""
from __future__ import annotations

import re

# Every phrasing named in the approved fix, as regex fragments. Deliberately
# broad — a false positive here just means a comparison-shaped question with
# only one real entity gets the comparison specialist's schema (which
# degrades reasonably, see comparison.py's symbol_hint handling for a single
# unresolved entity), while a false negative silently loses the whole
# specialist. Bias toward recall.
_COMPARISON_PATTERNS = re.compile(
    r"\b(?:vs\.?|versus)\b|"
    r"\bwhich\s+is\s+better\b|"
    r"\bwhich\s+(?:one\s+)?(?:has|offers|is)\s+(?:a\s+)?(?:better|stronger|higher|lower|less|fewer|worse|safer)\b|"
    r"\bcompare[sd]?\b|\bcomparison\b|\bdifference\s+between\b|"
    r"\bsafer\s+(?:investment|bet|choice)\b|"
    r"\bbetter\s+(?:buy|choice|pick|option|investment)\b|"
    r"\bbetter\s+for\s+\w|"
    r"\bswitch(?:ing)?\s+from\b|\bmove(?:ing)?\s+from\b|"
    r"\breplace(?:ing)?\b|"
    r"\bworth\s+buying\s+instead\b|\balternative\s+to\b|"
    r"\binstead\s+of\b|"
    r"\bor\b.{0,40}\?|"  # "X or Y?" — the trailing "?" narrows this broad token to genuine either/or questions
    r"\bcompared\s+(?:to|with)\b|"
    r"\bagainst\b|"
    r"\bbetween\s+\w.+\s+and\s+\w",
    re.IGNORECASE,
)


def looks_like_comparison(query: str) -> bool:
    """Pure text-pattern check — does this query's phrasing look
    comparison-shaped, independent of whether we can cleanly extract which
    two entities are being compared."""
    return bool(_COMPARISON_PATTERNS.search(query))


def resolve_comparison(query: str, intent_data: dict, entities: dict) -> tuple[bool, str | None, str | None]:
    """Returns (is_comparison, holding, target). Prefers V2's own extraction
    when it succeeded (holding_is_commodity/holding_is_sector flags and the
    horizon/risk parsing all live on intent_data and are worth keeping when
    available); falls back to our own entity resolution — grounded in the
    expanded, fuzzy-matched company universe — when V2's regex came up empty
    but this query is still clearly comparison-shaped and names 2+ real
    companies."""
    v2_holding = intent_data.get("holding")
    v2_target = intent_data.get("target")
    if intent_data.get("is_comparison") and v2_holding and v2_target:
        return True, v2_holding, v2_target

    if not looks_like_comparison(query):
        return False, None, None

    matches = entities.get("company_matches") or []
    if len(matches) >= 2:
        # Order by position of first mention in the query text, not
        # detection order, so "holding" genuinely reads as "the first-named
        # entity" the way a human would parse the sentence.
        def _first_pos(m: dict) -> int:
            needle = (m.get("matched_text") or m.get("name") or m.get("symbol") or "").lower()
            idx = query.lower().find(needle)
            return idx if idx >= 0 else 10_000

        # P5 Stage 4 — defense in depth, independent of entities.py's own
        # false-positive fix: an exact/alias match names a real,
        # unambiguous company; a fuzzy match is inherently less trustworthy
        # (it's a similarity guess, however well-tuned the matcher is).
        # An exact match should never be displaced from the 2 kept entities
        # by a fuzzy one that merely happens to appear earlier in the
        # sentence — found live: "continue" (fuzzy match -> CONCOR)
        # appearing before "BEL"/"HAL" (both exact) in "Should I continue
        # holding BEL or switch to HAL?" pushed BEL, the query's actual
        # subject, out of the kept pair. Position still breaks ties within
        # the same confidence tier.
        def _sort_key(m: dict) -> tuple[int, int]:
            tier = 0 if m.get("match_type") == "exact" else 1
            return (tier, _first_pos(m))

        ordered = sorted(matches, key=_sort_key)
        return True, ordered[0]["name"], ordered[1]["name"]

    # Comparison-shaped text but fewer than 2 real companies resolved (e.g.
    # a sector-vs-sector or commodity-vs-equity comparison V2's own
    # commodity/sector detection would normally catch) — not this module's
    # job to guess further; let the existing V2 signal (already checked
    # above) be the only source of truth for those cases.
    return False, None, None
