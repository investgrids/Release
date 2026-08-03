/**
 * Proper XML serialization for the sitemap — replaces Next.js's built-in
 * `sitemap.ts` MetadataRoute.Sitemap convention, which does NOT escape XML
 * special characters in URL segments. Confirmed live: ticker symbols
 * containing "&" (M&M, M&MFIN) were emitted as raw, unescaped `&` inside
 * <loc> — e.g. <loc>https://marketripple.in/companies/M&M</loc> — which is
 * invalid XML (Google Search Console: "EntityRef: expecting ';'" at the
 * exact byte where the parser hit "&M" with no terminating semicolon).
 *
 * Every text value that reaches the XML output goes through escapeXml()
 * here — centralized in one place so this class of bug can't recur by a
 * new field being added without remembering to escape it individually.
 */

// Order matters: "&" must be replaced first. Escaping the others before "&"
// would corrupt the entities they just created (e.g. "&lt;" becoming
// "&amp;lt;" if "&" were replaced last).
export function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export interface SitemapEntry {
  url: string;
  lastModified?: string | Date;
  changeFrequency?: "always" | "hourly" | "daily" | "weekly" | "monthly" | "yearly" | "never";
  priority?: number;
  images?: string[];
}

function toIsoDate(value: string | Date | undefined): string | null {
  if (!value) return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function buildSitemapXml(entries: SitemapEntry[]): string {
  const hasImages = entries.some(e => e.images && e.images.length > 0);
  const urlsetAttrs = hasImages
    ? `xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"`
    : `xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"`;

  const body = entries.map(e => {
    const lastmod = toIsoDate(e.lastModified);
    const parts = [
      `    <loc>${escapeXml(e.url)}</loc>`,
      lastmod ? `    <lastmod>${escapeXml(lastmod)}</lastmod>` : null,
      e.changeFrequency ? `    <changefreq>${escapeXml(e.changeFrequency)}</changefreq>` : null,
      e.priority != null ? `    <priority>${e.priority}</priority>` : null,
      ...(e.images ?? []).map(img => `    <image:image><image:loc>${escapeXml(img)}</image:loc></image:image>`),
    ].filter((p): p is string => p !== null);
    return `  <url>\n${parts.join("\n")}\n  </url>`;
  }).join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset ${urlsetAttrs}>\n${body}\n</urlset>`;
}
