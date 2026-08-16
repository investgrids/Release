/**
 * Phase 5A.12 — display-layer mapping for the real Economic Calendar
 * backend categories (rbi_mpc, india_cpi, india_iip, fomc, us_cpi,
 * us_jobs — see app/services/economic_calendar/*_source.py). Backend
 * taxonomy stays exactly as ingested; this file is the one place a new
 * backend category needs a display entry, so nothing about how these
 * events look is hardcoded into the API layer just to satisfy an old
 * UI convention.
 *
 * Two real bugs this replaces, found while wiring real data through
 * the existing UI: EventIcon's title-substring regex gave "India CPI"
 * a US flag (matched "cpi") and gave "FOMC Interest Rate Decision" the
 * RBI/Landmark icon (matched "rate") — both wrong, both silent. An
 * exact category lookup can't misfire that way.
 */

export const CALENDAR_CATEGORY_LABELS: Record<string, string> = {
  rbi_mpc: "RBI Policy Decision",
  india_cpi: "India CPI",
  india_iip: "India IIP",
  fomc: "US Fed Decision (FOMC)",
  us_cpi: "US CPI",
  us_jobs: "US Jobs Report (NFP)",
};

/** Existing display-group vocabulary the calendar UI already has icons/
 * colors for (RBI/Policy/Macro/Global) — new categories map onto it
 * rather than each inventing their own visual treatment. */
export const CALENDAR_CATEGORY_DISPLAY_GROUP: Record<string, string> = {
  rbi_mpc: "RBI",
  india_cpi: "Macro",
  india_iip: "Macro",
  fomc: "Global",
  us_cpi: "Global",
  us_jobs: "Global",
};

export function calendarCategoryLabel(category: string | undefined | null): string {
  if (!category) return "Event";
  return CALENDAR_CATEGORY_LABELS[category] ?? category;
}

export function calendarCategoryDisplayGroup(category: string | undefined | null): string | undefined {
  if (!category) return undefined;
  return CALENDAR_CATEGORY_DISPLAY_GROUP[category];
}
