import { notFound } from "next/navigation";
import { API_BASE_URL as API } from "@/lib/api";
import { neutralRating } from "@/lib/text";
import StockPage, { type StockDetail } from "./CompanyPageClient";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

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

// SEO fix: previously a 404 from the backend (symbol genuinely doesn't
// exist — verified live via /companies/ABNB, /companies/AEGISCHEM,
// /companies/BAJAJEL all returning a real 404 there) and any OTHER failure
// (network error, a transient 5xx) both collapsed to the same `null`,
// which just skipped the <h1>/description block below and still shipped
// HTTP 200 — an indexable-looking page with no real content for a company
// that doesn't exist. Distinguishing "genuinely not found" from "couldn't
// fetch right now" matters: only the former should ever 404 the page —
// a transient backend blip shouldn't tell a crawler a valid company page
// doesn't exist.
async function fetchStock(symbol: string): Promise<{ data: StockDetail | null; symbolNotFound: boolean }> {
  try {
    const res = await fetch(`${API}/api/stocks/${symbol}`, { next: { revalidate: 300 } });
    if (res.status === 404) return { data: null, symbolNotFound: true };
    if (!res.ok) return { data: null, symbolNotFound: false };
    return { data: await res.json(), symbolNotFound: false };
  } catch {
    return { data: null, symbolNotFound: false };
  }
}

