"""
CD3-B typed claim provenance / Ripple evidence-state vocabulary.

Introduced because CD3-A's read-only audit found the platform's directional
fields (companies_affected[].impact, Event impact_type, ripple_effect[],
Event graph edges, etc.) are produced by several genuinely incompatible
signals -- a real observed price move, a one-shot LLM guess, a measured
historical outcome, a generated causal hypothesis, a zero-evidence fallback
-- all silently rendered as the same "positive"/"negative"/"neutral" string.
See the CD3-A/CD3-B audit (memory: project_cd3_semantic_provenance_repair)
for the full producer inventory and compatibility matrix this codifies.

This module is the vocabulary + the documented authorization boundary only.
CD3-B (this phase) attaches these tags to existing data as new, additive
fields -- it does not change what's publicly rendered or enforce the
boundary at render time. Enforcing AUTHORIZATION_BOUNDARY against actual
UI/API output is CD3-D's job, not this one's.

Unknown or legacy data must resolve to UNKNOWN/UNAVAILABLE -- never
inferred into a stronger provenance than the code can actually prove.
"""
from __future__ import annotations

from enum import Enum


class ClaimProvenance(str, Enum):
    """What kind of signal actually produced a directional/impact value."""

    # Real, observed market price movement (e.g. _change_pct_to_impact).
    # The *observation* is supported; converting it into a labeled "impact"
    # already changes its semantics -- see AUTHORIZATION_BOUNDARY below.
    PRICE_SIGN = "price_sign"

    # One event-level LLM direction judgment, broadcast to every company
    # matched to that event (e.g. _direction_to_impact) -- not a per-company
    # assessment, even though it gets attached to individual company chips.
    EVENT_DIRECTION = "event_direction"

    # An LLM's analytical judgment about a specific company/sector (AIPE
    # companies_affected[].impact, sectors_affected[].impact, Event
    # impact_type, Event sector impact). Deliberately named "hypothesis",
    # not "interpretation" -- a hypothesis can be explained but must never
    # be reconstructed into forecast/beneficiary/"Likely Winner" framing by
    # a downstream consumer just because it carries a direction and an LLM
    # label.
    ANALYTICAL_HYPOTHESIS = "analytical_hypothesis"

    # A measured past result (what actually happened after a similar prior
    # event). Real, but describes the past -- never itself a forecast.
    HISTORICAL_OUTCOME = "historical_outcome"

    # Static exception-path boilerplate (_safe_json_call's fallback dict) --
    # unrelated to the specific entity/event it happens to be attached to.
    FALLBACK = "fallback"

    # Zero evidence backing this value at all (e.g. _FakeSector). Authorizes
    # nothing directional -- not even "neutral", which is itself a claim.
    UNAVAILABLE = "unavailable"

    # Legacy/unmapped data with no known producer. Never inferred into a
    # stronger provenance than this.
    UNKNOWN = "unknown"


class RippleEvidenceState(str, Enum):
    """Evidence state for a Ripple/graph relationship -- kept as a
    separate axis from the relationship's own direction/mechanism/type,
    since the same relationship can progress hypothesized -> supported ->
    observed without the relationship itself changing. Applies uniformly
    to AIPE ripple_effect[], Event graph edges, and Deep Research
    second-order effects -- CD3-A found all three are the same underlying
    shape today (100% of sampled live entries are HYPOTHESIZED)."""

    # Something measurably happened in the data for this specific event.
    OBSERVED = "observed"

    # Real evidence plus a named transmission mechanism supports the
    # relationship for this specific event.
    SUPPORTED = "supported"

    # A model-proposed, plausible chain, unverified for this specific
    # event. What every current AI-generated ripple/graph/second-order
    # producer actually is, as of the CD3-A audit -- none of the pipelines
    # have an evidence-validation path that could produce OBSERVED or
    # SUPPORTED yet.
    HYPOTHESIZED = "hypothesized"

    # Insufficient evidence to say anything.
    UNAVAILABLE = "unavailable"


