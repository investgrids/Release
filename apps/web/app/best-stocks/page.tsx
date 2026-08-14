import type { Metadata } from "next";
import { BestStocksContent } from "./BestStocksContent";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "Best Stocks by Sector — Real AI Opportunity Rankings",
  description: "Which stocks are best positioned in Defence, Banking, Energy, IT and more — ranked by MarketRipple's AI Company Intelligence Score, real signals from published analysis and Opportunity Radar, not a generic list.",
  openGraph: {
    type: "website",
    title: "Best Stocks by Sector — MarketRipple",
    description: "Real, opportunity-scored stock rankings by sector.",
    url: `${SITE}/best-stocks`,
    siteName: "MarketRipple",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
  alternates: { canonical: `${SITE}/best-stocks` },
};

export default function BestStocksHubPage() {
  return <BestStocksContent headingLevel="h1" />;
}
