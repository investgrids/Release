"""
AEV2 Build 1 (2026-09-21) — the backend response assembler + citation
validator built from CoreAnswer only: deterministic restructuring
fields, deterministic company attribution, live-price-movement groups
with Yahoo Finance fetch-time provenance, the four-component AEV2
confidence score, claim-level evidence references with fail-closed
validation (invalid ref / unsupported number / entity mismatch), and
zero regeneration (no LLM call anywhere in this module).

See test_ai_search_single_pipeline_runtime.py for the still-holding
one-specialist-call and cache-hit invariants (unaffected by this slice
— assemble_aev2's signature is unchanged) and test_aev2_foundation.py
for the still-holding readiness-latch/mode-gating tests.
"""
from __future__ import annotations

from app.services.ai_search.aev2 import citation_validator, price_movement
from app.services.ai_search.aev2.assemble import assemble_aev2
from app.services.ai_search.aev2.confidence import compute_aev2_confidence
from app.services.ai_search.aev2.mode import AEV2Mode
from app.services.ai_search.core_answer import from_v3_response

FRESH_EVENT = {"id": "e1", "title": "Reliance Industries secures 2,500 MW RTC power supply contract", "date": "2026-09-15"}
FRESH_NEWS = {"id": "n1", "headline": "Reliance shares gain on power deal", "published_at": "2026-09-15"}


def _v3_response(**overrides) -> dict:
    base = {
        "query": "Should I invest in Reliance Industries?",
        "response_id": "resp-1",
        "specialist": "company",
        "answer": {
            "bottom_line": "Reliance Industries secured a 2,500 MW power supply contract.",
            "summary": "ok",
            "what_happened": "Reliance Industries announced a 2,500 MW RTC power supply agreement.",
            "why_it_happened": "The contract reflects growing demand for round-the-clock clean power.",
            "immediate_impact": "Shares reacted positively to the announcement.",
            "medium_term": "",
            "long_term": "",
            "risks": ["Execution risk on large infrastructure contracts remains real."],
        },
        "companies": [{
            "symbol": "RELIANCE", "name": "Reliance Industries Ltd",
            "price": "1,402.50", "change": "+1.20%", "positive": True,
            "price_fetched_at": "2026-09-21T10:00:00+00:00",
        }],
        "related_events": [dict(FRESH_EVENT)],
        "news": [dict(FRESH_NEWS)],
        "policies": [],
        "investment_verdict": {"horizon": "1-3 months"},
        "confidence_breakdown": {"evidence_quality": 70.0, "data_freshness": 90.0},
    }
    base.update(overrides)
    return base


def _core(**overrides):
    return from_v3_response(_v3_response(**overrides))


# ── Deterministic restructuring fields ──────────────────────────────────────

def test_direct_conclusion_what_happened_why_it_matters_populated_from_core():
    result = assemble_aev2(_core(), mode=AEV2Mode.PUBLIC)
    assert result["direct_conclusion"]["text"] == "Reliance Industries secured a 2,500 MW power supply contract."
    assert result["direct_conclusion"]["evidence_refs"]
    assert result["what_happened"]["summary"] == "Reliance Industries announced a 2,500 MW RTC power supply agreement."
    assert result["why_it_matters"]["text"] == "The contract reflects growing demand for round-the-clock clean power."
    assert result["why_it_matters"]["is_fallback"] is False


def test_time_horizon_and_timeline_phases_populated():
    result = assemble_aev2(_core(), mode=AEV2Mode.PUBLIC)
    assert result["time_horizon"]["primary_horizon"] == "1-3 months"
    phases = {p["phase"]: p["text"] for p in result["time_horizon"]["timeline_phases"]}
    assert phases["immediate"] == "Shares reacted positively to the announcement."
    assert "medium_term" not in phases  # empty in the fixture — correctly absent, not fabricated


