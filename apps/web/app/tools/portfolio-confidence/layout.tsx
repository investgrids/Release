import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Portfolio Data Confidence Check — MarketRipple",
  description: "Paste your holdings and see, honestly, which ones have strong real-time event and news coverage on MarketRipple — and which ones we're not tracking much on yet.",
  openGraph: {
    type: "website",
    title: "Portfolio Data Confidence Check — MarketRipple",
    description: "See which of your holdings have real, recent data coverage — and which ones don't, with honest reasons why.",
    siteName: "MarketRipple",
  },
  twitter: {
    card: "summary_large_image",
    title: "Portfolio Data Confidence Check — MarketRipple",
    description: "See which of your holdings have real, recent data coverage — and which ones don't.",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
