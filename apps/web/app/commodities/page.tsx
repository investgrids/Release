import type { Metadata } from "next";
import { CommoditiesContent } from "./CommoditiesContent";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "Commodity & Energy Prices Today — Gold, Silver, Crude Oil",
  description: "Live gold, silver, copper, platinum, Brent crude, WTI crude, and natural gas prices with 7-day trend charts and India-relevant market impact.",
  openGraph: {
    type: "website",
    title: "Commodity & Energy Prices Today — MarketRipple",
    description: "Live metals and energy prices with real 7-day trend data.",
    url: `${SITE}/commodities`,
    siteName: "MarketRipple",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
  alternates: { canonical: `${SITE}/commodities` },
};

export default function CommoditiesHubPage() {
  return <CommoditiesContent headingLevel="h1" />;
}
