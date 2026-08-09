import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { API_BASE_URL as API } from "@/lib/api";
import { safeJsonLd } from "@/lib/text";
import { AskAICta } from "@/components/AskAICta";

/**
 * Sector landing page (SEO Phase 2, §2.1 — the single largest programmatic-
 * SEO gap identified in the audit: real sector data was used throughout
 * the product but had no dedicated, indexable URL of its own). Server
 * Component from the start — no client-fetch SSR gap to retrofit here,
 * unlike the Phase 1 pages. Every field comes from /api/sectors/{id}/
 * intelligence, itself a pure aggregation of existing tables (see
 * sectors.py's own docstring) — no new intelligence generated.
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

interface SectorStock { symbol: string; name: string; price: string; change: string; positive: boolean }
interface SectorOpportunity { id: number; slug: string; title: string; opportunity_score: number | null; confidence: number | null }
interface SectorEvent { id: string; slug?: string; title: string; impact_score: number | null; date: string | null }
interface SectorIntelligence {
  id: string; name: string;
  // null for sectors with real constituent stocks + opportunities/events
  // but no live-momentum SectorData row (e.g. Defence, Chemicals, Telecom,
  // Finance) — an honest "no live index for this one" rather than a
  // fabricated 0%.
  value: string | null; positive: boolean | null;
  stocks: SectorStock[]; opportunities: SectorOpportunity[]; events: SectorEvent[];
}

async function fetchSector(sector: string): Promise<SectorIntelligence | null> {
  try {
    const res = await fetch(`${API}/api/sectors/${sector}/intelligence`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

interface RelatedArticle {
  slug: string; headline: string; article_type: string;
  companies_affected: { symbol: string }[];
}

// TS mirror of sectors.py's _words_overlap — real sector-name variance
// (SectorData's "IT" vs an article's own "Technology" tag; "Auto" vs
// "Automotive") means a naive exact-string match silently misses real,
// already-published content. Same alias pair as the Python version (the
// one case with zero substring relationship).
const _SECTOR_ALIASES: Record<string, Set<string>> = { it: new Set(["technology", "information"]) };
function sectorWordsOverlap(a: Set<string>, b: Set<string>): boolean {
  for (const wa of a) {
    const aliases = _SECTOR_ALIASES[wa] ?? new Set<string>();
    for (const wb of b) {
      if (wa === wb || wa.includes(wb) || wb.includes(wa) || aliases.has(wb)) return true;
    }
  }
  return false;
}
function sectorMatches(sectorName: string, tag: string): boolean {
  return sectorWordsOverlap(new Set(sectorName.toLowerCase().split(/\s+/)), new Set(tag.toLowerCase().split(/\s+/)));
}

// "Related Research" (comparisons) and "Latest Intelligence Signals" —
// SEO roadmap, "each sector page should become a topical authority hub."
// Both reuse endpoints already built for the company page's own Compare-
// With section and the Live Intelligence signal pipeline — no new backend
// surface, just a sector-scoped view of real, already-persisted content.
async function fetchSectorComparisons(sectorName: string): Promise<RelatedArticle[]> {
  try {
    const res = await fetch(`${API}/api/insights/comparisons?sector=${encodeURIComponent(sectorName)}&limit=6`, { next: { revalidate: 900 } });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.items) ? data.items : [];
  } catch {
    return [];
  }
}

// live_signal articles don't have their own sector-filter endpoint yet
// (only anomaly-type signals carry a real `sector` field on
// sectors_affected — policy/theme/historical signals are topic-scoped,
// not sector-scoped) — filtered here in the Server Component rather than
// adding a narrow one-off API param for a single caller.
async function fetchSectorSignals(sectorName: string): Promise<RelatedArticle[]> {
  try {
    const res = await fetch(`${API}/api/insights/?article_type=live_signal&limit=50&sort_by=newest`, { next: { revalidate: 300 } });
    if (!res.ok) return [];
    const data = await res.json();
    const items = Array.isArray(data.items) ? data.items : [];
    return items.filter((a: any) =>
      (a.sectors_affected ?? []).some((s: any) => s?.name && sectorMatches(sectorName, s.name))
    ).slice(0, 6);
  } catch {
    return [];
  }
}

async function fetchSectorArticles(sectorName: string): Promise<RelatedArticle[]> {
  try {
    const res = await fetch(`${API}/api/insights/?limit=60&sort_by=newest`, { next: { revalidate: 900 } });
    if (!res.ok) return [];
    const data = await res.json();
    const items = Array.isArray(data.items) ? data.items : [];
    return items.filter((a: any) =>
      a.article_type !== "comparison_intelligence" && a.article_type !== "live_signal" &&
      (a.sectors_affected ?? []).some((s: any) => s?.name && sectorMatches(sectorName, s.name))
    ).slice(0, 6);
  } catch {
    return [];
  }
}

interface SectorScoreCompany { symbol: string; score: number | null; top_contributors: { reason: string | null }[] }

// AI Company Intelligence Score (company_score_engine.py) — real per-company
// ranking + reason, previously nowhere on this page: "Companies in {sector}"
// was an unranked flat grid of just price/change. Additive only — stocks
// with no real signal yet keep their original position, not hidden.
async function fetchSectorScores(sectorName: string): Promise<Map<string, { score: number; reason: string | null }>> {
  try {
    const res = await fetch(`${API}/api/company-scores/sector/${encodeURIComponent(sectorName)}?limit=50`, { next: { revalidate: 900 } });
    if (!res.ok) return new Map();
    const data = await res.json();
    const companies: SectorScoreCompany[] = Array.isArray(data.companies) ? data.companies : [];
    const map = new Map<string, { score: number; reason: string | null }>();
    for (const c of companies) {
      if (c.score == null) continue;
      map.set(c.symbol, { score: c.score, reason: c.top_contributors?.[0]?.reason ?? null });
    }
    return map;
  } catch {
    return new Map();
  }
}

export async function generateMetadata({ params }: { params: Promise<{ sector: string }> }): Promise<Metadata> {
  const { sector } = await params;
  const url = `${SITE}/sectors/${sector}`;
  const d = await fetchSector(sector);
  if (!d) return { title: "Sector Not Found", alternates: { canonical: url } };
  const desc = `${d.name} sector on NSE${d.value ? ` — live performance (${d.value})` : ""}, constituent stocks, and AI-driven opportunity and event analysis on MarketRipple.`;
  return {
    title: `${d.name} Sector — AI Analysis`,
    description: desc,
    openGraph: { type: "website", title: `${d.name} Sector — MarketRipple`, description: desc, url, siteName: "MarketRipple" },
    twitter: { card: "summary_large_image", title: `${d.name} Sector`, description: desc },
    alternates: { canonical: url },
  };
}

export default async function SectorPage({ params }: { params: Promise<{ sector: string }> }) {
  const { sector } = await params;
  const d = await fetchSector(sector);
  if (!d) notFound();

  const [comparisons, signals, articles, scores] = await Promise.all([
    fetchSectorComparisons(d.name),
    fetchSectorSignals(d.name),
    fetchSectorArticles(d.name),
    fetchSectorScores(d.name),
  ]);

  // Rank by real AI score where available; stocks with no signal yet keep
  // their original relative order, appended after the ranked ones.
  const rankedStocks = [...d.stocks].sort((a, b) => {
    const sa = scores.get(a.symbol)?.score;
    const sb = scores.get(b.symbol)?.score;
    if (sa == null && sb == null) return 0;
    if (sa == null) return 1;
    if (sb == null) return -1;
    return sb - sa;
  });

  const url = `${SITE}/sectors/${sector}`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: `${d.name} Sector — MarketRipple`,
    url,
    breadcrumb: {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "MarketRipple", item: SITE },
        { "@type": "ListItem", position: 2, name: "Sectors", item: `${SITE}/sectors` },
        { "@type": "ListItem", position: 3, name: `${d.name} Sector`, item: url },
      ],
    },
    mainEntity: {
      "@type": "ItemList",
      itemListElement: rankedStocks.map((s, i) => ({
        "@type": "ListItem", position: i + 1, name: s.name,
        url: `${SITE}/companies/${s.symbol}`,
      })),
    },
  };

  return (
    <main className="mx-auto max-w-[1400px] space-y-6 py-6 pb-16">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(jsonLd) }} />

      <nav className="flex items-center gap-2 text-[12px] text-text-muted">
        <Link href="/sectors" className="hover:text-text-secondary transition">Sectors</Link>
        <span>/</span>
        <span className="text-text-secondary">{d.name}</span>
      </nav>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-sky-400">Sector Intelligence</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-text-primary">{d.name} Sector</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Live NSE {d.name} sector performance, constituent stocks, and AI-driven opportunity and event analysis.
          </p>
        </div>
        {d.value ? (
          <div className={`rounded-2xl border px-5 py-3 ${d.positive ? "bg-emerald-500/10 border-emerald-500/20" : "bg-rose-500/10 border-rose-500/20"}`}>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">Today</p>
            <p className={`mt-1 text-2xl font-black ${d.positive ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300"}`}>{d.value}</p>
          </div>
        ) : (
          <div className="rounded-2xl border border-surface-border/10 bg-text-primary/[0.03] px-5 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">Companies</p>
            <p className="mt-1 text-2xl font-black text-text-primary">{d.stocks.length}</p>
          </div>
        )}
      </div>

      {/* Constituent stocks — ranked by real AI Company Intelligence Score
          where available (company_score_engine.py); stocks with no signal
          yet keep price/change only, appended after the ranked ones. */}
      {rankedStocks.length > 0 && (
        <section>
          <h2 className="mb-3 text-[15px] font-semibold text-text-primary">Companies in {d.name}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {rankedStocks.map((s, i) => {
              const ranked = scores.get(s.symbol);
              return (
                <Link key={s.symbol} href={`/companies/${s.symbol}`}
                  className="group flex flex-col gap-2 rounded-[16px] border border-surface-border/8 bg-surface-card px-4 py-3 transition hover:border-surface-border/15">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {ranked && <span className="text-[10px] font-bold text-text-muted">#{i + 1}</span>}
                      <div>
                        <p className="text-[13px] font-bold text-text-primary">{s.symbol}</p>
                        <p className="text-[11px] text-text-muted">{s.price !== "—" ? `₹${s.price.replace("₹", "")}` : "—"}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {ranked && (
                        <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-600 dark:text-emerald-300">
                          {Math.round(ranked.score)}
                        </span>
                      )}
                      <span className={`text-[12px] font-semibold tabular-nums ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.change}</span>
                    </div>
                  </div>
                  {ranked?.reason && (
                    <p className="line-clamp-1 text-[10.5px] text-text-muted">{ranked.reason}</p>
                  )}
                </Link>
              );
            })}
          </div>
        </section>
      )}

      {/* Opportunities + Events */}
      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-[15px] font-semibold text-text-primary">Opportunities in {d.name}</h2>
          {d.opportunities.length > 0 ? (
            <div className="space-y-2">
              {d.opportunities.map((o) => (
                <Link key={o.id} href={`/opportunity-radar/${o.id}`}
                  className="flex items-center justify-between rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] px-4 py-3 transition hover:border-emerald-500/25">
                  <p className="text-[13px] text-text-primary line-clamp-1">{o.title}</p>
                  {o.opportunity_score != null && (
                    <span className="shrink-0 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-bold text-emerald-600 dark:text-emerald-300">{Math.round(o.opportunity_score)}</span>
                  )}
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-[12px] text-text-muted">No sector-specific opportunities identified right now.</p>
          )}
        </section>
        <section>
          <h2 className="mb-3 text-[15px] font-semibold text-text-primary">Recent Events Affecting {d.name}</h2>
          {d.events.length > 0 ? (
            <div className="space-y-2">
              {d.events.map((e) => (
                <Link key={e.id} href={`/events/${e.slug || e.id}`}
                  className="flex items-center justify-between rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] px-4 py-3 transition hover:border-violet-500/25">
                  <p className="text-[13px] text-text-primary line-clamp-1">{e.title}</p>
                  {e.impact_score != null && (
                    <span className="shrink-0 rounded-full bg-violet-500/10 px-2 py-0.5 text-[11px] font-bold text-violet-600 dark:text-violet-300">{Math.round(e.impact_score)}</span>
                  )}
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-[12px] text-text-muted">No recent events specifically affecting {d.name} right now.</p>
          )}
        </section>
      </div>

      {/* Sector authority hub — real Related Research (comparisons),
          Latest Intelligence Signals, and Recent AI Articles, each scoped
          to this sector via its own real sectors_affected tag. Sections
          that have nothing real to show simply don't render — no
          "coming soon" filler. */}
      <div className="grid gap-6 lg:grid-cols-3">
        {comparisons.length > 0 && (
          <section>
            <h2 className="mb-3 text-[15px] font-semibold text-text-primary">Related Research</h2>
            <div className="space-y-2">
              {comparisons.map((c) => (
                <Link key={c.slug} href={`/research/${c.slug}`}
                  className="flex items-center justify-between rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] px-4 py-3 transition hover:border-sky-500/25">
                  <p className="text-[13px] text-text-primary line-clamp-1">{c.companies_affected?.map(x => x.symbol).join(" vs ")}</p>
                  <span className="shrink-0 text-[11px] font-semibold text-sky-400">Compare →</span>
                </Link>
              ))}
            </div>
          </section>
        )}

        {signals.length > 0 && (
          <section>
            <h2 className="mb-3 text-[15px] font-semibold text-text-primary">Latest Intelligence Signals</h2>
            <div className="space-y-2">
              {signals.map((s) => (
                <Link key={s.slug} href={`/intelligence/signal/${s.slug}`}
                  className="flex items-center justify-between rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] px-4 py-3 transition hover:border-amber-500/25">
                  <p className="text-[13px] text-text-primary line-clamp-1">{s.headline}</p>
                </Link>
              ))}
            </div>
          </section>
        )}

        {articles.length > 0 && (
          <section>
            <h2 className="mb-3 text-[15px] font-semibold text-text-primary">Recent AI Articles</h2>
            <div className="space-y-2">
              {articles.map((a) => (
                <Link key={a.slug} href={`/newsroom/article/${a.slug}`}
                  className="flex items-center justify-between rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] px-4 py-3 transition hover:border-emerald-500/25">
                  <p className="text-[13px] text-text-primary line-clamp-1">{a.headline}</p>
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>

      <div className="rounded-[16px] border border-violet-500/20 bg-violet-500/[0.04] px-5 py-4">
        <p className="text-[13px] text-text-secondary">
          Want a deeper read on {d.name}?{" "}
          <AskAICta query={`What is the outlook for the ${d.name} sector?`} source="sector_page" />
        </p>
      </div>
    </main>
  );
}
