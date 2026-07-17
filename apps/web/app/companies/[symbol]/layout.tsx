import type { Metadata } from "next";
import { API_BASE_URL as API } from "@/lib/api";

const SITE = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://marketripple.com";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ symbol: string }>;
}): Promise<Metadata> {
  const { symbol } = await params;
  const upper = symbol.toUpperCase();
  const url   = `${SITE}/companies/${upper}`;
  try {
    const res = await fetch(`${API}/api/stocks/${upper}`, { next: { revalidate: 300 } });
    if (res.ok) {
      const stock = await res.json();
      const name  = stock.name ?? upper;
      const desc  = `${name} (${upper}) — AI-powered market analysis, investment thesis, ripple chain impact, and event-driven intelligence on MarketRipple.`;
      return {
        title: `${name} (${upper}) — AI Analysis`,
        description: desc.slice(0, 160),
        openGraph: {
          type: "article", title: `${name} (${upper}) — MarketRipple`, description: desc.slice(0, 160), url,
          siteName: "MarketRipple",
        },
        twitter: { card: "summary_large_image", title: `${name} (${upper})`, description: desc.slice(0, 160) },
        alternates: { canonical: url },
      };
    }
  } catch {}
  return {
    title: `${upper} — AI Analysis`,
    description: `AI-powered market intelligence for ${upper} on MarketRipple.`,
    alternates: { canonical: url },
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
