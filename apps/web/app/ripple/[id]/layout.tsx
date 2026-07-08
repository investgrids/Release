import type { Metadata } from "next";

const API  = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const SITE = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://marketripple.com";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const url = `${SITE}/ripple/${id}`;
  try {
    const res = await fetch(`${API}/api/ripple/${id}`, { next: { revalidate: 3600 } });
    if (res.ok) {
      const data  = await res.json();
      const title = data.event_title ?? data.title ?? "Ripple Intelligence";
      const desc  = (data.insights?.summary ?? data.summary ?? "").slice(0, 160) || "Trace how a market event ripples through sectors and companies on MarketRipple.";
      return {
        title: `${title} — Ripple Intelligence`,
        description: desc,
        openGraph: {
          type: "article", title: `${title} — Ripple Intelligence`, description: desc, url,
          siteName: "MarketRipple",
        },
        twitter: { card: "summary_large_image", title, description: desc },
        alternates: { canonical: url },
      };
    }
  } catch {}
  return {
    title: "Ripple Intelligence",
    description: "Trace how market events ripple through sectors and companies on MarketRipple.",
    alternates: { canonical: url },
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
