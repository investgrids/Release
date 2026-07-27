"""
Research Session Memory (Phase 1.7) — resolves natural-language follow-ups
against the CLIENT-HELD session context (companies/sectors/etc. already
discussed this browser session — see the frontend's sessionStorage-backed
hook, never persisted server-side, never merged across sessions or users).

Two jobs, both deterministic, both BEFORE any LLM call (per the spec's own
performance rule — "Context resolution should happen before LLM
invocation"):

1. `check_ambiguous_group()` — "Compare with Tata" names a conglomerate,
   not a company. Rather than guess which Tata entity the model should
   discuss (silently wrong half the time), this returns real candidates so
   the frontend can ask. Reuses the exact conglomerate-prefix families
   found live in last session's alias-collision audit (Tata/Adani/Bajaj/
   HDFC/ICICI/Godrej/Jindal/...) — computed from the real universe, not a
   hand-maintained guess list that goes stale.

2. `resolve_context()` — merges session-held companies/sectors into this
   query's own extracted entities when (and only when) the query looks
   like it's continuing an existing discussion rather than starting a new
   one: no companies of its own plus referential language ("them", "it",
   "which is"), or exactly one new company plus comparison-shaped language
   ("what about X"). A query that's already fully self-contained (2+ of
   its own companies, or no referential/comparison signal at all) is left
   untouched — conservative by design, matching the spec's "never guess."
"""
from __future__ import annotations

import re

_REFERENTIAL_RE = re.compile(
    r"\b(them|it|this|that|those|these|which (?:is|one|company|stock)|"
    r"what about|how about|and (?:the other|others)|compared? to (?:it|this|them))\b",
    re.IGNORECASE,
)
_COMPARISON_RE = re.compile(
    r"\bvs\.?\b|\bversus\b|\bcompare\b|\bbetter\b|\bsafer\b|\bswitch\b|\binstead of\b",
    re.IGNORECASE,
)

_GENERIC_STOP = {
    "ltd", "limited", "the", "india", "co", "company", "corporation", "of", "and",
    "industries", "industry", "services", "service", "group", "holdings", "enterprises",
    "power", "energy", "finance", "financial", "capital", "investment", "investments",
}


def _group_prefixes() -> dict[str, list[dict]]:
    """Groups the real universe by first significant word of company name —
    families with 3+ real members are genuinely ambiguous if a user names
    only the family. Recomputed from live data (not hardcoded), same
    principle as last session's alias-collision audit."""
    from app.api.companies import _NSE_UNIVERSE

    groups: dict[str, list[dict]] = {}
    for co in _NSE_UNIVERSE:
        words = [w for w in re.sub(r"[.,()&]", " ", co["name"]).split() if w.lower() not in _GENERIC_STOP]
        if not words:
            continue
        prefix = words[0].lower()
        if len(prefix) < 3:
            continue
        groups.setdefault(prefix, []).append(co)
    return {k: v for k, v in groups.items() if len(v) >= 3}


_AMBIGUOUS_GROUPS_CACHE: dict[str, list[dict]] | None = None


def _ambiguous_groups() -> dict[str, list[dict]]:
    global _AMBIGUOUS_GROUPS_CACHE
    if _AMBIGUOUS_GROUPS_CACHE is None:
        _AMBIGUOUS_GROUPS_CACHE = _group_prefixes()
    return _AMBIGUOUS_GROUPS_CACHE


def check_ambiguous_group(query: str, entities: dict) -> dict | None:
    """Returns {"term": str, "candidates": [{"symbol","name"}]} when the
    query names a conglomerate family but didn't resolve to one specific
    company — None otherwise (including when the query names a specific
    member, e.g. "Tata Motors").

    Deliberately does NOT trust entities["companies"] alone to decide
    "already resolved": found live that the fuzzy pass's own generic-word
    stripping (see entities._strip_generic) can silently resolve a BARE
    family name to one specific member — "Tata" alone matched TCS at
    ratio 1.0, because stripping "Consultancy" as a generic suffix word
    left "tata" vs "tata" with nothing left to distinguish them. So this
    checks the RAW QUERY TEXT for one of each candidate's own distinguishing
    words (e.g. "Motors", "Steel", "Consultancy") — only that counts as a
    real disambiguation, not whatever the fuzzy pass happened to pick."""
    words = {w.lower() for w in re.findall(r"[A-Za-z]+", query) if len(w) >= 3}
    groups = _ambiguous_groups()
    for word in words:
        candidates = groups.get(word)
        if not candidates:
            continue
        distinguishing_present = any(
            any(w.lower() in words for w in re.sub(r"[.,()&]", " ", c["name"]).split()[1:] if w.lower() not in _GENERIC_STOP and len(w) >= 3)
            for c in candidates
        )
        if distinguishing_present:
            continue
        return {
            "term": word.title(),
            "candidates": [{"symbol": c["symbol"], "name": c["name"]} for c in candidates[:6]],
        }
    return None


def resolve_context(query: str, entities: dict, session_context: dict | None) -> tuple[dict, dict]:
    """Returns (possibly-enriched entities, context_used) — context_used
    records exactly what was pulled from session state so the response can
    honestly report it (the "Using current research context" indicator),
    rather than the frontend having to guess what happened server-side."""
    context_used: dict = {"companies": [], "sectors": []}
    if not session_context:
        return entities, context_used

    own_companies = list(entities.get("companies") or [])
    session_companies = [s for s in (session_context.get("companies") or []) if s not in own_companies]
    if not session_companies:
        return entities, context_used

    is_referential = bool(_REFERENTIAL_RE.search(query))
    is_comparison_shaped = bool(_COMPARISON_RE.search(query))

    should_merge = False
    if not own_companies and (is_referential or is_comparison_shaped):
        # "Which is safer?" / "What about exports?" — nothing of its own,
        # clearly continuing the existing discussion.
        should_merge = True
    elif len(own_companies) == 1 and (is_referential or is_comparison_shaped):
        # "What about BEML?" (referential) or "BEML vs the others" (compare-
        # shaped) against a prior HAL vs BEL discussion — both phrasings
        # mean the same thing here, so both trigger the merge.
        should_merge = True

    if not should_merge:
        return entities, context_used

    # Recency-weighted, not the full session history — "what about BEML"
    # should pair BEML with the MOST RECENTLY discussed company/pair, not
    # every company mentioned all session, or a 10-query-old detour stays
    # stuck to every later question.
    merged = list(dict.fromkeys(own_companies + session_companies[-2:]))
    entities = {**entities, "companies": merged}
    context_used["companies"] = session_companies[-2:]

    own_sectors = set(entities.get("sectors") or [])
    session_sectors = [s for s in (session_context.get("sectors") or []) if s not in own_sectors]
    if should_merge and session_sectors:
        entities = {**entities, "sectors": list(entities.get("sectors") or []) + session_sectors[:1]}
        context_used["sectors"] = session_sectors[:1]

    return entities, context_used
