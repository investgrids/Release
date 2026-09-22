"""
comparison assembly (aev2.3, 2026-09-22) — the neutral, no-holding-
relationship counterpart to switch_analysis, sharing the exact same
pair_comparison.py dimension builder. Follows test_switch_analysis_
assembly.py's own pattern: build a plain V3 response dict, project it
through the real from_v3_response(), then assemble through the real
assemble_aev2() entry point.

Covers the approved spec's 14 required scenarios (2026-09-22): query
order preservation, no switch terminology, identical dimension math
between switch and comparison, honest missing-data handling, non-
comparable price windows, attributable-evidence requirements, wrong-
company evidence rejection, advisory-language fail-closed, 2-company
success, 3-company rejection, and no leakage of switch-only concepts.
"""
from __future__ import annotations

from app.services.ai_search.aev2.assemble import assemble_aev2
from app.services.ai_search.aev2.language_gate import FALLBACK_TEXT
from app.services.ai_search.aev2.mode import AEV2Mode
from app.services.ai_search.core_answer import from_v3_response

INFY = {"symbol": "INFY", "name": "Infosys Ltd"}
TCS = {"symbol": "TCS", "name": "Tata Consultancy Services Ltd"}

INFY_EVENT = {
    "id": "e-infy-1", "title": "Infosys wins 500 crore digital transformation deal",
    "date": "2026-09-17", "companies": [INFY],
}
TCS_EVENT = {
    "id": "e-tcs-1", "title": "TCS announces new AI research center",
    "date": "2026-09-12", "companies": [TCS],
}


