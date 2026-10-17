// Pure types/logic extracted out of page.tsx (2026-09-20 build fix) --
// Next.js's App Router only allows a page.tsx file to export a specific
// fixed set of names (default, metadata, generateStaticParams, etc.);
// any other named export fails `next build`'s route-type validation
// (confirmed live: "Property 'isHighConviction' is incompatible with
// index signature" -- `tsc --noEmit` alone does not catch this, only a
// real `next build` does). Kept in its own module so it's directly
// importable from both the page and its unit test without ever
// re-triggering that constraint.

export interface RadarItem {
  id: string | number;
  // Batch E consumer migration, 2026-08-24 — /api/radar/'s list endpoint
  // returns V2 items (uuid id + slug) once promoted; a raw item.id link
  // would 404 in that mode (radar.py's dual lookup treats a non-numeric
  // segment as a slug lookup, and a uuid isn't a real slug).
  slug?: string;
  theme: string;
  score: number | null;
  reason: string;
  confidence: number | null;
  beneficiaries: string[];
  sectors?: string[];
  trend?: string | null;
  // Honest-classification fix (2026-10-17): absent for V2 items (no
  // concept of this at all, same as confidence below) and for V1 items
  // fetched before this fix shipped (page.tsx's mapping defaults it to
  // "classified" only when the API's own field is itself undefined --
  // see the mapping in page.tsx). "unclassified" means the AI call that
  // would have produced a real trend/risk/confidence verdict failed or
  // returned unparseable output.
  classification_status?: "classified" | "unclassified";
}

// 2026-09-20 V2-compatibility fix: `confidence` is a V1-only concept
// (opportunity_generator.py's own derived score/110 formula) -- V2's list
// contract has no confidence field at all, by design (see read_service.py's
// module docstring: never ported a fabricated concept forward). Treating
// "no confidence concept" as "confidence = 0" (the old `(i.confidence ??
// 0) >= 0.85`) silently disqualified every real V2 opportunity from High
// Conviction forever, no matter how strong its real score. This does NOT
// invent a replacement confidence number for V2 -- it simply stops
// requiring a criterion that structurally doesn't apply: a real score
// alone qualifies when there's no confidence concept to check; V1 items
// still require both real thresholds, unchanged.
export function isHighConviction(item: Pick<RadarItem, "score" | "confidence" | "classification_status">): boolean {
  // Honest-classification fix (2026-10-17): a V1 item whose AI
  // classification failed must never qualify as High Conviction just
  // because its null confidence happened to take the same "no concept to
  // check" bypass V2 items legitimately use below -- missing/failed
  // evidence must not silently produce maximum conviction.
  if (item.classification_status === "unclassified") return false;
  if ((item.score ?? 0) < 90) return false;
  return item.confidence === null ? true : item.confidence >= 0.85;
}
