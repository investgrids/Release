// CD3-D (D3) — extracted from page.tsx's homepage "Companies In Focus"
// merge logic so the reconstruction fix is directly unit-tested, not
// just visually inspected.
//
// The bug this replaces: page.tsx used to hardcode `impact: "positive"`
// unconditionally for every company from the top event (regardless of
// the real impact_type Event.companies actually carried), and defaulted
// activeCompanies to "positive" for anything that wasn't the literal
// string "negative" (including "neutral" or a missing value). Both were
// reconstructing a stronger, more specific claim than the underlying
// data supported -- exactly the BALUFORGE-style failure CD3-D's audit
// found. This function reads the real value; a caller is still
// responsible for gating on authorizeDirection(impact_provenance) before
// using the result (see claimAuthorization.ts) -- this module only fixes
// the "read the real field" half of the bug, not the "should this be
// shown at all" half.

export type CompanyDirection = "positive" | "negative" | "neutral";

/**
 * Maps a real impact_type ("beneficiary"/"loser"/"neutral", from Event
 * data) or a real impact string ("Positive"/"Negative"/"Neutral", from
 * the events-list CompanyImpact schema) to a direction -- never a
 * hardcoded default that ignores the input. A missing/absent value
 * resolves to "positive" ONLY for the one case where absence IS the
 * real signal: event_lifecycle.py's beneficiaries[]-sourced companies
 * never carry impact_type at all, because that list is already
 * pre-filtered server-side to impact_type=="beneficiary" -- the absence
 * there is not a guess, it's the server having already done the
 * filtering. Any OTHER genuinely unknown/malformed value also falls
 * through to this same default, which is why callers must additionally
 * gate on authorizeDirection() before trusting the result for anything
 * genuinely unprovenanced.
 */
export function companyDirection(impact: string | null | undefined): CompanyDirection {
  const t = (impact ?? "").toLowerCase();
  if (t === "loser" || t === "negative") return "negative";
  if (t === "neutral") return "neutral";
  return "positive";
}
