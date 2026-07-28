import { API_BASE_URL as API } from "@/lib/api";

/**
 * Google News sitemap (SEO Phase 3, §3.3) — a separate XML route, not
 * Next.js's built-in sitemap.ts convention, because the News sitemap
 * extension (<news:news>) isn't part of that convention's type.
 *
 * Deliberately sourced from /api/insights/ (AIPE-generated intelligence
 * articles — real, substantively original AI-authored analysis: headline,
 * executive summary, full body) and NOT from /api/news/, whose items wrap
 * third-party syndicated headlines (each carries an external `url` field
 * pointing at the original publisher, e.g. livemint.com) — submitting
 * those under MarketRipple's own URLs is exactly the "aggregated content
 * presented as original" pattern Google News policy is strict about.
 *
 * Google News only wants genuinely fresh content — this filters to the
 * last 48 hours and caps at 1000 URLs per its own limits. The Publisher
 * Center application itself (google.com/publisher-center) is a human
 * approval process, not something this route can do — this exists so the
 * technical sitemap is ready the moment that approval lands, not before.
 */

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://marketripple.in";
const NEWS_WINDOW_MS = 48 * 60 * 60 * 1000;

interface InsightItem {
  slug: string;
  headline?: string;
  seo_title?: string;
  published_at?: string;
}

function escapeXml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export async function GET() {
  let items: InsightItem[] = [];
  try {
    const res = await fetch(`${API}/api/insights/?limit=100`, { next: { revalidate: 900 } });
    if (res.ok) {
      const data = await res.json();
      items = Array.isArray(data.items) ? data.items : [];
    }
  } catch {
    items = [];
  }

  const cutoff = Date.now() - NEWS_WINDOW_MS;
  const fresh = items.filter(a => {
    if (!a.published_at) return false;
    const t = new Date(a.published_at).getTime();
    return !Number.isNaN(t) && t >= cutoff;
  }).slice(0, 1000);

  const urls = fresh.map(a => {
    const title = escapeXml(a.seo_title || a.headline || a.slug);
    const pubDate = new Date(a.published_at!).toISOString();
    return `  <url>
    <loc>${SITE}/newsroom/article/${a.slug}</loc>
    <news:news>
      <news:publication>
        <news:name>MarketRipple</news:name>
        <news:language>en</news:language>
      </news:publication>
      <news:publication_date>${pubDate}</news:publication_date>
      <news:title>${title}</news:title>
    </news:news>
  </url>`;
  }).join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
${urls}
</urlset>`;

  return new Response(xml, {
    headers: { "Content-Type": "application/xml; charset=utf-8" },
  });
}
