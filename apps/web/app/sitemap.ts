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
    { url: `${base}/events`,                     lastModified: now, changeFrequency: "hourly", priority: 0.95 },
    { url: `${base}/companies`,                  lastModified: now, changeFrequency: "daily",  priority: 0.9 },
    { url: `${base}/stories`,                    lastModified: now, changeFrequency: "daily",  priority: 0.9 },
    { url: `${base}/radar`,                      lastModified: now, changeFrequency: "daily",  priority: 0.85 },
    { url: `${base}/ripple`,                     lastModified: now, changeFrequency: "daily",  priority: 0.85 },
    { url: `${base}/ai-search`,                  lastModified: now, changeFrequency: "daily",  priority: 0.8 },
    { url: `${base}/about`,                      lastModified: now, changeFrequency: "monthly",priority: 0.5 },
    { url: `${base}/why-marketripple`,           lastModified: now, changeFrequency: "monthly",priority: 0.5 },
    { url: `${base}/how-it-works`,               lastModified: now, changeFrequency: "monthly",priority: 0.5 },
    { url: `${base}/how-marketripple-thinks`,    lastModified: now, changeFrequency: "monthly",priority: 0.5 },
    { url: `${base}/ai-methodology`,             lastModified: now, changeFrequency: "monthly",priority: 0.5 },
    { url: `${base}/data-sources`,               lastModified: now, changeFrequency: "monthly",priority: 0.4 },
    { url: `${base}/faq`,                        lastModified: now, changeFrequency: "monthly",priority: 0.4 },
    { url: `${base}/whats-new`,                  lastModified: now, changeFrequency: "weekly", priority: 0.4 },
    { url: `${base}/contact`,                    lastModified: now, changeFrequency: "yearly", priority: 0.3 },
  ];

  // Dynamic routes — best-effort; graceful fallback to static-only on error
  const [eventsData, storiesData, radarData] = await Promise.all([
    safeJson<{ events?: Array<{ id: string; updated_at?: string }> }>(`${API}/api/events?limit=200`, {}),
    safeJson<Array<{ slug: string; updated_at?: string }>>(`${API}/api/stories?limit=200`, []),
    safeJson<Array<{ id: string; updated_at?: string }>>(`${API}/api/radar?limit=100`, []),
  ]);

  const eventRoutes: MetadataRoute.Sitemap = (eventsData.events ?? []).map(e => ({
    url: `${base}/events/${e.id}`,
    lastModified: e.updated_at ?? now,
    changeFrequency: "weekly",
    priority: 0.75,
  }));

  const storyRoutes: MetadataRoute.Sitemap = (Array.isArray(storiesData) ? storiesData : []).map(s => ({
    url: `${base}/stories/${s.slug}`,
    lastModified: s.updated_at ?? now,
    changeFrequency: "weekly",
    priority: 0.75,
  }));

  const radarRoutes: MetadataRoute.Sitemap = (Array.isArray(radarData) ? radarData : []).map(r => ({
    url: `${base}/radar/${r.id}`,
    lastModified: r.updated_at ?? now,
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  return [...staticRoutes, ...eventRoutes, ...storyRoutes, ...radarRoutes];
}
