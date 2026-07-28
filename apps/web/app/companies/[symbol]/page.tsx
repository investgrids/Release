import { API_BASE_URL as API } from "@/lib/api";
import StockPage, { type StockDetail } from "./CompanyPageClient";

/**
 * Server wrapper (Phase 1 SEO fix — see the SEO/Growth audit's Critical
 * Finding #1: this route previously shipped zero server-rendered content,
 * confirmed live via `curl` returning an empty body). Fetches the same
 * /api/stocks/{symbol} endpoint the client component already calls, purely
 * so crawlers (and the very first paint, before hydration) see a real,
 * indexable <h1> + description instead of nothing. The rich, interactive
 * page — charts, ripple graph, tabs — is unchanged and still lives in
 * CompanyPageClient.tsx; this file never duplicates that UI, only the
 * minimum real prose a search result snippet or a non-JS crawler needs.
 */

async function fetchStock(symbol: string): Promise<StockDetail | null> {
  try {
    const res = await fetch(`${API}/api/stocks/${symbol}`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function fmtCrore(v?: string) {
  if (!v || v === "—" || v === "N/A") return null;
  return v;
}

// The backend's `description` field (yfinance's longBusinessSummary) is
// occasionally truncated mid-word at the source — ensure a clean sentence
// boundary before appending MarketRipple's own stats sentence, rather than
// running two unrelated clauses together with no punctuation.
function withPeriod(text: string) {
  const t = text.trim();
  return /[.!?]$/.test(t) ? t : `${t}.`;
}

export default async function CompanyPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const upper = symbol.toUpperCase();
  const stock = await fetchStock(upper);

  return (
    <>
      {stock && (
        <section className="mb-4 border-b border-white/[0.06] pb-4">
          {/* The single real <h1> for this page — CompanyHero inside the
              client component renders the same name as a styled <p>, not
              a second <h1>, to avoid a duplicate heading. Genuinely
              visible (not sr-only/hidden) — real page context for users
              on first paint, not a cloaked SEO-only block. */}
          <h1 className="text-[13px] font-semibold uppercase tracking-wide text-slate-500">
            {stock.name} ({upper}) — AI Investment Analysis
          </h1>
          <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-slate-400">
            {withPeriod(
              stock.description
                ? stock.description
                : `${stock.name} (${upper}) trades on the NSE${stock.sector && stock.sector !== "N/A" ? ` in the ${stock.sector} sector` : ""}${stock.industry && stock.industry !== stock.sector ? ` (${stock.industry})` : ""}`
            )}
            {" "}Current price ₹{stock.price}{stock.change ? ` (${stock.change})` : ""}
            {fmtCrore(stock.market_cap) ? `, market cap ₹${stock.market_cap}` : ""}
            {fmtCrore(stock.pe) ? `, P/E ${stock.pe}` : ""}. MarketRipple's AI analysis covers the investment thesis,
            ripple-chain impact, and event-driven intelligence behind {stock.name}.
          </p>
        </section>
      )}
      <StockPage params={params} initialStock={stock} />
    </>
  );
}
