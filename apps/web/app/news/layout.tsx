import type { Metadata } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

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
  // SEO fix (2026-10-14): this route had no canonical at all since the root layout's
  // blanket default was removed (see app/layout.tsx) — tracked separately, now added.
  alternates: { canonical: `${SITE}/news` },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
