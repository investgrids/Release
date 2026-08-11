import Link from "next/link";
import { fetchAPI } from "@/lib/api";

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

export async function SectorsContent({ headingLevel = "h1" }: { headingLevel?: "h1" | "h2" }) {
  const sectors = await getSectors() ?? [];
  const Heading = headingLevel;

  const positive = sectors.filter((s) => s.positive).length;
  const negative = sectors.filter((s) => !s.positive).length;

  return (
    <main className="mx-auto max-w-[1400px] space-y-6 py-6 pb-16">
      {/* Page header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-sky-400">Market Overview</p>
          <Heading className="mt-2 text-3xl font-black tracking-tight text-text-primary">Sector Performance</Heading>
          <p className="mt-1 text-sm text-text-secondary">Live performance across NSE sectoral indices.</p>
        </div>
        <Link href="/market-intelligence"
          className="flex items-center gap-2 rounded-2xl border border-surface-border/10 bg-text-primary/[0.04] px-4 py-2 text-[13px] font-medium text-text-primary transition hover:bg-text-primary/[0.07]">
          Full Market Dashboard →
        </Link>
      </div>

      {/* Summary pills */}
      <div className="flex flex-wrap gap-3">
        {[
          { label: "Advancing",    count: positive,        color: "text-emerald-600 dark:text-emerald-300", bg: "bg-emerald-500/10 border-emerald-500/20" },
          { label: "Declining",    count: negative,        color: "text-rose-600 dark:text-rose-300",    bg: "bg-rose-500/10 border-rose-500/20" },
          { label: "Total Sectors",count: sectors.length,  color: "text-text-secondary",   bg: "bg-text-primary/5 border-surface-border/10" },
        ].map(({ label, count, color, bg }) => (
          <div key={label} className={`rounded-2xl border px-5 py-3 ${bg}`}>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-text-muted">{label}</p>
            <p className={`mt-1 text-2xl font-black ${color}`}>{count}</p>
          </div>
        ))}
      </div>

      {/* Empty state */}
      {sectors.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-[24px] border border-surface-border/8 bg-text-primary/[0.02] py-20 text-center">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-4 h-10 w-10 text-text-muted">
            <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" /><line x1="2" y1="20" x2="22" y2="20" />
          </svg>
          <p className="text-base font-semibold text-text-primary">No sector data available</p>
          <p className="mt-1 text-sm text-text-muted">Connect the NSE sectoral index API to see live data.</p>
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
              <Link key={s.id} href={`/sectors/${s.id}`}
                className="group block rounded-[20px] border border-surface-border/8 bg-surface-card p-5 transition hover:-translate-y-0.5 hover:border-surface-border/15 hover:shadow-lg">
                {/* Header */}
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[15px] font-bold text-text-primary">{s.name}</p>
                  <span className={`rounded-full px-2.5 py-1 text-[12px] font-black tabular-nums ${isPositive ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300" : "bg-rose-500/15 text-rose-600 dark:text-rose-300"}`}>
                    {isPositive ? "+" : ""}{s.value}
                  </span>
                </div>

                {/* Performance bar */}
                <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-text-primary/[0.05]">
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
                  <span className="text-[11px] font-semibold text-violet-400 opacity-0 transition group-hover:opacity-100">
                    View Sector →
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {/* Sectors with real constituent stocks + opportunity/event data but
          no live-momentum index tracked yet (see sectors.py's /intelligence
          endpoint docstring) — still real pages, just without a "Today"
          momentum badge. */}
      <div>
        <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.2em] text-text-muted">More Sectors</p>
        <div className="flex flex-wrap gap-2">
          {[
            { id: "defence", name: "Defence" },
            { id: "chemicals", name: "Chemicals" },
            { id: "telecom", name: "Telecom" },
            { id: "finance", name: "Finance (NBFC)" },
          ].map((s) => (
            <Link key={s.id} href={`/sectors/${s.id}`}
              className="rounded-full border border-surface-border/10 bg-text-primary/[0.03] px-4 py-2 text-[13px] font-medium text-text-secondary transition hover:border-surface-border/20 hover:text-text-primary">
              {s.name}
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
