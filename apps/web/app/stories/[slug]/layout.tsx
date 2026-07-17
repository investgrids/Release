import type { Metadata } from "next";
import { API_BASE_URL as API } from "@/lib/api";

const SITE = process.env.NEXT_PUBLIC_SITE_URL     ?? "https://marketripple.com";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const url = `${SITE}/stories/${slug}`;
  try {
    const res = await fetch(`${API}/api/stories/${slug}`, { next: { revalidate: 3600 } });
    if (res.ok) {
      const story = await res.json();
      const title = story.title ?? "Investment Story";
      const desc  = (story.description ?? story.summary ?? "").slice(0, 160) || "AI-synthesized investment theme on MarketRipple.";
      return {
        title: `${title} — Investment Story`,
        description: desc,
        openGraph: {
          type: "article", title: `${title} — MarketRipple Stories`, description: desc, url,
          siteName: "MarketRipple",
        },
        twitter: { card: "summary_large_image", title, description: desc },
        alternates: { canonical: url },
      };
    }
  } catch {}
  return {
    title: "Investment Story",
    description: "AI-synthesized investment themes and market intelligence on MarketRipple.",
    alternates: { canonical: url },
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
