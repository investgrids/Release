import type { Metadata } from "next";
import { API_BASE_URL as API } from "@/lib/api";

const SITE = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://marketripple.com";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const url = `${SITE}/news/${id}`;
  try {
    const res = await fetch(`${API}/api/news/${id}`, { next: { revalidate: 3600 } });
    if (res.ok) {
      const article = await res.json();
      const title = article.headline ?? "Market News";
      const desc  = (article.summary ?? "").slice(0, 160) || "Market news and financial intelligence from MarketRipple.";
      return {
        title,
        description: desc,
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
    alternates: { canonical: url },
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
