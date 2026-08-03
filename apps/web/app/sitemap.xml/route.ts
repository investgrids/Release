import { API_BASE_URL as API } from "@/lib/api";
import { GLOSSARY } from "@/lib/glossary-data";
import { GUIDES } from "@/lib/guides-data";
import { ARTICLES } from "@/lib/articles-data";
import { getSectorsWithCounts } from "@/lib/bestStocks";
import { buildSitemapXml, type SitemapEntry } from "@/lib/xmlSitemap";

/**
 * Custom Route Handler, not the app/sitemap.ts MetadataRoute.Sitemap
 * convention — that built-in convention does not XML-escape URL segments,
 * which broke Google Search Console validation on any ticker containing
 * "&" (M&M, M&MFIN — see xmlSitemap.ts's docstring for the exact error).
 * All data-fetching logic below is unchanged from the previous sitemap.ts;
 * only the final serialization step changed, from Next's own (unescaped)
 * builder to buildSitemapXml(), which escapes every text value.
 */

export const revalidate = 3600;

const base  = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://www.marketripple.in";
const now   = new Date().toISOString();

async function safeJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), 8000);
    const res = await fetch(url, { next: { revalidate: 3600 }, signal: ac.signal });
    clearTimeout(timer);
    if (!res.ok) return fallback;
    return res.json() as Promise<T>;
  } catch { return fallback; }
}

