"""
AEV2 Build 1 (2026-09-21) — the backend response assembler + citation
validator built from CoreAnswer only. Rewritten in review's second pass
(same day) to reflect two corrections and two verification asks:

  1. Confidence restored to the CLOSED SPEC formula (0.35/0.25/0.25/0.15
     over evidence_quality/market_confirmation/historical_similarity/
     data_freshness) — the first draft's source_diversity/company_
     attribution substitution is gone.
  2. Entity validation is no longer vacuous when zero companies
     resolved, and the global "known acronym" allowlist is gone — an
     acronym-shaped token now passes only via a resolved company or by
     literally appearing in the cited evidence text.
  3. evidence_refs is now citation_validator.deterministic_claim_
     evidence_refs(core)'s output (real company<->event field matching)
     — never the whole catalog attached indiscriminately. Fixtures below
     give events a real `companies` field so this relationship is
     genuinely exercised, not accidentally vacuous.
  4. related_intelligence.events carries no url/link/href field (Slice
     3's route-builder doesn't exist yet) — checked explicitly here in
     addition to the readiness latch.

See test_ai_search_single_pipeline_runtime.py for the still-holding
one-specialist-call and cache-hit invariants (unaffected — assemble_
aev2's signature is unchanged) and test_aev2_foundation.py for the
still-holding readiness-latch/mode-gating tests.
"""
from __future__ import annotations

import copy

from app.services.ai_search.aev2 import citation_validator, price_movement
from app.services.ai_search.aev2.assemble import assemble_aev2
from app.services.ai_search.aev2.confidence import compute_aev2_confidence
from app.services.ai_search.aev2.language_gate import FALLBACK_TEXT
from app.services.ai_search.aev2.mode import AEV2Mode
from app.services.ai_search.core_answer import from_v3_response
from app.services.ai_search.response_finalize import finalize_v3_response

RELIANCE = {"symbol": "RELIANCE", "name": "Reliance Industries Ltd"}
# A real, company-linked event — companies field is what
# deterministic_claim_evidence_refs actually keys on.
LINKED_EVENT = {
    "id": "e1", "title": "Reliance Industries secures 2,500 MW RTC power supply contract",
    "date": "2026-09-15", "companies": [RELIANCE],
}
# A second, UNLINKED event — a real event that exists in evidence, but
# for a different company entirely. Used to prove "valid ID, wrong
# company" and "number exists in another uncited source" cases.
UNLINKED_EVENT = {
    "id": "e2", "title": "Tata Motors reports 9,999 crore quarterly revenue",
    "date": "2026-09-16", "companies": [{"symbol": "TATAMOTORS", "name": "Tata Motors Ltd"}],
}
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
        "related_events": [dict(LINKED_EVENT)],
        "news": [dict(FRESH_NEWS)],
        "policies": [],
        "investment_verdict": {"horizon": "1-3 months"},
        "confidence_breakdown": {
            "evidence_quality": 70.0, "market_confirmation": 60.0,
            "historical_similarity": 40.0, "data_freshness": 90.0,
        },
    }
    base.update(overrides)
    return base


def _core(**overrides):
    return from_v3_response(_v3_response(**overrides))


# ── Deterministic restructuring fields ──────────────────────────────────────

def test_direct_conclusion_what_happened_why_it_matters_populated_from_core():
    result = assemble_aev2(_core(), mode=AEV2Mode.PUBLIC)
    assert result["direct_conclusion"]["text"] == "Reliance Industries secured a 2,500 MW power supply contract."
    assert result["direct_conclusion"]["evidence_refs"] == ["event:e1"]
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
    assert events[0]["title"] == LINKED_EVENT["title"]
    assert result["related_intelligence"]["opportunities"] == []
    assert result["related_intelligence"]["ripple"] is None


def test_related_intelligence_events_carry_no_link_or_route_field():
    """Slice 3's canonical route-builder doesn't exist yet — this must
    stay data-only (id/title/date) regardless of what the readiness
    latch is doing; a second, independent boundary at the shape itself."""
    result = assemble_aev2(_core(), mode=AEV2Mode.PUBLIC)
    for event in result["related_intelligence"]["events"]:
        assert set(event.keys()) == {"id", "title", "date"}
        for forbidden in ("url", "link", "href", "path", "route"):
            assert forbidden not in event


