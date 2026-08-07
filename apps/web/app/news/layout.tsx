import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Market News — Real-Time Indian Market Coverage",
  description: "Real-time Indian market news from NSE, BSE, RBI, SEBI, and financial media, categorized and ranked by market impact.",
  openGraph: {
    type: "website",
    title: "Market News — MarketRipple",
    description: "Real-time Indian market news, categorized and ranked by market impact.",
    siteName: "MarketRipple",
  },
  twitter: {
    card: "summary_large_image",
    title: "Market News — MarketRipple",
    description: "Real-time Indian market news, categorized and ranked by market impact.",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