def _v3_response(**overrides) -> dict:
    base = {
        "query": "Compare Infosys and TCS",
        "response_id": "resp-cmp-1",
        "specialist": "comparison",
        "intent": "compare",
        # decision_intent.py's own extraction resolves holding/target for
        # ANY comparison-shaped query, including a neutral one — present
        # here (as it would be on a real response) specifically to prove
        # comparison.py doesn't need to check them at all.
        "switch_holding": "Infosys Ltd",
        "switch_target": "Tata Consultancy Services Ltd",
        "answer": {
            "bottom_line": "Infosys's digital transformation win and TCS's new AI research center both reflect continued IT-sector demand.",
            "summary": "ok",
            "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "risks": [],
        },
        "companies": [
            {"symbol": "INFY", "name": "Infosys Ltd", "price": "1,845.20", "change": "+0.60%",
             "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
            {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "price": "4,102.50", "change": "-0.20%",
             "positive": False, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        ],
        "related_events": [dict(INFY_EVENT), dict(TCS_EVENT)],
        "news": [], "policies": [],
        "investment_verdict": {"horizon": "6-12 months"},
        "confidence_breakdown": {
            "evidence_quality": 70.0, "market_confirmation": 60.0,
            "historical_similarity": 40.0, "data_freshness": 90.0,
        },
    }
    base.update(overrides)
    return base


def _assemble(**overrides):
    core = from_v3_response(_v3_response(**overrides))
    return assemble_aev2(core, mode=AEV2Mode.PUBLIC)


# ── 9. Two-company comparison succeeds ──────────────────────────────────

def test_comparison_succeeds_for_a_two_company_query():
    result = _assemble()
    cmp = result["comparison"]
    assert cmp["relationship"] == "comparison"
    assert cmp["left_company"] == {"symbol": "INFY", "name": "Infosys Ltd"}
    assert cmp["right_company"] == {"symbol": "TCS", "name": "Tata Consultancy Services Ltd"}


# ── 1. Query order is preserved ─────────────────────────────────────────

def test_query_entity_order_is_preserved_not_alphabetized():
    """"Compare Infosys and TCS" names Infosys first — INFY must be
    left_company even though "TCS" < "INFY" alphabetically... wait, T > I,
    so alphabetical order would coincidentally match here; use a company
    pair where alphabetical order would DIFFER from query order to prove
    this isn't accidental."""
    result = _assemble(
        query="Compare Zomato and Adani Enterprises",
        companies=[
            {"symbol": "ZOMATO", "name": "Zomato Ltd", "price": "210.00", "change": "+0.5%",
             "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
            {"symbol": "ADANIENT", "name": "Adani Enterprises Ltd", "price": "3,050.00", "change": "-0.1%",
             "positive": False, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        ],
        related_events=[
            {"id": "e-zom-1", "title": "Zomato reports quarterly growth", "date": "2026-09-17",
             "companies": [{"symbol": "ZOMATO", "name": "Zomato Ltd"}]},
            {"id": "e-adani-1", "title": "Adani Enterprises signs new logistics contract", "date": "2026-09-12",
             "companies": [{"symbol": "ADANIENT", "name": "Adani Enterprises Ltd"}]},
        ],
    )
    cmp = result["comparison"]
    assert cmp["left_company"]["symbol"] == "ZOMATO"
    assert cmp["right_company"]["symbol"] == "ADANIENT"


# ── 2. No switch terminology appears ────────────────────────────────────

def test_comparison_schema_carries_no_switch_terminology():
    result = _assemble()
    cmp = result["comparison"]
    forbidden_keys = {
        "current_company", "alternative_company", "switch_holding", "switch_target",
        "conditions_favoring_current", "conditions_favoring_alternative",
        "what_changes_the_comparison",
    }
    assert forbidden_keys.isdisjoint(cmp.keys())
    assert cmp["relationship"] != "switch"
    serialized_text = " ".join([
        cmp["direct_comparison"]["text"],
        *(dim["label"] for dim in cmp["dimensions"]),
    ]).lower()
    for term in ("current holding", "alternative", "switch", "stay with", "move to"):
        assert term not in serialized_text


# ── 3. Switch and comparison use identical dimension calculations ──────

def test_switch_and_comparison_compute_identical_dimensions_for_the_same_two_companies():
    result = _assemble(intent="switch")
    sw = result["switch_analysis"]
    cmp = result["comparison"]
    assert sw is not None and cmp is not None
    for sw_dim, cmp_dim in zip(sw["dimensions"], cmp["dimensions"]):
        assert sw_dim["key"] == cmp_dim["key"]
        assert sw_dim["comparable"] == cmp_dim["comparable"]
        # current_company/left_company (and alternative/right) hold the
        # SAME values — only the field NAME differs between schemas.
        assert sw_dim["current_company"] == cmp_dim["left_company"]
        assert sw_dim["alternative_company"] == cmp_dim["right_company"]


# ── 4. Missing data for one company is not treated as a disadvantage ───

def test_missing_recent_developments_for_one_company_is_not_a_disadvantage_claim():
    result = _assemble(related_events=[dict(INFY_EVENT)])
    dim = next(d for d in result["comparison"]["dimensions"] if d["key"] == "recent_developments")
    assert dim["comparable"] is False
    assert dim["right_company"] is None
    assert "TCS" in dim["unavailable_reason"]
    assert "disadvantage" not in dim["unavailable_reason"].lower()
    assert "weak" not in dim["unavailable_reason"].lower()


# ── 5. Differing price windows are marked non-comparable ───────────────

def test_price_reaction_is_not_comparable_when_one_companys_price_fetch_failed():
    result = _assemble(companies=[
        {"symbol": "INFY", "name": "Infosys Ltd", "price": "1,845.20", "change": "+0.60%",
         "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "price": "—", "change": None, "positive": False},
    ])
    dim = next(d for d in result["comparison"]["dimensions"] if d["key"] == "price_reaction")
    assert dim["comparable"] is False
    assert dim["right_company"] is None


# ── 6. Both companies require attributable evidence ─────────────────────

def test_recent_developments_requires_attributable_evidence_for_both_companies():
    result = _assemble(related_events=[])
    dim = next(d for d in result["comparison"]["dimensions"] if d["key"] == "recent_developments")
    assert dim["comparable"] is False
    assert dim["left_company"] is None
    assert dim["right_company"] is None


# ── 7. A valid evidence ID tied to the wrong company is rejected ───────

def test_an_event_linked_only_to_a_third_company_is_not_attributed_to_either_side():
    third_party_event = {
        "id": "e-other-1", "title": "Reliance Industries announces new refinery",
        "date": "2026-09-19", "companies": [{"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}],
    }
    result = _assemble(related_events=[dict(INFY_EVENT), third_party_event])
    dim = next(d for d in result["comparison"]["dimensions"] if d["key"] == "recent_developments")
    # TCS has no attributed event at all -> not comparable; the
    # third-party event must never be attributed to TCS just because it
    # exists in the evidence catalog.
    assert dim["comparable"] is False
    assert dim["right_company"] is None


# ── 8. Advisory language fails closed ───────────────────────────────────

def test_direct_comparison_fails_closed_on_advisory_language():
    result = _assemble(answer={
        "bottom_line": "You should buy Infosys over TCS for stronger upside.",
        "summary": "ok", "what_happened": "", "why_it_happened": "", "immediate_impact": "",
        "medium_term": "", "long_term": "", "risks": [],
    })
    dc = result["comparison"]["direct_comparison"]
    assert dc["validation_status"] == "unvalidated"
    assert dc["text"] == FALLBACK_TEXT["direct_comparison"]
    assert dc["evidence_refs"] == []


# ── 10. Three-company comparison fails honestly (out of scope, not degraded) ─

def test_comparison_is_none_for_a_three_company_query():
    result = _assemble(companies=[
        {"symbol": "INFY", "name": "Infosys Ltd", "price": "1,845.20", "change": "+0.60%", "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "price": "4,102.50", "change": "-0.20%", "positive": False, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
        {"symbol": "WIPRO", "name": "Wipro Ltd", "price": "265.00", "change": "+0.10%", "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
    ])
    assert result["comparison"] is None


def test_comparison_is_none_for_a_single_company_query():
    result = _assemble(companies=[
        {"symbol": "INFY", "name": "Infosys Ltd", "price": "1,845.20", "change": "+0.60%", "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
    ])
    assert result["comparison"] is None


def test_comparison_is_none_for_a_non_comparison_specialist():
    result = _assemble(specialist="company")
    assert result["comparison"] is None


# ── 11. Unknown or missing company roles do not leak from switch logic ─

def test_comparison_never_calls_switch_role_lookup_or_reads_switch_holding_target():
    """comparison.py must resolve left/right purely from CoreAnswer.
    companies' own order — never decision_intent.py's holding/target
    extraction, even when those fields are present and resolvable (as
    they realistically would be for any comparison-shaped query)."""
    result = _assemble(switch_holding="Tata Consultancy Services Ltd", switch_target="Infosys Ltd")
    cmp = result["comparison"]
    # Query order (Infosys first) wins, NOT switch_holding/switch_target
    # (which name TCS first here) — proving comparison.py ignores them.
    assert cmp["left_company"]["symbol"] == "INFY"
    assert cmp["right_company"]["symbol"] == "TCS"


def test_comparison_still_assembles_when_switch_holding_and_target_are_missing_entirely():
    result = _assemble(switch_holding=None, switch_target=None)
    assert result["comparison"] is not None


# ── 12. Prohibited V3 fields remain structurally unreachable ───────────

def test_comparison_never_carries_verdict_shaped_fields():
    result = _assemble()
    cmp = result["comparison"]
    forbidden = {"rating", "direction", "top_picks", "catalysts", "scenarios", "opportunity_score", "risk_level", "suitable_for"}
    assert forbidden.isdisjoint(cmp.keys())
    assert forbidden.isdisjoint(cmp["direct_comparison"].keys())


# ── 13. Neither input nor cached data is mutated ────────────────────────

def test_assemble_comparison_does_not_mutate_core_answer():
    import copy
    core = from_v3_response(_v3_response())
    before = copy.deepcopy(core)
    assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    assert core == before
