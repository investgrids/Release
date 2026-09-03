// CD3-C fix (2026-09-03) — extracted from RipplePageClient.tsx's inline
// OpportunityLifecycleCard stage assignment so the scale-boundary fix is
// directly unit-testable, not just visually inspected.
//
// event_impact is a real 0-10 impact MAGNITUDE (app/api/ripple.py's
// _impact_hint: Event.impact_score, the real Scoring Engine composite,
// divided by 10 -- see app/services/measurement_semantics.py,
// measurement_type=DETERMINISTIC_METRIC). The original thresholds here
// (>80, >60) assumed a 0-100 scale and were unreachable for every real
// event (max real event_impact is ~10) -- confirmed live via a real
// production specimen, event_impact=0.9. Rewritten against the real
// scale, preserving the original intended proportions (roughly the
// top-20%/top-40% bands).

export type RippleStage = "strong-momentum" | "developing" | "emerging";

export function deriveRippleStage(
  eventImpact: number | null | undefined,
  directStrength: string | null | undefined,
): RippleStage {
  const directStr = (directStrength ?? "").toLowerCase();
  if (eventImpact !== null && eventImpact !== undefined) {
    if (eventImpact > 8 || directStr.includes("high")) return "strong-momentum";
    if (eventImpact > 6 || directStr.includes("medium")) return "developing";
    return "emerging";
  }
  if (directStr.includes("high")) return "strong-momentum";
  if (directStr.includes("medium")) return "developing";
  return "emerging";
}
