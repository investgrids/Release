import type { MetadataRoute } from "next";
import { API_BASE_URL as API } from "@/lib/api";

const base  = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://marketripple.com";
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
    { url: `${base}/themes`,                     lastModified: now, changeFrequency: "daily",  priority: 0.85 },
    { url: `${base}/opportunity-radar`,          lastModified: now, changeFrequency: "daily",  priority: 0.85 },
    { url: `${base}/ripple`,                     lastModified: now, changeFrequency: "daily",  priority: 0.8 },
    { url: `${base}/ai-search`,                  lastModified: now, changeFrequency: "daily",  priority: 0.8 },
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
  ];

  // Dynamic routes — best-effort; graceful fallback to static-only on error.
  // Each endpoint's real response shape and query-param limits (verified live,
  // not assumed — /api/events caps `limit` at 100, /api/companies caps
  // `page_size` at 60, both silently 422 and fall back to [] if exceeded):
  //   /api/events/  -> bare array of events, keyed by `id`
  //   /api/stories/ -> bare array of stories; `id` doubles as the /stories/[slug] param
  //   /api/radar/   -> { items: [...] }; /opportunity-radar/[id] uses the numeric `id`
  //   /api/companies/ -> { companies: [...], total_pages }, keyed by `symbol`
  //   /api/news/    -> bare array of news items, keyed by `id`
  const [events, stories, radar, companiesPage1, news] = await Promise.all([
    safeJson<Array<{ id: string; date?: string }>>(`${API}/api/events/?limit=100`, []),
    safeJson<Array<{ id: string }>>(`${API}/api/stories/?limit=100`, []),
    safeJson<{ items?: Array<{ id: number }> }>(`${API}/api/radar/?page_size=100`, {}),
    safeJson<{ companies?: Array<{ symbol: string }>; total_pages?: number }>(`${API}/api/companies/?page_size=60&page=1`, {}),
    safeJson<Array<{ id: string; published_at?: string }>>(`${API}/api/news/?limit=100`, []),
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

  const storyRoutes: MetadataRoute.Sitemap = (Array.isArray(stories) ? stories : []).map(s => ({
    url: `${base}/stories/${s.id}`,
    lastModified: now,
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

  return [...staticRoutes, ...eventRoutes, ...storyRoutes, ...radarRoutes, ...companyRoutes, ...newsRoutes];
}
