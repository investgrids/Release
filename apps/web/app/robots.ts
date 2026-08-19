import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // /_next/ deliberately NOT disallowed (2026-08 SEO audit, GSC
        // "Blocked by robots.txt" report) — it holds the JS/CSS/font
        // assets every page needs to render, and blocking it doesn't stop
        // Google from indexing pages (it never served indexable HTML in
        // the first place), it only stops Googlebot from fetching what it
        // needs to render pages properly, which Google's own guidance
        // explicitly warns against.
        disallow: ["/api/", "/operations/", "/admin/"],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
    host: base,
  };
}
