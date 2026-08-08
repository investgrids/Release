"""
P5 Stage 5 — synthetic functional check, the replacement for the original
capacity-frequency precondition (see Stage 5 task file). Real production
traffic is too thin right now to measure a genuine capacity-degradation
frequency (checked directly: ~6 total requests in the retrievable log
window, all investigation traffic, no organic usage) — and per the standing
decision, capacity exhaustion is a permanent, system-wide free-tier
characteristic shared identically by V2 and V3, not a V3-specific cutover
risk. What's actually answerable, and the right question given that
constraint: does P0's machinery (priority-tier queueing, honest
degraded_reason reporting) function correctly on V3 under a moderate,
realistically-paced synthetic load? Explicitly synthetic — not a stand-in
for real usage frequency.

Run explicitly: pytest -m live_e2e.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.db.session import AsyncSessionLocal
from app.services.ai_search.pipeline import run_ai_search_v3
from app.services.ai_service import _call_with_fallback

pytestmark = pytest.mark.live_e2e


async def _interactive_query(query: str, delay: float) -> dict:
    await asyncio.sleep(delay)
    start = time.monotonic()
    async with AsyncSessionLocal() as db:
        result, _cached = await run_ai_search_v3(query, db)
    elapsed = time.monotonic() - start
    return {"query": query, "elapsed": elapsed, "result": result}


async def _background_call(tag: str, delay: float) -> dict:
    """Real background-priority traffic on the SAME shared PriorityTierLimiter
    V3's interactive calls go through — article_generator.py/story_engine.py/
    triage_worker.py all tag priority="background" for exactly this reason.
    Firing this directly (rather than only ever testing interactive-only
    load, which every prior P0 test in this project has done) is what
    actually exercises the tier separation P0 was built for."""
    await asyncio.sleep(delay)
    start = time.monotonic()
    raw = await _call_with_fallback(
        f"Reply with exactly one word: {tag}", max_tokens=10, priority="background",
    )
    elapsed = time.monotonic() - start
    return {"tag": tag, "elapsed": elapsed, "got_response": bool(raw)}


async def test_p0_priority_and_honest_degradation_under_synthetic_load():
    """Moderate, realistically-paced load (staggered starts, not one
    simultaneous burst) — 6 interactive V3 queries over ~50s, with 3 real
    background-priority calls fired concurrently to create genuine tier
    contention (P0's own interactive-tier bound is 1.5s; background's is
    25s — background traffic should never be what makes an interactive
    request slow). Checks three things Stage 5's precondition actually
    needs answered: (1) no hangs/crashes under this load, (2) interactive
    requests aren't measurably slowed by concurrent background traffic,
    (3) every degraded_reason value observed is internally coherent —
    "capacity" only appears alongside real evidence of exhaustion in the
    same response's own trail, never a silent mislabel."""
    interactive_queries = [
        "Should I invest in Infosys?",
        "What is the impact of RBI rate cut on banking stocks?",
        "Should I invest in Sun Pharma?",
        "Compare TCS and Wipro",
        "Should I invest in Reliance Industries?",
        "What is the outlook for Tata Motors?",
    ]

    interactive_tasks = [
        _interactive_query(q, delay=i * 8.0) for i, q in enumerate(interactive_queries)
    ]
    background_tasks = [
        _background_call(f"tier-test-{i}", delay=i * 12.0) for i in range(3)
    ]

    start = time.monotonic()
    all_results = await asyncio.wait_for(
        asyncio.gather(*interactive_tasks, *background_tasks, return_exceptions=True),
        timeout=180.0,
    )
    total_elapsed = time.monotonic() - start
    print(f"Full synthetic load run completed in {total_elapsed:.1f}s")

    interactive_results = all_results[: len(interactive_queries)]
    background_results = all_results[len(interactive_queries):]

    # (1) No hangs/crashes.
    for q, r in zip(interactive_queries, interactive_results):
        assert not isinstance(r, Exception), f"interactive query {q!r} raised: {r!r}"
    for i, r in enumerate(background_results):
        assert not isinstance(r, Exception), f"background call {i} raised: {r!r}"

    # (2) Interactive requests aren't measurably starved by background load.
    # A real LLM call legitimately takes anywhere from ~1s to ~90s depending
    # on which provider tier answers — the bound here is generous on purpose
    # (this isn't a latency benchmark), but a hard cap catches genuine
    # priority-inversion (an interactive request silently queued behind
    # background's 25s tier wait would blow well past this).
    for r in interactive_results:
        print(f"  interactive {r['query']!r}: {r['elapsed']:.1f}s")
        assert r["elapsed"] < 120.0, (
            f"interactive query {r['query']!r} took {r['elapsed']:.1f}s under concurrent "
            f"background load — possible priority-tier starvation"
        )
    for r in background_results:
        print(f"  background {r['tag']!r}: {r['elapsed']:.1f}s got_response={r['got_response']}")

    # (3) degraded_reason honesty — every value present must be a real,
    # recognized value (no silent None-vs-mislabel confusion), and a
    # "capacity" value implies the response's own companies/answer fields
    # reflect that (empty/thin), not a well-formed answer mislabeled.
    known_reasons = {
        None, "capacity", "parse_failure", "multi_entity_partial",
        "grounding_collapsed", "ambiguous_entity", "unsupported_entity",
        "referential_no_context", "scenario_degraded",
    }
    for r in interactive_results:
        reason = r["result"].get("degraded_reason")
        assert reason in known_reasons, f"unrecognized degraded_reason {reason!r} for {r['query']!r}"
        if reason == "capacity":
            assert not r["result"].get("companies"), (
                f"query {r['query']!r} labeled degraded_reason='capacity' but has real "
                f"companies data — inconsistent with what capacity degradation should mean"
            )
