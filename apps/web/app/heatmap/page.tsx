import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Market Heatmap | MarketRipple",
};

export default function HeatmapPage() {
  return (
    <div className="mx-auto max-w-[1200px] px-6 py-16 pb-24">
      {/* Coming Soon card */}
      <div className="relative overflow-hidden rounded-[28px] border border-white/[0.08] bg-gradient-to-br from-[#0d1526] to-[#080c18] p-10 text-center">
        {/* Decorative glow */}
        <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-48 w-96 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-16 right-8 h-40 w-64 rounded-full bg-sky-500/8 blur-2xl" />

        {/* Icon */}
        <div className="relative mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-[22px] border border-white/[0.1] bg-white/[0.04]">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="h-9 w-9 text-slate-400">
            <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
        </div>

        {/* Badge */}
        <div className="relative mb-4 inline-flex items-center gap-2 rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
          <span className="text-[11px] font-bold uppercase tracking-widest text-amber-400">Pending Live Data Integration</span>
        </div>

        <h1 className="relative mb-3 text-3xl font-black tracking-tight text-white">
          Nifty 50 Heatmap
        </h1>
        <p className="relative mx-auto mb-8 max-w-md text-[14px] leading-7 text-slate-400">
          A real-time treemap of all 50 Nifty constituents sized by market cap and coloured by daily performance.
          Coming once we wire the NSE constituent API for live prices.
        </p>

        {/* What you'll see */}
        <div className="relative mx-auto mb-8 grid max-w-xl grid-cols-2 gap-3 text-left sm:grid-cols-3">
          {[
            { label: "Live % Change", icon: "📈" },
            { label: "Market Cap Size", icon: "🔲" },
            { label: "Sector Grouping", icon: "🏭" },
            { label: "Click → Company", icon: "🔍" },
            { label: "Auto-refresh 5m", icon: "⏱" },
            { label: "Sector Heat", icon: "🌡" },
          ].map(f => (
            <div key={f.label} className="flex items-center gap-2.5 rounded-2xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
              <span className="text-lg leading-none">{f.icon}</span>
              <span className="text-[12px] font-medium text-slate-300">{f.label}</span>
            </div>
          ))}
        </div>

        {/* CTAs */}
        <div className="relative flex flex-wrap items-center justify-center gap-3">
          <Link href="/market-intelligence"
            className="flex items-center gap-2 rounded-2xl bg-gradient-to-r from-violet-600 to-sky-500 px-5 py-2.5 text-[13px] font-semibold text-white shadow-lg shadow-violet-500/20 transition hover:opacity-90">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            Live Market Intelligence
          </Link>
          <Link href="/sectors"
            className="flex items-center gap-2 rounded-2xl border border-white/[0.1] bg-white/[0.04] px-5 py-2.5 text-[13px] font-medium text-slate-200 transition hover:bg-white/[0.07]">
            View Sectors →
          </Link>
        </div>
      </div>
    </div>
  );
}
