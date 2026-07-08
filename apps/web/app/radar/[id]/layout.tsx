import type { Metadata } from "next";

const API  = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const SITE = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://marketripple.com";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const url = `${SITE}/radar/${id}`;
  try {
    const res = await fetch(`${API}/api/radar/${id}`, { next: { revalidate: 3600 } });
    if (res.ok) {
      const item = await res.json();
      const title = item.title ?? "Investment Opportunity";
      const desc  = (item.summary ?? "").slice(0, 160) || "AI-powered investment opportunity analysis on MarketRipple.";
      return {
        title: `${title} — Opportunity Radar`,
        description: desc,
        openGraph: {
          type: "article", title: `${title} — Opportunity Radar`, description: desc, url,
          siteName: "MarketRipple",
        },
        twitter: { card: "summary_large_image", title: `${title} — Opportunity Radar`, description: desc },
        alternates: { canonical: url },
      };
    }
  } catch {}
  return {
    title: "Opportunity Radar",
    description: "AI-powered investment opportunity analysis from MarketRipple.",
    alternates: { canonical: url },
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