def test_evidence_catalog_includes_both_event_and_news():
    result = assemble_aev2(_core(), mode=AEV2Mode.PUBLIC)
    ids = {e["id"] for e in result["evidence"]}
    assert ids == {"event:e1", "news:n1"}


# ── CompanyAnnouncement coverage (per-symbol, already-approved link) ───────

LINKED_ANNOUNCEMENT = {
    "id": "a1", "symbol": "RELIANCE", "subject": "Reliance Industries board approves 2,500 MW power project",
    "announcement_date": "2026-09-16",
}


def test_announcement_included_in_evidence_catalog():
    core = _core(announcements=[dict(LINKED_ANNOUNCEMENT)])
    result = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    ids = {e["id"] for e in result["evidence"]}
    assert "announcement:a1" in ids


def test_announcement_contributes_to_deterministic_claim_refs_via_direct_symbol():
    """CompanyAnnouncement rows carry a direct `symbol` column — an even
    more unambiguous match than events' companies list."""
    core = _core(related_events=[], news=[], announcements=[dict(LINKED_ANNOUNCEMENT)])
    refs = citation_validator.deterministic_claim_evidence_refs(core)
    assert refs == ["announcement:a1"]


def test_announcement_for_a_different_company_is_not_cited():
    other_company_announcement = {"id": "a2", "symbol": "TATAMOTORS", "subject": "Tata Motors reports results"}
    core = _core(related_events=[], news=[], announcements=[other_company_announcement])
    refs = citation_validator.deterministic_claim_evidence_refs(core)
    assert refs == []


def test_end_to_end_claim_supported_by_a_cited_announcement_number():
    core = _core(
        related_events=[], news=[], announcements=[dict(LINKED_ANNOUNCEMENT)],
        answer={
            "bottom_line": "Reliance's board approved a 2,500 MW power project.",
            "summary": "ok", "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "risks": [],
        },
    )
    result = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    assert result["direct_conclusion"]["text"] == "Reliance's board approved a 2,500 MW power project."
    assert result["direct_conclusion"]["evidence_refs"] == ["announcement:a1"]


# ── Verdict/scenario/suitability/top-pick concepts are absent everywhere ───

