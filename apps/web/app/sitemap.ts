import type { MetadataRoute } from "next";
import { API_BASE_URL as API } from "@/lib/api";
import { GLOSSARY } from "@/lib/glossary-data";
import { GUIDES } from "@/lib/guides-data";
import { ARTICLES } from "@/lib/articles-data";

const base  = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://marketripple.in";
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

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticRoutes: MetadataRoute.Sitemap = [
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
    { url: `${base}/learn`,                      lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${base}/learn/glossary`,             lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${base}/learn/guides`,               lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${base}/learn/articles`,             lastModified: now, changeFrequency: "weekly", priority: 0.6 },
  ];

  const glossaryRoutes: MetadataRoute.Sitemap = GLOSSARY.map(t => ({
    url: `${base}/learn/glossary/${t.slug}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.55,
  }));

  const guideRoutes: MetadataRoute.Sitemap = GUIDES.map(g => ({
    url: `${base}/learn/guides/${g.slug}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.55,
  }));

  const articleRoutes: MetadataRoute.Sitemap = ARTICLES.map(a => ({
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
  const [events, radar, companiesPage1, news, insights, sectors, research] = await Promise.all([
    safeJson<Array<{ id: string; date?: string }>>(`${API}/api/events/?limit=100`, []),
    safeJson<{ items?: Array<{ id: number }> }>(`${API}/api/radar/?page_size=100`, {}),
    safeJson<{ companies?: Array<{ symbol: string }>; total_pages?: number }>(`${API}/api/companies/?page_size=60&page=1`, {}),
    safeJson<Array<{ id: string; published_at?: string }>>(`${API}/api/news/?limit=100`, []),
    safeJson<{ items?: Array<{ slug: string; last_updated?: string; published_at?: string; hero_image_url?: string | null }> }>(`${API}/api/insights/?limit=100`, {}),
    safeJson<Array<{ id: string }>>(`${API}/api/sectors/`, []),
    // SEO Phase 2, §2.2 — comparison research pages.
    safeJson<{ items?: Array<{ slug: string; last_updated?: string; published_at?: string }> }>(`${API}/api/insights/?article_type=comparison_intelligence&limit=100`, {}),
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

  const eventRoutes: MetadataRoute.Sitemap = (Array.isArray(events) ? events : []).map(e => ({
    url: `${base}/events/${e.id}`,
    lastModified: e.date ?? now,
    changeFrequency: "weekly",
    priority: 0.75,
  }));

  const radarRoutes: MetadataRoute.Sitemap = (radar.items ?? []).map(r => ({
    url: `${base}/opportunity-radar/${r.id}`,
    lastModified: now,
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  const companyRoutes: MetadataRoute.Sitemap = (companies.companies ?? []).map(c => ({
    url: `${base}/companies/${c.symbol}`,
    lastModified: now,
    changeFrequency: "daily",
    priority: 0.7,
  }));

  const newsRoutes: MetadataRoute.Sitemap = (Array.isArray(news) ? news : []).map(n => ({
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
  // Next.js's sitemap type accepts a plain `images: string[]` per entry,
  // which is all Google's image sitemap extension needs — no separate
  // sitemap file required. Served from the backend's own domain
  // (/api/media/*), which is fine for an image sitemap — it only needs a
  // publicly reachable absolute URL, not same-origin.
  const insightRoutes: MetadataRoute.Sitemap = (insights.items ?? []).map(a => ({
    url: `${base}/newsroom/article/${a.slug}`,
    lastModified: a.last_updated ?? a.published_at ?? now,
    changeFrequency: "weekly",
    priority: 0.85,
    ...(a.hero_image_url ? { images: [`${API}${a.hero_image_url}`] } : {}),
  }));

  // SEO Phase 2 §2.1 — real sector landing pages (/sectors/[sector]),
  // sourced from the same SectorData rows the /sectors overview already
  // lists, each backed by real constituent stocks + matched opportunities/
  // events (see sectors.py's /intelligence endpoint).
  const sectorRoutes: MetadataRoute.Sitemap = (Array.isArray(sectors) ? sectors : []).map(s => ({
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
  const extraSectorRoutes: MetadataRoute.Sitemap = ["defence", "chemicals", "telecom", "finance"].map(id => ({
    url: `${base}/sectors/${id}`,
    lastModified: now,
    changeFrequency: "daily",
    priority: 0.7,
  }));

  // SEO Phase 2, §2.2 — comparison research pages, generated (with a real
  // retry+quality gate) from the live AI Search decision engine — see
  // comparison_publisher.py.
  const researchRoutes: MetadataRoute.Sitemap = (research.items ?? []).map(a => ({
    url: `${base}/research/${a.slug}`,
    lastModified: a.last_updated ?? a.published_at ?? now,
    changeFrequency: "weekly",
    priority: 0.8,
  }));

  return [...staticRoutes, ...eventRoutes, ...radarRoutes, ...companyRoutes, ...newsRoutes, ...insightRoutes, ...sectorRoutes, ...extraSectorRoutes, ...researchRoutes, ...glossaryRoutes, ...guideRoutes, ...articleRoutes];
}
