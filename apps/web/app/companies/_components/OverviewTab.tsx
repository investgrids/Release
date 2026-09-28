import Link from "next/link";
import { Flame, Sparkles, Newspaper, ArrowRight } from "lucide-react";
import { fetchAPI } from "@/lib/api";
import { getSectorRankings, getTopLocalPreviewScores, type RankedCompanyRow, type TopLocalPreviewRow } from "@/lib/companyRankings";
import { marketRippleRatingColor, marketRippleScoreDisplayInt } from "@/lib/scoring";

// Real data only, every section — no fabricated numbers. Confirmed live
// before building this: /api/company-scores/ has no score-history field
// (so no honest "Fastest Improving Companies" section is possible without
// a backend change), and there's no comparison-usage tracking anywhere in
// the app (so no honest "Recently Compared Companies" either) — both were
// in the original 7-section spec, both omitted here rather than faked,
// same principle already agreed for Opportunity Radar's "Today's
// Opportunities". The 5 sections below are each backed by a real endpoint.

interface CompanyScoreContributor {
  reason: string | null;
  source_type: "article" | "opportunity";
  signed_magnitude: number;
  signal_at: string | null;
}
interface CompanyScoreRow {
  symbol: string;
  score: number | null;
  confidence: number | null;
  signal_count: number;
  sector: string | null;
  top_contributors: CompanyScoreContributor[];
}
interface ArticleRow { slug: string; headline: string; angle_entity?: string | null; published_at?: string; }

async function getCompanyScores(): Promise<CompanyScoreRow[]> {
  const data = await fetchAPI<{ companies: CompanyScoreRow[] }>("/api/company-scores/?limit=50").catch(() => null);
  return data?.companies ?? [];
}
async function getLatestCompanyArticles(): Promise<ArticleRow[]> {
  const data = await fetchAPI<{ items: ArticleRow[] }>("/api/insights/?article_type=company_intelligence&limit=4").catch(() => null);
  return data?.items ?? [];
}

interface QuoteRow { symbol: string; price_str: string; change_pct_str: string; positive: boolean }

// Real live prices for the Trending/Highest-Score widgets' own symbols
// only (never a separate, wider fetch) -- one batched call, same
// /api/data/quotes endpoint AllCompaniesTab's own price column reads
// indirectly via list_companies().
async function getQuotesFor(symbols: string[]): Promise<Map<string, QuoteRow>> {
  if (symbols.length === 0) return new Map();
  const data = await fetchAPI<{ quotes: QuoteRow[] }>(
    `/api/data/quotes?symbols=${encodeURIComponent(symbols.join(","))}`,
  ).catch(() => null);
  const map = new Map<string, QuoteRow>();
  for (const q of data?.quotes ?? []) {
    if (q?.symbol) map.set(q.symbol, q);
  }
  return map;
}

function displayName(symbol: string) {
  return symbol.replace(/^NSE_/, "");
}

function PriceTag({ quote }: { quote: QuoteRow | undefined }) {
  if (!quote) return null;
  return (
    <span className={`text-[10.5px] font-semibold tabular-nums ${quote.positive ? "text-emerald-400" : "text-rose-400"}`}>
      ₹{quote.price_str} <span className="text-[9.5px]">({quote.change_pct_str})</span>
    </span>
  );
}

function SectionCard({
  icon, title, href, children,
}: { icon: React.ReactNode; title: string; href: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-500/10 text-accent-violet">{icon}</span>
          <h3 className="text-[13px] font-bold text-text-primary">{title}</h3>
        </div>
        <Link href={href as any} className="flex items-center gap-0.5 text-[11px] font-semibold text-accent-violet hover:opacity-80 transition">
          View All <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      {children}
    </div>
  );
}

