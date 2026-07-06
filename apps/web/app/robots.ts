import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://investgrids.com";
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/news", "/news/*", "/events", "/events/*", "/stocks", "/stocks/*", "/radar", "/radar/*", "/market-indices", "/sectors", "/calendar"],
        disallow: ["/ai-search", "/compare", "/api/"],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
  };
}