async function buildEntries(): Promise<SitemapEntry[]> {
  const staticRoutes: SitemapEntry[] = [
    { url: base,                                 lastModified: now, changeFrequency: "daily",  priority: 1.0 },
    { url: `${base}/market-intelligence`,        lastModified: now, changeFrequency: "hourly", priority: 0.95 },
    { url: `${base}/events`,                     lastModified: now, changeFrequency: "hourly", priority: 0.95 },
    { url: `${base}/companies`,                  lastModified: now, changeFrequency: "daily",  priority: 0.9 },
    { url: `${base}/news`,                       lastModified: now, changeFrequency: "hourly", priority: 0.85 },
    // Real destination, not /themes — that path 301-redirects here (see
    // next.config.ts's "AI Newsroom consolidation" redirects). A sitemap
    // listing a redirecting URL is a confirmed Search Console warning
    // ("Page with redirect") and wastes crawl budget every cycle.
    { url: `${base}/newsroom/themes`,            lastModified: now, changeFrequency: "daily",  priority: 0.85 },
    { url: `${base}/opportunity-radar`,          lastModified: now, changeFrequency: "daily",  priority: 0.85 },
    { url: `${base}/ripple`,                     lastModified: now, changeFrequency: "daily",  priority: 0.8 },
    { url: `${base}/ai-search`,                  lastModified: now, changeFrequency: "daily",  priority: 0.8 },
    // Real destination, not /research — that path now redirects to this
    // hub (see research/page.tsx), same "don't list a redirecting URL"
    // fix already applied to /themes, /insights, and bare /insights above.
    { url: `${base}/research/comparisons`,       lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${base}/about`,                      lastModified: now, changeFrequency: "monthly",priority: 0.5 },
    { url: `${base}/why-marketripple`,           lastModified: now, changeFrequency: "monthly",priority: 0.5 },
    { url: `${base}/how-it-works`,               lastModified: now, changeFrequency: "monthly",priority: 0.5 },
    { url: `${base}/how-marketripple-thinks`,    lastModified: now, changeFrequency: "monthly",priority: 0.5 },
    { url: `${base}/ai-methodology`,             lastModified: now, changeFrequency: "monthly",priority: 0.5 },
    { url: `${base}/data-sources`,               lastModified: now, changeFrequency: "monthly",priority: 0.4 },
    { url: `${base}/faq`,                        lastModified: now, changeFrequency: "monthly",priority: 0.4 },
    { url: `${base}/whats-new`,                  lastModified: now, changeFrequency: "weekly", priority: 0.4 },
    { url: `${base}/legal`,                      lastModified: now, changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/contact`,                    lastModified: now, changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/calendar`,                   lastModified: now, changeFrequency: "daily",  priority: 0.5 },
    // Real destination, not /insights — that path 301-redirects to
    // /newsroom (same "AI Newsroom consolidation" redirect block already
    // fixed for /themes and /insights/{slug} — this bare entry was missed
    // in that earlier pass, found while adding /research below).
    { url: `${base}/newsroom`,                   lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    // Historical Memory hub — real dated market-pattern data
    // (historical_memory_service.py, 52 events) previously powering only a
    // sidebar widget with no indexable URL of its own.
    { url: `${base}/historical`,                 lastModified: now, changeFrequency: "weekly", priority: 0.75 },
    // Best Stocks hub — real, opportunity-scored rankings by sector (pure
    // presentation layer over the existing Opportunity Radar data).
    { url: `${base}/best-stocks`,                lastModified: now, changeFrequency: "daily",  priority: 0.8 },
    // Commodities — real live metals/energy prices (commodities.py), fixed
    // 8-item set (4 metals + 4 energy) defined in the backend itself, so
    // listed directly rather than fetched.
    { url: `${base}/commodities`,                lastModified: now, changeFrequency: "hourly", priority: 0.75 },
    ...["gold", "silver", "copper", "platinum", "brent", "wti", "natgas", "petrol"].map(id => ({
      url: `${base}/commodities/${id}`,
      lastModified: now,
      changeFrequency: "hourly" as const,
      priority: 0.7,
    })),
    { url: `${base}/learn`,                      lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${base}/learn/glossary`,             lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${base}/learn/guides`,               lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${base}/learn/articles`,             lastModified: now, changeFrequency: "weekly", priority: 0.6 },
  ];

  const glossaryRoutes: SitemapEntry[] = GLOSSARY.map(t => ({
    url: `${base}/learn/glossary/${t.slug}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.55,
  }));

  const guideRoutes: SitemapEntry[] = GUIDES.map(g => ({
    url: `${base}/learn/guides/${g.slug}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.55,
  }));

  const articleRoutes: SitemapEntry[] = ARTICLES.map(a => ({
    url: `${base}/learn/articles/${a.slug}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.6,
  }));

  // Dynamic routes — best-effort; graceful fallback to static-only on error.
  // Each endpoint's real response shape and query-param limits (verified live,
  // not assumed — /api/events caps `limit` at 100, /api/companies caps
  // `page_size` at 60, both silently 422 and fall back to [] if exceeded):
  //   /api/events/  -> bare array of events, keyed by `id`
  //   /api/radar/   -> { items: [...] }; /opportunity-radar/[id] uses the numeric `id`
  //   /api/companies/ -> { companies: [...], total_pages }, keyed by `symbol`
  //   /api/news/    -> bare array of news items, keyed by `id`
  // Deliberately NOT fetching /api/stories/ — the Story model is confirmed
  // dead (seed data only, see next.config.ts's redirect comment) and
  // /stories/:slug 301-redirects to /newsroom/themes for every id, so
  // submitting these URLs in the sitemap only produced Search Console
  // "Page with redirect" warnings for pages that never had real content.
  const [events, radar, companiesPage1, news, insights, sectors, research, historical] = await Promise.all([
    safeJson<Array<{ id: string; date?: string }>>(`${API}/api/events/?limit=100`, []),
    safeJson<{ items?: Array<{ id: number }> }>(`${API}/api/radar/?page_size=100`, {}),
    safeJson<{ companies?: Array<{ symbol: string }>; total_pages?: number }>(`${API}/api/companies/?page_size=60&page=1`, {}),
    safeJson<Array<{ id: string; published_at?: string }>>(`${API}/api/news/?limit=100`, []),
    safeJson<{ items?: Array<{ slug: string; article_type?: string; canonical_url?: string; last_updated?: string; published_at?: string; hero_image_url?: string | null }> }>(`${API}/api/insights/?limit=100`, {}),
    safeJson<Array<{ id: string }>>(`${API}/api/sectors/`, []),
    // SEO Phase 2, §2.2 — comparison research pages.
    safeJson<{ items?: Array<{ slug: string; last_updated?: string; published_at?: string }> }>(`${API}/api/insights/?article_type=comparison_intelligence&limit=100`, {}),
    // Historical Memory pages — real dated events, ids are already
    // human-readable slugs (e.g. "rbi-rate-pause-2023"), not opaque UUIDs.
    safeJson<{ events?: Array<{ id: string; nifty_1w?: number | null; opportunity_score?: number | null }> }>(`${API}/api/historical/all?limit=200`, {}),
  ]);

  // Companies list is paginated server-side (60/page) — fetch the remaining
  // pages in parallel rather than truncating to just the first 60 of 200+.
  const extraCompanyPages = await Promise.all(
    Array.from({ length: Math.max(0, (companiesPage1.total_pages ?? 1) - 1) }, (_, i) =>
      safeJson<{ companies?: Array<{ symbol: string }> }>(`${API}/api/companies/?page_size=60&page=${i + 2}`, {})
    )
  );
  const companies = {
    companies: [...(companiesPage1.companies ?? []), ...extraCompanyPages.flatMap(p => p.companies ?? [])],
  };

  const eventRoutes: SitemapEntry[] = (Array.isArray(events) ? events : []).map(e => ({
    url: `${base}/events/${e.id}`,
    lastModified: e.date ?? now,
    changeFrequency: "weekly",
    priority: 0.75,
  }));

  const radarRoutes: SitemapEntry[] = (radar.items ?? []).map(r => ({
    url: `${base}/opportunity-radar/${r.id}`,
    lastModified: now,
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  // Ticker symbols routinely contain "&" (M&M, M&MFIN) — this is exactly
  // the field that broke Search Console validation. buildSitemapXml()
  // escapes it at serialization time; no special-casing needed here.
  const companyRoutes: SitemapEntry[] = (companies.companies ?? []).map(c => ({
    url: `${base}/companies/${c.symbol}`,
    lastModified: now,
    changeFrequency: "daily",
    priority: 0.7,
  }));

  const newsRoutes: SitemapEntry[] = (Array.isArray(news) ? news : []).map(n => ({
    url: `${base}/news/${n.id}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.55,
  }));

  // Real destination, not /insights/{slug} — that path also 301-redirects
  // (to /newsroom/article/{slug}, same "AI Newsroom consolidation" redirect
  // block as /themes above). Same bug, same fix.
  //
  // `images` (SEO Phase 3, §3.4) — real AI-generated hero images already
  // exist per article (a genuine backend pipeline, not a placeholder);
  // buildSitemapXml() emits a real <image:image> entry per image URL, which
  // is all Google's image sitemap extension needs.
  // comparison_intelligence is excluded here — it's already submitted via
  // researchRoutes below at its real /research/{slug} destination; including
  // it again at /newsroom/article/{slug} would submit two URLs for the same
  // article. For every other type, prefer the article's own real
  // canonical_url (set once at publish time, e.g. live_signal points at
  // /intelligence/signal/{slug}) over guessing the path from article_type —
  // this was previously hardcoded to /newsroom/article/{slug} for every
  // type, which put a non-canonical URL in the sitemap for live_signal
  // articles (confirmed live: their own canonical tag disagreed with this).
  const insightRoutes: SitemapEntry[] = (insights.items ?? [])
    .filter(a => a.article_type !== "comparison_intelligence")
    .map(a => ({
      url: a.canonical_url || `${base}/newsroom/article/${a.slug}`,
      lastModified: a.last_updated ?? a.published_at ?? now,
      changeFrequency: "weekly" as const,
      priority: 0.85,
      ...(a.hero_image_url ? { images: [`${API}${a.hero_image_url}`] } : {}),
    }));

  // SEO Phase 2 §2.1 — real sector landing pages (/sectors/[sector]),
  // sourced from the same SectorData rows the /sectors overview already
  // lists, each backed by real constituent stocks + matched opportunities/
  // events (see sectors.py's /intelligence endpoint).
  const sectorRoutes: SitemapEntry[] = (Array.isArray(sectors) ? sectors : []).map(s => ({
    url: `${base}/sectors/${s.id}`,
    lastModified: now,
    changeFrequency: "daily",
    priority: 0.75,
  }));

  // Sectors.py's /intelligence endpoint also serves 4 sectors with real
  // constituent stocks + opportunity/event data but no SectorData momentum
  // row (Defence, Chemicals, Telecom, Finance) — not present in the
  // /api/sectors/ list above, so listed explicitly here rather than
  // silently missing from the sitemap.
  const extraSectorRoutes: SitemapEntry[] = ["defence", "chemicals", "telecom", "finance"].map(id => ({
    url: `${base}/sectors/${id}`,
    lastModified: now,
    changeFrequency: "daily",
    priority: 0.7,
  }));

  // Some stored events are thin, auto-captured recent items with no real
  // Nifty-reaction or scoring data yet (verified live: a "General"-category
  // event with nifty_1w/1m all null and no winners/losers) — the page still
  // renders honestly for these (no fabricated numbers), but submitting a
  // near-empty page to Google is exactly the thin-content risk the SEO
  // audit flagged. Only events with real reaction/scoring data go in the
  // sitemap; the hub page still lists everything for browsing.
  // Best Stocks — reuses the same thin-content threshold (>=3 real
  // companies) already applied inside getSectorsWithCounts().
  const bestStocksSectors = await getSectorsWithCounts();
  const bestStocksRoutes: SitemapEntry[] = bestStocksSectors.map(s => ({
    url: `${base}/best-stocks/${s.slug}`,
    lastModified: now,
    changeFrequency: "daily",
    priority: 0.75,
  }));

  const historicalRoutes: SitemapEntry[] = (historical.events ?? [])
    .filter(e => e.nifty_1w != null || e.opportunity_score != null)
    .map(e => ({
      url: `${base}/historical/${e.id}`,
      lastModified: now,
      // Real dated pattern, not today's news — long organic life, doesn't
      // need frequent recrawl.
      changeFrequency: "monthly" as const,
      priority: 0.65,
    }));

  // SEO Phase 2, §2.2 — comparison research pages, generated (with a real
  // retry+quality gate) from the live AI Search decision engine — see
  // comparison_publisher.py.
  const researchRoutes: SitemapEntry[] = (research.items ?? []).map(a => ({
    url: `${base}/research/${a.slug}`,
    lastModified: a.last_updated ?? a.published_at ?? now,
    changeFrequency: "weekly",
    priority: 0.8,
  }));

  return [...staticRoutes, ...eventRoutes, ...radarRoutes, ...companyRoutes, ...newsRoutes, ...insightRoutes, ...sectorRoutes, ...extraSectorRoutes, ...historicalRoutes, ...bestStocksRoutes, ...researchRoutes, ...glossaryRoutes, ...guideRoutes, ...articleRoutes];
}

export async function GET() {
  const entries = await buildEntries();
  const xml = buildSitemapXml(entries);
  return new Response(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600, s-maxage=3600",
    },
  });
}