def test_risks_populated_from_core_risks():
    result = assemble_aev2(_core(), mode=AEV2Mode.PUBLIC)
    assert result["risks_and_invalidation"]["risks"] == ["Execution risk on large infrastructure contracts remains real."]
    assert result["risks_and_invalidation"]["invalidates_if"] == []
    assert result["risks_and_invalidation"]["watch_for"] == []


def test_related_intelligence_events_populated_zero_new_retrieval():
    result = assemble_aev2(_core(), mode=AEV2Mode.PUBLIC)
    events = result["related_intelligence"]["events"]
    assert len(events) == 1
    assert events[0]["id"] == "event:e1"
    assert events[0]["title"] == FRESH_EVENT["title"]
    assert result["related_intelligence"]["opportunities"] == []
    assert result["related_intelligence"]["ripple"] is None


def test_evidence_catalog_includes_both_event_and_news():
    result = assemble_aev2(_core(), mode=AEV2Mode.PUBLIC)
    ids = {e["id"] for e in result["evidence"]}
    assert ids == {"event:e1", "news:n1"}


# ── Verdict/scenario/suitability/top-pick concepts are absent everywhere ───

def _flatten_keys(obj, path="") -> set[str]:
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _flatten_keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for item in obj:
            keys |= _flatten_keys(item, path)
    return keys


def test_no_verdict_scenario_suitability_top_pick_keys_anywhere_in_aev2_output():
    result = assemble_aev2(_core(), mode=AEV2Mode.PUBLIC)
    forbidden = {
        "rating", "direction", "top_picks", "suitable_for", "opportunity_score",
        "risk_level", "engine_verdict", "scenarios", "catalysts", "verdict_scale",
    }
    present_keys = _flatten_keys(result)
    assert present_keys & forbidden == set(), f"forbidden verdict/scenario/top-pick keys leaked into AEV2 output: {present_keys & forbidden}"


def test_core_answer_type_itself_excludes_verdict_fields():
    import dataclasses
    from app.services.ai_search.core_answer import CoreAnswer
    field_names = {f.name for f in dataclasses.fields(CoreAnswer)}
    forbidden = {"rating", "direction", "top_picks", "suitable_for", "opportunity_score", "risk_level", "engine_verdict", "scenarios"}
    assert field_names & forbidden == set()


# ── Deterministic company attribution + Yahoo Finance provenance ──────────

def test_price_movement_groups_by_live_price_not_impact_type():
    """A company the specialist called "at_risk" (narrative judgment) but
    whose REAL live price is up right now must land in currently_higher —
    proving attribution is deterministic from market data, not the
    model's own claim about why."""
    companies = (
        {"symbol": "TCS", "name": "Tata Consultancy Services", "impact_type": "at_risk",
         "price": "3,900.00", "positive": True, "price_fetched_at": "2026-09-21T10:00:00+00:00"},
    )
    groups = price_movement.build_price_movement_groups(companies)
    assert [c["symbol"] for c in groups["currently_higher"]] == ["TCS"]
    assert groups["currently_lower"] == []


def test_price_movement_fetch_time_provenance_carried_through():
    companies = (
        {"symbol": "RELIANCE", "name": "Reliance Industries", "price": "1,400", "positive": True,
         "price_fetched_at": "2026-09-21T10:00:00+00:00"},
    )
    groups = price_movement.build_price_movement_groups(companies)
    assert groups["currently_higher"][0]["fetched_at"] == "2026-09-21T10:00:00+00:00"


def test_price_movement_omits_companies_with_no_real_fetch():
    """enrichment.py's own existing failure sentinel (price == "—", no
    price_fetched_at) must be grouped as omitted, never guessed into
    higher/lower using its stale positive=True default."""
    companies = (
        {"symbol": "WIPRO", "name": "Wipro Ltd", "price": "—", "positive": True},  # the existing fallback shape
    )
    groups = price_movement.build_price_movement_groups(companies)
    assert groups["currently_higher"] == []
    assert groups["currently_lower"] == []
    assert [c["symbol"] for c in groups["omitted_unattributed"]] == ["WIPRO"]


