// Market Intelligence hub — which tabs show the India-centric right sidebar
// (MarketIntelligenceSidebar: NSE Pre-Market Top Movers, India Breaking News,
// India-derived Fear & Greed from /api/market/insights).
//
// The sidebar is India market context, so it must NOT appear on the Global
// Markets or Crypto tabs — showing NSE movers / India news / an India sentiment
// gauge there would mislabel Indian data as global or crypto (§2.5 leak fix,
// 2026-10-25). live-market / pre-market already carry their own canonical
// widgets; commodities / calendar / sector-intelligence never had it.

export const INDIA_SIDEBAR_HIDDEN_TABS: readonly string[] = [
  "live-market",
  "pre-market",
  "commodities",
  "calendar",
  "sector-intelligence",
  "global-markets", // §2.5 — global markets must never show NSE movers as its own
  "crypto",         // §2.5 — crypto stays isolated from equity data
];

/** Does this tab render the India-centric Market Intelligence sidebar? */
export function showsIndiaSidebar(tab: string): boolean {
  return !INDIA_SIDEBAR_HIDDEN_TABS.includes(tab);
}
