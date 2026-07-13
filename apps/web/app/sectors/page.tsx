import type { Metadata } from "next";
import Link from "next/link";
import { fetchAPI } from "@/lib/api";

export const metadata: Metadata = {
  title: "Sectors — NSE Sectoral Performance | MarketRipple",
};

interface SectorRow {
  id: string;
  name: string;
  value: string;
  positive: boolean;
}

async function getSectors() {
  try {
    return await fetchAPI<SectorRow[]>("/api/sectors");
  } catch {
    return null;
  }
}

export default async function SectorsPage() {
  const sectors = await getSectors() ?? [];

  const positive = sectors.filter((s) => s.positive).length;
  const negative = sectors.filter((s) => !s.positive).length;

  return (
    <main className="mx-auto max-w-[1400px] space-y-6 px-6 py-6 pb-16">
      {/* Page header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-sky-400">Market Overview</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">Sector Performance</h1>
          <p className="mt-1 text-sm text-slate-400">Live performance across NSE sectoral indices.</p>
        </div>
        <Link href="/market-intelligence"
          className="flex items-center gap-2 rounded-2xl border border-white/[0.1] bg-white/[0.04] px-4 py-2 text-[13px] font-medium text-slate-200 transition hover:bg-white/[0.07]">
          Full Market Dashboard →
        </Link>
      </div>

      {/* Summary pills */}
      <div className="flex flex-wrap gap-3">
        {[
          { label: "Advancing",    count: positive,        color: "text-emerald-300", bg: "bg-emerald-500/10 border-emerald-500/20" },
          { label: "Declining",    count: negative,        color: "text-rose-300",    bg: "bg-rose-500/10 border-rose-500/20" },
          { label: "Total Sectors",count: sectors.length,  color: "text-slate-300",   bg: "bg-white/5 border-white/10" },
        ].map(({ label, count, color, bg }) => (
          <div key={label} className={`rounded-2xl border px-5 py-3 ${bg}`}>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</p>
            <p className={`mt-1 text-2xl font-black ${color}`}>{count}</p>
          </div>
        ))}
      </div>

      {/* Empty state */}
      {sectors.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-[24px] border border-white/[0.08] bg-white/[0.02] py-20 text-center">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-4 h-10 w-10 text-slate-600">
            <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" /><line x1="2" y1="20" x2="22" y2="20" />
          </svg>
          <p className="text-base font-semibold text-white">No sector data available</p>
          <p className="mt-1 text-sm text-slate-500">Connect the NSE sectoral index API to see live data.</p>
        </div>
      )}

      {/* Sector grid */}
      {sectors.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {sectors.map((s) => {
            const pct = parseFloat(s.value.replace("%", "")) || 0;
            const barWidth = Math.min(Math.abs(pct) * 15, 100);
            const isPositive = s.positive;

            return (
              <div key={s.id}
                className="group rounded-[20px] border border-white/[0.08] bg-[#0c1422] p-5 transition hover:-translate-y-0.5 hover:border-white/[0.15] hover:shadow-lg">
                {/* Header */}
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[15px] font-bold text-white">{s.name}</p>
                  <span className={`rounded-full px-2.5 py-1 text-[12px] font-black tabular-nums ${isPositive ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>
                    {isPositive ? "+" : ""}{s.value}
                  </span>
                </div>

                {/* Performance bar */}
                <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.05]">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${isPositive ? "bg-gradient-to-r from-emerald-500 to-teal-400" : "bg-gradient-to-r from-rose-500 to-rose-400"}`}
                    style={{ width: `${barWidth}%` }}
                  />
                </div>

                {/* CTA */}
                <div className="mt-5 flex items-center justify-between">
                  <span className={`text-[11px] font-medium ${isPositive ? "text-emerald-400" : "text-rose-400"}`}>
                    {isPositive ? "↑ Outperforming" : "↓ Underperforming"}
                  </span>
                  <Link
                    href={`/ai-search?q=${encodeURIComponent(`${s.name} sector outlook and top stocks`)}`}
                    className="text-[11px] font-semibold text-violet-400 opacity-0 transition group-hover:opacity-100 hover:text-violet-300">
                    Ask AI →
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}
