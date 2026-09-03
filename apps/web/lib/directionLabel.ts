// CD3-D (D5) — the homepage's "Companies In Focus" and "Since Previous
// Session" cards used to render bare "Positive"/"Improving"/"New
// Opportunity" labels for data that's entirely ANALYTICAL_HYPOTHESIS-
// shaped (LLM judgments on Development Memory rows / AIPE sector self-
// reports, never raw observed price data) -- the exact "BALUFORGE:
// Positive" / "Banking: Improving" audit specimens. D3 already fixed
// which rows get INCLUDED (authorizeDirection gates inclusion); these
// two functions fix the WORDING for the ones that legitimately are,
// without excluding anything new.

import type { Strength } from "./claimAuthorization";

/** "Companies In Focus" badge wording -- AUTHORIZED renders the bare
 * direction (reserved for a future real observed-price producer;
 * nothing today reaches this branch), QUALIFIED hedges with "Likely",
 * anything else (including "neutral"/"mixed", which aren't claims of
 * direction strength) passes through unchanged. */
export function directionLabel(direction: string, strength: Strength): string {
  if (strength === "qualified" && (direction === "positive" || direction === "negative")) {
    return `Likely ${direction}`;
  }
  return direction;
}

/** "Since Previous Session" delta wording. Every row here is derived
 * from AIPE's own self-reported per-sector impact/magnitude
 * (_sector_score, ANALYTICAL_HYPOTHESIS-shaped) -- always QUALIFIED,
 * so this hedges unconditionally rather than taking a strength param. */
export function sessionChangeLabel(isNew: boolean, up: boolean): string {
  if (isNew) return up ? "Possible New Opportunity" : "Possible New Risk";
  return up ? "Likely Improving" : "Likely Weakening";
}
