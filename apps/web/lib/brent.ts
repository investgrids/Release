import { API_BASE_URL } from "@/lib/api";

// The single canonical Brent observation for the Global Markets card (the
// Commodities page already fetches the full commodities payload itself). It reads
// the EXISTING, backend-cached `/api/commodities/` Brent item (EIA RBRTE) — there
// is no new EIA call and no new backend endpoint. The result is
// module-cached so repeated tab mounts in one session reuse a single request and
// every consumer shows the same observation. A failed/empty fetch is NOT cached,
// so a later mount can retry; callers render an explicit unavailable state.
export interface BrentObservation {
  price: string;        // e.g. "123.10" (USD per barrel)
  unit: string;         // "USD / bbl"
  change: string;       // day-over-day, e.g. "-5.02"
  pct: number;          // day-over-day %, e.g. -3.92
  positive: boolean;
  source: string;       // "U.S. Energy Information Administration"
  asOf: string | null;  // observation date (NOT retrieval time), e.g. "2026-10-27"
  stale: boolean;       // observation older than the EIA source's staleness window
}

let _cache: Promise<BrentObservation | null> | null = null;

async function _fetchBrent(): Promise<BrentObservation | null> {
  try {
    const r = await fetch(`${API_BASE_URL}/api/commodities/`);
    if (!r.ok) return null;
    const data = await r.json();
    const groups: unknown[] = [data?.metals, data?.energy].filter(Array.isArray) as unknown[];
    let brent: Record<string, unknown> | null = null;
    for (const g of groups as Record<string, unknown>[][]) {
      const hit = g.find((c) => c?.id === "brent");
      if (hit) { brent = hit; break; }
    }
    if (!brent || brent.price == null || brent.price === "—") return null;
    return {
      price: String(brent.price),
      unit: typeof brent.unit === "string" && brent.unit ? brent.unit : "USD / bbl",
      change: brent.change == null ? "" : String(brent.change),
      pct: typeof brent.pct === "number" ? brent.pct : Number(brent.pct) || 0,
      positive: !!brent.positive,
      source: typeof brent.source === "string" && brent.source ? brent.source : "U.S. Energy Information Administration",
      asOf: typeof brent.as_of === "string" ? brent.as_of : null,
      stale: !!brent.stale,
    };
  } catch {
    return null;
  }
}

export function getBrentObservation(): Promise<BrentObservation | null> {
  if (!_cache) {
    _cache = _fetchBrent().then((v) => {
      if (v === null) _cache = null; // don't cache failures — allow a later retry
      return v;
    });
  }
  return _cache;
}

// Test-only: reset the module cache between tests.
export function __resetBrentObservationCache(): void {
  _cache = null;
}
