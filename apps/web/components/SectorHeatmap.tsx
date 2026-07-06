interface SectorItem {
  id: string;
  name: string;
  value: string;
  positive: boolean;
  span?: string;
}

interface SectorHeatmapProps {
  sectors: SectorItem[];
}

export function SectorHeatmap({ sectors }: SectorHeatmapProps) {
  return (
    <section className="min-w-0 overflow-hidden rounded-[24px] border border-white/10 bg-white/[0.03] p-5 shadow-glow h-full">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-violet-400"><svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg></span>
          <h2 className="text-sm font-semibold text-white">Sector Heatmap</h2>
        </div>
        <button className="text-xs text-slate-500 transition hover:text-white">View All</button>
      </div>

      <div className="grid grid-cols-4 gap-x-2 gap-y-4">
        {sectors.map((sector) => (
          <div key={sector.id} className="flex flex-col items-center gap-1.5">
            {/* Bubble circle */}
            <div
              className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                sector.positive
                  ? "bg-gradient-to-br from-emerald-500/30 to-emerald-900/10 text-emerald-300 ring-1 ring-emerald-500/40 shadow-[0_0_12px_rgba(34,197,94,0.15)]"
                  : "bg-gradient-to-br from-rose-500/30 to-rose-900/10 text-rose-300 ring-1 ring-rose-500/40 shadow-[0_0_12px_rgba(244,63,94,0.15)]"
              }`}
            >
              {sector.value}
            </div>
            {/* Sector label */}
            <p className="w-full text-center text-[8px] font-medium leading-tight text-slate-400 line-clamp-2">
              {sector.name}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
