// CD3-D — Central Public Claim Authorization. TypeScript mirror of
// app/services/claim_authorization.py (kept in sync by inspection, same
// convention as measurementSemantics.ts/claimProvenance's relationship to
// their backend counterparts).
//
// Authorization itself is a BACKEND concern (see the Python module's own
// docstring: enforcement lives below presentation, in API-serialization /
// view-model code, never inside a shared component). This module exists
// as the SECOND, defensive layer the CD3-D design calls for: a fail-closed
// parser for whatever an API response actually contains, so a component
// never has to re-derive authorization itself and never trusts an
// untyped/legacy value it wasn't given real authorization for.
//
// Components (ScoreDisplay, ConfidenceBadge, direction badges, graph
// edges, verdict components) become dumb renderers: they receive an
// AuthorizedClaim-shaped prop and render UNAVAILABLE as an explicit
// unavailable state -- never `null -> 0%`, `unknown -> "Neutral"`,
// `missing relationship -> "causes"`. Those defaults are exactly the
// regression category this phase exists to close.

export type Capability =
  | "observed_direction"
  | "historical_description"
  | "analytical_hypothesis"
  | "causal_relationship"
  | "evidence_quality"
  | "forecast"
  | "recommendation";

export type Strength = "authorized" | "qualified" | "unavailable";

export interface AuthorizedClaim {
  capability: Capability;
  strength: Strength;
  reason?: string | null;
}

// Mirrors app.services.claim_provenance.ClaimProvenance /
// RippleEvidenceState and app.services.measurement_semantics.
// IntegrityStatus (no TS type for these existed before CD3-D; frontend
// CD3-B consumers used inline string literals matching the backend
// values directly). Kept in sync by inspection, same convention as
// every other Python<->TS mirror in this codebase.
export type ClaimProvenanceValue =
  | "price_sign" | "event_direction" | "analytical_hypothesis"
  | "historical_outcome" | "fallback" | "unavailable" | "unknown";
export type RippleEvidenceStateValue = "observed" | "supported" | "hypothesized" | "unavailable";
export type IntegrityStatusValue = "valid" | "degraded" | "fallback" | "unavailable" | "invalid";

// ── Authorization decision logic — mirrors claim_authorization.py's
// three functions exactly. This IS enforcement logic living in the
// frontend, which looks like it contradicts "authorization lives below
// presentation" -- it doesn't: this is not a component deciding for
// itself, it's the same SHARED, reusable, non-bypassable-by-a-new-page
// contract as the Python version, callable from view-model code before
// any component ever sees the data (server components building page
// props, not JSX). The two implementations must be changed together;
// test_claim_authorization.py (backend) and claimAuthorization.test.ts
// (frontend) both pin the exact same decision table so drift is caught
// immediately, not silently. ────────────────────────────────────────

export function authorizeDirection(
  provenance: ClaimProvenanceValue,
  integrity: IntegrityStatusValue = "valid",
): AuthorizedClaim {
  if (integrity !== "valid") {
    return { capability: "analytical_hypothesis", strength: "unavailable", reason: `integrity_status=${integrity}` };
  }
  if (provenance === "price_sign") return { capability: "observed_direction", strength: "authorized" };
  if (provenance === "historical_outcome") return { capability: "historical_description", strength: "authorized" };
  if (provenance === "analytical_hypothesis" || provenance === "event_direction") {
    return { capability: "analytical_hypothesis", strength: "qualified" };
  }
  return { capability: "analytical_hypothesis", strength: "unavailable", reason: `provenance=${provenance}` };
}

export function authorizeRipple(
  evidenceState: RippleEvidenceStateValue,
  integrity: IntegrityStatusValue = "valid",
): AuthorizedClaim {
  if (integrity !== "valid") {
    return { capability: "causal_relationship", strength: "unavailable", reason: `integrity_status=${integrity}` };
  }
  if (evidenceState === "observed") return { capability: "causal_relationship", strength: "authorized" };
  if (evidenceState === "supported") return { capability: "causal_relationship", strength: "qualified" };
  if (evidenceState === "hypothesized") return { capability: "causal_relationship", strength: "qualified" };
  return { capability: "causal_relationship", strength: "unavailable", reason: `evidence_state=${evidenceState}` };
}

