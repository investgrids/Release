import type { Metadata } from "next";
import Link from "next/link";
import { TrendingUp } from "lucide-react";
import { getSectorsWithCounts } from "@/lib/bestStocks";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.marketripple.in";

export const metadata: Metadata = {
  title: "Best Stocks by Sector — Real AI Opportunity Rankings",
  description: "Which stocks are best positioned in Defence, Banking, Energy, IT and more — ranked by MarketRipple's AI Company Intelligence Score, real signals from published analysis and Opportunity Radar, not a generic list.",
  openGraph: {
    type: "website",
    title: "Best Stocks by Sector — MarketRipple",
    description: "Real, opportunity-scored stock rankings by sector.",
    url: `${SITE}/best-stocks`,
    siteName: "MarketRipple",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "MarketRipple — AI-Powered Market Intelligence" }],
  },
  alternates: { canonical: `${SITE}/best-stocks` },
};

export default async function BestStocksHubPage() {
  const sectors = await getSectorsWithCounts();

  return (
    <main className="mx-auto max-w-[900px] px-5 py-8 pb-16 sm:px-6">
      <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-text-muted">
        <TrendingUp className="h-3.5 w-3.5" /> Best Stocks
      </div>
      <h1 className="text-[28px] font-black leading-tight text-text-primary md:text-[34px]">
        Best Stocks By Sector
      </h1>
      <p className="mt-3 max-w-[640px] text-[14px] leading-relaxed text-text-secondary">
        Ranked by MarketRipple&apos;s AI Company Intelligence Score — every company here is backed
        by real signals from published analysis and Opportunity Radar, not a generic screener list.
      </p>

      {sectors.length === 0 && (
        <p className="mt-10 text-[13px] text-text-muted">No sector rankings available right now.</p>
      )}

      <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {sectors.map(s => (
          <Link
            key={s.slug}
            href={`/best-stocks/${s.slug}`}
            className="flex items-center justify-between rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-4 transition hover:border-emerald-500/25 hover:bg-text-primary/[0.03]"
          >
            <span className="text-[14px] font-semibold text-text-primary">Best {s.sector} Stocks</span>
            <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-[11px] font-bold text-emerald-400">
              {s.companyCount} ranked
            </span>
          </Link>
        ))}
      </div>
    </main>
  );
}
