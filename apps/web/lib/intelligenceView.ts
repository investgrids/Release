// Presentation helpers for the company Intelligence tab. Pure: no fetching, no scoring. Nothing here invents a number; it only
// removes repeats, orders what the backend already sent, and words it plainly.

export type Evidence = {
  reason: string | null;
  source_type: "article" | "opportunity";
  href: string | null;
  signed_magnitude: number;
  signal_at: string | null;
};

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();

// The same point is often published several times (the same sentence from two opportunities, a reworded repeat of one article).
// Keep one row per distinct reason: the strongest, then the most recent. Rows without a reason are dropped. Order: strongest first.
export function dedupeEvidence(rows: Evidence[] | undefined | null): Evidence[] {
  const best = new Map<string, Evidence>();
  for (const r of rows ?? []) {
    if (!r?.reason || !norm(r.reason)) continue;
    const k = norm(r.reason);
    const cur = best.get(k);
    const stronger = !cur || Math.abs(r.signed_magnitude) > Math.abs(cur.signed_magnitude) ||
      (Math.abs(r.signed_magnitude) === Math.abs(cur.signed_magnitude) && (r.signal_at ?? "") > (cur.signal_at ?? ""));
    if (stronger) best.set(k, r);
  }
  return [...best.values()].sort((a, b) => Math.abs(b.signed_magnitude) - Math.abs(a.signed_magnitude) || (b.signal_at ?? "").localeCompare(a.signal_at ?? ""));
}

// Share of the distinct evidence that supports vs counters, for the balance bar. Null when there is nothing to compare.
export function evidenceBalance(supporting: Evidence[], countering: Evidence[]): { support: number; counter: number; supportPct: number } | null {
  const support = supporting.length, counter = countering.length;
  if (support + counter === 0) return null;
  return { support, counter, supportPct: Math.round((support / (support + counter)) * 100) };
}

// "Low / Moderate / High" for the Investment Watch confidence percentage.
export function confidenceWord(pct: number | null | undefined): string | null {
  if (pct == null || !Number.isFinite(pct)) return null;
  return pct < 40 ? "Low" : pct < 70 ? "Moderate" : "High";
}

// 2026-08-19 -> "19 Aug 2026"; anything that is not a parseable date is returned unchanged.
export function plainDate(s: string | null | undefined): string {
  if (!s) return "";
  const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(s) ? `${s}T00:00:00Z` : s);
  return Number.isNaN(d.getTime()) ? s : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

// One distinct headline per event, in the order given.
export function distinctHeadlines<T extends { headline: string }>(events: T[] | undefined | null): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const e of events ?? []) {
    const k = norm(e.headline || "");
    if (!k || seen.has(k)) continue;
    seen.add(k);
    out.push(e);
  }
  return out;
}
