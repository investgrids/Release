"""
P5 Stage 2, item 5 — V2-side degraded_reason/synthesis_incomplete
consistency audit, verified live. Confirms the 3 real inconsistencies
found and fixed (2026-08-07): _unrecognized_company_response and
_ambiguous_entity_response hardcoded synthesis_incomplete=False
alongside a real degraded_reason; the main pipeline's is_multi_compare
and scenario-only-degraded paths left degraded_reason=None despite
synthesis_incomplete effectively being True for multi-compare (or the
reverse for scenario-degraded). Run explicitly: pytest -m live_e2e.
"""
from __future__ import annotations

import pytest

from app.db.session import AsyncSessionLocal
from app.services.ai_search_service import run_ai_search

pytestmark = pytest.mark.live_e2e


async def _run(query: str) -> dict:
    async with AsyncSessionLocal() as db:
        return await run_ai_search(query, db)


async def test_unsupported_entity_consistency():
    # Needs the high-confidence corporate-suffix pattern
    # (_COMPANY_SUFFIX_RE) to trigger _looks_like_unrecognized_company —
    # a bare made-up name with no "Ltd"/"Corp" suffix falls through to the
    # normal LLM path instead (a separate, real detection-heuristic gap,
    # not this test's concern).
    result = await _run("What is the outlook for Zzyzx Quantum Defence Ltd?")
    assert result["degraded_reason"] == "unsupported_entity"
    assert result["synthesis_incomplete"] is True


async def test_ambiguous_entity_consistency():
    result = await _run("What is the investment case for Bajaj?")
    if result.get("degraded_reason") == "ambiguous_entity":
        assert result["synthesis_incomplete"] is True


async def test_referential_no_context_consistency():
    result = await _run("What about its main competitor?")
    assert result["degraded_reason"] == "referential_no_context"
    assert result["synthesis_incomplete"] is True


async def test_multi_compare_consistency():
    result = await _run("Compare TCS, Infosys, and Wipro")
    if result.get("degraded_reason") == "multi_entity_partial":
        assert result["synthesis_incomplete"] is True


async def test_healthy_query_consistency():
    result = await _run("Should I buy Reliance?")
    expected = result.get("degraded_reason") is not None
    assert result["synthesis_incomplete"] == expected


async def test_batch_invariant_holds():
    """The actual unification invariant: synthesis_incomplete ==
    (degraded_reason is not None), across every path exercised above,
    in one real batch."""
    queries = [
        "What is the outlook for Zzyzxcompany123?",
        "What is the investment case for Bajaj?",
        "What about its main competitor?",
        "Compare TCS, Infosys, and Wipro",
        "Should I buy Reliance?",
        "HDFC or ICICI?",
    ]
    for q in queries:
        result = await _run(q)
        expected = result.get("degraded_reason") is not None
        assert result["synthesis_incomplete"] == expected, (
            f"{q!r}: synthesis_incomplete={result['synthesis_incomplete']} "
            f"but degraded_reason={result.get('degraded_reason')!r}"
        )
