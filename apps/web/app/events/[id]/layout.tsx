import type { Metadata } from "next";
import { API_BASE_URL as API } from "@/lib/api";

const SITE = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://marketripple.in";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const url = `${SITE}/events/${id}`;
  try {
    const res = await fetch(`${API}/api/events/${id}`, { next: { revalidate: 3600 } });
    if (res.ok) {
      const data = await res.json();
      const event = data.event ?? data;
      const title = event.title ?? "Market Event";
      const desc  = (data.summary?.text ?? event.description ?? "").slice(0, 160) || "Market event analysis on MarketRipple.";
      return {
        title,
        description: desc,
        openGraph: {
          type: "article", title, description: desc, url,
          siteName: "MarketRipple",
          publishedTime: event.event_date,
        },
        twitter: { card: "summary_large_image", title, description: desc },
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
