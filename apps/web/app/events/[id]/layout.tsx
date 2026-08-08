import type { Metadata } from "next";
import { API_BASE_URL as API } from "@/lib/api";

const SITE = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://www.marketripple.in";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  // SEO fix: every event already has a real, human-readable slug in the DB
  // (e.g. "nmdc-limited-has-informed-the-exchange-about-general-updates-
  // nse-4cc9") that was never actually used — every link pointed at the
  // opaque id instead. The backend now accepts either for lookup, so old
  // id-based links (already indexed, bookmarked) keep working; canonical
  // below is what tells search engines the slug is the real address.
  let url = `${SITE}/events/${id}`;
  try {
    const res = await fetch(`${API}/api/events/${id}`, { next: { revalidate: 3600 } });
    if (res.ok) {
      const data = await res.json();
      const event = data.event ?? data;
      if (event.slug) url = `${SITE}/events/${event.slug}`;
      const title = event.title ?? "Market Event";
      const desc  = (data.summary?.text ?? event.description ?? "").slice(0, 160) || "Market event analysis on MarketRipple.";
      return {
        title,
        description: desc,
        openGraph: {
          type: "article", title, description: desc, url,
          siteName: "MarketRipple",
          publishedTime: event.event_date,
          images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
        },
        twitter: { card: "summary_large_image", title, description: desc, images: ["/opengraph-image"] },
        alternates: { canonical: url },
      };
    }
  } catch {}
  return {
    title: "Market Event",
    description: "Event-driven market intelligence from MarketRipple.",
    alternates: { canonical: url },
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
