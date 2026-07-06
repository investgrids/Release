import type { MetadataRoute } from "next";

const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://investgrids.com";
const now = new Date().toISOString();

export default function sitemap(): MetadataRoute.Sitemap {
  const staticRoutes: MetadataRoute.Sitemap = [
    { url: base, lastModified: now, changeFrequency: "daily", priority: 1 },
    { url: `${base}/news`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${base}/events`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/stocks`, lastModified: now, changeFrequency: "daily", priority: 0.8 },
    { url: `${base}/radar`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${base}/market-indices`, lastModified: now, changeFrequency: "daily", priority: 0.7 },
    { url: `${base}/sectors`, lastModified: now, changeFrequency: "daily", priority: 0.7 },
    { url: `${base}/calendar`, lastModified: now, changeFrequency: "daily", priority: 0.6 },
    { url: `${base}/market-breadth`, lastModified: now, changeFrequency: "daily", priority: 0.6 },
    { url: `${base}/heatmap`, lastModified: now, changeFrequency: "daily", priority: 0.6 },
  ];
  return staticRoutes;
}
