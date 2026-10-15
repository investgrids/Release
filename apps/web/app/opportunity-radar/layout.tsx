import type { Metadata } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "Opportunity Radar — AI-Ranked Investment Ideas",
  description: "AI-scored investment opportunities across Indian equities, ranked by conviction and confidence — high-conviction picks and emerging setups in one view.",
  openGraph: {
    type: "website",
    title: "Opportunity Radar — MarketRipple",
    description: "AI-scored, conviction-ranked investment opportunities across Indian equities.",
    siteName: "MarketRipple",
  },
  twitter: {
    card: "summary_large_image",
    title: "Opportunity Radar — MarketRipple",
    description: "AI-scored, conviction-ranked investment opportunities across Indian equities.",
  },
  // SEO fix (2026-10-14): see app/news/layout.tsx's identical comment.
  alternates: { canonical: `${SITE}/opportunity-radar` },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