def test_end_to_end_companies_affected_reflects_price_movement():
    result = assemble_aev2(_core(), mode=AEV2Mode.PUBLIC)
    assert [c["symbol"] for c in result["companies_affected"]["currently_higher"]] == ["RELIANCE"]
    assert result["companies_affected"]["currently_lower"] == []
    assert result["companies_affected"]["omitted_unattributed"] == []


# ── Four-component AEV2 confidence score ────────────────────────────────────

def test_confidence_uses_all_four_components_when_available():
    result = assemble_aev2(_core(), mode=AEV2Mode.PUBLIC)
    confidence = result["confidence"]
    assert set(confidence["components_available"]) == {
        "evidence_quality", "data_freshness", "source_diversity", "company_attribution",
    }
    assert confidence["score"] is not None
    assert confidence["level"] != "unscored"


def test_confidence_unscored_when_no_signal_available():
    core = from_v3_response({"answer": {"bottom_line": "x"}})
    result = compute_aev2_confidence(core, {"currently_higher": [], "currently_lower": [], "omitted_unattributed": []})
    assert result == {"score": None, "level": "unscored", "components_available": []}


def test_confidence_partial_components_when_only_some_signals_exist():
    core = from_v3_response({
        "answer": {"bottom_line": "x"},
        "confidence_breakdown": {"evidence_quality": 80.0},
    })
    result = compute_aev2_confidence(core, {"currently_higher": [], "currently_lower": [], "omitted_unattributed": []})
    assert result["components_available"] == ["evidence_quality"]
    assert result["score"] == 80.0


# ── Claim-level evidence references + fail-closed validation ───────────────

def test_invalid_evidence_ref_makes_the_claim_invalid():
    claim = citation_validator.validate_claim(
        text="Reliance reported strong results.",
        evidence_refs=["event:does-not-exist"],
        catalog_ids={"event:e1"},
        recognized_symbols={"RELIANCE"},
        supporting_text="Reliance reported strong results.",
    )
    assert claim.valid is False
    assert "invalid_evidence_ref" in claim.reasons


def test_unsupported_number_makes_the_claim_invalid():
    claim = citation_validator.validate_claim(
        text="Reliance secured a 9,999 MW contract.",
        evidence_refs=["event:e1"],
        catalog_ids={"event:e1"},
        recognized_symbols={"RELIANCE"},
        supporting_text="Reliance secured a 2,500 MW contract.",
    )
    assert claim.valid is False
    assert "unsupported_number" in claim.reasons


def test_supported_number_is_valid():
    claim = citation_validator.validate_claim(
        text="Reliance secured a 2,500 MW contract.",
        evidence_refs=["event:e1"],
        catalog_ids={"event:e1"},
        recognized_symbols={"RELIANCE"},
        supporting_text="Reliance secured a 2,500 MW RTC power contract.",
    )
    assert claim.valid is True
    assert claim.reasons == []


def test_entity_mismatch_makes_the_claim_invalid():
    """WIPRO was never resolved for this query (recognized_symbols only
    has RELIANCE) — a claim naming it must fail closed."""
    claim = citation_validator.validate_claim(
        text="WIPRO also benefits from this contract.",
        evidence_refs=["event:e1"],
        catalog_ids={"event:e1"},
        recognized_symbols={"RELIANCE"},
        supporting_text="Reliance secured a 2,500 MW contract.",
        name_tokens={"RELIANCE", "INDUSTRIES", "LTD"},
    )
    assert claim.valid is False
    assert "unsupported_entity" in claim.reasons


