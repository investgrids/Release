import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Opportunity Radar — AI-Scored Investments",
  description: "Discover AI-scored investment opportunities in Indian markets. Each opportunity is backed by evidence, confidence scores, and a full investment thesis.",
  openGraph: {
    type: "website",
    title: "Opportunity Radar — MarketRipple",
    description: "AI-scored investment opportunities backed by evidence and confidence scores.",
    siteName: "MarketRipple",
  },
  twitter: {
    card: "summary_large_image",
    title: "Opportunity Radar — MarketRipple",
    description: "AI-scored investment opportunities backed by evidence and confidence scores.",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
