// CD3-D (D4) — the Ripple graph used to render every edge as a literal
// "X causes Y" arrow regardless of where the edge came from, and an edge
// with no `relationship` field at all silently defaulted to "causes" too
// (RippleGraph.tsx). Both reconstructed a stronger, more specific claim
// than the underlying data supported -- the same failure class CD3-D's
// audit found elsewhere (BALUFORGE-style hardcoded defaults).
//
// This module picks display wording from the real evidence_state a
// backend edge now carries (see ripple_service.py's _annotate_evidence_
// state), never from the raw `relationship` string alone. The hard rule
// from the owner's spec: undefined/missing relationship must NEVER
// resolve to "causes" -- it fails closed to the same wording an
// UNAVAILABLE evidence_state gets, regardless of what evidence_state
// itself says.

export type RippleEvidenceStateValue = "observed" | "supported" | "hypothesized" | "unavailable";

export interface RippleEdgeDisplay {
  label: string;
  /** Whether this label asserts a real relationship (true) or is a
   * deliberate non-claim (false) -- callers use this to pick a muted vs
   * a confident color, not the raw evidence_state string directly. */
  asserts: boolean;
}

const NO_RELATIONSHIP: RippleEdgeDisplay = { label: "no confirmed relationship", asserts: false };

export function rippleEdgeDisplay(
  evidenceState: string | null | undefined,
  relationship: string | null | undefined,
): RippleEdgeDisplay {
  const rel = (relationship ?? "").trim();

  switch (evidenceState) {
    case "observed":
      // Only an OBSERVED edge with a real relationship string is
      // rendered as a direct claim -- a missing relationship on a
      // nominally "observed" edge is malformed data, not license to
      // guess, so it fails closed the same as everything else.
      return rel ? { label: rel, asserts: true } : NO_RELATIONSHIP;
    case "supported":
      return rel
        ? { label: `may transmit through ${rel}`, asserts: true }
        : { label: "may transmit through an unspecified mechanism", asserts: true };
    case "hypothesized":
      // Deliberately generic, never the raw relationship word as fact --
      // a single-shot AI narrative with no evidence-validation path
      // (CD3-A's own finding) doesn't get to assert "causes"/"hurts".
      return { label: "possible link", asserts: false };
    case "unavailable":
    case "unknown":
    default:
      // Covers UNAVAILABLE, UNKNOWN, and any unrecognized/missing
      // evidence_state -- fail closed, never a silent "causes".
      return NO_RELATIONSHIP;
  }
}
