"""
Phase 6G Slice 1 — porting V2's 3 missing capabilities into V3:
list_picks real-screener override, pairwise Decision Engine, true 3+-way
comparison (entity_analyses[]). All 3 are additive post-processing/prompt
branches — no routing change, no V2 change beyond Gap #4.

Unit tests below check the prompt-construction/branching logic without a
real LLM call. Live end-to-end proof (real screener/engine data actually
appearing in a real V3 response) is run separately against the running
server, not as part of this file — matching this codebase's own
live_e2e convention for expensive real-LLM tests.
"""
from __future__ import annotations

from app.services.ai_search.specialists.comparison import _build_multi_compare_prompt, build_prompt


def _bundle_stub():
    """Minimal evidence-bundle-shaped stub — only the attributes
    build_prompt()/_build_multi_compare_prompt() actually read."""
    class _Stub:
        vix_level = None
        valuation: dict = {}
        mie_state: dict = {}

        def deduped_events(self):
            return []

        def deduped_news(self):
            return []

        def to_context_text(self):
            return ""

    return _Stub()


def test_three_or_more_companies_routes_to_multi_compare_prompt():
    entities = {
        "companies": ["TCS", "INFY", "WIPRO"],
        "company_matches": [
            {"name": "Tata Consultancy Services", "symbol": "TCS"},
            {"name": "Infosys", "symbol": "INFY"},
            {"name": "Wipro", "symbol": "WIPRO"},
        ],
    }
    prompt = build_prompt("Compare TCS, Infosys, and Wipro", _bundle_stub(), {}, entities)
    assert "MULTI-ENTITY comparison" in prompt
    assert "entity_analyses" in prompt
    for name in ("Tata Consultancy Services", "Infosys", "Wipro"):
        assert name in prompt
    # Must NOT contain the pairwise-only fields — this is the whole point
    # of the port: no fabricated head-to-head framing for 3+.
    assert "holding_analysis" not in prompt
    assert '"comparison": [' not in prompt


def test_exactly_two_companies_still_uses_pairwise_prompt():
    entities = {"companies": ["TCS", "INFY"], "company_matches": [
        {"name": "Tata Consultancy Services", "symbol": "TCS"},
        {"name": "Infosys", "symbol": "INFY"},
    ]}
    intent_data = {"holding": "Tata Consultancy Services", "target": "Infosys"}
    prompt = build_prompt("TCS or Infosys?", _bundle_stub(), intent_data, entities)
    assert "holding_analysis" in prompt
    assert "entity_analyses" not in prompt


def test_multi_compare_prompt_falls_back_to_symbols_when_no_names_resolved():
    entities = {"companies": ["TCS", "INFY", "WIPRO"], "company_matches": []}
    prompt = _build_multi_compare_prompt("Compare TCS, INFY, WIPRO", _bundle_stub(), entities)
    for sym in ("TCS", "INFY", "WIPRO"):
        assert sym in prompt


def test_multi_compare_prompt_caps_at_three_entities_for_token_budget():
    """Confirmed live: even after fixing the schema shape, a genuine
    3-entity request with the full standard schema still truncated
    mid-JSON before completing. Capped tighter than this package's usual
    top-6 discipline specifically for this reason -- see the function's
    own docstring."""
    entities = {
        "companies": ["A", "B", "C", "D"],
        "company_matches": [{"name": n, "symbol": n} for n in ("A", "B", "C", "D")],
    }
    prompt = _build_multi_compare_prompt("Compare A, B, C, D", _bundle_stub(), entities)
    assert prompt.count('"entity":') == 3
    assert "\"D\"" not in prompt.split("COMPANIES TO ANALYZE")[1].split("\n")[0]
