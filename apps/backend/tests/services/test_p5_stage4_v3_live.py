"""
P5 Stage 4 verification — the full-parity gate for V3. Covers exactly the
bug classes section 2's single-query real-world comparison battery cannot
catch (concurrency/contention, cache identity/collision) plus the
capacity/parse_failure observability fix built as part of this stage.
Run explicitly: pytest -m live_e2e.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.db.session import AsyncSessionLocal
from app.services.ai_search.pipeline import run_ai_search_v3
from app.services.ai_search_service import run_ai_search

pytestmark = pytest.mark.live_e2e


def test_cache_identity_shared_with_v2():
    """P5 Stage 1's core invariant, restated as an actual assertion instead
    of a code-comment claim: V2 and V3 must mutate the exact same dict
    object, not two separate instances that happen to share a name — a
    silent split here would quietly break caching for one pipeline while
    everything else looked fine."""
    from app.services.ai_search_service import _CACHE as v2_cache
    from app.services.ai_search.cache import _CACHE as v3_cache
    assert v2_cache is v3_cache
    assert id(v2_cache) == id(v3_cache)


async def _run_v3(query: str, session_context: dict | None = None) -> dict:
    async with AsyncSessionLocal() as db:
        result, was_cached = await run_ai_search_v3(query, db, session_context)
        return result, was_cached


async def test_exact_key_cache_collision_across_sessions():
    """V3's own three-layer cache (cache.py) is a materially different
    design from V2's — this is a new test, not a port of V2's original
    cache-collision test, which doesn't apply here.

    cache.py's Layer-1 exact_key() is keyed on normalized query text ALONE
    — checked in pipeline.py before any entity/session-context resolution
    happens, and written unconditionally regardless of what entities are
    passed to set_response(). Two different sessions asking the literally
    identical referential text but holding different prior context should
    NOT silently share one session's answer — this is exactly the
    collision class P2 already closed on V2's cache key (_ck() incorporates
    resolved entities into the hash specifically to prevent it)."""
    q = "What about its single biggest competitor by market capitalisation right now?"

    result_a, cached_a = await _run_v3(q, session_context={"companies": ["TCS"]})
    assert not cached_a, "test assumes a cold cache for this exact query text"
    result_b, cached_b = await _run_v3(q, session_context={"companies": ["RELIANCE"]})

    companies_a = {c["symbol"] for c in result_a.get("companies", [])}
    companies_b = {c["symbol"] for c in result_b.get("companies", [])}

    assert companies_a != companies_b, (
        f"session A (context=TCS) and session B (context=RELIANCE) got the same "
        f"companies ({companies_a}) for the identical literal query text — "
        f"exact-key cache collision across sessions with different resolved context. "
        f"cached_b={cached_b}"
    )


async def test_exact_key_cache_still_shared_across_same_context():
    """Flip side of the collision fix, same discipline P2's original fix
    was held to: a fix that scopes the cache per-session so aggressively
    that two sessions holding the IDENTICAL resolved context never share a
    hit would 'solve' the collision by deleting the cache's own value.
    Two different session_context dicts with the same companies (not the
    same dict instance — a genuinely different session that happens to
    have discussed the same company) must still share Layer 1."""
    q = "What about its overall 12 month outlook given current sector trends?"

    result_a, cached_a = await _run_v3(q, session_context={"companies": ["HDFCBANK"]})
    assert not cached_a, "test assumes a cold cache for this exact query text"
    result_b, cached_b = await _run_v3(q, session_context={"companies": ["HDFCBANK"]})

    assert cached_b, (
        "two sessions with the SAME resolved context (companies=['HDFCBANK']) asking "
        "identical literal text did not share a Layer-1 cache hit — the collision fix "
        "over-corrected and fragmented the cache per-session-instance instead of "
        "per-resolved-context"
    )
    assert result_a["response_id"] == result_b["response_id"]


async def test_degraded_capacity_vs_parse_failure_distinguished():
    """P5 Stage 4 fix — specialists/base.py's parse_specialist_json now
    distinguishes 'the LLM never returned any text' (capacity) from 'it
    returned text that didn't parse' (parse_failure), mirroring V2's
    existing ai_search.degraded_capacity / ai_search.json_parse_fail split.
    Unit-level, not live — no LLM call needed to test the pure function."""
    from app.services.ai_search.specialists.base import parse_specialist_json

    parsed_empty, degraded_empty = parse_specialist_json("", "test query")
    assert degraded_empty is True
    assert parsed_empty["_degraded_reason"] == "capacity"

    parsed_garbage, degraded_garbage = parse_specialist_json("not { valid json at all", "test query")
    assert degraded_garbage is True
    assert parsed_garbage["_degraded_reason"] == "parse_failure"


async def test_concurrent_load_v3_no_hang_no_cross_contamination():
    """P0's concurrency work (PriorityTierLimiter, bounded per-tier waits)
    was built and load-tested against V2 only — no test was ever committed
    for either pipeline (confirmed via git history), and this bug class
    (race conditions, shared-state contamination under real concurrency)
    is exactly what a single-query comparison can never catch. Fires 4
    genuinely different interactive-priority V3 requests simultaneously —
    matching the original P0 load test's own scale — and checks both that
    none hang past a generous bound and that no response's companies leak
    into another's (a real risk if any shared mutable state were touched
    without a lock)."""
    queries = [
        "Should I invest in Infosys?",
        "Should I invest in Reliance Industries?",
        "What is the impact of RBI rate cut on banking stocks?",
        "Should I invest in Sun Pharma?",
    ]
    expected_symbol_hint = ["INFY", "RELIANCE", None, "SUNPHARMA"]

    start = time.monotonic()
    results = await asyncio.wait_for(
        asyncio.gather(*(_run_v3(q) for q in queries), return_exceptions=True),
        timeout=180.0,
    )
    elapsed = time.monotonic() - start
    print(f"4 concurrent V3 requests completed in {elapsed:.1f}s")

    for q, r in zip(queries, results):
        assert not isinstance(r, Exception), f"query {q!r} raised under concurrent load: {r!r}"

    for (q, hint), (result, _cached) in zip(zip(queries, expected_symbol_hint), results):
        if hint is None:
            continue
        symbols = {c["symbol"] for c in result.get("companies", [])}
        assert hint in symbols or not symbols, (
            f"query {q!r} expected to surface {hint} among its companies but got "
            f"{symbols} — possible cross-request state contamination under concurrent load"
        )


async def test_transition_scenario_mixed_v2_v3_concurrent_burst():
    """P5 Stage 4, section 5 — the Stage 5 flag-flip moment: a burst of
    requests landing right as traffic shifts from V2 to V3, both pipelines
    hitting the shared _CACHE dict at once. Not a full production
    simulation — confirms the two structural guarantees that matter for a
    cutover specifically: (1) no crash/exception from concurrent access to
    the shared dict (Python/asyncio is single-threaded cooperative
    concurrency under the GIL — dict item assignment is atomic at the
    bytecode level, so this is a real guarantee, not a hope), and (2) no
    cross-pipeline cache-key collision (V2's _ck() produces a bare 32-char
    MD5 hex digest; V3's exact_key() always has a "v3:exact:" prefix —
    structurally incompatible formats, verified here under the specific
    conditions of a mixed burst, not just by static key-format inspection)."""
    v2_queries = ["Should I invest in Wipro?", "What is the outlook for Tata Steel?"]
    v3_queries = ["Should I invest in Infosys?", "What is the outlook for JSW Steel?"]

    async def _v2(q):
        async with AsyncSessionLocal() as db:
            return await run_ai_search(q, db)

    async def _v3(q):
        async with AsyncSessionLocal() as db:
            result, _cached = await run_ai_search_v3(q, db)
            return result

    tasks = [_v2(q) for q in v2_queries] + [_v3(q) for q in v3_queries]
    results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=180.0)

    for q, r in zip(v2_queries + v3_queries, results):
        assert not isinstance(r, Exception), f"query {q!r} raised in mixed V2/V3 burst: {r!r}"

    # Each result should be schema-correct for ITS OWN pipeline — a V2
    # result has no schema_version (V2 never sets one); a V3 result always
    # does. Confirms no cross-pipeline response got swapped in the shared cache.
    for q, r in zip(v2_queries, results[:2]):
        assert not r.get("schema_version"), f"V2 query {q!r} unexpectedly got a V3-shaped response"
    for q, r in zip(v3_queries, results[2:]):
        assert r.get("schema_version"), f"V3 query {q!r} missing schema_version — got a V2-shaped response?"
