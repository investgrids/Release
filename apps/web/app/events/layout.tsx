import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Market Events — Event-Driven Intelligence",
  description: "Explore Indian market events with AI-powered ripple analysis. See which companies and sectors are affected, with confidence scores and investment implications.",
  openGraph: {
    type: "website",
    title: "Market Events — MarketRipple",
    description: "Event-driven market intelligence for Indian equity markets.",
    siteName: "MarketRipple",
  },
  twitter: {
    card: "summary_large_image",
    title: "Market Events — MarketRipple",
    description: "Event-driven market intelligence for Indian equity markets.",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
