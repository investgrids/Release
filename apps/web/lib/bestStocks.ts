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
  verdict: { label: string; tone: string; reasoning: string } | null;
  riskLevel: string | null;
  sector: string | null;
  signalCount: number;
  lastSignalAt: string | null;
  riskFactor: string | null;
  price: string | null;
  changePct: number | null;
  marketCap: string | null;
  cap: "large" | "mid" | "small" | null;
}

interface ScoreApiCompany {
  symbol: string; score: number | null; confidence: number | null;
  signal_count: number; sector: string | null; trend?: string; risk_level?: string;
  verdict?: { label: string; tone: string; reasoning: string } | null;
  top_contributors: { reason: string | null; source_type: string; signed_magnitude: number; signal_at?: string | null }[];
  positive_reasons?: { reason: string | null; source_type: string; signed_magnitude: number; signal_at?: string | null }[];
  risk_factors?: { reason: string | null; source_type: string; signed_magnitude: number; signal_at?: string | null }[];
}

export interface RankingStats {
  stocksRanked: number;
  sectorsCovered: number;
  avgScore: number | null;
  avgConfidence: number | null;
  updatedAt: string | null;
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

// Was two lookups: this fetch for the real display name, plus a separate
// synchronous find() against a static local copy of the universe (lib/
// companies-data.ts) for cap tier — that static copy had silently drifted
// to 194 companies vs. the backend's real 512, so cap silently came back
// null for any company outside the stale list. The /api/companies/search
// response already carries cap alongside name in the same payload; no
// second network call needed, just read the field that was already there.
async function fetchCompanyMeta(symbol: string): Promise<{ name: string; cap: "large" | "mid" | "small" | null }> {
  const d = await safeJson<{ companies?: { symbol: string; name: string; cap?: "large" | "mid" | "small" }[] }>(`${API}/api/companies/search?q=${symbol}`);
  const match = d?.companies?.find(c => c.symbol === symbol);
  return { name: match?.name ?? symbol, cap: match?.cap ?? null };
}

function toRankedCompany(c: ScoreApiCompany, meta: { name: string; cap: "large" | "mid" | "small" | null }): RankedCompany {
  const top = c.top_contributors[0];
  const positive = c.positive_reasons?.[0];
  const risk = c.risk_factors?.[0];
  return {
    symbol: c.symbol,
    name: cleanText(meta.name),
    impactScore: c.score ?? 0,
    impactLabel: impactLabelFor(c.score ?? 0),
    trend: c.trend ?? trendFor(c.score ?? 0),
    confidence: c.confidence,
    reason: cleanText((positive ?? top)?.reason || `Based on ${c.signal_count} real market signal${c.signal_count === 1 ? "" : "s"}`),
    fromOpportunity: top?.source_type === "opportunity" ? "Opportunity Radar" : "Published Analysis",
    verdict: c.verdict ?? null,
    riskLevel: c.risk_level ?? null,
    sector: c.sector,
    signalCount: c.signal_count,
    lastSignalAt: top?.signal_at ?? null,
    riskFactor: risk?.reason ? cleanText(risk.reason) : null,
    price: null,
    changePct: null,
    marketCap: null,
    cap: meta.cap,
  };
}

function formatMarketCap(raw: number): string {
  if (raw >= 1e12) return `₹${(raw / 1e12).toFixed(2)}T`;
  if (raw >= 1e9) return `₹${(raw / 1e9).toFixed(0)}B`;
  if (raw >= 1e7) return `₹${(raw / 1e7).toFixed(0)}Cr`;
  return `₹${raw.toLocaleString("en-IN")}`;
}

// Real live price/change/market-cap per symbol. Deliberately NOT
// /api/stocks/{symbol} (confirmed live: ~5s per call, synchronous yfinance
// underneath — 10-30 of those in parallel either queue behind the
// browser's 6-connections-per-origin cap or serialize on the backend,
// leaving the sector filter/table stuck "loading" for 30s+). Price/change
// come from /api/data/quotes, a real bulk endpoint (all symbols in one
// ~0.8s call); market cap still needs one call per symbol, but
// /api/data/company/{symbol} returns it in ~0.7s vs 5s. A quote lookup
// failing for one symbol never drops that company from the ranking — it
// just shows without price data rather than being silently excluded.
export async function enrichWithQuotes(companies: RankedCompany[]): Promise<RankedCompany[]> {
  if (companies.length === 0) return companies;
  const symbols = companies.map(c => c.symbol).join(",");
  const [bulk, caps] = await Promise.all([
    safeJson<{ quotes: { symbol: string; price_str?: string; change_pct_str?: string; change_percent?: number }[] }>(
      `${API}/api/data/quotes?symbols=${encodeURIComponent(symbols)}`
    ),
    Promise.all(companies.map(c => safeJson<{ market_cap?: number }>(`${API}/api/data/company/${c.symbol}`))),
  ]);
  const quoteBySymbol = new Map((bulk?.quotes ?? []).map(q => [q.symbol, q]));

  return companies.map((c, i) => {
    const q = quoteBySymbol.get(c.symbol);
    const cap = caps[i]?.market_cap;
    return {
      ...c,
      price: q?.price_str ?? null,
      changePct: q?.change_percent ?? null,
      marketCap: cap ? formatMarketCap(cap) : null,
    };
  });
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

export async function getRankedCompaniesForSector(sector: string, withQuotes = false): Promise<RankedCompany[]> {
  const d = await safeJson<{ companies: ScoreApiCompany[] }>(`${API}/api/company-scores/sector/${encodeURIComponent(sector)}?limit=50`);
  const companies = d?.companies ?? [];
  const withNames = await Promise.all(
    companies.map(async c => toRankedCompany(c, await fetchCompanyMeta(c.symbol)))
  );
  const sorted = withNames.sort((a, b) => b.impactScore - a.impactScore);
  return withQuotes ? enrichWithQuotes(sorted) : sorted;
}

export async function getTopRankedCompanies(limit = 12, withQuotes = false): Promise<RankedCompany[]> {
  const d = await safeJson<{ companies: ScoreApiCompany[] }>(`${API}/api/company-scores/?limit=${limit}`);
  const companies = d?.companies ?? [];
  const withNames = await Promise.all(
    companies.map(async c => toRankedCompany(c, await fetchCompanyMeta(c.symbol)))
  );
  const sorted = withNames.sort((a, b) => b.impactScore - a.impactScore);
  return withQuotes ? enrichWithQuotes(sorted) : sorted;
}

export async function getRankingStats(): Promise<RankingStats> {
  const d = await safeJson<{
    stocks_ranked: number; sectors_covered: number;
    avg_score: number | null; avg_confidence: number | null; updated_at: string | null;
  }>(`${API}/api/company-scores/stats`);
  return {
    stocksRanked: d?.stocks_ranked ?? 0,
    sectorsCovered: d?.sectors_covered ?? 0,
    avgScore: d?.avg_score ?? null,
    avgConfidence: d?.avg_confidence ?? null,
    updatedAt: d?.updated_at ?? null,
  };
}

// Real, live market bias — reuses the same MIE state every other page (e.g.
// newsroom's Market Sentiment panel) already reads, not a page-local guess.
export async function getMarketRegime(): Promise<string | null> {
  const d = await safeJson<{ market_bias?: string }>(`${API}/api/mie/state`);
  return d?.market_bias ?? null;
}

// Real, live count of currently-active Opportunity Radar items — deliberately
// not labeled "Today's Opportunities" since there is no real per-day date
// field on opportunities (confirmed absent this session while building the
// Opportunity Radar hub) — this is the honest total, not a fabricated daily one.
export async function getActiveOpportunityCount(): Promise<number> {
  const d = await safeJson<{ total?: number }>(`${API}/api/radar/?limit=1`);
  return d?.total ?? 0;
}
