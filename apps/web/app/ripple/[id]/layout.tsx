import type { Metadata } from "next";
import { API_BASE_URL as API } from "@/lib/api";

const SITE = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://www.marketripple.in";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const url = `${SITE}/ripple/${id}`;
  try {
    // SEO fix: was /api/ripple/{id} — always 404 (confirmed live), which
    // silently fell through to the generic "Ripple Intelligence" fallback
    // below for every single ripple page, no exceptions — a crawler flagged
    // 10 of them as duplicate titles, but the underlying bug affects all of
    // them. The real endpoint (matching what RipplePageClient.tsx's own
    // client-side fetch already uses successfully) is /api/ripple/event/{id}.
    const res = await fetch(`${API}/api/ripple/event/${id}`, { next: { revalidate: 3600 } });
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
