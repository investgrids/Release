import { API_BASE_URL as API } from "@/lib/api";

// Reuses the fully-built commodities.py engine (live yfinance prices + 7-day
// chart for 4 metals + 4 energy commodities) — a "free win" per the SEO
// audit: zero pages consumed this before, only a dashboard widget did.
export interface CommodityItem {
  id: string; name: string; unit: string;
  price: string; change: string; pct: number; positive: boolean;
  high: string; low: string;
  chart: { label: string; value: number }[];
}
export interface CommoditiesInsights {
  degraded?: boolean;
  metals?: { impact: string; items: { text: string; impact: string }[] };
  energy?: { impact: string; items: { text: string; impact: string }[] };
  key_drivers_metals?: { label: string; level: string }[];
  key_drivers_energy?: { label: string; level: string }[];
  daily_summary?: string;
}
interface CommoditiesResponse {
  metals: CommodityItem[]; energy: CommodityItem[];
  insights: CommoditiesInsights; updated: string;
}

export async function getCommodities(): Promise<CommoditiesResponse | null> {
  try {
    const res = await fetch(`${API}/api/commodities/`, { next: { revalidate: 120 } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export function findCommodity(data: CommoditiesResponse, id: string): { item: CommodityItem; group: "metals" | "energy" } | null {
  const m = data.metals.find(c => c.id === id);
  if (m) return { item: m, group: "metals" };
  const e = data.energy.find(c => c.id === id);
  if (e) return { item: e, group: "energy" };
  return null;
}

// Real, derived-not-fabricated week trend from the same chart array already
// shown on the page — first vs. last of the 7 real daily points.
export function weekTrend(chart: { value: number }[]): { pct: number; positive: boolean } | null {
  if (chart.length < 2) return null;
  const first = chart[0].value;
  const last = chart[chart.length - 1].value;
  if (!first) return null;
  const pct = ((last - first) / first) * 100;
  return { pct, positive: pct >= 0 };
}
