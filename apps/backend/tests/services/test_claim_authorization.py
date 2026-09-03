"""
CD3-D — tests for app.services.claim_authorization, the central public
claim authorization contract. Same shape as test_claim_provenance.py /
test_measurement_semantics.py: lock in the exact boundary a real
regression could silently cross.
"""
from __future__ import annotations

from app.services.claim_authorization import (
    FORECAST_UNAVAILABLE,
    RECOMMENDATION_UNAVAILABLE,
    Capability,
    Strength,
    authorize_direction,
    authorize_measurement,
    authorize_ripple,
)
from app.services.claim_provenance import ClaimProvenance, RippleEvidenceState
from app.services.measurement_semantics import IntegrityStatus, MeasurementType


# ── Directional claims ────────────────────────────────────────────────────────

def test_price_sign_is_authorized_observed_direction():
    c = authorize_direction(ClaimProvenance.PRICE_SIGN)
    assert c.capability == Capability.OBSERVED_DIRECTION
    assert c.strength == Strength.AUTHORIZED


def test_historical_outcome_is_authorized_historical_description():
    c = authorize_direction(ClaimProvenance.HISTORICAL_OUTCOME)
    assert c.capability == Capability.HISTORICAL_DESCRIPTION
    assert c.strength == Strength.AUTHORIZED


def test_analytical_hypothesis_is_qualified_never_authorized():
    c = authorize_direction(ClaimProvenance.ANALYTICAL_HYPOTHESIS)
    assert c.capability == Capability.ANALYTICAL_HYPOTHESIS
    assert c.strength == Strength.QUALIFIED


def test_event_direction_is_qualified_same_as_analytical_hypothesis():
    c = authorize_direction(ClaimProvenance.EVENT_DIRECTION)
    assert c.capability == Capability.ANALYTICAL_HYPOTHESIS
    assert c.strength == Strength.QUALIFIED


def test_fallback_provenance_is_unavailable():
    c = authorize_direction(ClaimProvenance.FALLBACK)
    assert c.strength == Strength.UNAVAILABLE


def test_unavailable_provenance_is_unavailable():
    c = authorize_direction(ClaimProvenance.UNAVAILABLE)
    assert c.strength == Strength.UNAVAILABLE


def test_unknown_provenance_is_unavailable():
    c = authorize_direction(ClaimProvenance.UNKNOWN)
    assert c.strength == Strength.UNAVAILABLE


def test_any_non_valid_integrity_collapses_to_unavailable_regardless_of_provenance():
    for provenance in ClaimProvenance:
        for status in (IntegrityStatus.DEGRADED, IntegrityStatus.FALLBACK,
                       IntegrityStatus.UNAVAILABLE, IntegrityStatus.INVALID):
            c = authorize_direction(provenance, integrity=status)
            assert c.strength == Strength.UNAVAILABLE, f"{provenance}+{status} must be UNAVAILABLE"


# ── Ripple / relationship claims ─────────────────────────────────────────────

def test_ripple_observed_is_authorized():
    c = authorize_ripple(RippleEvidenceState.OBSERVED)
    assert c.capability == Capability.CAUSAL_RELATIONSHIP
    assert c.strength == Strength.AUTHORIZED


def test_ripple_supported_is_qualified():
    c = authorize_ripple(RippleEvidenceState.SUPPORTED)
    assert c.strength == Strength.QUALIFIED


def test_ripple_hypothesized_is_qualified_never_authorized():
    """The owner's explicit example: HYPOTHESIZED must never authorize
    "X causes Y" -- only "possible transmission mechanism" (QUALIFIED)."""
    c = authorize_ripple(RippleEvidenceState.HYPOTHESIZED)
    assert c.capability == Capability.CAUSAL_RELATIONSHIP
    assert c.strength == Strength.QUALIFIED
    assert c.strength != Strength.AUTHORIZED


def test_ripple_unavailable_is_unavailable():
    c = authorize_ripple(RippleEvidenceState.UNAVAILABLE)
    assert c.strength == Strength.UNAVAILABLE


def test_ripple_non_valid_integrity_collapses_to_unavailable():
    for status in (IntegrityStatus.DEGRADED, IntegrityStatus.FALLBACK,
                   IntegrityStatus.UNAVAILABLE, IntegrityStatus.INVALID):
        c = authorize_ripple(RippleEvidenceState.OBSERVED, integrity=status)
        assert c.strength == Strength.UNAVAILABLE


# ── Measurement claims ────────────────────────────────────────────────────────

def test_self_reported_certainty_is_always_qualified():
    c = authorize_measurement(MeasurementType.SELF_REPORTED_CERTAINTY, IntegrityStatus.VALID)
    assert c.strength == Strength.QUALIFIED
    assert c.strength != Strength.AUTHORIZED