def _flatten_keys(obj) -> set[str]:
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _flatten_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _flatten_keys(item)
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
    companies = (
        {"symbol": "WIPRO", "name": "Wipro Ltd", "price": "—", "positive": True},
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


# ── Confidence: restored to the closed-spec formula ─────────────────────────

def test_confidence_matches_the_approved_weighted_formula():
    core = _core()  # evidence_quality=70, market_confirmation=60, historical_similarity=40, data_freshness=90
    expected = round(0.35 * 70.0 + 0.25 * 60.0 + 0.25 * 40.0 + 0.15 * 90.0, 1)
    result = compute_aev2_confidence(core)
    assert result["score"] == expected
    assert result["components_available"] == ["data_freshness", "evidence_quality", "historical_similarity", "market_confirmation"]


def test_confidence_unscored_when_no_signal_available():
    core = from_v3_response({"answer": {"bottom_line": "x"}})
    result = compute_aev2_confidence(core)
    assert result == {"score": None, "level": "unscored", "components_available": []}


def test_confidence_missing_components_contribute_zero_never_renormalized():
    """The closed errata's exact example: evidence_quality=100 with the
    other 3 missing must score 0.35 * 100 = 35.0, NOT 100.0. A missing
    component contributes zero — it is never redistributed onto the
    weights of whatever IS present."""
    core = from_v3_response({
        "answer": {"bottom_line": "x"},
        "confidence_breakdown": {"evidence_quality": 100.0},
    })
    result = compute_aev2_confidence(core)
    assert result["score"] == 35.0
    assert result["components_available"] == ["evidence_quality"]


def test_confidence_two_missing_components_still_fixed_weight():
    """evidence_quality(0.35) and data_freshness(0.15) present — must be
    0.35*80 + 0.15*40, the fixed-weight sum, NOT that sum divided by
    (0.35+0.15) as a renormalized average would compute."""
    core = from_v3_response({
        "answer": {"bottom_line": "x"},
        "confidence_breakdown": {"evidence_quality": 80.0, "data_freshness": 40.0},
    })
    result = compute_aev2_confidence(core)
    expected = round(0.35 * 80.0 + 0.15 * 40.0, 1)  # = 34.0, not 66.7
    assert result["score"] == expected
    assert result["score"] != round((0.35 * 80.0 + 0.15 * 40.0) / (0.35 + 0.15), 1), (
        "score must not match what renormalizing across only the present weights would produce"
    )
    assert result["components_available"] == ["data_freshness", "evidence_quality"]


def test_sparse_evidence_cannot_receive_a_fully_confident_score():
    """A single perfect component (100) must never map to a "Very
    High"/near-100 level just because it's the only one available —
    sparse coverage must read as sparse, not as strong."""
    core = from_v3_response({
        "answer": {"bottom_line": "x"},
        "confidence_breakdown": {"market_confirmation": 100.0},
    })
    result = compute_aev2_confidence(core)
    assert result["score"] == 25.0  # 0.25 * 100
    assert result["level"] not in ("Very High", "High")


def test_all_four_missing_is_unscored_not_a_misleading_zero():
    core = from_v3_response({"answer": {"bottom_line": "x"}, "confidence_breakdown": {}})
    result = compute_aev2_confidence(core)
    assert result["score"] is None
    assert result["level"] == "unscored"
    assert result["components_available"] == []


def test_confidence_score_bounded_by_min_and_max_component_never_exceeds_best():
    """A weighted average of bounded values can never exceed the best
    individual component nor fall below the worst — proof, not just
    claim, that this formula cannot inflate a score beyond what the
    individual (already deduplication-aware) components support."""
    core = from_v3_response({
        "answer": {"bottom_line": "x"},
        "confidence_breakdown": {
            "evidence_quality": 20.0, "market_confirmation": 100.0,
            "historical_similarity": 20.0, "data_freshness": 20.0,
        },
    })
    result = compute_aev2_confidence(core)
    assert 20.0 <= result["score"] <= 100.0


def test_confidence_identical_regardless_of_corroborating_source_count():
    """AEV2 does zero counting of its own — evidence_quality is read
    verbatim from postprocess.py's already-dedup-aware value. Two
    otherwise-identical CoreAnswers differing only in how many raw
    (possibly duplicate) source rows corroborate the same evidence_
    quality score must produce the IDENTICAL AEV2 score — proving
    duplicate sources/companies cannot inflate this formula, because it
    never looks at counts at all."""
    breakdown = {"evidence_quality": 70.0, "market_confirmation": 60.0, "historical_similarity": 40.0, "data_freshness": 90.0}
    core_few_sources = from_v3_response({
        "answer": {"bottom_line": "x"}, "confidence_breakdown": dict(breakdown),
        "related_events": [{"id": "e1", "title": "one filing", "companies": [RELIANCE]}],
    })
    core_many_duplicate_sources = from_v3_response({
        "answer": {"bottom_line": "x"}, "confidence_breakdown": dict(breakdown),
        "related_events": [
            {"id": f"e{i}", "title": "the same filing reported again", "companies": [RELIANCE]} for i in range(10)
        ],
    })
    assert compute_aev2_confidence(core_few_sources) == compute_aev2_confidence(core_many_duplicate_sources)


def test_confidence_distribution_across_representative_fixtures():
    """The requested distribution comparison: several realistic
    combinations of the 4 approved components, each hand-computed
    against the exact 0.35/0.25/0.25/0.15 weighting, proving the formula
    is applied correctly across the range rather than for one lucky
    fixture."""
    fixtures = [
        # (evidence_quality, market_confirmation, historical_similarity, data_freshness)
        (90.0, 85.0, 80.0, 95.0),   # strong, well-evidenced case
        (50.0, 50.0, 50.0, 50.0),   # flat/uniform case
        (10.0, 5.0, 0.0, 20.0),     # weak/thin-evidence case
        (100.0, 0.0, 0.0, 0.0),     # single dominant component
        (0.0, 0.0, 0.0, 100.0),     # freshness-only signal
    ]
    for eq, mc, hs, df in fixtures:
        core = from_v3_response({
            "answer": {"bottom_line": "x"},
            "confidence_breakdown": {
                "evidence_quality": eq, "market_confirmation": mc,
                "historical_similarity": hs, "data_freshness": df,
            },
        })
        expected = round(0.35 * eq + 0.25 * mc + 0.25 * hs + 0.15 * df, 1)
        result = compute_aev2_confidence(core)
        assert result["score"] == expected, f"fixture {(eq, mc, hs, df)}: expected {expected}, got {result['score']}"
        assert min(eq, mc, hs, df) <= result["score"] <= max(eq, mc, hs, df)


def test_confidence_component_meanings_documented_and_stable():
    """A cheap regression guard on the labels a future UI will render —
    catches an accidental rename of a component key."""
    result = compute_aev2_confidence(_core())
    assert set(result["components_available"]) <= {
        "evidence_quality", "market_confirmation", "historical_similarity", "data_freshness",
    }


# ── Entity validation: no vacuous pass, no global acronym trust ────────────

def test_entities_supported_no_longer_vacuous_when_nothing_resolved():
    """The exact regression this review named: zero companies resolved
    is precisely when an unsupported company mention is riskiest, so it
    must now FAIL, not pass by default."""
    assert not citation_validator.entities_supported(
        "WIPRO is expected to benefit as well.", set(), set(), supporting_text="",
    )


def test_entities_supported_passes_when_token_appears_in_cited_evidence_text():
    """No acronym allowlist needed — RBI passes here only because the
    cited evidence text itself contains "RBI", a genuine, traceable
    source, not a blanket trust grant."""
    assert citation_validator.entities_supported(
        "RBI's policy stance supports this outlook.", set(), set(),
        supporting_text="RBI kept the repo rate unchanged at its latest policy meeting.",
    )


def test_entities_supported_fails_for_acronym_absent_from_cited_evidence():
    """The same RBI token, but the cited evidence never mentions it —
    must now fail; there is no more global "well-known acronym" pass."""
    assert not citation_validator.entities_supported(
        "RBI's policy stance supports this outlook.", set(), set(),
        supporting_text="Reliance Industries secured a 2,500 MW contract.",
    )


def test_recognized_name_tokens_still_covers_name_shorthand():
    tokens = citation_validator.recognized_name_tokens(({"symbol": "HDFCBANK", "name": "HDFC Bank Ltd"},))
    assert "HDFC" in tokens
    assert citation_validator.entities_supported(
        "HDFC Bank reported results.", {"HDFCBANK"}, tokens, supporting_text="",
    )


# ── Adversarial citation tests (review-required) ────────────────────────────

def test_valid_id_pointing_to_the_wrong_company_is_not_included_as_a_claim_ref():
    """UNLINKED_EVENT is a real, valid catalog member — but it's tied to
    Tata Motors, not Reliance (the query's only resolved company).
    deterministic_claim_evidence_refs must exclude it even though it
    "exists" — a valid ID for the wrong company is not evidence for this
    claim."""
    core = _core(related_events=[dict(LINKED_EVENT), dict(UNLINKED_EVENT)])
    refs = citation_validator.deterministic_claim_evidence_refs(core)
    assert refs == ["event:e1"]
    assert "event:e2" not in refs


def test_number_in_an_uncited_source_does_not_support_the_claim():
    """9,999 crore is a REAL number that genuinely exists in
    UNLINKED_EVENT's own title — but that event is never cited for a
    Reliance-only claim. Citing a number because it's true SOMEWHERE in
    the overall evidence set (not the specific cited source) must fail."""
    core = _core(
        related_events=[dict(LINKED_EVENT), dict(UNLINKED_EVENT)],
        answer={
            "bottom_line": "Reliance reported 9,999 crore in the same period.",
            "summary": "ok", "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "risks": [],
        },
    )
    result = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    assert result["direct_conclusion"]["text"] == FALLBACK_TEXT["direct_conclusion"]


def test_a_claim_cannot_cite_all_evidence_indiscriminately():
    """With 2 catalog entries but only 1 company-linked, evidence_refs
    for any claim must be a genuine subset, never the full catalog."""
    core = _core(related_events=[dict(LINKED_EVENT), dict(UNLINKED_EVENT)])
    result = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    assert result["direct_conclusion"]["evidence_refs"] == ["event:e1"]
    assert len(result["evidence"]) == 3  # e1 + e2 + n1 all still shown in the transparent catalog
    assert set(result["direct_conclusion"]["evidence_refs"]) < {e["id"] for e in result["evidence"]}


def test_no_company_resolves_but_the_claim_names_one_fails_closed():
    core = _core(
        companies=[], related_events=[], news=[], policies=[],
        answer={
            "bottom_line": "WIPRO also stands to benefit from this contract.",
            "summary": "ok", "what_happened": "", "why_it_happened": "", "immediate_impact": "",
            "medium_term": "", "long_term": "", "risks": [],
        },
    )
    result = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    assert result["direct_conclusion"]["text"] == FALLBACK_TEXT["direct_conclusion"]
    assert result["direct_conclusion"]["evidence_refs"] == []


def test_deterministic_fallback_text_itself_contains_no_unsupported_entity_or_number():
    """The safety-net text must never accidentally trip its own
    validator, even under the strictest possible conditions (nothing
    resolved, nothing cited) — checked for every fallback string."""
    for field_kind, fallback in FALLBACK_TEXT.items():
        claim = citation_validator.validate_claim(
            fallback, evidence_refs=[], catalog_ids=set(),
            recognized_symbols=set(), supporting_text="", name_tokens=set(),
        )
        assert claim.valid, f"fallback text for {field_kind!r} failed its own validator: {claim.reasons}"


# ── End-to-end: existing fabrication/violation scenarios still caught ──────

def test_end_to_end_unsupported_number_falls_back_to_honest_fallback():
    core = _core(answer={
        "bottom_line": "Reliance secured a 99,999 MW contract.",
        "summary": "ok", "what_happened": "", "why_it_happened": "", "immediate_impact": "",
        "medium_term": "", "long_term": "", "risks": [],
    })
    result = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
    assert result["direct_conclusion"]["text"] == FALLBACK_TEXT["direct_conclusion"]
    assert result["direct_conclusion"]["evidence_refs"] == []


def test_end_to_end_advisory_language_in_what_happened_is_gated():
    core = _core(answer={
        "bottom_line": "Reliance reported strong results.", "summary": "ok",
        "what_happened": "Reliance remains a solid buy candidate.",
        "why_it_happened": "", "immediate_impact": "", "medium_term": "", "long_term": "", "risks": [],
    })
    result = assemble_aev2(core, mode=AEV2Mode.PUBLIC)
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


# ── V3 output unchanged (snapshot) — successful, degraded, cached ─────────
#
# 2026-09-23: also excludes "answer_availability" from the compared
# snapshot, the same way "answer_experience_v2" already is — it is a
# real, intentional new field response_finalize.py now always attaches
# (see _derive_answer_availability), not a regression in the pre-
# existing V3 contract these tests exist to protect. Its own behavior
# has dedicated coverage in test_answer_availability.py.
_SNAPSHOT_EXCLUDED_FIELDS = ("answer_experience_v2", "answer_availability")


def test_v3_snapshot_unchanged_for_successful_response_regardless_of_aev2_mode(monkeypatch):
    from app.core.config import settings
    from app.services.ai_search.aev2 import mode as mode_mod

    monkeypatch.setattr(mode_mod, "AEV2_BUILD_COMPLETE", True)
    monkeypatch.setattr(settings, "admin_api_key", "real-secret")

    for mode in ("off", "shadow", "canary", "public"):
        monkeypatch.setattr(settings, "ai_search_aev2_mode", mode)
        v3 = _v3_response()
        before = copy.deepcopy(v3)
        # was_cached=True isolates this from the fire-and-forget prediction
        # task's own side effects — not what this test is checking.
        result = finalize_v3_response("q", v3, x_admin_key="real-secret", was_cached=True)
        v3_only = {k: v for k, v in result.items() if k not in _SNAPSHOT_EXCLUDED_FIELDS}
        assert v3_only == before, f"V3 portion changed under mode={mode}"


def test_v3_snapshot_unchanged_for_degraded_response():
    degraded = {
        "query": "q", "response_id": "r1", "schema_version": "v3.1", "specialist": "company",
        "degraded_reason": "parse_failure", "synthesis_incomplete": True,
        "answer": {"summary": "no analysis available", "bottom_line": "no analysis available", "sources_count": 0},
        "companies": [], "related_events": [], "news": [], "policies": [],
    }
    before = copy.deepcopy(degraded)
    result = finalize_v3_response("q", degraded, was_cached=True)
    v3_only = {k: v for k, v in result.items() if k not in _SNAPSHOT_EXCLUDED_FIELDS}
    assert v3_only == before


def test_v3_snapshot_unchanged_on_a_cache_hit():
    """The object the cache actually stored must be byte-identical
    before and after passing through finalize_v3_response on a
    (simulated) later cache-hit request."""
    cached = _v3_response()
    before = copy.deepcopy(cached)
    result = finalize_v3_response("q", cached, was_cached=True)
    assert cached == before, "the cached object itself must never be mutated"
    v3_only = {k: v for k, v in result.items() if k not in _SNAPSHOT_EXCLUDED_FIELDS}
    assert v3_only == before
