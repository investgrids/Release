import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Market Intelligence — Live Sentiment, Sectors & Commodities",
  description: "Track NIFTY sentiment, sector rotation, commodities, and the economic calendar in one live market intelligence hub for Indian equities.",
  openGraph: {
    type: "website",
    title: "Market Intelligence — MarketRipple",
    description: "Live NIFTY sentiment, sector rotation, commodities, and economic calendar for Indian markets.",
    siteName: "MarketRipple",
  },
  twitter: {
    card: "summary_large_image",
    title: "Market Intelligence — MarketRipple",
    description: "Live NIFTY sentiment, sector rotation, commodities, and economic calendar for Indian markets.",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
