// P0-CD1 legacy-history containment patch (2026-09-01).
//
// CD2 (backend, app/services/aipe/recommendation_language.py) stops NEW
// articles from being generated with recommendation language in
// opportunities[]/key_takeaway. It cannot do anything about content
// persisted BEFORE CD2 shipped — and a real live example proved that
// legacy content, is still publicly reachable through fields CD1's
// structural suppression never touched: the CURRENT key_takeaway (30-
// Second Answer) and update_history[]'s stored opinion-evolution text
// (previous_takeaway/new_takeaway/summary), both of which predate CD2 and
// can still carry the exact "Consider shorting over-valued..." language
// CD1 was built to keep off the page.
//
// This is deliberately the same taxonomy as the backend's
// recommendation_language.py (kept in sync by inspection, not by a shared
// build step — there's no code-sharing bridge between the Python backend
// and this Next.js frontend) but is scoped even narrower here: it exists
// only to decide whether to SHOW or OMIT already-persisted text, never to
// modify or "clean up" the text itself — matching the same fail-closed,
// never-rewrite contract as the backend validator.
const PATTERNS: RegExp[] = [
  /\bbuy\b(?!\s*-?\s*back)/i,
  /\bsell\b/i,
  /(?:^|\bconsider\s+|\binvestors?\s+should\s+)short(?:ing)?\s+(?!term\b)\w/i,
  /\baccumulat(?:e|ing)\b/i,
  /\breduc(?:e|ing)\b.{0,20}\b(position|stake|holding|weight(?:age)?)\b/i,
  /\bexit(?:ing)?\b.{0,20}\b(position|stake|holding)\b/i,
  /\b(?:enter|initiate|take)\s+a\s+position\b/i,
  /\benter(?:ing)?\s+(?:the\s+stock|now)\b/i,
  /\btarget\s+price\b/i,
  /\bstop[\s-]?loss\b/i,
  /\bbook(?:ing)?\s+profits?\b/i,
  /\boverweight\b/i,
  /\bunderweight\b/i,
  /\bdip[\s-]?buy(?:ing)?\b/i,
  /\bswing[\s-]?buy\b/i,
  /\bconsider\s+buying\b/i,
  /\binvestors?\s+should\s+buy\b/i,
  /\bgood\s+entry\s+point\b/i,
  /\bpotential\s+entry\b/i,
  /\ba\s+buying\s+opportunity\b/i,
  /\bstrong\s+buy\b/i,
  /\blikely\s+winner\b/i,
  /\blikely\s+loser\b/i,
];

export function containsRecommendationLanguage(text: string | null | undefined): boolean {
  if (!text) return false;
  return PATTERNS.some(p => p.test(text));
}
