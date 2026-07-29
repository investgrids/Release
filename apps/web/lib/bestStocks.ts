import { API_BASE_URL as API } from "@/lib/api";
import { cleanText } from "@/lib/text";

/**
 * "Best <sector> stocks" pages — pure presentation layer over data that
 * already exists and is already scored: the Opportunity Radar
 * (opportunity_service.py / scoring_engine.py) already computes a real
 * per-company impact_score, confidence, trend, and reason for every
 * company it names inside each of the ~40-50 live opportunities. This
 * file only aggregates that already-real data by sector — no new scoring
 * logic, no LLM call, no fabricated ranking.
 *
 * Sector classification deliberately uses each COMPANY's own real sector
 * (from /api/companies/, e.g. "Automotive", "Banking") rather than the
 * opportunity's own `sectors[]` field. An opportunity is often tagged with
 * several sectors at once (e.g. one Q1-earnings-roundup opportunity tagged
 * ["Technology","Banking","Automotive"] because it mentions companies from
 * all three) and its `companies[]` array mixes names from every tagged
 * sector — using the opportunity's tags to classify its companies produced
 * "Best Automotive Stocks" pages containing HDFC Bank and Sun Pharma,
 * caught in local screenshot review before this ever shipped. The
 * company's own stored sector is the correct ground truth.
 */

export interface RankedCompany {
  symbol: string;
  name: string;
  impactScore: number;
  impactLabel: string;
  trend: string;
  confidence: number | null;
  reason: string;
  fromOpportunity: string; // title, for attribution
}

interface RadarListItem { id: number }
interface RadarDetail {
  id: number;
  title: string;
  companies?: { symbol: string; company_name: string; impact_score: number | null; impact_label: string; trend: string; confidence: number | null; reason: string }[];
}
interface CompanyRow { symbol: string; sector: string }

async function safeJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// Cached per request-render via Next's fetch cache (revalidate: 3600) — the
// ~40-50 detail calls this fans out to are the same calls the individual
// /opportunity-radar/[id] pages already make, just batched here rather than
// duplicated per sector page.
async function fetchAllOpportunityDetails(): Promise<RadarDetail[]> {
  const list = await safeJson<{ items?: RadarListItem[] }>(`${API}/api/radar/?page_size=100`);
  const items = list?.items ?? [];
  const details = await Promise.all(
    items.map(it => safeJson<RadarDetail>(`${API}/api/radar/${it.id}`))
  );
  return details.filter((d): d is RadarDetail => d !== null);
}

// Ground-truth symbol -> real sector map, paginated (backend caps
// page_size at 60) across all ~510 companies.
async function fetchCompanySectorMap(): Promise<Map<string, string>> {
  const map = new Map<string, string>();
  const first = await safeJson<{ companies?: CompanyRow[]; total_pages?: number }>(`${API}/api/companies/?page_size=60&page=1`);
  for (const c of first?.companies ?? []) if (c.sector) map.set(c.symbol, c.sector);
  const totalPages = first?.total_pages ?? 1;
  const rest = await Promise.all(
    Array.from({ length: Math.max(0, totalPages - 1) }, (_, i) =>
      safeJson<{ companies?: CompanyRow[] }>(`${API}/api/companies/?page_size=60&page=${i + 2}`)
    )
  );
  for (const page of rest) for (const c of page?.companies ?? []) if (c.sector) map.set(c.symbol, c.sector);
  return map;
}

export function sectorSlug(sector: string): string {
  return sector.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

interface SectorAggregate { sector: string; slug: string; companies: Map<string, RankedCompany> }

// Single shared pass — both callers need the same (opportunity x company x
// real-sector) join, so this computes it once rather than duplicating the
// fan-out fetch + join logic in two functions that could silently drift
// out of sync with each other.
async function aggregateBySector(): Promise<Map<string, SectorAggregate>> {
  const [details, sectorMap] = await Promise.all([
    fetchAllOpportunityDetails(),
    fetchCompanySectorMap(),
  ]);

  const bySector = new Map<string, SectorAggregate>();
  for (const d of details) {
    for (const c of d.companies ?? []) {
      if (c.impact_score == null) continue;
      const realSector = sectorMap.get(c.symbol);
      if (!realSector) continue; // no ground-truth sector on record — skip rather than misclassify
      const slug = sectorSlug(realSector);
      if (!bySector.has(slug)) bySector.set(slug, { sector: realSector, slug, companies: new Map() });
      const agg = bySector.get(slug)!;
      const existing = agg.companies.get(c.symbol);
      // Same company can be named by multiple opportunities — keep the
      // single highest real impact_score seen, not an average (a company
      // is a "best pick" if ANY real signal strongly supports it).
      if (!existing || c.impact_score > existing.impactScore) {
        agg.companies.set(c.symbol, {
          symbol: c.symbol,
          name: cleanText(c.company_name || c.symbol),
          impactScore: c.impact_score,
          impactLabel: c.impact_label,
          trend: c.trend,
          confidence: c.confidence,
          reason: cleanText(c.reason),
          fromOpportunity: cleanText(d.title),
        });
      }
    }
  }
  return bySector;
}

export async function getSectorsWithCounts(): Promise<{ sector: string; slug: string; companyCount: number }[]> {
  const bySector = await aggregateBySector();
  return [...bySector.values()]
    .map(agg => ({ sector: agg.sector, slug: agg.slug, companyCount: agg.companies.size }))
    // Thin-content guard — same reasoning as the historical pages: a
    // "best stocks" page with 1-2 real names isn't worth indexing.
    .filter(s => s.companyCount >= 3)
    .sort((a, b) => b.companyCount - a.companyCount);
}

export async function getRankedCompaniesForSector(sector: string): Promise<RankedCompany[]> {
  const bySector = await aggregateBySector();
  const agg = bySector.get(sectorSlug(sector));
  if (!agg) return [];
  return [...agg.companies.values()].sort((a, b) => b.impactScore - a.impactScore);
}
