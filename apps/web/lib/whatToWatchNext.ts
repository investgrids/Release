// Homepage Hero — "What To Watch Next" (2026-09-03).
//
// Deterministic derivation only — no LLM call, ever. Every condition text
// below is a hand-written template selected by a real observed boolean;
// nothing here is generated text a model wrote. See the module-level tests
// (whatToWatchNext.test.ts) for the exact CD3-B provenance argument this
// design rests on.
//
// CD3-B provenance boundary, respected deliberately:
//   - Every "condition" item is grounded in a real PRICE_SIGN value (an
//     actual observed index/commodity/currency/flow direction from
//     /api/market/premarket or /api/indices/ — the same real fields the
//     homepage ticker strip and "Today's Drivers" already trust). PRICE_SIGN
//     may authorize "rose/fell" language; it is never converted into
//     "beneficiary"/"likely winner"/"bullish" framing here.
//   - Nothing here reads the AIPE article's own sectors_affected/
//     companies_affected impact judgments (ANALYTICAL_HYPOTHESIS) as the
//     SOURCE of a condition's direction — an analytical judgment is never
//     silently promoted into "observed fact." (An earlier draft considered
//     using the hero's `highestRisk` sector name to select which real index
//     to show; this version doesn't need it — the fixed candidate list
//     below already covers the deterministic set the task named, so no
//     ANALYTICAL_HYPOTHESIS-typed signal enters this function at all.)
//   - Nothing here reads or reflects Ripple relationships (HYPOTHESIZED
//     evidence state) or historical-outcome data (HISTORICAL_OUTCOME) —
//     out of scope for this deterministic mapper entirely.
//   - The legacy AIPE `what_to_watch_next` article field is NEVER an input
//     to this function — its type signature below doesn't accept it, by
//     design, not merely by omission. It has known unsafe recommendation
//     language risk (see recommendationLanguage.ts) and no semantic
//     guarantees for this use.
//
// Every generated condition string is also checked at runtime against
// containsRecommendationLanguage() before being returned — belt and
// suspenders, matching this codebase's established "deterministic backstop,
// not just template trust" pattern (recommendation_language.py /
// historical_forecast_guard.py on the backend apply the same philosophy).

import { containsRecommendationLanguage } from "./recommendationLanguage";

export type WatchItemKind = "trigger" | "condition";

export interface WatchItem {
  kind:   WatchItemKind;
  entity: string;   // e.g. "Bank Nifty", "Brent Crude", or a real event title
  detail: string;   // the observable-condition phrase, or "2:30 PM" style timing for a trigger
  meta?:  string;   // optional secondary label (category, for a trigger)
}

// ── Inputs — every field is the REAL observed value already fetched
// elsewhere on this exact homepage render (zero new network calls). A
// `null`/`undefined` field, or a `positive: null`, means "unknown" —
// never inferred into a direction. ──────────────────────────────────────

export interface DirectionalSignal {
  /** true = the raw value rose, false = it fell, null = genuinely unknown. */
  positive: boolean | null;
}

export interface FlowSignal {
  available: boolean;
  /** Real net FII flow figure; sign is the only thing used (>=0 = buying). */
  fiiNet: number | null;
}

export interface CalendarTriggerInput {
  title: string;
  /** Real, already-formatted display time/date string from the calendar
   * source (the same field WatchTomorrowCard already renders verbatim). */
  when: string;
  category?: string | null;
}

export interface WhatToWatchNextInput {
  bankNifty?:  DirectionalSignal | null;
  nifty50?:    DirectionalSignal | null;
  usFutures?:  DirectionalSignal | null;
  crude?:      DirectionalSignal | null;
  usdInr?:     DirectionalSignal | null;
  fiiDii?:     FlowSignal | null;
  /** Already real, already verified — the same source WatchTomorrowCard
   * reads from. This function does not fetch or invent triggers itself. */
  calendarTriggers?: CalendarTriggerInput[];
}

const MAX_ITEMS = 4;
const MAX_TRIGGERS = 2;

