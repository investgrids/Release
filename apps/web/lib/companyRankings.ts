import { API_BASE_URL as API } from "@/lib/api";

/**
 * Company Rankings — pure presentation layer over the real MarketRipple
 * Score (apps/backend/app/services/marketripple_score/rankings.py).
 * Replaces the older AI Company Score ranking surface (lib/bestStocks.ts) —
 * never falls back to it. Banking-only today (the only approved
 * methodology); every other sector reports its own honest "not yet
 * available" state from the backend, never an empty list dressed up as
 * complete. No score is computed here — every field is read as-is from
 * the one real backend endpoint.
 */

export interface RankedCompanyRow {
  symbol: string;
  companyName: string;
  rank: number;
  score: number;
  rating: string | null;
  coveragePct: number | null;
  calculatedAt: string | null;
}

export interface PartialCoverageRow {
  symbol: string;
  companyName: string;
  message: string;
  calculatedAt: string | null;
}

export interface UnavailableRow {
  symbol: string;
  companyName: string;
  reason: "no_snapshot_computed_yet" | "publication_locked" | "ineligible" | "stale";
  message: string;
  calculatedAt: string | null;
}

export interface SectorRankings {
  sector: string;
  supported: boolean;
  message?: string;
  methodologyVersion?: string;
  ranked: RankedCompanyRow[];
  partialCoverage: PartialCoverageRow[];
  unavailable: UnavailableRow[];
  totalUniverse?: number;
  generatedAt?: string;
}

interface ApiRankedRow { symbol: string; company_name: string; rank: number; score: number; rating: string | null; coverage_pct: number | null; calculated_at: string | null; }
interface ApiPartialRow { symbol: string; company_name: string; message: string; calculated_at: string | null; }
interface ApiUnavailableRow { symbol: string; company_name: string; reason: UnavailableRow["reason"]; message: string; calculated_at?: string | null; }
interface ApiSectorRankings {
  sector: string; supported: boolean; message?: string; methodology_version?: string;
  ranked: ApiRankedRow[]; partial_coverage: ApiPartialRow[]; unavailable: ApiUnavailableRow[];
  total_universe?: number; generated_at?: string;
}

async function safeJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function getSectorRankings(sector: string): Promise<SectorRankings> {
  const d = await safeJson<ApiSectorRankings>(`${API}/api/company-rankings/${encodeURIComponent(sector)}`);
  if (!d) {
    return { sector, supported: false, message: "Rankings are temporarily unavailable.", ranked: [], partialCoverage: [], unavailable: [] };
  }
  return {
    sector: d.sector,
    supported: d.supported,
    message: d.message,
    methodologyVersion: d.methodology_version,
    ranked: (d.ranked ?? []).map(r => ({
      symbol: r.symbol, companyName: r.company_name, rank: r.rank, score: r.score,
      rating: r.rating, coveragePct: r.coverage_pct, calculatedAt: r.calculated_at,
    })),
    partialCoverage: (d.partial_coverage ?? []).map(r => ({
      symbol: r.symbol, companyName: r.company_name, message: r.message, calculatedAt: r.calculated_at,
    })),
    unavailable: (d.unavailable ?? []).map(r => ({
      symbol: r.symbol, companyName: r.company_name, reason: r.reason, message: r.message,
      calculatedAt: r.calculated_at ?? null,
    })),
    totalUniverse: d.total_universe,
    generatedAt: d.generated_at,
  };
}

// The real, currently-supported sector list for this ranking surface —
// deliberately just one entry today (Banking is the only approved
// methodology). A future sector's methodology approval adds to this list;
// it must never be inferred from the general company-sector list, which
// would silently imply support that doesn't exist yet.
export const SUPPORTED_RANKING_SECTORS = ["Banking"] as const;