# What each ClaimProvenance value may/must-not authorize when rendered
# publicly -- documents the CD3-B compatibility matrix in code so tests can
# assert against it directly. Enforcement at the actual render/API boundary
# is CD3-D scope; this dict is the agreed contract those tests check code
# against today, and CD3-D will check UI/API behavior against tomorrow.
AUTHORIZATION_BOUNDARY: dict[ClaimProvenance, dict[str, str]] = {
    ClaimProvenance.PRICE_SIGN: {
        "may_authorize": "An observed price statement (\"shares rose/fell X% today\")",
        "must_not_authorize": "Beneficiary status, forecast, or likely-winner framing",
    },
    ClaimProvenance.EVENT_DIRECTION: {
        "may_authorize": "Internal/event-level interpretation only",
        "must_not_authorize": "A company-specific directional claim",
    },
    ClaimProvenance.ANALYTICAL_HYPOTHESIS: {
        "may_authorize": "Clearly-labeled analysis, with its hypothesis nature visible",
        "must_not_authorize": "An observed fact, a forecast, or \"Likely Winner\" framing",
    },
    ClaimProvenance.HISTORICAL_OUTCOME: {
        "may_authorize": "A statement of historical performance (\"rose/fell after this historical event\")",
        "must_not_authorize": "A current or forward-looking forecast",
    },
    ClaimProvenance.FALLBACK: {
        "may_authorize": "Nothing, unless visibly flagged as fallback/template content",
        "must_not_authorize": "Any directional or analytical output presented as real",
    },
    ClaimProvenance.UNAVAILABLE: {
        "may_authorize": "Nothing",
        "must_not_authorize": "Any directional claim at all, including \"neutral\"",
    },
    ClaimProvenance.UNKNOWN: {
        "may_authorize": "Nothing until classified",
        "must_not_authorize": "Any directional claim at all",
    },
}

def get_claim_provenance(entry: dict, key: str = "impact_provenance") -> ClaimProvenance:
    """Read a provenance tag from a dict, defaulting to UNKNOWN for a
    missing key or an unrecognized value -- never inferred into a
    stronger provenance than the data can prove. In particular: a row
    written before CD3-B (no `impact_provenance` key at all) reads as
    UNKNOWN, not as whatever the newest producer for that field happens
    to be today. Use this instead of a bare dict.get() wherever a future
    consumer needs to check a producer's provenance."""
    raw = entry.get(key) if isinstance(entry, dict) else None
    try:
        return ClaimProvenance(raw)
    except ValueError:
        return ClaimProvenance.UNKNOWN


def get_ripple_evidence_state(entry: dict, key: str = "evidence_state") -> RippleEvidenceState:
    """Same fail-safe pattern as get_claim_provenance, for Ripple/graph
    relationships -- a missing/unrecognized value reads as UNAVAILABLE
    (the weakest ripple state), never HYPOTHESIZED or stronger."""
    raw = entry.get(key) if isinstance(entry, dict) else None
    try:
        return RippleEvidenceState(raw)
    except ValueError:
        return RippleEvidenceState.UNAVAILABLE


RIPPLE_AUTHORIZATION_BOUNDARY: dict[RippleEvidenceState, dict[str, str]] = {
    RippleEvidenceState.OBSERVED: {
        "may_authorize": "A statement that this relationship was measured in real data for this event",
        "must_not_authorize": "n/a -- this is the strongest evidence state",
    },
    RippleEvidenceState.SUPPORTED: {
        "may_authorize": "A statement that evidence and a named mechanism support this relationship for this event",
        "must_not_authorize": "Presenting it as directly measured/observed",
    },
    RippleEvidenceState.HYPOTHESIZED: {
        "may_authorize": "A visibly-labeled \"possible mechanism\" or \"hypothesized relationship\"",
        "must_not_authorize": "An unlabeled graph arrow implying established/verified causality; feeding it into Market Memory as a learned relationship",
    },
    RippleEvidenceState.UNAVAILABLE: {
        "may_authorize": "Nothing",
        "must_not_authorize": "Any relationship claim at all",
    },
}
