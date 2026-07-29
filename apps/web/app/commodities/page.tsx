import type { Metadata } from "next";
import Link from "next/link";
import { Flame, Gem } from "lucide-react";
import { getCommodities } from "@/lib/commodities";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://marketripple.in";

export const metadata: Metadata = {
  title: "Commodity & Energy Prices Today — Gold, Silver, Crude Oil | MarketRipple",
  description: "Live gold, silver, copper, platinum, Brent crude, WTI crude, and natural gas prices with 7-day trend charts and India-relevant market impact.",
  openGraph: {
    type: "website",
    title: "Commodity & Energy Prices Today — MarketRipple",
    description: "Live metals and energy prices with real 7-day trend data.",
    url: `${SITE}/commodities`,
    siteName: "MarketRipple",
  },
  alternates: { canonical: `${SITE}/commodities` },
};

function PriceCard({ id, name, price, change, pct, positive, unit }: { id: string; name: string; price: string; change: string; pct: number; positive: boolean; unit: string }) {
  return (
    <Link href={`/commodities/${id}`} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 transition hover:border-amber-500/25 hover:bg-white/[0.03]">
      <p className="text-[13px] font-semibold text-white">{name}</p>
      <p className="text-[10px] text-slate-600">{unit}</p>
      <p className="mt-2 text-[20px] font-black tabular-nums text-white">{price}</p>
      <p className={`text-[12px] font-bold tabular-nums ${positive ? "text-emerald-400" : "text-rose-400"}`}>
        {change} ({positive ? "+" : ""}{pct.toFixed(2)}%)
      </p>
    </Link>
  );
}

export default async function CommoditiesHubPage() {
  const data = await getCommodities();

  return (
    <main className="mx-auto max-w-[900px] px-5 py-8 pb-16 sm:px-6">
      <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-slate-500">
        <Flame className="h-3.5 w-3.5" /> Commodities
      </div>
      <h1 className="text-[28px] font-black leading-tight text-white md:text-[34px]">
        Commodity &amp; Energy Prices Today
      </h1>
      <p className="mt-3 max-w-[640px] text-[14px] leading-relaxed text-slate-400">
        Live prices with real 7-day trend data — updated {data?.updated ?? "periodically"}.
      </p>

      {!data && <p className="mt-10 text-[13px] text-slate-600">Live price data unavailable right now.</p>}

      {data && (
        <>
          <section className="mt-8">
            <h2 className="mb-3 flex items-center gap-2 text-[12px] font-bold uppercase tracking-widest text-slate-500">
              <Gem className="h-3.5 w-3.5" /> Metals
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {data.metals.map(c => <PriceCard key={c.id} {...c} />)}
            </div>
          </section>

          <section className="mt-8">
            <h2 className="mb-3 flex items-center gap-2 text-[12px] font-bold uppercase tracking-widest text-slate-500">
              <Flame className="h-3.5 w-3.5" /> Energy
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {data.energy.map(c => <PriceCard key={c.id} {...c} />)}
            </div>
          </section>

          {!data.insights?.degraded && data.insights?.daily_summary && (
            <section className="mt-8 rounded-xl border border-amber-500/15 bg-amber-500/[0.04] p-4">
              <p className="mb-1.5 text-[10px] font-bold uppercase tracking-widest text-amber-500">Today&apos;s Summary</p>
              <p className="text-[13px] leading-relaxed text-slate-300">{data.insights.daily_summary}</p>
            </section>
          )}
        </>
      )}
    </main>
  );
}