function safeCondition(entity: string, detail: string): WatchItem | null {
  // Defense in depth: every hand-written template is checked at runtime,
  // not just trusted at authoring time.
  if (containsRecommendationLanguage(detail) || containsRecommendationLanguage(entity)) {
    return null;
  }
  return { kind: "condition", entity, detail };
}

function indexCondition(label: string, s: DirectionalSignal | null | undefined): WatchItem | null {
  if (!s || s.positive === null || s.positive === undefined) return null;
  return safeCondition(
    label,
    s.positive ? "Whether today's gains hold" : "Whether today's weakness recovers",
  );
}

function usFuturesCondition(s: DirectionalSignal | null | undefined): WatchItem | null {
  if (!s || s.positive === null || s.positive === undefined) return null;
  return safeCondition(
    "US Futures",
    s.positive ? "Whether today's strength in US futures holds" : "Whether weakness persists into the US session",
  );
}

function crudeCondition(s: DirectionalSignal | null | undefined): WatchItem | null {
  if (!s || s.positive === null || s.positive === undefined) return null;
  return safeCondition(
    "Brent Crude",
    s.positive ? "Whether today's rise continues" : "Whether today's decline reverses",
  );
}

function usdInrCondition(s: DirectionalSignal | null | undefined): WatchItem | null {
  if (!s || s.positive === null || s.positive === undefined) return null;
  // positive = USD/INR value rose = the rupee weakened (real, consistent
  // with how market.py's own `positive: change >= 0` field is computed for
  // this instrument, and confirmed against how page.tsx's existing
  // "Today's Drivers" row already labels it: positive -> "INR Weaker").
  return safeCondition(
    "USD/INR",
    s.positive ? "Whether rupee weakness persists" : "Whether rupee strength persists",
  );
}

function fiiCondition(s: FlowSignal | null | undefined): WatchItem | null {
  if (!s || !s.available || s.fiiNet === null || s.fiiNet === undefined) return null;
  return safeCondition(
    "FII Flows",
    s.fiiNet >= 0 ? "Whether FII buying persists" : "Whether FII selling pressure eases",
  );
}

function normalizeKey(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, " ");
}

/**
 * Pure, deterministic, no-LLM derivation of the homepage's "What To Watch
 * Next" items. Never reads the legacy AIPE what_to_watch_next field — that
 * field isn't even part of this function's input type. Returns [] when
 * nothing trustworthy is available; the caller renders nothing rather than
 * a "No data" placeholder (see WhatToWatchNext.tsx).
 */
export function deriveWhatToWatchNext(input: WhatToWatchNextInput): WatchItem[] {
  const items: WatchItem[] = [];
  const seen = new Set<string>();

  const push = (item: WatchItem | null) => {
    if (!item) return;
    const key = normalizeKey(item.entity);
    if (seen.has(key)) return;
    seen.add(key);
    items.push(item);
  };

  // Priority 1 — verified upcoming triggers (real calendar data only).
  for (const t of (input.calendarTriggers ?? []).slice(0, MAX_TRIGGERS)) {
    if (!t || !t.title || !t.when) continue;
    const detail = t.category ? t.when : t.when; // kept explicit for clarity if category formatting changes later
    push(
      containsRecommendationLanguage(t.title)
        ? null
        : { kind: "trigger", entity: t.title, detail, meta: t.category ?? undefined },
    );
    if (items.length >= MAX_ITEMS) break;
  }

  // Priority 2 — deterministically derived observable conditions, fixed
  // priority order (matches this file's own established "importance to
  // Indian equity flows" ordering: index movement first as the most direct
  // signal of today's market picture, then FII, US futures, crude, INR).
  if (items.length < MAX_ITEMS) {
    const indexItem = indexCondition("Bank Nifty", input.bankNifty) ?? indexCondition("Nifty 50", input.nifty50);
    const candidates = [
      indexItem,
      fiiCondition(input.fiiDii),
      usFuturesCondition(input.usFutures),
      crudeCondition(input.crude),
      usdInrCondition(input.usdInr),
    ];
    for (const c of candidates) {
      if (items.length >= MAX_ITEMS) break;
      push(c);
    }
  }

  return items;
}
