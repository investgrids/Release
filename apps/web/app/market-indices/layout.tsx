import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Market Indices",
  alternates: { canonical: "/market-indices" },
};

export default function MarketIndicesLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
