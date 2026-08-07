import type { Metadata } from "next";

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
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
