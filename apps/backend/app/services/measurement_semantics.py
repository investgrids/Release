"""
CD3-C typed measurement semantics vocabulary — measurement_type +
integrity_status, kept as two independent axes on purpose.

CD3-C's read-only audit found the platform's confidence/evidence-score
fields are produced by several genuinely incompatible mechanisms -- a
bare LLM self-rating, a real structural evidence composite, a hybrid
rubric blending both, a historical-accuracy calibration factor, a
deterministic non-confidence metric (e.g. an impact magnitude) mislabeled
as "confidence," and static fallback content with no marker distinguishing
it from a real answer -- all rendered to users as an undifferentiated
"Confidence: X%". See the CD3-C audit and CD3-C implementation record
(memory: project_cd3_semantic_provenance_repair) for the full producer
inventory this codifies.

Deliberately two independent axes, mirroring CD3-B's
ClaimProvenance/RippleEvidenceState split (claim_provenance.py):
  - `measurement_type` answers "what kind of thing is this number,
    structurally" -- it does not change based on whether THIS particular
    instance succeeded or degraded.
  - `integrity_status` answers "is this specific instance trustworthy
    right now" -- the same measurement_type can be VALID today and
    FALLBACK tomorrow if the producer that made it failed.
A value's public wording must be authorized by BOTH axes together, never
by field name alone and never by numeric shape alone (a 0-100 self-rating
and a 0-100 evidence composite look identical as numbers; they are not
interchangeable claims).

Hard rule, per the CD3-C authorization: measurement type unknown -> do
not infer from field name -> do not convert to a percentage -> do not
display as "Confidence". Unknown/legacy data (persisted before this
vocabulary existed) must resolve to UNKNOWN measurement_type and
UNAVAILABLE integrity_status -- never inferred into a stronger claim than
the code can actually prove, exactly the same fail-closed contract
claim_provenance.py already established for directional claims.

This module is the vocabulary + documented authorization boundary +
fail-safe resolution helpers. It does not itself enforce the boundary at
every render/API call site -- CD3-C's implementation wires it into the
specific producers/consumers named in the CD3-C audit; enforcing it as a
single central public-claim-authorization boundary everywhere is CD3-D's
job, per the same sequencing CD3-B/CD3-C already followed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MeasurementType(str, Enum):
    """What structurally produced this number -- independent of whether
    this specific instance is currently trustworthy (see IntegrityStatus)."""

    # A bare LLM self-rating, no downstream computation. Never a
    # probability, never "accuracy" -- just what the model said about
    # itself when asked.
    SELF_REPORTED_CERTAINTY = "self_reported_certainty"

    # Computed entirely from real structural signals (source count,
    # historical similarity, market confirmation, etc.) with zero
    # self-report input. The reference exemplar is
    # weekend_intelligence/confidence.py's explicit "never reads an
    # LLM's own .confidence value" design.
    EVIDENCE_COMPOSITE = "evidence_composite"

    # Mostly EVIDENCE_COMPOSITE, but with a real self-report folded in as
    # one minor weighted factor (e.g. confidence_service.py's
    # `ai_certainty`, ~10% of the total). Must never be presented as
    # "fully computed"/"deterministic" without that caveat.
    HYBRID_RUBRIC = "hybrid_rubric"

    # A real accuracy/calibration figure computed from verified past
    # outcomes (Phase 6C's PredictionRecord/PredictionEvaluation/
    # CalibrationStat). Pooled coarsely (by confidence_level only, across
    # every source/prediction_type/horizon) -- see the CD3-C audit's
    # granularity note. May describe historical accuracy for a broad
    # tier; must never become a per-claim outcome probability.
    HISTORICAL_CALIBRATION = "historical_calibration"

    # A real, deterministic, non-confidence quantity (a magnitude, a
    # count, a coverage fraction) that happens to be numeric and was
    # mislabeled "confidence" somewhere along the way. The Ripple
    # event_impact scale-mismatch bug is the concrete example this value
    # exists for: event_impact is a real 0-10 IMPACT MAGNITUDE, never a
    # confidence in anything.
    DETERMINISTIC_METRIC = "deterministic_metric"

    # A client- or server-side arithmetic transform of some other real
    # value (e.g. IntelligenceGraph.tsx's average-of-edge-confidence
    # formulas) whose own semantic meaning has not been independently
    # established -- flag, don't silently trust just because the
    # arithmetic is well-defined. Averaging several HYPOTHESIZED-evidence-
    # state values (see claim_provenance.RippleEvidenceState) does not
    # produce a confidence; it produces an average of hypotheses.
    DERIVED_TRANSFORM = "derived_transform"

    # Legacy/unmapped data with no known producer -- never inferred into
    # a stronger type than this. The hard rule this whole module exists
    # to enforce: unknown type -> never displayed as "Confidence".
    UNKNOWN = "unknown"


class IntegrityStatus(str, Enum):
    """Is THIS specific instance of a measurement_type trustworthy right
    now -- independent of what kind of measurement it structurally is."""

    # A real, current, successfully-produced value of its measurement_type.
    VALID = "valid"

    # Produced, but under conditions that weaken it (e.g. a materiality
    # gate skipped, thin sample size) without being a total failure.
    DEGRADED = "degraded"

    # The real producer failed; this is static/templated content standing
    # in for it (e.g. deepseek_provider.py's _safe_json_call fallback
    # dicts, generate_scenario_analysis's degraded template). Matches the
    # Scenario Analysis fix's own contract exactly: FALLBACK content is
    # never publicly presented as analysis-shaped output.
    FALLBACK = "fallback"

    # No value exists at all for this instance (never assigned, or the
    # producer had insufficient data to even attempt one).
    UNAVAILABLE = "unavailable"

    # A value exists and is numeric, but it is not a legitimate
    # measurement of anything -- it was corrupted by unrelated logic
    # (e.g. AIPE's hardcoded 0.7 publish-gate floor overwriting a
    # genuine, lower self-report). Distinct from FALLBACK: the producer
    # didn't fail: publication logic silently overwrote a real answer.
    # Distinct from UNAVAILABLE: a number IS present, it's just not
    # trustworthy. Must always carry a `reason` explaining what corrupted
    # it (see Measurement.reason below).
    INVALID = "invalid"


@dataclass(frozen=True)
class Measurement:
    """A single typed value: what it structurally is, whether this
    instance is trustworthy, its real scale (never silently normalized to
    0-100 -- see the CD3-C rule against collapsing distinct scales into
    one universal percentage), and the human-facing label/reason to
    actually show. `value` is intentionally untyped (float | str | None)
    -- some measurements are qualitative buckets, not numbers."""

    measurement_type:  MeasurementType
    integrity_status:  IntegrityStatus
    value:             float | str | None
    # A short, real description of the native scale/unit -- e.g.
    # "0-100 evidence coverage", "0-10 impact magnitude", "qualitative
    # bucket (Low/Medium/High/Very High)", "percent historically correct".
    # Never assume 0-100 just because a number is present.
    scale:             str
    # The human-facing name for this specific value, chosen for what it
    # actually measures -- e.g. "Evidence Coverage", "Model Self-Rating",
    # "Impact Magnitude" -- never a bare, undifferentiated "Confidence".
    label:             str
    # Set only for INVALID (e.g. "GATE_FLOOR_APPLIED") or DEGRADED/
    # FALLBACK values, explaining what corrupted or weakened this
    # instance. None for a clean VALID measurement.
    reason:            str | None = None


# What each (measurement_type) may/must-not authorize in public wording,
# independent of integrity_status (a FALLBACK/UNAVAILABLE/INVALID instance
# of ANY type authorizes nothing regardless of what's listed here -- see
# `is_publicly_authorized` below).
AUTHORIZATION_BOUNDARY: dict[MeasurementType, dict[str, str]] = {
    MeasurementType.SELF_REPORTED_CERTAINTY: {
        "may_authorize": "\"The model's own self-rated certainty\" -- never a probability or accuracy claim",
        "must_not_authorize": "\"X% confidence\" unqualified, \"X% accurate\", \"X% likely\"",
    },
    MeasurementType.EVIDENCE_COMPOSITE: {
        "may_authorize": "\"Evidence Coverage\" or an equivalent structural-completeness label",
        "must_not_authorize": "Being called the model's certainty, or a probability of correctness",
    },
    MeasurementType.HYBRID_RUBRIC: {
        "may_authorize": "\"Evidence-based composite, primarily structural, with a minor self-assessed component\"",
        "must_not_authorize": "\"Fully computed\"/\"deterministic\" without disclosing the self-report component",
    },
    MeasurementType.HISTORICAL_CALIBRATION: {
        "may_authorize": "\"Historically X% correct across N verified predictions at this confidence tier\"",
        "must_not_authorize": "A per-claim outcome probability, or any source/horizon-specific accuracy claim the pooling can't support",
    },
    MeasurementType.DETERMINISTIC_METRIC: {
        "may_authorize": "Its own real, correctly-scaled name (e.g. \"Impact Magnitude: 7.2/10\")",
        "must_not_authorize": "Being labeled or displayed as \"Confidence\" in any form",
    },
    MeasurementType.DERIVED_TRANSFORM: {
        "may_authorize": "Nothing until the transform's own inputs' evidence states are confirmed compatible with averaging/combining",
        "must_not_authorize": "Presenting an average of HYPOTHESIZED-state inputs as a confidence value",
    },
    MeasurementType.UNKNOWN: {
        "may_authorize": "Nothing until classified",
        "must_not_authorize": "Any confidence-shaped public claim at all",
    },
}


def is_publicly_authorized(m: Measurement | None) -> bool:
    """The one boolean gate every consumer should check before rendering
    a Measurement as anything confidence-shaped. False for any non-VALID
    integrity_status regardless of measurement_type, and false for
    UNKNOWN/DERIVED_TRANSFORM measurement_type even when "valid" (a
    derived transform's own inputs must be checked separately -- this
    function can't see them). False for None -- no Measurement at all is
    never publicly authorized."""
    if m is None:
        return False
    if m.integrity_status != IntegrityStatus.VALID:
        return False
    if m.measurement_type in (MeasurementType.UNKNOWN, MeasurementType.DERIVED_TRANSFORM):
        return False
    return True


def resolve_measurement_type(raw: str | None) -> MeasurementType:
    """Fail-safe accessor, same pattern as claim_provenance.py's
    get_claim_provenance(): a missing/unrecognized value resolves to
    UNKNOWN, never inferred into a stronger type than the data proves.
    Use this instead of a bare dict.get() wherever a persisted/legacy
    value needs to be read back as a MeasurementType."""
    try:
        return MeasurementType(raw)
    except ValueError:
        return MeasurementType.UNKNOWN


def resolve_integrity_status(raw: str | None) -> IntegrityStatus:
    """Same fail-safe pattern as resolve_measurement_type -- a missing or
    unrecognized value resolves to UNAVAILABLE (the weakest status),
    never VALID just because the field happened to be absent."""
    try:
        return IntegrityStatus(raw)
    except ValueError:
        return IntegrityStatus.UNAVAILABLE
