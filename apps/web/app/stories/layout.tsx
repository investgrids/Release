import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Investment Stories — Thematic Intelligence",
  description: "Discover AI-synthesized investment themes for India. Multi-event thematic analysis covering defense, infrastructure, EV, AI adoption, and more with evidence-backed insights.",
  openGraph: {
    type: "website",
    title: "Investment Stories — MarketRipple",
    description: "AI-synthesized investment themes for Indian equity markets.",
    siteName: "MarketRipple",
  },
  twitter: {
    card: "summary_large_image",
    title: "Investment Stories — MarketRipple",
    description: "AI-synthesized investment themes for Indian equity markets.",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
