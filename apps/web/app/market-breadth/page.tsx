import type { Metadata } from "next";
import Link from "next/link";
import { TrendingUp, LineChart, Layers, Globe, Banknote, Bookmark } from "lucide-react";

export const metadata: Metadata = {
  title: "Market Breadth | MarketRipple",
};

export default function MarketBreadthPage() {
  return (
    <div className="mx-auto max-w-[1200px] px-6 py-16 pb-24">
      <div className="relative overflow-hidden rounded-[28px] border border-white/[0.08] bg-gradient-to-br from-[#0d1526] to-[#080c18] p-10 text-center">
        <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-48 w-96 rounded-full bg-sky-500/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-16 right-8 h-40 w-64 rounded-full bg-emerald-500/8 blur-2xl" />

        <div className="relative mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-[22px] border border-white/[0.1] bg-white/[0.04]">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="h-9 w-9 text-slate-400">
            <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" /><line x1="2" y1="20" x2="22" y2="20" />
          </svg>
        </div>

        <div className="relative mb-4 inline-flex items-center gap-2 rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
          <span className="text-[11px] font-bold uppercase tracking-widest text-amber-400">Pending NSE Market Breadth API</span>
        </div>

        <h1 className="relative mb-3 text-3xl font-black tracking-tight text-white">
          Market Breadth
        </h1>
        <p className="relative mx-auto mb-8 max-w-md text-[14px] leading-7 text-slate-400">
          Real advance-decline data, sector breadth charts, FII/DII institutional flow, and the A/D ratio line.
          Activates once the NSE breadth API integration is complete.
        </p>

        <div className="relative mx-auto mb-8 grid max-w-xl grid-cols-2 gap-3 text-left sm:grid-cols-3">
          {[
            { label: "Advance / Decline", icon: <TrendingUp size={15} strokeWidth={1.7}/> },
            { label: "A/D Ratio Line",    icon: <LineChart  size={15} strokeWidth={1.7}/> },
            { label: "Sector Breadth",    icon: <Layers     size={15} strokeWidth={1.7}/> },
            { label: "FII Net Flow",      icon: <Globe      size={15} strokeWidth={1.7}/> },
            { label: "DII Net Flow",      icon: <Banknote   size={15} strokeWidth={1.7}/> },
            { label: "52W High/Low",      icon: <Bookmark   size={15} strokeWidth={1.7}/> },
          ].map(f => (
            <div key={f.label} className="flex items-center gap-2.5 rounded-2xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
              <span className="text-slate-400 flex items-center">{f.icon}</span>
              <span className="text-[12px] font-medium text-slate-300">{f.label}</span>
            </div>
          ))}
        </div>

        <div className="relative flex flex-wrap items-center justify-center gap-3">
          <Link href="/market-intelligence"
            className="flex items-center gap-2 rounded-2xl bg-gradient-to-r from-violet-600 to-sky-500 px-5 py-2.5 text-[13px] font-semibold text-white shadow-lg shadow-violet-500/20 transition hover:opacity-90">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            Live Market Intelligence
          </Link>
          <Link href="/market-indices"
            className="flex items-center gap-2 rounded-2xl border border-white/[0.1] bg-white/[0.04] px-5 py-2.5 text-[13px] font-medium text-slate-200 transition hover:bg-white/[0.07]">
            View Market Indices →
          </Link>
        </div>
      </div>
    </div>
  );
}
