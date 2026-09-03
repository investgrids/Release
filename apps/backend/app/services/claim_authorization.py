"""
CD3-D — Central Public Claim Authorization.

CD3-B (claim_provenance.py) answers "what kind of signal produced this
directional/relationship value." CD3-C (measurement_semantics.py) answers
"what kind of number is this, and is this specific instance trustworthy."
Neither enforces anything -- both were explicitly scoped to tagging data,
not deciding what a consumer may say. The CD3-D audit found exactly the
predicted consequence: dozens of independent consumers each decided for
themselves what to render, several silently discarding the B/C tags
along the way and reconstructing a stronger claim than the data
supports (an event-company's real, mixed impact_type collapsed to a
hardcoded "positive" in page.tsx; a HYPOTHESIZED Ripple edge rendered as
an unlabeled "-> causes" arrow, defaulting to "causes" even when the
relationship was undefined; a homepage template sentence built a
forecast ("will likely be led by X") with no forecast-capable producer
anywhere in the pipeline).

This module is the single place that answers the owner's own framing of
the question: **"Given this claim's type, provenance, evidence state,
measurement semantics, and integrity status, what is MarketRipple
allowed to tell the user?"**

Deliberately NOT a giant `isClaimAllowed()` enumerating page-specific
rules. A small, reusable CAPABILITY model instead: every public claim is
an attempt to exercise one of 7 capabilities (see `Capability` below).
A claim's real provenance/evidence-state/measurement-type, combined with
its current integrity_status, determines whether that capability is
granted -- and at what strength (AUTHORIZED / QUALIFIED / UNAVAILABLE).
Two capabilities (FORECAST, RECOMMENDATION) have NO legitimate producer
anywhere in the current pipeline and resolve UNAVAILABLE unconditionally
-- this is not a gap to be "fixed" by inventing complicated authorization
rules to rescue existing forecast/recommendation-shaped output. If a
future producer earns one of these (e.g. a real calibrated, benchmark-
relative forecast engine), it gets a real new authorization rule then --
not before.

Enforcement location, per the owner's explicit correction when opening
this phase: authorization must live BELOW presentation, not inside a
shared component (a component-level gate is one new caller away from
being bypassed). This module is imported by API-serialization / view-
model code (D2 onward), never by a React component directly -- shared
components (D7) become dumb renderers that trust the AuthorizedClaim
they're handed, they never re-derive authorization themselves.

Fail-closed contract, matching claim_provenance.py/measurement_
semantics.py exactly: UNKNOWN provenance/measurement-type, and any
non-VALID integrity_status, never yield AUTHORIZED. A missing/legacy
value must never be inferred into a stronger claim than the data proves.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.claim_provenance import ClaimProvenance, RippleEvidenceState
from app.services.measurement_semantics import IntegrityStatus, MeasurementType


class Capability(str, Enum):
    """What kind of public claim is being attempted. A claim's real
    provenance/evidence-state/measurement-type determines which single
    capability is even relevant to it (see the `authorize_*` functions);
    FORECAST and RECOMMENDATION are listed for completeness -- and
    because their permanent UNAVAILABLE status is itself part of the
    contract -- even though no `authorize_*` function currently grants
    either."""

    # A real, already-observed price/index/flow movement, stated as fact.
    OBSERVED_DIRECTION = "observed_direction"
    # A real, measured past outcome, described in past tense only.
    HISTORICAL_DESCRIPTION = "historical_description"
    # An LLM's own analytical judgment about a specific entity/sector.
    ANALYTICAL_HYPOTHESIS = "analytical_hypothesis"
    # A claim that one thing produced/affects another (Ripple/graph edges).
    CAUSAL_RELATIONSHIP = "causal_relationship"
    # The right to state how confident/well-evidenced a claim is.
    EVIDENCE_QUALITY = "evidence_quality"
    # A genuinely forward-looking statement about what will happen.
    # No current producer earns this -- see FORECAST_UNAVAILABLE below.
    FORECAST = "forecast"
    # An instruction to act (buy/sell/hold/allocate).
    # No current producer earns this -- see RECOMMENDATION_UNAVAILABLE.
    RECOMMENDATION = "recommendation"


class Strength(str, Enum):
    """How strongly a granted capability may be exercised."""

    # The claim may be stated at the producer's own real strength.
    AUTHORIZED = "authorized"
    # The claim may be stated, but only in visibly hedged/qualified
    # wording -- never a bare declarative badge/label.
    QUALIFIED = "qualified"
    # Nothing may be publicly claimed. Render an explicit unavailable
    # state, never infer a fallback value (never "neutral", never 0%,
    # never "causes" as a default relationship).
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AuthorizedClaim:
    """The result of an authorization decision. `reason` is set whenever
    strength is QUALIFIED or UNAVAILABLE, explaining why -- consumers
    may show it as a tooltip/disclosure, matching the pattern CD3-C's
    fixes already established (e.g. "the model's own self-rated
    certainty, not a verified score")."""

    capability: Capability
    strength: Strength
    reason: str | None = None


def _claim(capability: Capability, strength: Strength, reason: str | None = None) -> AuthorizedClaim:
    return AuthorizedClaim(capability=capability, strength=strength, reason=reason)


# ── Directional claims (ClaimProvenance) ─────────────────────────────────────

def authorize_direction(
    provenance: ClaimProvenance,
    integrity: IntegrityStatus = IntegrityStatus.VALID,
) -> AuthorizedClaim:
    """Authorizes a directional/impact claim (e.g. "RELIANCE fell 0.5%",
    "Potential positive impact on RELIANCE"). Any non-VALID integrity
    status collapses straight to UNAVAILABLE regardless of provenance --
    a real self-reported hypothesis that's currently DEGRADED/FALLBACK/
    INVALID authorizes nothing, matching the owner's explicit rule that
    FALLBACK/DEGRADED/INVALID always resolve UNAVAILABLE."""
    if integrity != IntegrityStatus.VALID:
        return _claim(Capability.ANALYTICAL_HYPOTHESIS, Strength.UNAVAILABLE,
                       reason=f"integrity_status={integrity.value}")

    if provenance == ClaimProvenance.PRICE_SIGN:
        return _claim(Capability.OBSERVED_DIRECTION, Strength.AUTHORIZED)
    if provenance == ClaimProvenance.HISTORICAL_OUTCOME:
        return _claim(Capability.HISTORICAL_DESCRIPTION, Strength.AUTHORIZED)
    if provenance in (ClaimProvenance.ANALYTICAL_HYPOTHESIS, ClaimProvenance.EVENT_DIRECTION):
        # EVENT_DIRECTION is an event-level LLM read broadcast to every
        # matched company -- never stronger than the sector/entity-level
        # hypothesis it actually is, so it gets the same capability/
        # strength as a direct analytical hypothesis, never AUTHORIZED.
        return _claim(Capability.ANALYTICAL_HYPOTHESIS, Strength.QUALIFIED)
    # FALLBACK, UNAVAILABLE, UNKNOWN -- no legitimate directional claim.
    return _claim(Capability.ANALYTICAL_HYPOTHESIS, Strength.UNAVAILABLE,
                   reason=f"provenance={provenance.value}")


# ── Ripple / relationship claims (RippleEvidenceState) ───────────────────────

def authorize_ripple(
    evidence_state: RippleEvidenceState,
    integrity: IntegrityStatus = IntegrityStatus.VALID,
) -> AuthorizedClaim:
    """Authorizes a causal/relationship claim (a Ripple edge, an
    Intelligence Graph edge, Deep Research second-order effects). Per
    the CD3-A audit, 100% of live Ripple/graph data sampled was
    HYPOTHESIZED -- this function returns QUALIFIED for that state, not
    AUTHORIZED, exactly matching the owner's explicit example ("Possible
    transmission mechanism", never "X causes Y"). An UNDEFINED/missing
    evidence_state must resolve here to UNAVAILABLE -- never silently to
    HYPOTHESIZED or any stronger state; callers are responsible for
    passing RippleEvidenceState.UNAVAILABLE (via claim_provenance.py's
    own get_ripple_evidence_state() fail-safe accessor) rather than None."""
    if integrity != IntegrityStatus.VALID:
        return _claim(Capability.CAUSAL_RELATIONSHIP, Strength.UNAVAILABLE,
                       reason=f"integrity_status={integrity.value}")

    if evidence_state == RippleEvidenceState.OBSERVED:
        return _claim(Capability.CAUSAL_RELATIONSHIP, Strength.AUTHORIZED)
    if evidence_state == RippleEvidenceState.SUPPORTED:
        return _claim(Capability.CAUSAL_RELATIONSHIP, Strength.QUALIFIED)
    if evidence_state == RippleEvidenceState.HYPOTHESIZED:
        return _claim(Capability.CAUSAL_RELATIONSHIP, Strength.QUALIFIED)
    # UNAVAILABLE, UNKNOWN, or anything else -- no relationship assertion.
    return _claim(Capability.CAUSAL_RELATIONSHIP, Strength.UNAVAILABLE,
                   reason=f"evidence_state={getattr(evidence_state, 'value', evidence_state)}")


# ── Measurement / confidence claims (MeasurementType) ────────────────────────

def authorize_measurement(
    measurement_type: MeasurementType,
    integrity: IntegrityStatus,
) -> AuthorizedClaim:
    """Authorizes the right to state how confident/well-evidenced a
    claim is. SELF_REPORTED_CERTAINTY is always QUALIFIED, never
    AUTHORIZED -- it may be shown, but only with its self-report nature
    disclosed (matching every CD3-C fix's wording pattern), never as a
    bare, undifferentiated percentage. Real composites/deterministic
    metrics/calibration are AUTHORIZED at their own real scale -- callers
    must still use the real unit/label (e.g. "Evidence Coverage", not a
    bare "%"), this function only answers whether disclosure is
    required, not what the disclosure says."""
    if integrity != IntegrityStatus.VALID:
        return _claim(Capability.EVIDENCE_QUALITY, Strength.UNAVAILABLE,
                       reason=f"integrity_status={integrity.value}")

    if measurement_type == MeasurementType.SELF_REPORTED_CERTAINTY:
        return _claim(Capability.EVIDENCE_QUALITY, Strength.QUALIFIED,
                       reason="self-reported, not independently verified")
    if measurement_type in (
        MeasurementType.EVIDENCE_COMPOSITE, MeasurementType.HYBRID_RUBRIC,
        MeasurementType.DETERMINISTIC_METRIC, MeasurementType.HISTORICAL_CALIBRATION,
    ):
        return _claim(Capability.EVIDENCE_QUALITY, Strength.AUTHORIZED)
    # DERIVED_TRANSFORM, UNKNOWN -- no claim about evidence quality here;
    # a derived transform's own inputs must be authorized by their own
    # producers, this function can't see them (matches measurement_
    # semantics.is_publicly_authorized's identical DERIVED_TRANSFORM rule).
    return _claim(Capability.EVIDENCE_QUALITY, Strength.UNAVAILABLE,
                   reason=f"measurement_type={measurement_type.value}")


# ── Capabilities with no legitimate producer today ───────────────────────────
# Not omitted from the model -- named explicitly, permanently UNAVAILABLE,
# so a future implementer sees the boundary rather than inventing ad hoc
# authorization logic to make an existing forecast/recommendation-shaped
# UI element "fit." RECOMMENDATION is also independently backstopped by
# recommendation_language.py's generation-time blacklist; FORECAST is why
# historical_forecast_guard.py exists. Both stay UNAVAILABLE until a real
# producer for either is built and reviewed on its own merits.

FORECAST_UNAVAILABLE = AuthorizedClaim(
    capability=Capability.FORECAST, strength=Strength.UNAVAILABLE,
    reason="No producer in the pipeline generates a verified forward-looking claim today",
)
RECOMMENDATION_UNAVAILABLE = AuthorizedClaim(
    capability=Capability.RECOMMENDATION, strength=Strength.UNAVAILABLE,
    reason="MarketRipple does not issue investment instructions",
)
