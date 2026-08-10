import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Portfolio Intelligence Brief — MarketRipple",
  description: "What's happening across the companies you own, right now — real events, news, market-moving price signals, and shared themes across your holdings, plus where MarketRipple's intelligence coverage is thin. No login, no broker connection, no portfolio storage.",
  openGraph: {
    type: "website",
    title: "Portfolio Intelligence Brief",
    description: "A daily intelligence view powered by real events, news, themes, and market impact across your holdings.",
    siteName: "MarketRipple",
  },
  twitter: {
    card: "summary_large_image",
    title: "Portfolio Intelligence Brief",
    description: "What's happening across the companies you own — right now.",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
