import type { Metadata } from "next";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ symbol: string }>;
}): Promise<Metadata> {
  const { symbol } = await params;
  const upper = symbol.toUpperCase();
  try {
    const res = await fetch(`${API}/api/stocks/${upper}`, {
      next: { revalidate: 300 },
    });
    if (res.ok) {
      const stock = await res.json();
      const name = stock.name ?? upper;
      return {
        title: `${name} (${upper}) Stock Price & Analysis | InvestGrids`,
        description: `${name} live price, charts, financials, and AI-powered market analysis on InvestGrids.`,
      };
    }
  } catch {}
  return {
    title: `${upper} Stock Price & Analysis | InvestGrids`,
    description: `Live price, charts, and AI analysis for ${upper} on InvestGrids.`,
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
