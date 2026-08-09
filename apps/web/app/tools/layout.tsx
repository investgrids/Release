import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Tools — MarketRipple",
  description: "Small, standalone tools built directly on MarketRipple's own real data — honest answers to specific questions, no fabricated numbers.",
  openGraph: {
    type: "website",
    title: "Tools — MarketRipple",
    description: "Standalone tools built directly on MarketRipple's own real data.",
    siteName: "MarketRipple",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
