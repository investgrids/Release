import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ripple Intelligence — Market Impact Chains",
  description: "Trace how market events ripple through sectors, companies, and portfolios. AI-powered dependency graph for Indian equity markets.",
  openGraph: {
    type: "website",
    title: "Ripple Intelligence — MarketRipple",
    description: "Trace market event ripple effects through sectors and companies.",
    siteName: "MarketRipple",
  },
  twitter: {
    card: "summary_large_image",
    title: "Ripple Intelligence — MarketRipple",
    description: "Trace market event ripple effects through sectors and companies.",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
