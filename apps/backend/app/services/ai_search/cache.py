"""
Three-layer cache for the AI Search V3 pipeline.

Layer 1 — Exact Query Cache: the literal query text, normalized
(lowercased/whitespace-collapsed) and hashed. This already existed in a
narrower form (pipeline.py's "v3:" prefix into ai_search_service._CACHE) —
formalized here as `exact_key()` so all three V3 entry points (POST
/search/v3, GET /search/stream, and the benchmark runner) share one
definition instead of three ad-hoc ones.

Layer 2 — Semantic Cache: many literal phrasings resolve to the same
canonical *intent shape* once entity extraction + comparison routing have
run — "HAL vs BEL", "Compare HAL and BEL", "Which is better: HAL or BEL?"
all resolve to the same two symbols under a comparison intent. Keyed on
that resolved shape rather than the raw text, so it can only be computed
AFTER intent/entity resolution (itself cheap and deterministic — no LLM
call). Checked as a second lookup when the exact key misses, and written
alongside the exact key whenever the query resolves cleanly to entities —
queries with no resolvable entity (pure macro/news questions) get no
semantic key at all rather than a coarse key that risks colliding two
unrelated questions.

Layer 3 — Component Cache: sub-results expensive enough to be worth
reusing independently of the full specialist response — company
intelligence, sector intelligence, historical precedents, policy
analysis, and the ripple graph — each with its own TTL reflecting how
fast that specific data actually goes stale (live prices: minutes;
historical precedent matches: hours). Lets "HAL vs BEL" and "Should I buy
HAL" reuse the same HAL company-intelligence fetch without either query
having hit Layer 1 or 2.

All three layers share the same underlying store V2 also uses (`_CACHE`,
defined below — P5 Stage 1 relocated it here from ai_search_service.py,
which now imports it back from this module; the proven, already-running
in-process mechanism didn't change, only which file owns the definition)
— namespaced by key prefix so nothing collides. This module adds no new
cache backend, no new eviction policy, nothing V2 didn't already have; it
only adds normalization (Layer 2) and finer-grained keys (Layer 3) on top
of the same dict.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Awaitable, Callable, TypeVar

import structlog

log = structlog.get_logger(__name__)

# P5 Stage 1 (2026-08-06): relocated here from ai_search_service.py — the
# one STATEFUL symbol in the whole extraction. V2 now imports this object
# back from here (`from app.services.ai_search.cache import _CACHE`) rather
# than defining it — both pipelines must mutate the exact same dict, not two
# separate instances that happen to share a name. Verified explicitly via
# object identity (id(_CACHE) compared across both import paths), not just
# "imports without error" — a silent split here would quietly break caching
# for one pipeline while everything else looked fine.
_CACHE: dict[str, tuple[float, Any]] = {}

T = TypeVar("T")

EXACT_TTL = 1800      # 30 min — matches V2's existing full-response cache TTL
SEMANTIC_TTL = 1800   # same window; a coarser key, not a longer-lived one

# Per-component TTLs — independent of the 30-min full-response TTL above.
# A company's story/announcements/valuation genuinely goes stale faster
# than a historical-precedent match does, so each gets its own honest window
# rather than one blanket duration.
COMPONENT_TTL = {
    "company": 900,       # 15 min — story/announcements/valuation shift intraday
    "sector": 300,         # 5 min — sector %-change is live price data
    "historical": 21600,  # 6 hr — precedent matches don't move intraday
    "policy": 1200,        # 20 min
    "graph": 900,           # 15 min — matches "company", its main input
}


def _norm(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _session_signature(session_context: dict | None) -> str:
    """P5 Stage 4 fix — normalized signature of the ONLY session_context
    fields that actually influence entity resolution: session_context.py's
    resolve_context() reads companies/sectors and nothing else. Folded into
    the Layer-1 exact key below so two sessions holding different resolved
    context never collide on identical literal query text (found live:
    session A with prior context TCS and session B with prior context
    RELIANCE both asking "What about its main competitor?" — B silently
    got A's cached TCS-competitor answer). Empty string when there's
    nothing to disambiguate on (no session_context, or an empty one) —
    that's what keeps the common case (no prior session, or a session with
    nothing merge-worthy) sharing one cache entry exactly as before,
    instead of needlessly fragmenting the cache per session."""
    if not session_context:
        return ""
    companies = sorted({c.upper() for c in (session_context.get("companies") or [])})
    sectors = sorted({s.lower() for s in (session_context.get("sectors") or [])})
    if not companies and not sectors:
        return ""
    return "|ctx:" + ",".join(companies) + ";" + ",".join(sectors)


def exact_key(query: str, session_context: dict | None = None) -> str:
    basis = _norm(query) + _session_signature(session_context)
    return "v3:exact:" + hashlib.md5(basis.encode()).hexdigest()


# Several fine-grained detected intents ask the same effective question for
# caching purposes — "should I invest" (-> "decision"), "is this a good
# buy" (-> "buy"), a plain company question (-> "general"), and "is now a
# good entry point" (-> "entry_timing") all want the same current
# investment view, not four distinct analyses — so paraphrases across
# these collide in Layer 2. Deliberately conservative beyond that: "hold"
# and "sell" stay their own buckets rather than merging in, since "should
# I keep holding X" and "should I sell X" are existing-position questions
# that can reasonably warrant a differently-emphasized answer (exit risk
# vs. entry risk) even about the same company — and news_reaction /
# earnings_preview / list_picks stay separate for the same reason: they
# hinge on a specific event or a multi-company framing, not a generic
# view, and collapsing them in risks serving a stale or mismatched answer.
_INTENT_BUCKETS = {
    "buy": "investment_view", "decision": "investment_view",
    "entry_timing": "investment_view", "general": "investment_view",
}


def semantic_key(intent_data: dict, entities: dict) -> str | None:
    """None when there isn't enough resolved-entity signal to build a
    stable canonical key — callers fall back to exact-only caching rather
    than a coarse key that could wrongly collide two unrelated queries
    (e.g. two different macro questions with no company/sector entities).

    Built from `entities["companies"]` (resolved NSE symbols) rather than
    intent_data's holding/target — those are raw display-name strings
    (`resolve_comparison` returns `ordered[0]["name"]`, not a symbol), so
    two comparisons naming the same pair with different casing/spacing
    would otherwise miss each other. Symbols are already canonical.

    Step 3C, Case D — the comparison branch used to truncate to
    `companies[:2]` regardless of how many were actually resolved, so a
    2-company query ("TCS vs Infosys") and a 3-company query ("Compare
    TCS, Infosys, and Wipro") produced the IDENTICAL key `v3:sem:cmp:INFY:
    TCS` and collided — confirmed live, a 3-way query silently got served
    a 2-way cached answer. Fixed by encoding the FULL sorted company list:
    cache reuse now requires the complete resolved entity set to match,
    not just an overlapping prefix, while two queries that genuinely
    resolve to the same N companies (any phrasing) still correctly share
    one cache entry."""
    companies = sorted({c.upper() for c in (entities.get("companies") or [])})

    if intent_data.get("is_comparison") and len(companies) >= 2:
        return f"v3:sem:cmp:{':'.join(companies)}"

    if companies:
        bucket = _INTENT_BUCKETS.get(intent_data.get("intent", "general"), intent_data.get("intent", "general"))
        return f"v3:sem:company:{'+'.join(companies)}:{bucket}"

    sectors = sorted({s for s in (entities.get("sectors") or [])})
    if sectors:
        return f"v3:sem:sector:{'+'.join(sectors)}"

    return None


def get_response(
    query: str, intent_data: dict | None = None, entities: dict | None = None,
    session_context: dict | None = None,
) -> Any | None:
    """Layer 1 then Layer 2 lookup for a full pipeline response. Layer 2 is
    only checked once intent/entities are available (they're resolved
    before this is called a second time in the pipeline — see pipeline.py).
    session_context is threaded into the Layer-1 key (see _session_signature)
    even on this pre-resolution first call — it's already available in full
    at that point, before entity resolution runs, so there's no need to wait."""
    hit = _get(exact_key(query, session_context), EXACT_TTL)
    if hit is not None:
        return hit
    if intent_data is not None and entities is not None:
        sk = semantic_key(intent_data, entities)
        if sk:
            return _get(sk, SEMANTIC_TTL)
    return None


def set_response(
    query: str, result: Any, intent_data: dict | None = None, entities: dict | None = None,
    session_context: dict | None = None,
) -> None:
    """Writes the exact key always, plus the semantic key when computable —
    so the *next* differently-phrased-but-equivalent query hits Layer 2
    even though this exact phrasing seeded it. Layer 2's semantic_key is
    already entity-aware by construction (built from resolved companies/
    sectors, not raw text) and needs no session_context fix of its own —
    only Layer 1 collided across sessions."""
    _set(exact_key(query, session_context), result)
    if intent_data is not None and entities is not None:
        sk = semantic_key(intent_data, entities)
        if sk:
            _set(sk, result)


def _get(key: str, ttl: int) -> Any | None:
    entry = _CACHE.get(key)
    return entry[1] if entry and time.time() - entry[0] < ttl else None


def _set(key: str, value: Any) -> None:
    _CACHE[key] = (time.time(), value)


def set_snapshot(response_id: str, snapshot: dict) -> None:
    """Stores the real evidence context + companies behind a generated
    answer, keyed by that answer's response_id — lets Refine Analysis
    (adjust horizon/risk/goal and regenerate just the decision layer)
    reuse the SAME real evidence instead of re-fetching it, and skip
    straight to a small decision-only LLM call. Same TTL as the full
    response it belongs to — once that expires, refining it would mean
    grounding a "new" decision in evidence that's no longer fresh anyway."""
    _set(f"v3:snap:{response_id}", snapshot)


def get_snapshot(response_id: str) -> dict | None:
    return _get(f"v3:snap:{response_id}", EXACT_TTL)


async def component(kind: str, discriminator: str, factory: Callable[[], Awaitable[T]]) -> T:
    """Layer 3 helper: `kind` selects the TTL bucket (see COMPONENT_TTL),
    `discriminator` is the specific cache key body (e.g. a symbol, a sorted
    sector list, a policy-keyword signature). Awaits `factory()` only on a
    miss. Never caches an exception — a failed fetch should be retried next
    call, not frozen as a miss for the TTL window."""
    key = f"v3:comp:{kind}:{discriminator}"
    ttl = COMPONENT_TTL[kind]
    hit = _get(key, ttl)
    if hit is not None:
        log.info("ai_search_v3.component_cache_hit", kind=kind, discriminator=discriminator[:60])
        return hit
    val = await factory()
    _set(key, val)
    return val
