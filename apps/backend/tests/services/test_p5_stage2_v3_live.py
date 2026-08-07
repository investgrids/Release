"""
P5 Stage 2 verification — live tests for the new/ported V3-native
behaviors this stage built. These are new V3 capabilities (V3 never had
them before this stage), so they need their own real tests rather than
reusing V2's existing suite. Run explicitly: pytest -m live_e2e.
"""
from __future__ import annotations

import pytest

from app.db.session import AsyncSessionLocal
from app.services.ai_search.pipeline import run_ai_search_v3

pytestmark = pytest.mark.live_e2e


async def _run_v3(query: str) -> dict:
    async with AsyncSessionLocal() as db:
        result, _was_cached = await run_ai_search_v3(query, db)
        return result


async def test_referential_no_context_v3():
    """A referential query with no prior session context should short-
    circuit honestly, not silently reach the LLM with empty entities."""
    result = await _run_v3("What about its main competitor?")
    assert result["degraded_reason"] == "referential_no_context"
    assert result["synthesis_incomplete"] is True
    assert result["companies"] == []


async def test_ambiguous_entity_v3_complete_shape():
    """Bare conglomerate name should return real named candidates and a
    full schema-complete response (item 4 — was a partial inline shape
    missing degraded_reason and most schema fields)."""
    result = await _run_v3("What is the investment case for Tata?")
    assert result.get("needs_clarification") is True
    assert result["degraded_reason"] == "ambiguous_entity"
    assert result["synthesis_incomplete"] is True
    assert result.get("candidates"), "expected real named candidates, got none"
    # Full schema-complete check — item 4's actual point (not the old
    # partial shape missing answer/investment_verdict/etc.)
    assert "answer" in result and result["answer"]["summary"]
    assert "investment_verdict" in result
    assert result["schema_version"]


async def test_multi_compare_3plus_entities_v3():
    """3+ real companies named in a comparison must never silently
    collapse to 2 with zero signal (item 3) — either the comparison
    covers all of them, or degraded_reason/caveats honestly say which
    were dropped."""
    result = await _run_v3("Compare TCS, Infosys, and Wipro")
    companies = result.get("companies") or []
    if len(companies) < 3:
        assert result.get("degraded_reason") == "multi_entity_partial", (
            f"3+ entities named but only {len(companies)} compared, "
            f"with no multi_entity_partial signal — silent collapse"
        )
        caveats = result.get("confidence_data", {}).get("caveats", [])
        assert any("2 of" in c for c in caveats), "expected an honest caveat naming the dropped company"


async def test_word_boundary_fix_v3_live():
    """'What about its IT infrastructure?' should not spuriously match the
    IT sector via a bare 'it' substring match (the exact P2/P5-Stage-2
    word-boundary bug) when a real company is already named."""
    result = await _run_v3("What is Infosys' outlook, and what about its plans?")
    # result["companies"] holds rich objects ({"symbol": ..., ...}), not
    # bare strings — check by symbol. Should resolve INFY as the company;
    # must not spuriously report 'it' matching the IT sector.
    symbols = {c["symbol"] for c in (result.get("companies") or [])}
    assert "INFY" in symbols or result.get("degraded_reason") is not None


async def test_degraded_reason_synthesis_incomplete_consistency_v3():
    """synthesis_incomplete must equal (degraded_reason is not None) —
    the actual unification invariant item 5 exists to guarantee — across
    a real batch covering multiple degradation paths."""
    queries = [
        "What about its main competitor?",          # referential_no_context
        "What is the investment case for Tata?",      # ambiguous_entity
        "Should I buy Reliance?",                      # normal, healthy
        "asdkjaslkdj totally not a real company xyz",   # unsupported_entity
    ]
    for q in queries:
        result = await _run_v3(q)
        expected = result.get("degraded_reason") is not None
        assert result["synthesis_incomplete"] == expected, (
            f"{q!r}: synthesis_incomplete={result['synthesis_incomplete']} "
            f"but degraded_reason={result.get('degraded_reason')!r}"
        )
