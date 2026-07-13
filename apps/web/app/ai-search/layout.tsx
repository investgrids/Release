import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Search — Ask Any Market Question",
  description: "Ask any Indian market question in natural language. MarketRipple's AI synthesizes events, companies, and data into a sourced, reasoned answer in seconds.",
  openGraph: {
    type: "website",
    title: "AI Market Search — MarketRipple",
    description: "Ask any market question. Get AI-synthesized, evidence-backed answers about Indian equity markets.",
    siteName: "MarketRipple",
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Market Search — MarketRipple",
    description: "Ask any market question. Get AI-synthesized, evidence-backed answers.",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