def test_recognized_name_tokens_covers_name_shorthand_not_just_symbol():
    """"HDFC Bank" the name vs "HDFCBANK" the symbol — a genuine mention
    of the company's own name must not be flagged just because it isn't
    a byte-for-byte match of the trading symbol."""
    tokens = citation_validator.recognized_name_tokens(({"symbol": "HDFCBANK", "name": "HDFC Bank Ltd"},))
    assert "HDFC" in tokens
    assert citation_validator.entities_supported("HDFC Bank reported results.", {"HDFCBANK"}, tokens)


def test_entities_supported_vacuous_pass_when_nothing_resolved():
    """A macro/sector query that resolved zero companies has nothing to
    compare a mention against — this must not reject every all-caps
    token in the text by default."""
    assert citation_validator.entities_supported("RBI announced a rate cut affecting IT stocks.", set(), set())


def test_known_acronyms_never_flagged_as_unsupported_entities():
    assert citation_validator.entities_supported(
        "RBI's GDP outlook and IPO pipeline remain strong for FY25.",
        recognized_symbols={"RELIANCE"}, name_tokens=set(),
    )


# ── End-to-end: a fabricated number in generated text is caught and dropped ─

def test_end_to_end_unsupported_number_falls_back_to_honest_fallback():
    core = _core(answer={
        "bottom_line": "Reliance secured a 99,999 MW contract.",  # fabricated figure, not in evidence
        "summary": "ok", "what_happened": "", "why_it_happened": "", "immediate_impact": "",
        "medium_term": "", "long_term": "", "risks": [],
    })
    result = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    from app.services.ai_search.aev2.language_gate import FALLBACK_TEXT
    assert result["direct_conclusion"]["text"] == FALLBACK_TEXT["direct_conclusion"]
    assert result["direct_conclusion"]["evidence_refs"] == []


def test_end_to_end_entity_mismatch_falls_back_to_honest_fallback():
    core = _core(answer={
        "bottom_line": "WIPRO also stands to benefit from this contract.",  # never resolved for this query
        "summary": "ok", "what_happened": "", "why_it_happened": "", "immediate_impact": "",
        "medium_term": "", "long_term": "", "risks": [],
    })
    result = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    from app.services.ai_search.aev2.language_gate import FALLBACK_TEXT
    assert result["direct_conclusion"]["text"] == FALLBACK_TEXT["direct_conclusion"]


def test_end_to_end_advisory_language_in_what_happened_is_gated():
    core = _core(answer={
        "bottom_line": "Reliance reported strong results.",
        "summary": "ok",
        "what_happened": "Reliance remains a solid buy candidate.",
        "why_it_happened": "", "immediate_impact": "", "medium_term": "", "long_term": "", "risks": [],
    })
    result = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    from app.services.ai_search.aev2.language_gate import FALLBACK_TEXT
    assert result["what_happened"]["summary"] == FALLBACK_TEXT["what_happened"]


def test_end_to_end_advisory_risk_is_dropped_not_replaced():
    core = _core(answer={
        "bottom_line": "Reliance reported strong results.", "summary": "ok",
        "what_happened": "", "why_it_happened": "", "immediate_impact": "", "medium_term": "", "long_term": "",
        "risks": ["This is a solid buy candidate regardless of risk.", "Execution risk remains real."],
    })
    result = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    assert result["risks_and_invalidation"]["risks"] == ["Execution risk remains real."]


# ── Zero regeneration: no LLM / retrieval imports anywhere in Build 1 ──────

def test_new_build1_modules_never_import_provider_or_retrieval_code():
    import inspect
    from app.services.ai_search.aev2 import citation_validator as cv_mod
    from app.services.ai_search.aev2 import confidence as conf_mod
    from app.services.ai_search.aev2 import price_movement as pm_mod

    for mod in (cv_mod, conf_mod, pm_mod):
        source = inspect.getsource(mod)
        assert "yfinance" not in source
        assert "_fetch_quote" not in source
        assert "_call_with_fallback" not in source
        assert "evidence.collect" not in source
