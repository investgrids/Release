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
