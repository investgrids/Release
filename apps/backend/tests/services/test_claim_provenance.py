"""
CD3-B — consumer compatibility tests for the typed claim provenance /
Ripple evidence-state vocabulary (app.services.claim_provenance). These
matter more than enum serialization: they lock in the compatibility
matrix itself (a producer's real semantic vs. what it may/must-not
authorize) and the fail-safe behavior for unknown/legacy data, since
CD3-A found the platform's core failure mode is exactly the opposite --
different producers' incompatible signals silently authorizing the same
strong public claim.
"""
from __future__ import annotations

from app.services.claim_provenance import (
    AUTHORIZATION_BOUNDARY,
    RIPPLE_AUTHORIZATION_BOUNDARY,
    ClaimProvenance,
    RippleEvidenceState,
    get_claim_provenance,
    get_ripple_evidence_state,
)


# ── Vocabulary completeness ──────────────────────────────────────────────────

def test_every_claim_provenance_value_has_a_documented_boundary():
    for value in ClaimProvenance:
        assert value in AUTHORIZATION_BOUNDARY, f"{value} has no documented authorization boundary"
        entry = AUTHORIZATION_BOUNDARY[value]
        assert entry.get("may_authorize")
        assert entry.get("must_not_authorize")


def test_every_ripple_evidence_state_has_a_documented_boundary():
    for value in RippleEvidenceState:
        assert value in RIPPLE_AUTHORIZATION_BOUNDARY, f"{value} has no documented authorization boundary"


# ── Named consumer-compatibility scenarios (owner's exact list, 2026-09-02) ──

def test_price_sign_positive_may_render_shares_rose_not_beneficiary():
    b = AUTHORIZATION_BOUNDARY[ClaimProvenance.PRICE_SIGN]
    assert "rose" in b["may_authorize"].lower() or "price" in b["may_authorize"].lower()
    assert "beneficiary" in b["must_not_authorize"].lower()
    assert "forecast" in b["must_not_authorize"].lower()


def test_historical_outcome_positive_may_render_history_not_current_forecast():
    b = AUTHORIZATION_BOUNDARY[ClaimProvenance.HISTORICAL_OUTCOME]
    assert "historical" in b["may_authorize"].lower()
    assert "forecast" in b["must_not_authorize"].lower()


def test_analytical_hypothesis_positive_may_render_labeled_analysis_not_likely_winner():
    b = AUTHORIZATION_BOUNDARY[ClaimProvenance.ANALYTICAL_HYPOTHESIS]
    assert "labeled" in b["may_authorize"].lower() or "label" in b["may_authorize"].lower()
    assert "forecast" in b["must_not_authorize"].lower()
    assert "fact" in b["must_not_authorize"].lower()


def test_fallback_cannot_authorize_directional_output():
    b = AUTHORIZATION_BOUNDARY[ClaimProvenance.FALLBACK]
    assert b["may_authorize"].lower().startswith("nothing")
    assert "directional" in b["must_not_authorize"].lower()


def test_unavailable_cannot_authorize_even_neutral():
    """The owner's explicit correction: _FakeSector's fabricated "positive"
    must not become a fabricated "neutral" either -- UNAVAILABLE authorizes
    no directional claim at all, "neutral" included."""
    b = AUTHORIZATION_BOUNDARY[ClaimProvenance.UNAVAILABLE]
    assert b["may_authorize"].lower() == "nothing"
    assert "neutral" in b["must_not_authorize"].lower()


def test_hypothesized_ripple_cannot_render_as_observed_or_verified_causality():
    b = RIPPLE_AUTHORIZATION_BOUNDARY[RippleEvidenceState.HYPOTHESIZED]
    assert "hypothesized" in b["may_authorize"].lower() or "possible" in b["may_authorize"].lower()
    assert "verified" in b["must_not_authorize"].lower() or "established" in b["must_not_authorize"].lower()
    # The Market Memory / Intelligence Brain protection named explicitly.
    assert "market memory" in b["must_not_authorize"].lower() or "learned relationship" in b["must_not_authorize"].lower()


# ── State kept separate from relationship shape (owner's explicit design) ───

def test_ripple_evidence_state_is_a_distinct_axis_from_claim_provenance():
    """The owner's instruction: don't encode e.g. HYPOTHESIZED_POSITIVE into
    one enum -- a relationship's mechanism/direction and its evidence state
    are separate concerns, so the same mechanism can progress hypothesized
    -> supported -> observed without the relationship description changing.
    This just proves the two enums are genuinely independent types, not a
    single combined enum."""
    assert set(ClaimProvenance) != set(RippleEvidenceState)
    assert RippleEvidenceState.HYPOTHESIZED.value not in {v.value for v in ClaimProvenance}


# ── Fail-safe accessors: unknown/legacy never inferred into a stronger state ─

def test_get_claim_provenance_missing_key_resolves_to_unknown():
    assert get_claim_provenance({"impact": "positive"}) is ClaimProvenance.UNKNOWN


def test_get_claim_provenance_unrecognized_value_resolves_to_unknown():
    assert get_claim_provenance({"impact_provenance": "some_future_value_this_code_predates"}) is ClaimProvenance.UNKNOWN


def test_get_claim_provenance_reads_a_real_tag():
    entry = {"impact": "positive", "impact_provenance": ClaimProvenance.PRICE_SIGN.value}
    assert get_claim_provenance(entry) is ClaimProvenance.PRICE_SIGN


def test_get_claim_provenance_non_dict_input_resolves_to_unknown():
    assert get_claim_provenance("not-a-dict") is ClaimProvenance.UNKNOWN  # type: ignore[arg-type]


def test_get_ripple_evidence_state_missing_key_resolves_to_unavailable():
    """Weakest ripple state on missing/legacy data -- never HYPOTHESIZED or
    stronger just because the field is absent."""
    assert get_ripple_evidence_state({"from_entity": "a", "to_entity": "b"}) is RippleEvidenceState.UNAVAILABLE


def test_get_ripple_evidence_state_reads_a_real_tag():
    entry = {"evidence_state": RippleEvidenceState.HYPOTHESIZED.value}
    assert get_ripple_evidence_state(entry) is RippleEvidenceState.HYPOTHESIZED