// SEO Phase 2, §2.4 — server-fetches the same /api/related endpoint
// RelatedContent otherwise fetches client-side, so the internal-link web
// this block builds exists in the initial HTML, not just after hydration.
async function fetchRelated(symbol: string, name: string, sector?: string) {
  try {
    const params = new URLSearchParams({ title: name, ...(sector ? { sector } : {}) });
    const res = await fetch(`${API}/api/related/company/${encodeURIComponent(symbol)}?${params}`, { next: { revalidate: 600 } });
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

// Real, honest FAQ candidates — every question only appears when the
// backing field actually has a real (non-placeholder) value; nothing is
// invented to fill out a fixed list. AEO-shaped (direct-answer, plain
// sentence) using data already fetched for the page, not a new call.
function buildFaqs(stock: StockDetail, upper: string): { question: string; answer: string }[] {
  const faqs: { question: string; answer: string }[] = [];

  faqs.push({
    question: `What is ${stock.name}'s share price today?`,
    answer: `${stock.name} (NSE: ${upper}) is currently trading at ₹${stock.price}${stock.change ? ` (${stock.change})` : ""}.`,
  });

  if (fmtCrore(stock.market_cap)) {
    faqs.push({
      question: `What is ${stock.name}'s market capitalization?`,
      answer: `${stock.name}'s market capitalization is ₹${stock.market_cap}.`,
    });
  }

  if (fmtCrore(stock.pe)) {
    faqs.push({
      question: `What is ${stock.name}'s P/E ratio?`,
      answer: `${stock.name}'s price-to-earnings (P/E) ratio is ${stock.pe}.`,
    });
  }

  if (stock.sector && stock.sector !== "N/A") {
    faqs.push({
      question: `What sector does ${stock.name} operate in?`,
      answer: `${stock.name} operates in the ${stock.sector} sector${stock.industry && stock.industry !== stock.sector ? ` (${stock.industry})` : ""}.`,
    });
  }

  if (stock.analyst_count > 0) {
    faqs.push({
      question: `What is the analyst consensus on ${stock.name}?`,
      answer: `Analyst consensus on ${stock.name} currently reads ${neutralRating(stock.recommendation).toLowerCase()}, based on ${stock.analyst_count} analyst${stock.analyst_count > 1 ? "s" : ""} covering the stock. This is third-party analyst data, not a MarketRipple recommendation.`,
    });
  }

  return faqs;
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
  const { data: stock, symbolNotFound } = await fetchStock(upper);
  if (symbolNotFound) notFound();
  const related = stock ? await fetchRelated(upper, stock.name, stock.sector) : null;
  const url = `${SITE}/companies/${upper}`;
  const faqs = stock ? buildFaqs(stock, upper) : [];

  // No nested `breadcrumb` here — the root layout already renders a global
  // <Breadcrumbs/> emitting its own BreadcrumbList JSON-LD on every page
  // (confirmed live: this page was shipping two separate BreadcrumbList
  // blocks before this fix). One canonical breadcrumb source, not two.
  const jsonLd = stock ? {
    "@context": "https://schema.org",
    "@type": "Corporation",
    name: stock.name,
    tickerSymbol: upper,
    url,
    description: stock.description
      ? withPeriod(stock.description)
      : `${stock.name} (${upper}) — AI-powered market analysis on MarketRipple.`,
    ...(stock.sector && stock.sector !== "N/A" ? { industry: stock.sector } : {}),
  } : null;

  const faqJsonLd = faqs.length > 0 ? {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map(f => ({ "@type": "Question", name: f.question, acceptedAnswer: { "@type": "Answer", text: f.answer } })),
  } : null;

  return (
    <>
      {jsonLd && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      )}
      {faqJsonLd && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />
      )}
      {stock && (
        <section className="mb-4 border-b border-surface-border/6 pb-4">
          {/* The single real <h1> for this page — CompanyHero inside the
              client component renders the same name as a styled <p>, not
              a second <h1>, to avoid a duplicate heading. Genuinely
              visible (not sr-only/hidden) — real page context for users
              on first paint, not a cloaked SEO-only block. */}
          <h1 className="text-[13px] font-semibold uppercase tracking-wide text-text-muted">
            {stock.name} ({upper}) Share Price &amp; AI Investment Analysis
          </h1>
          {/* No max-width cap — the old max-w-3xl (768px) capped this well
              short of the page's real container width, wasting the space
              beside it on wide screens and forcing 6 lines where 3 would
              do; letting it fill the section naturally fixes both. */}
          <p className="mt-1.5 text-[13px] leading-relaxed text-text-secondary">
            {withPeriod(
              stock.description
                ? stock.description
                : `${stock.name} (${upper}) trades on the NSE${stock.sector && stock.sector !== "N/A" ? ` in the ${stock.sector} sector` : ""}${stock.industry && stock.industry !== stock.sector ? ` (${stock.industry})` : ""}`
            )}
            {" "}Track {stock.name}&apos;s live NSE:{upper} share price ₹{stock.price}{stock.change ? ` (${stock.change})` : ""}
            {fmtCrore(stock.market_cap) ? `, market cap ₹${stock.market_cap}` : ""}
            {fmtCrore(stock.pe) ? `, P/E ${stock.pe}` : ""}. MarketRipple's AI analysis covers the investment thesis, ripple-chain impact, and
            {stock.sector && stock.sector !== "N/A" ? ` ${stock.sector} sector ` : " "}outlook for {upper} — real-time NSE India stock intelligence.
          </p>
        </section>
      )}
      {faqs.length > 0 && (
        <section className="mb-4 border-b border-surface-border/6 pb-4" aria-label={`${stock?.name} frequently asked questions`}>
          <h2 className="mb-2 text-[11px] font-bold uppercase tracking-wide text-text-muted">Frequently Asked Questions</h2>
          <div className="space-y-1.5">
            {faqs.map((f, i) => (
              <details key={i} className="group rounded-lg border border-surface-border/6 bg-text-primary/[0.015] px-3 py-2">
                <summary className="cursor-pointer list-none text-[12.5px] font-medium text-text-secondary marker:content-none">
                  {f.question}
                </summary>
                <p className="mt-1.5 text-[12px] leading-5 text-text-muted">{f.answer}</p>
              </details>
            ))}
          </div>
        </section>
      )}
      <StockPage params={params} initialStock={stock} initialRelated={related} />
    </>
  );
}
