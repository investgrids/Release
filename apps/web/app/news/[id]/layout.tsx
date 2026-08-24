import type { Metadata } from "next";
import { API_BASE_URL as API } from "@/lib/api";

const SITE = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://www.marketripple.in";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const url = `${SITE}/news/${id}`;
  // Sitemap Truth Audit, 2026-08-24 — /news/{id} is backed by an in-memory
  // RSS cache (app/services/news_fetcher.py), not a database table. Once an
  // item ages out of the rolling fetch window (or the backend process
  // restarts), the id is gone permanently with no recovery path — a real
  // page that ranked and earned real impressions (live-d0a558cbe3ba, ~20k)
  // was found already 404ing on the backend while still served stale by
  // Vercel's ISR cache. Per the Indexability Contract's EPHEMERAL/CACHE-ONLY
  // rule: noindex until this content type has durable persistence.
  const noindex: Metadata["robots"] = { index: false, follow: true };
  try {
    const res = await fetch(`${API}/api/news/${id}`, { next: { revalidate: 3600 } });
    if (res.ok) {
      const article = await res.json();
      const title = article.headline ?? "Market News";
      const desc  = (article.summary ?? "").slice(0, 160) || "Market news and financial intelligence from MarketRipple.";
      return {
        title,
        description: desc,
        robots: noindex,
        openGraph: {
          type: "article", title, description: desc, url,
          siteName: "MarketRipple",
          publishedTime: article.published_at,
        },
        twitter: { card: "summary_large_image", title, description: desc },
        alternates: { canonical: url },
      };
    }
  } catch {}
  return {
    title: "Market News",
    description: "Real-time Indian market news and financial intelligence from MarketRipple.",
    robots: noindex,
    alternates: { canonical: url },
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
