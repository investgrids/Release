import Link from "next/link";

interface SectorItem {
  id: string;
  name: string;
  value: string;
  positive: boolean;
}

export function SectorPerformanceCard({ sectors }: { sectors: SectorItem[] }) {
  const maxAbs = sectors.reduce((m, s) => {
    const v = Math.abs(parseFloat(s.value.replace(/[^0-9.-]/g, "")) || 0);
    return v > m ? v : m;
  }, 2);

  return (
    <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5 shadow-lg h-full">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[14px] font-bold text-white">Sector Performance</h2>
        <Link href="/opportunity-radar" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>
      <div className="space-y-2.5">
        {sectors.slice(0, 8).map((s) => {
          const val = parseFloat(s.value.replace(/[^0-9.-]/g, "")) || 0;
          const pct = Math.min(Math.abs(val) / maxAbs, 1);
          const sign = val >= 0 ? "+" : "";
          const displayVal = s.value.startsWith("+") || s.value.startsWith("-")
            ? s.value
            : `${sign}${s.value}%`;
          return (
            <div key={s.id} className="flex items-center gap-3">
              {/* Colored dot */}
              <div className={`h-2 w-2 shrink-0 rounded-full ${s.positive ? "bg-emerald-400" : "bg-rose-400"}`}/>
              {/* Name */}
              <p className="w-32 shrink-0 text-[12px] text-slate-300 truncate">{s.name}</p>
              {/* Bar */}
              <div className="flex-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${s.positive ? "bg-emerald-500" : "bg-rose-500"}`}
                  style={{ width: `${pct * 100}%` }}/>
              </div>
              {/* Value */}
              <span className={`w-14 shrink-0 text-right text-[12px] font-semibold ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>
                {displayVal}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
