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
  reason: "no_snapshot_computed_yet" | "publication_locked" | "ineligible" | "stale" | "INSUFFICIENT_MARKET_HISTORY";
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

// ── Full-directory paginated rankings (owner instruction, 2026-09-27,
// "Company Rankings and UI") — every real company, not just Banking's own
// per-sector view above. `status` is the one honest field driving display:
// "ranked" is the only status that ever carries a real score/rating/rank;
// everything else is an explicit N/A with its own real reason, never a
// fabricated number and never a rank.
export type AllCompanyRankingStatus =
  | "ranked"
  // 2026-09-28 public coverage states (backend coverage.py)
  | "not_processed" | "needs_refresh" | "insufficient_data" | "unsupported" | "peer_group_review" | "no_peer_group"
  // legacy names, still accepted from an older backend
  | "partial_coverage" | "no_snapshot_computed_yet"
  | "publication_locked" | "ineligible" | "stale" | "unsupported_sector" | "not_yet_scored";

export interface AllCompanyLocalPreview {
  score: number;
  rating: string | null;
  rank: number;
  totalRankedInSector: number;
}

export interface AllCompanyRankingRow {
  symbol: string;
  companyName: string;
  sector: string;
  status: AllCompanyRankingStatus;
  score: number | null;
  rating: string | null;
  coveragePct: number | null;
  rank: number | null;
  totalRankedInSector: number | null;
  calculatedAt: string | null;
  message: string | null;
  // The peer group a ranked score was calculated against (grouped sectors, e.g. Infrastructure).
  peerGroup?: string | null;
  // LOCAL-DEV-ONLY (2026-09-27) — a real score/rating/rank regardless of
  // `publishable`, always null in real production (backend strips it).
  localPreview: AllCompanyLocalPreview | null;
}

export interface AllCompanyRankingsPage {
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  companies: AllCompanyRankingRow[];
  generatedAt?: string;
}

interface ApiAllCompanyLocalPreview {
  score: number; rating: string | null; rank: number; total_ranked_in_sector: number;
}
interface ApiAllCompanyRow {
  symbol: string; company_name: string; sector: string; status: AllCompanyRankingStatus;
  score: number | null; rating: string | null; coverage_pct: number | null;
  rank: number | null; total_ranked_in_sector: number | null;
  calculated_at: string | null; message: string | null; peer_group?: string | null;
  local_preview: ApiAllCompanyLocalPreview | null;
}
interface ApiAllCompanyRankingsPage {
  total: number; page: number; page_size: number; total_pages: number;
  companies: ApiAllCompanyRow[]; generated_at?: string;
}

const EMPTY_ALL_COMPANIES_PAGE: AllCompanyRankingsPage = {
  total: 0, page: 1, pageSize: 50, totalPages: 1, companies: [],
};

export interface TopLocalPreviewRow {
  symbol: string;
  companyName: string;
  score: number;
  rating: string | null;
}

// LOCAL-DEV-ONLY (2026-09-27) — real top-N scores regardless of
// `publishable`, mirroring the per-company local-preview pattern already
// used on Company/Compare/All Companies. 404s in real production (backend
// gate), so this always resolves to [] there — callers should only use it
// as a dev-only supplement to the real public ranked list, never a
// replacement for it.
export async function getTopLocalPreviewScores(limit: number): Promise<TopLocalPreviewRow[]> {
  const d = await safeJson<{ companies: { symbol: string; company_name: string; score: number; rating: string | null }[] }>(
    `${API}/api/company-rankings/local-preview/top?limit=${encodeURIComponent(String(limit))}`,
  );
  if (!d) return [];
  return d.companies.map(c => ({ symbol: c.symbol, companyName: c.company_name, score: c.score, rating: c.rating }));
}

// Public: highest published scores across every supported sector.
export async function getTopPublishedScores(limit: number): Promise<TopLocalPreviewRow[]> {
  const d = await safeJson<{ companies: { symbol: string; company_name: string; score: number; rating: string | null }[] }>(
    `${API}/api/company-rankings/top?limit=${encodeURIComponent(String(limit))}`,
  );
  if (!d) return [];
  return d.companies.map(c => ({ symbol: c.symbol, companyName: c.company_name, score: c.score, rating: c.rating }));
}

export async function getAllCompaniesRankings(page: number, pageSize: number): Promise<AllCompanyRankingsPage> {
  const d = await safeJson<ApiAllCompanyRankingsPage>(
    `${API}/api/company-rankings/?page=${encodeURIComponent(String(page))}&page_size=${encodeURIComponent(String(pageSize))}`,
  );
  if (!d) return EMPTY_ALL_COMPANIES_PAGE;
  return {
    total: d.total, page: d.page, pageSize: d.page_size, totalPages: d.total_pages,
    generatedAt: d.generated_at,
    companies: (d.companies ?? []).map(r => ({
      symbol: r.symbol, companyName: r.company_name, sector: r.sector, status: r.status,
      score: r.score, rating: r.rating, coveragePct: r.coverage_pct,
      rank: r.rank, totalRankedInSector: r.total_ranked_in_sector,
      calculatedAt: r.calculated_at, message: r.message, peerGroup: r.peer_group ?? null,
      localPreview: r.local_preview ? {
        score: r.local_preview.score, rating: r.local_preview.rating,
        rank: r.local_preview.rank, totalRankedInSector: r.local_preview.total_ranked_in_sector,
      } : null,
    })),
  };
}
