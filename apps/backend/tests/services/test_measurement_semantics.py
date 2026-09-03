"""
CD3-C — vocabulary/gate tests for app.services.measurement_semantics.
Same shape as test_claim_provenance.py: lock in the authorization
boundary and the fail-safe resolution helpers, since CD3-C's core failure
mode is exactly the opposite of what these functions guarantee --
different producers' incompatible measurements silently authorizing the
same "Confidence: X%" public claim.
"""
from __future__ import annotations

from app.services.measurement_semantics import (
    AUTHORIZATION_BOUNDARY,
    IntegrityStatus,
    Measurement,
    MeasurementType,
    is_publicly_authorized,
    resolve_integrity_status,
    resolve_measurement_type,
)


def _m(mt: MeasurementType, status: IntegrityStatus, value=50.0, scale="0-100", label="Test", reason=None) -> Measurement:
    return Measurement(measurement_type=mt, integrity_status=status, value=value, scale=scale, label=label, reason=reason)


# ── Vocabulary completeness ──────────────────────────────────────────────────

def test_every_non_unknown_measurement_type_has_a_documented_boundary():
    for value in MeasurementType:
        assert value in AUTHORIZATION_BOUNDARY, f"{value} has no documented authorization boundary"


def test_self_reported_certainty_may_not_authorize_a_confidence_percentage():
    b = AUTHORIZATION_BOUNDARY[MeasurementType.SELF_REPORTED_CERTAINTY]
    assert "self-rated" in b["may_authorize"].lower()
    assert "confidence" in b["must_not_authorize"].lower()


def test_evidence_composite_may_authorize_evidence_coverage_wording():
    b = AUTHORIZATION_BOUNDARY[MeasurementType.EVIDENCE_COMPOSITE]
    assert "evidence coverage" in b["may_authorize"].lower()
    assert "certainty" in b["must_not_authorize"].lower() or "probability" in b["must_not_authorize"].lower()


def test_deterministic_metric_must_never_be_called_confidence():
    b = AUTHORIZATION_BOUNDARY[MeasurementType.DETERMINISTIC_METRIC]
    assert "confidence" in b["must_not_authorize"].lower()


def test_historical_calibration_must_not_authorize_per_claim_probability():
    b = AUTHORIZATION_BOUNDARY[MeasurementType.HISTORICAL_CALIBRATION]
    assert "per-claim" in b["must_not_authorize"].lower()


def test_derived_transform_must_not_authorize_averaging_hypotheses_into_confidence():
    b = AUTHORIZATION_BOUNDARY[MeasurementType.DERIVED_TRANSFORM]
    assert "hypothesized" in b["must_not_authorize"].lower()


# ── The core public gate ─────────────────────────────────────────────────────

def test_valid_evidence_composite_is_publicly_authorized():
    assert is_publicly_authorized(_m(MeasurementType.EVIDENCE_COMPOSITE, IntegrityStatus.VALID)) is True


def test_valid_self_reported_certainty_is_publicly_authorized_as_itself():
    # Authorized to be SHOWN (as a self-rating) -- not authorized to be
    # shown AS a probability; that's the AUTHORIZATION_BOUNDARY's job,
    # this gate only answers "is there anything legitimate to show at all".
    assert is_publicly_authorized(_m(MeasurementType.SELF_REPORTED_CERTAINTY, IntegrityStatus.VALID)) is True


def test_fallback_is_never_publicly_authorized_regardless_of_type():
    for mt in MeasurementType:
        assert is_publicly_authorized(_m(mt, IntegrityStatus.FALLBACK)) is False


def test_invalid_gate_floor_is_never_publicly_authorized():
    m = _m(MeasurementType.SELF_REPORTED_CERTAINTY, IntegrityStatus.INVALID, value=0.7, reason="GATE_FLOOR_APPLIED")
    assert is_publicly_authorized(m) is False


def test_unavailable_is_never_publicly_authorized():
    assert is_publicly_authorized(_m(MeasurementType.EVIDENCE_COMPOSITE, IntegrityStatus.UNAVAILABLE)) is False


def test_degraded_is_never_publicly_authorized():
    assert is_publicly_authorized(_m(MeasurementType.HYBRID_RUBRIC, IntegrityStatus.DEGRADED)) is False


def test_unknown_measurement_type_is_never_publicly_authorized_even_if_valid():
    assert is_publicly_authorized(_m(MeasurementType.UNKNOWN, IntegrityStatus.VALID)) is False


def test_derived_transform_is_never_publicly_authorized_even_if_valid():
    """A derived transform (e.g. averaging edge confidences) needs its
    OWN inputs checked by its own caller -- this gate can't see them, so
    it must never wave one through just because someone marked it VALID."""
    assert is_publicly_authorized(_m(MeasurementType.DERIVED_TRANSFORM, IntegrityStatus.VALID)) is False


def test_none_measurement_is_never_publicly_authorized():
    assert is_publicly_authorized(None) is False


# ── Fail-safe resolution helpers ─────────────────────────────────────────────

def test_resolve_measurement_type_missing_value_is_unknown():
    assert resolve_measurement_type(None) is MeasurementType.UNKNOWN


def test_resolve_measurement_type_unrecognized_value_is_unknown():
    assert resolve_measurement_type("some_future_type_this_code_predates") is MeasurementType.UNKNOWN


def test_resolve_measurement_type_reads_a_real_value():
    assert resolve_measurement_type("evidence_composite") is MeasurementType.EVIDENCE_COMPOSITE


def test_resolve_integrity_status_missing_value_is_unavailable():
    assert resolve_integrity_status(None) is IntegrityStatus.UNAVAILABLE


def test_resolve_integrity_status_unrecognized_value_is_unavailable_not_valid():
    """The hard rule: a legacy persisted record with no recognizable
    integrity_status must never default to VALID just because a numeric
    value happens to be present."""
    assert resolve_integrity_status("some_legacy_status") is IntegrityStatus.UNAVAILABLE


def test_resolve_integrity_status_reads_a_real_value():
    assert resolve_integrity_status("invalid") is IntegrityStatus.INVALID


# ── Legacy-record fail-closed scenario, end to end ───────────────────────────

def test_legacy_record_with_no_typed_fields_fails_closed_end_to_end():
    """Simulates a real pre-CD3-C persisted record: only a bare numeric
    confidence value, no measurement_type/integrity_status fields at all.
    Reading it through the fail-safe resolvers and the public gate must
    produce a value that's never shown as a real confidence claim."""
    legacy_record = {"confidence": 0.8}  # no typed fields -- the exact shape old rows have
    mt = resolve_measurement_type(legacy_record.get("measurement_type"))
    status = resolve_integrity_status(legacy_record.get("integrity_status"))
    m = Measurement(measurement_type=mt, integrity_status=status, value=legacy_record["confidence"],
                     scale="unknown", label="unknown")
    assert is_publicly_authorized(m) is False