export function authorizeMeasurement(
  measurementType: string,
  integrity: IntegrityStatusValue,
): AuthorizedClaim {
  if (integrity !== "valid") {
    return { capability: "evidence_quality", strength: "unavailable", reason: `integrity_status=${integrity}` };
  }
  if (measurementType === "self_reported_certainty") {
    return { capability: "evidence_quality", strength: "qualified", reason: "self-reported, not independently verified" };
  }
  if (["evidence_composite", "hybrid_rubric", "deterministic_metric", "historical_calibration"].includes(measurementType)) {
    return { capability: "evidence_quality", strength: "authorized" };
  }
  return { capability: "evidence_quality", strength: "unavailable", reason: `measurement_type=${measurementType}` };
}

// FORECAST/RECOMMENDATION: no authorize_* function ever produces these
// capabilities. Named explicitly, permanently unavailable -- same
// reasoning as the Python constants.
export const FORECAST_UNAVAILABLE: AuthorizedClaim = {
  capability: "forecast", strength: "unavailable",
  reason: "No producer in the pipeline generates a verified forward-looking claim today",
};
export const RECOMMENDATION_UNAVAILABLE: AuthorizedClaim = {
  capability: "recommendation", strength: "unavailable",
  reason: "MarketRipple does not issue investment instructions",
};

const KNOWN_CAPABILITIES: Capability[] = [
  "observed_direction", "historical_description", "analytical_hypothesis",
  "causal_relationship", "evidence_quality", "forecast", "recommendation",
];
const KNOWN_STRENGTHS: Strength[] = ["authorized", "qualified", "unavailable"];

/** Fail-safe parse of a capability string from an API response --
 * unrecognized/missing values are NOT assumed; callers must treat a
 * `null` return the same as UNAVAILABLE (there is no "unknown but
 * renderable" state). */
export function parseCapability(raw: string | null | undefined): Capability | null {
  return (KNOWN_CAPABILITIES as string[]).includes(raw ?? "") ? (raw as Capability) : null;
}

/** Fail-safe parse of a strength string -- a missing/unrecognized value
 * resolves to "unavailable", the weakest state, never "authorized". */
export function parseStrength(raw: string | null | undefined): Strength {
  return (KNOWN_STRENGTHS as string[]).includes(raw ?? "") ? (raw as Strength) : "unavailable";
}

/**
 * The one gate every consumer should check before rendering ANYTHING
 * from an AuthorizedClaim -- false for "unavailable" strength, false for
 * a missing/malformed claim, false for an unrecognized capability. This
 * mirrors claim_authorization.py's own fail-closed contract: a claim
 * this function rejects must render an explicit unavailable state, not
 * a fabricated default.
 */
export function isRenderable(claim: AuthorizedClaim | null | undefined): boolean {
  if (!claim) return false;
  if (parseStrength(claim.strength) === "unavailable") return false;
  if (parseCapability(claim.capability) === null) return false;
  return true;
}

/**
 * Parses a raw, possibly-legacy/untyped value from an API response into
 * a safe AuthorizedClaim. Use this at the view-model boundary for any
 * endpoint that hasn't been migrated to emit real AuthorizedClaim JSON
 * yet -- it NEVER upgrades an untyped value into "authorized"; anything
 * it can't positively identify resolves to unavailable.
 */
export function coerceAuthorizedClaim(raw: unknown): AuthorizedClaim {
  if (!raw || typeof raw !== "object") {
    return { capability: "evidence_quality", strength: "unavailable", reason: "no claim data" };
  }
  const r = raw as Record<string, unknown>;
  const capability = parseCapability(typeof r.capability === "string" ? r.capability : null);
  if (!capability) {
    return { capability: "evidence_quality", strength: "unavailable", reason: "unrecognized capability" };
  }
  return {
    capability,
    strength: parseStrength(typeof r.strength === "string" ? r.strength : null),
    reason: typeof r.reason === "string" ? r.reason : null,
  };
}
