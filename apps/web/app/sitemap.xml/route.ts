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

// SEO fix: eventRoutes/rippleRoutes used to fall back to the raw internal id
// (`e.slug || e.id`) whenever slug was missing — which happens for a real,
// narrow window on every freshly-ingested event (the DB row is written
// before `_make_unique_slug` finishes assigning its slug; see
// event_pipeline.py). Combined with this route's 1-hour fetch cache, that
// let a raw "nse-"/"bse-" URL get baked into a served sitemap. Rather than
// fall back to the id, skip the entry entirely until it has a real slug —
// it's still crawlable via internal links, and reappears in the sitemap on
// the next revalidate once the slug is assigned.
function hasCleanSlug(slug: string | null | undefined): slug is string {
  return !!slug && !/^(nse-|bse-)/i.test(slug);
}

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
    //
    // SEO P1-P2, 2026-08-24 — /newsroom/themes itself used to be listed
    // here too, at the same priority. It's a confirmed duplicate of this
    // exact page (same /api/radar/ data) and was just set to
    // robots: { index: false, follow: true } with its canonical pointed
    // here — submitting a noindex page in the sitemap is a real Search
    // Console "Excluded by 'noindex' tag" warning, so it's removed rather
    // than listed twice under two different URLs.
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
    { url: `${base}/faq`,                        lastModified: now, changeFrequency: "monthly",priority: 0.4 },
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
    // Best Stocks (real, opportunity-scored rankings by sector) is now
    // reached at /companies?tab=best-stocks — the bare /companies entry
    // above (priority 0.9) is the one indexable URL for this whole hub,
    // same "don't list a redirecting URL" reasoning as /newsroom above.
    // /best-stocks itself 301-redirects to that canonical view.
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
  //   /api/radar/   -> { items: [...] } — V1 items are keyed by numeric
  //                     `id` (/opportunity-radar/[id]); post-promotion
  //                     (V2-B, settings.opportunity_read_source="v2") the
  //                     same endpoint returns V2 items instead — string
  //                     uuid `id` + a separate `slug`
  //                     (/opportunity-radar/[slug]). Never both at once —
  //                     the backend itself is the single source of truth
  //                     for which shape is "live" right now.
  //   /api/companies/ -> { companies: [...], total_pages }, keyed by `symbol`
  // Deliberately NOT fetching /api/stories/ — the Story model is confirmed
  // dead (seed data only, see next.config.ts's redirect comment) and
  // /stories/:slug 301-redirects to /newsroom/themes for every id, so
  // submitting these URLs in the sitemap only produced Search Console
  // "Page with redirect" warnings for pages that never had real content.
  //
  // Deliberately NOT fetching /api/news/ (Sitemap Truth Audit, 2026-08-24) —
  // /news/{id} is backed by an in-memory RSS cache (news_fetcher.py), not a
  // database table. Submitting it here meant this sitemap was, on every
  // hourly regeneration, actively asking Google to index URLs guaranteed to
  // eventually 404 with no recovery path once they rotate out of the cache —
  // confirmed live: a real page that earned ~20k real impressions
  // (live-d0a558cbe3ba) had already 404'd on the backend while Vercel's ISR
  // cache masked it. Per the Indexability Contract, ephemeral/cache-only
  // content is never submitted. Route now sets `robots: {index:false}`
  // (see app/news/[id]/layout.tsx) as the durable backstop.
  const [events, ripple, radar, companiesPage1, insights, sectors, research, historical] = await Promise.all([
    safeJson<Array<{ id: string; slug?: string; date?: string; indexable?: boolean }>>(`${API}/api/events/?limit=100`, []),
    // Ripple pages exist for the same "featured" high-impact events the
    // Ripple hub itself surfaces — not blindly mirroring every event route,
    // since not every event has a ripple analysis worth indexing.
    safeJson<Array<{ id: string; slug?: string; event_date?: string }>>(`${API}/api/ripple/featured?limit=20`, []),
    safeJson<{ items?: Array<{ id: number | string; slug?: string; updated_at?: string }> }>(`${API}/api/radar/?page_size=100`, {}),
    // Final re-audit fix (2026-08-25) — this route only needs symbol/name
    // for URL generation, never live price. `live` defaults true on
    // /api/companies/, and _fetch_prices() does a real yfinance batch
    // call per page inside its own ThreadPoolExecutor(max_workers=1);
    // firing that concurrently across every page (see extraCompanyPages
    // below) triggered real Yahoo Finance throttling, most pages missing
    // the route's 8s abort timeout and silently falling back to `{}`.
    // Reproduced deterministically: with live=true, 11/13 concurrent page
    // fetches timed out (only 180 of 824 real companies collected,
    // matching the live sitemap's own observed truncation exactly); with
    // live=false, all 13 succeed in ~1s and all 824 are collected. The
    // Tier A qualification pipeline itself was never the problem — see
    // artifacts/company_redesign_final_reaudit.md §5/§12 and its
    // follow-up reconciliation.
    safeJson<{ companies?: Array<{ symbol: string }>; total_pages?: number }>(`${API}/api/companies/?page_size=60&page=1&live=false`, {}),
    safeJson<{ items?: Array<{ slug: string; article_type?: string; canonical_url?: string; last_updated?: string; published_at?: string; hero_image_url?: string | null }> }>(`${API}/api/insights/?limit=100`, {}),
    safeJson<Array<{ id: string }>>(`${API}/api/sectors/`, []),
    // SEO Phase 2, §2.2 — comparison research pages.
    safeJson<{ items?: Array<{ slug: string; last_updated?: string; published_at?: string }> }>(`${API}/api/insights/?article_type=comparison_intelligence&limit=100`, {}),
    // Historical Memory pages — real dated events, ids are already
    // human-readable slugs (e.g. "rbi-rate-pause-2023"), not opaque UUIDs.
    safeJson<{ events?: Array<{ id: string; nifty_1w?: number | null; opportunity_score?: number | null; has_winners?: boolean }> }>(`${API}/api/historical/all?limit=200`, {}),
  ]);

  // Companies list is paginated server-side (60/page) — fetch the remaining
  // pages in parallel rather than truncating to just the first 60 of 200+.
  const extraCompanyPages = await Promise.all(
    Array.from({ length: Math.max(0, (companiesPage1.total_pages ?? 1) - 1) }, (_, i) =>
      safeJson<{ companies?: Array<{ symbol: string }> }>(`${API}/api/companies/?page_size=60&page=${i + 2}&live=false`, {})
    )
  );
  const companies = {
    companies: [...(companiesPage1.companies ?? []), ...extraCompanyPages.flatMap(p => p.companies ?? [])],
  };

  const eventRoutes: SitemapEntry[] = (Array.isArray(events) ? events : [])
    // Phase 15 (2026-08 audit) — indexability threshold: only events with
    // real evidence of importance (Critical/High triage priority, or a
    // genuine extracted macro data release) are sitemap-eligible. Absence
    // of the field (an older cached response, or the flag defaulting
    // false) is treated as NOT indexable — the safe default, not `!==
    // false` which would wrongly include a genuinely-false flag.
    .filter(e => hasCleanSlug(e.slug) && e.indexable === true)
    .map(e => ({
      url: `${base}/events/${e.slug}`,
      lastModified: e.date ?? now,
      changeFrequency: "weekly",
      priority: 0.75,
    }));

  const rippleRoutes: SitemapEntry[] = (Array.isArray(ripple) ? ripple : [])
    .filter(e => hasCleanSlug(e.slug))
    .map(e => ({
      url: `${base}/ripple/${e.slug}`,
      lastModified: e.event_date ?? now,
      changeFrequency: "weekly",
      priority: 0.7,
    }));

  // V2-B, 2026-08-24 — shape-detected per item, not per a global flag this
  // route would have to fetch separately: typeof r.id === "number" is V1
  // (numeric primary key, real today), a string id is V2's uuid (real
  // post-promotion) and MUST use the real slug, never the uuid itself, or
  // the id-only V2 lookup branch (radar.py) would 404 every one of these.
  const radarRoutes: SitemapEntry[] = (radar.items ?? [])
    .filter(r => typeof r.id === "number" || hasCleanSlug(r.slug))
    .map(r => ({
      url: `${base}/opportunity-radar/${typeof r.id === "number" ? r.id : r.slug}`,
      lastModified: r.updated_at ?? now,
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

  // SEO P1-P2, 2026-08-24 — now matches the detail page's own
  // isSubstantive() gate exactly (nifty_1w || opportunity_score ||
  // has_winners), closing the Sitemap Truth Audit's confirmed (if
  // dormant) gate mismatch.
  const historicalRoutes: SitemapEntry[] = (historical.events ?? [])
    .filter(e => e.nifty_1w != null || e.opportunity_score != null || e.has_winners)
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

  return [...staticRoutes, ...eventRoutes, ...rippleRoutes, ...radarRoutes, ...companyRoutes, ...insightRoutes, ...sectorRoutes, ...extraSectorRoutes, ...historicalRoutes, ...bestStocksRoutes, ...researchRoutes, ...glossaryRoutes, ...guideRoutes, ...articleRoutes];
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
