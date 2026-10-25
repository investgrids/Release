// Market-selector registry (Global Markets Phase C — 2026-10-25).
//
// Single source of truth for the supported market universes, their index
// benchmarks, and — honestly — which sections each market can actually populate
// from EXISTING data. There is no non-India stock universe, no non-India sector
// data and no non-India market news in this product, so movers / sector heatmap /
// news are marked unavailable for US / Europe / Asia-Pacific with a concise,
// section-specific limitation (plus an internal `code` for diagnostics) rather
// than faked. India routes into the existing rich India surfaces instead of being
// duplicated here. Adding a market or upgrading a section's status is a
// data-provider decision made here, in one place — never by special-casing a
// presentational component.

export type MarketId = "US" | "EU" | "APAC" | "IN";

export type SectionKey =
  | "indexStrip"
  | "futures"
  | "movers"
  | "sectorHeatmap"
  | "news"
  | "screeners";

export type SectionAvailability =
  | { status: "available" }
  // `code` is an internal diagnostic tag (e.g. NO_STOCK_UNIVERSE); `title` +
  // `detail` are the concise two-line user-facing limitation.
  | { status: "unavailable"; code: string; title: string; detail: string }
  | { status: "external"; href: string; label: string };

export interface MarketConfig {
  id: MarketId;
  label: string;
  flag: string;
  /** Benchmark names EXACTLY as returned by GET /api/market/global. Empty for a
   *  market that routes out to existing surfaces instead of rendering a strip. */
  indexNames: string[];
  sections: Record<SectionKey, SectionAvailability>;
}

// Shared, honest limitation copy — one definition each, reused across markets.
// Concise title + a detail specific to the limitation; the code stays internal.
const LIMIT: Record<string, Extract<SectionAvailability, { status: "unavailable" }>> = {
  stockUniverse: { status: "unavailable", code: "NO_STOCK_UNIVERSE", title: "Index-level data only", detail: "Stock movers require a dedicated market-data source." },
  sectorData: { status: "unavailable", code: "NO_SECTOR_DATA", title: "Index-level data only", detail: "Sector heatmaps require a sector-classification source." },
  marketNews: { status: "unavailable", code: "NO_MARKET_NEWS", title: "No regional news feed", detail: "Region-specific market news requires an approved source." },
  screeners: { status: "unavailable", code: "NO_SCREENERS", title: "Not available yet", detail: "Screeners need per-constituent history and volume coverage." },
  futuresFeed: { status: "unavailable", code: "NO_FUTURES_FEED", title: "Cash indices only", detail: "No index-futures feed is wired for this market." },
};

// India routes into the existing rich India dashboard (same hub, other tabs) —
// never duplicated here.
const INDIA_HUB = "/market-intelligence";

export const MARKETS: MarketConfig[] = [
  {
    id: "US",
    label: "United States",
    flag: "🇺🇸",
    indexNames: ["S&P 500", "Dow Jones", "Nasdaq"],
    sections: {
      indexStrip: { status: "available" },
      futures: { status: "available" }, // ES/NQ/YM via /api/market/futures
      movers: LIMIT.stockUniverse,
      sectorHeatmap: LIMIT.sectorData,
      news: LIMIT.marketNews,
      screeners: LIMIT.screeners,
    },
  },
  {
    id: "EU",
    label: "Europe",
    flag: "🇪🇺",
    indexNames: ["FTSE 100", "DAX", "CAC 40"],
    sections: {
      indexStrip: { status: "available" },
      futures: LIMIT.futuresFeed,
      movers: LIMIT.stockUniverse,
      sectorHeatmap: LIMIT.sectorData,
      news: LIMIT.marketNews,
      screeners: LIMIT.screeners,
    },
  },
  {
    id: "APAC",
    label: "Asia-Pacific",
    flag: "🌏",
    indexNames: ["Nikkei 225", "Hang Seng", "Shanghai Composite", "KOSPI"],
    sections: {
      indexStrip: { status: "available" },
      futures: LIMIT.futuresFeed,
      movers: LIMIT.stockUniverse,
      sectorHeatmap: LIMIT.sectorData,
      news: LIMIT.marketNews,
      screeners: LIMIT.screeners,
    },
  },
  {
    id: "IN",
    label: "India",
    flag: "🇮🇳",
    indexNames: [], // routes out — see sections below
    sections: {
      indexStrip: { status: "external", href: INDIA_HUB, label: "Overview & Live Market tabs" },
      futures: { status: "external", href: INDIA_HUB, label: "Pre-Market tab (Gift Nifty, futures, India VIX)" },
      movers: { status: "external", href: INDIA_HUB, label: "Live Market tab (top movers, breadth)" },
      sectorHeatmap: { status: "external", href: INDIA_HUB, label: "Sector Intelligence tab" },
      news: { status: "external", href: INDIA_HUB, label: "Overview tab (market news)" },
      screeners: LIMIT.screeners,
    },
  },
];

export const DEFAULT_MARKET_ID: MarketId = "US";

export function getMarket(id: string): MarketConfig | undefined {
  return MARKETS.find((m) => m.id === id);
}

/** Does this market render a native index strip (vs route out)? */
export function hasOwnIndexStrip(m: MarketConfig): boolean {
  return m.sections.indexStrip.status === "available" && m.indexNames.length > 0;
}
