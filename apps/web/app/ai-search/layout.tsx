import type { Metadata } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

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
  // SEO fix (2026-10-14): see app/news/layout.tsx's identical comment.
  alternates: { canonical: `${SITE}/ai-search` },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