def test_evidence_composite_hybrid_deterministic_calibration_are_authorized():
    for mt in (MeasurementType.EVIDENCE_COMPOSITE, MeasurementType.HYBRID_RUBRIC,
               MeasurementType.DETERMINISTIC_METRIC, MeasurementType.HISTORICAL_CALIBRATION):
        c = authorize_measurement(mt, IntegrityStatus.VALID)
        assert c.strength == Strength.AUTHORIZED, f"{mt} should be AUTHORIZED"


def test_derived_transform_and_unknown_measurement_are_unavailable():
    for mt in (MeasurementType.DERIVED_TRANSFORM, MeasurementType.UNKNOWN):
        c = authorize_measurement(mt, IntegrityStatus.VALID)
        assert c.strength == Strength.UNAVAILABLE


def test_measurement_non_valid_integrity_collapses_to_unavailable():
    for status in (IntegrityStatus.DEGRADED, IntegrityStatus.FALLBACK,
                   IntegrityStatus.UNAVAILABLE, IntegrityStatus.INVALID):
        c = authorize_measurement(MeasurementType.EVIDENCE_COMPOSITE, status)
        assert c.strength == Strength.UNAVAILABLE


# ── FORECAST / RECOMMENDATION — permanently unavailable ─────────────────────

def test_forecast_capability_is_permanently_unavailable():
    assert FORECAST_UNAVAILABLE.capability == Capability.FORECAST
    assert FORECAST_UNAVAILABLE.strength == Strength.UNAVAILABLE
    assert FORECAST_UNAVAILABLE.reason


def test_recommendation_capability_is_permanently_unavailable():
    assert RECOMMENDATION_UNAVAILABLE.capability == Capability.RECOMMENDATION
    assert RECOMMENDATION_UNAVAILABLE.strength == Strength.UNAVAILABLE
    assert RECOMMENDATION_UNAVAILABLE.reason


# ── The owner's named adversarial scenario ───────────────────────────────────

class TestAdversarialAnalyticalHypothesisScenario:
    """impact=positive, provenance=ANALYTICAL_HYPOTHESIS,
    evidence_state=HYPOTHESIZED, integrity=VALID -- must never become
    Bullish / Positive company / Beneficiary / Likely winner / Forecast /
    Recommendation, while a properly qualified analytical hypothesis
    must still be renderable where the product needs one."""

    def test_cannot_reach_authorized_directional_strength(self):
        c = authorize_direction(ClaimProvenance.ANALYTICAL_HYPOTHESIS, IntegrityStatus.VALID)
        # This is the exact tuple a "Bullish"/"Positive company"/
        # "Beneficiary"/"Likely winner" badge would need AUTHORIZED
        # strength to legitimately render as a bare declarative claim.
        assert c.strength != Strength.AUTHORIZED
        assert c.strength == Strength.QUALIFIED

    def test_cannot_reach_forecast_capability_at_all(self):
        # No authorize_* function ever returns Capability.FORECAST --
        # the only way to "get" it is the permanently-unavailable
        # constant. Confirm the directional/ripple/measurement functions
        # never produce it, even fed this exact adversarial input.
        c1 = authorize_direction(ClaimProvenance.ANALYTICAL_HYPOTHESIS, IntegrityStatus.VALID)
        c2 = authorize_ripple(RippleEvidenceState.HYPOTHESIZED, IntegrityStatus.VALID)
        assert c1.capability != Capability.FORECAST
        assert c2.capability != Capability.FORECAST
        assert FORECAST_UNAVAILABLE.strength == Strength.UNAVAILABLE

    def test_cannot_reach_recommendation_capability_at_all(self):
        c1 = authorize_direction(ClaimProvenance.ANALYTICAL_HYPOTHESIS, IntegrityStatus.VALID)
        c2 = authorize_ripple(RippleEvidenceState.HYPOTHESIZED, IntegrityStatus.VALID)
        assert c1.capability != Capability.RECOMMENDATION
        assert c2.capability != Capability.RECOMMENDATION
        assert RECOMMENDATION_UNAVAILABLE.strength == Strength.UNAVAILABLE

    def test_the_hypothesized_ripple_edge_in_the_same_scenario_stays_qualified(self):
        c = authorize_ripple(RippleEvidenceState.HYPOTHESIZED, IntegrityStatus.VALID)
        assert c.strength == Strength.QUALIFIED
        assert c.strength != Strength.AUTHORIZED

    def test_a_properly_qualified_analytical_hypothesis_IS_still_renderable(self):
        """The positive control this whole model exists to preserve:
        QUALIFIED is not the same as UNAVAILABLE. The product can still
        show "potential positive impact" -- it just can never show it as
        an unqualified "Bullish"/"Beneficiary"/"Likely winner" claim."""
        c = authorize_direction(ClaimProvenance.ANALYTICAL_HYPOTHESIS, IntegrityStatus.VALID)
        assert c.strength == Strength.QUALIFIED
        assert c.strength != Strength.UNAVAILABLE  # still renderable, just hedged