export async function OverviewTab() {
  const isDev = process.env.NODE_ENV === "development";
  const [scores, articles, bankingRankings, topLocalPreview] = await Promise.all([
    getCompanyScores(),
    getLatestCompanyArticles(),
    getSectorRankings("Banking"),
    isDev ? getTopLocalPreviewScores(5) : Promise.resolve([] as TopLocalPreviewRow[]),
  ]);

  const scored = scores.filter(s => s.score !== null);
  // "Trending" = most recently signaled, not a fabricated popularity metric.
  // Kept on the older engine deliberately — this reflects real signal
  // recency, not a rating, so it isn't a competing public company score.
  const trending = [...scored]
    .sort((a, b) => new Date(b.top_contributors[0]?.signal_at ?? 0).getTime() - new Date(a.top_contributors[0]?.signal_at ?? 0).getTime())
    .slice(0, 5);

  // MarketRipple Score migration (2026-09-26) — "AI Top Picks" renamed to
  // "Highest MarketRipple Scores" (owner correction: "Top Picks" implies a
  // recommendation this score has never been validated to make — it's a
  // descriptive ranking preview, not investment advice). Reads the same
  // approved MarketRippleScoreSnapshot projections the Company Rankings
  // page and each company's own page use, never a separate computation.
  //
  // Real, honest empty state (not a fabricated fallback to the old score)
  // for as long as publishable stays False, which is every company today
  // (S2 phase lock) — this card would otherwise show nothing at all in
  // local dev even though real scores exist, unlike every other
  // MarketRipple Score surface (Company/Compare/All Companies), which all
  // already show a dev-only "local preview" fallback (2026-09-27: this
  // card had been missed). topLocalPreview is real, cross-sector (not
  // Banking-only), the same unified MARKETRIPPLE_SCORE_V1 data, gated
  // server-side to 404 in real production.
  const topPicks: RankedCompanyRow[] = bankingRankings.ranked.slice(0, 5);
  const showLocalPreview = topPicks.length === 0 && topLocalPreview.length > 0;

  // Real live price for each symbol actually shown in these two widgets --
  // one batched call for the union, never a per-row fetch.
  const priceSymbols = Array.from(new Set([
    ...trending.map(c => displayName(c.symbol)),
    ...topPicks.map(c => c.symbol),
    ...(showLocalPreview ? topLocalPreview.map(c => c.symbol) : []),
  ]));
  const quotes = await getQuotesFor(priceSymbols);

  // "Companies Under Pressure" removed (2026-09-26, Company Rankings
  // migration) rather than re-pointed at the new score: it classified
  // "under pressure" purely from a low old-engine composite, which was
  // never a real signal of selling pressure to begin with. A low
  // MarketRipple Score (a fundamentals/valuation/behaviour/intelligence
  // composite) doesn't establish that either — there's no honest way to
  // build this classification from either score, so it's dropped rather
  // than re-implemented on the new one. Same precedent as "Best
  // Performing Sectors" above (2026-09-22): a card with no honest basis
  // is worse than no card.

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <SectionCard icon={<Flame className="h-3.5 w-3.5" />} title="Trending Companies" href="/companies?tab=all-companies">
        {trending.length === 0 ? <p className="text-[12px] text-text-muted">No recent signals yet.</p> : (
          <ul className="space-y-2">
            {trending.map(c => (
              <li key={c.symbol}>
                <Link href={`/companies/${displayName(c.symbol)}`} className="flex items-center justify-between rounded-lg px-2 py-1.5 transition hover:bg-text-primary/[0.04]">
                  <span>
                    <span className="block text-[12.5px] font-semibold text-text-primary">{displayName(c.symbol)}</span>
                    <PriceTag quote={quotes.get(displayName(c.symbol))} />
                  </span>
                  <span className="text-[11px] text-text-muted line-clamp-1 max-w-[45%] text-right">{c.top_contributors[0]?.reason ?? ""}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard icon={<Sparkles className="h-3.5 w-3.5" />} title="Highest MarketRipple Scores" href="/companies?tab=company-rankings">
        {topPicks.length > 0 ? (
          <ul className="space-y-2">
            {topPicks.map(c => (
              <li key={c.symbol}>
                <Link href={`/companies/${c.symbol}`} className="flex items-center justify-between rounded-lg px-2 py-1.5 transition hover:bg-text-primary/[0.04]">
                  <span>
                    <span className="block text-[12.5px] font-semibold text-text-primary">{c.companyName}</span>
                    <PriceTag quote={quotes.get(c.symbol)} />
                  </span>
                  <span className={`text-[12px] font-bold tabular-nums ${marketRippleRatingColor(c.rating)}`}>{marketRippleScoreDisplayInt(c.score)}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : showLocalPreview ? (
          <ul className="space-y-2">
            {topLocalPreview.map(c => (
              <li key={c.symbol}>
                <Link href={`/companies/${c.symbol}`} className="flex items-center justify-between rounded-lg px-2 py-1.5 transition hover:bg-text-primary/[0.04]">
                  <span>
                    <span className="block text-[12.5px] font-semibold text-text-primary">{c.companyName}</span>
                    <PriceTag quote={quotes.get(c.symbol)} />
                  </span>
                  <span className="flex items-center gap-1">
                    <span className={`text-[12px] font-bold tabular-nums ${marketRippleRatingColor(c.rating)}`}>{marketRippleScoreDisplayInt(c.score)}</span>
                    <span className="rounded border border-amber-500/30 bg-amber-500/10 px-1 py-0.5 text-[7px] font-bold uppercase tracking-wide text-amber-500" title="Local unpublished preview — never shown in production">
                      preview
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[12px] text-text-muted">No companies have a published MarketRipple Score yet.</p>
        )}
      </SectionCard>

      {/* "Best Performing Sectors" removed (2026-09-22 content-integrity
          repair) — it ranked by SectorData.value, a hand-typed
          percentage frozen since a 2026-07-22 seed insert and never
          updated by any job. No replacement sector-performance source
          exists yet (Data Foundation phase); a permanently-empty
          "unavailable" card is worse than no card at all. */}

      <SectionCard icon={<Newspaper className="h-3.5 w-3.5" />} title="Latest Company Intelligence" href="/newsroom">
        {articles.length === 0 ? <p className="text-[12px] text-text-muted">No company articles yet.</p> : (
          <ul className="space-y-2">
            {articles.map(a => (
              <li key={a.slug}>
                <Link href={`/newsroom/article/${a.slug}`} className="block rounded-lg px-2 py-1.5 transition hover:bg-text-primary/[0.04]">
                  <span className="line-clamp-2 text-[12.5px] font-semibold leading-snug text-text-primary">{a.headline}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  );
}
