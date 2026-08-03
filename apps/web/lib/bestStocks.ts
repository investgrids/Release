import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

/**
 * "Best <sector> stocks" pages — pure presentation layer over the AI Company
 * Intelligence Score engine (apps/backend/app/services/aipe/
 * company_score_engine.py). Previously this file aggregated rankings ONLY
 * from the ~47 Opportunity Radar items, which is why only 2 sectors
 * (Banking, Technology) ever cleared the 3-company thin-content minimum —
 * Defence, Auto/EV, Pharma and others simply weren't covered by that narrow
 * pool. The engine now merges that same opportunity data with real
 * per-company signals extracted from every published article's
 * companies_affected[], unlocking every sector with real coverage across
 * either source. No new scoring logic lives here — this file only shapes
 * the engine's response for these two pages.
 */

export interface RankedCompany {
  symbol: string;
  name: string;
  impactScore: number;
  impactLabel: string;
  trend: string;
  confidence: number | null;
  reason: string;
  fromOpportunity: string; // attribution — kept as the field name existing callers use
}

interface ScoreApiCompany {
  symbol: string; score: number | null; confidence: number | null;
  signal_count: number; sector: string | null;
  top_contributors: { reason: string | null; source_type: string; signed_magnitude: number }[];
}

async function safeJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function sectorSlug(sector: string): string {
  return sector.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function impactLabelFor(score: number): string {
  if (score >= 80) return "Very High";
  if (score >= 65) return "High";
  if (score >= 50) return "Medium";
  return "Low";
}

function trendFor(score: number): string {
  if (score > 55) return "up";
  if (score < 45) return "down";
  return "neutral";
}

async function fetchCompanyName(symbol: string): Promise<string> {
  const d = await safeJson<{ companies?: { symbol: string; name: string }[] }>(`${API}/api/companies/search?q=${symbol}`);
  return d?.companies?.find(c => c.symbol === symbol)?.name ?? symbol;
}

function toRankedCompany(c: ScoreApiCompany, name: string): RankedCompany {
  const top = c.top_contributors[0];
  return {
    symbol: c.symbol,
    name: cleanText(name),
    impactScore: c.score ?? 0,
    impactLabel: impactLabelFor(c.score ?? 0),
    trend: trendFor(c.score ?? 0),
    confidence: c.confidence,
    reason: cleanText(top?.reason || `Based on ${c.signal_count} real market signal${c.signal_count === 1 ? "" : "s"}`),
    fromOpportunity: top?.source_type === "opportunity" ? "Opportunity Radar" : "Published Analysis",
  };
}

export async function getSectorsWithCounts(): Promise<{ sector: string; slug: string; companyCount: number }[]> {
  // Dedicated endpoint (distinct-symbol counts per sector), not the ranked
  // list — that one caps at 50 results globally, which would silently
  // undercount sectors whose companies didn't make an arbitrary top-50 cut
  // before counts were even taken.
  const counts = await safeJson<Record<string, number>>(`${API}/api/company-scores/sector-counts`);
  return Object.entries(counts ?? {})
    .map(([sector, companyCount]) => ({ sector, slug: sectorSlug(sector), companyCount }))
    // Thin-content guard — same reasoning as the historical pages: a
    // "best stocks" page with 1-2 real names isn't worth indexing.
    .filter(s => s.companyCount >= 3)
    .sort((a, b) => b.companyCount - a.companyCount);
}

export async function getRankedCompaniesForSector(sector: string): Promise<RankedCompany[]> {
  const d = await safeJson<{ companies: ScoreApiCompany[] }>(`${API}/api/company-scores/sector/${encodeURIComponent(sector)}?limit=20`);
  const companies = d?.companies ?? [];
  const withNames = await Promise.all(
    companies.map(async c => toRankedCompany(c, await fetchCompanyName(c.symbol)))
  );
  return withNames.sort((a, b) => b.impactScore - a.impactScore);
}
