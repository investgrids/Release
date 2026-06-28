interface OpportunityItem {
  id: string;
  score: number;
  theme: string;
  reason: string;
  category: string;
}

interface OpportunityRadarProps {
  items: OpportunityItem[];
}

export function OpportunityRadar({ items }: OpportunityRadarProps) {
  return (
    <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl h-full">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">✦</span>
          <h2 className="text-sm font-semibold text-white">Opportunity Radar</h2>
        </div>
        <button className="text-xs text-slate-500 transition hover:text-white">View All</button>
      </div>
      <div className="space-y-2.5">
        {items.map((item) => (
          <div key={item.id} className="flex items-center gap-3 rounded-[16px] border border-white/5 bg-slate-950/60 p-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px] bg-gradient-to-br from-emerald-500/20 to-sky-500/10 text-lg font-bold text-emerald-300">
              {item.score}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-white leading-snug">{item.theme}</p>
              <p className="mt-0.5 text-[11px] text-slate-500 truncate">{item.reason}</p>
            </div>
            <span className="shrink-0 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">
              {item.category}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
