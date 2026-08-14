import type { Metadata } from "next";
import { HistoricalPatternsContent } from "./HistoricalPatternsContent";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "Historical Market Patterns — What Happened Before & What It Means",
  description: "Real historical market data on Union Budgets, RBI rate cycles, market corrections and global shocks — how Nifty and key sectors actually reacted, with real winners and losers.",
  openGraph: {
    type: "website",
    title: "Historical Market Patterns — MarketRipple",
    description: "Real historical market data on how Indian markets reacted to past budgets, rate decisions, corrections and global shocks.",
    url: `${SITE}/historical`,
    siteName: "MarketRipple",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
  alternates: { canonical: `${SITE}/historical` },
};

export default function HistoricalHubPage() {
  return <HistoricalPatternsContent headingLevel="h1" />;
}
