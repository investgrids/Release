import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Companies — AI Stock Intelligence",
  description: "Research Indian companies with AI-powered analysis. Investment thesis, ripple chain impact, scenario analysis, and event-driven intelligence for NSE and BSE stocks.",
  openGraph: {
    type: "website",
    title: "Company Intelligence — MarketRipple",
    description: "AI-powered stock analysis for Indian equity markets. Investment thesis, ripple impact, scenario analysis.",
    siteName: "MarketRipple",
  },
  twitter: {
    card: "summary_large_image",
    title: "Company Intelligence — MarketRipple",
    description: "AI-powered stock analysis for Indian equity markets.",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
