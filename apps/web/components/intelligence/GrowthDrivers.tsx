"use client";

import { TrendingUp } from "lucide-react";

interface Driver {
  title: string;
  description: string;
  impact: "high" | "medium" | "low";
  timeframe: string;
}

interface GrowthDriversProps {
  drivers?: Driver[];
}

const IMPACT_STYLES = {
  high:   { pill: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400", dot: "bg-emerald-400" },
  medium: { pill: "border-amber-500/30  bg-amber-500/10  text-amber-400",    dot: "bg-amber-400"   },
  low:    { pill: "border-slate-500/30  bg-slate-500/10  text-slate-400",    dot: "bg-slate-500"   },
};

export function GrowthDrivers({ drivers = [] }: GrowthDriversProps) {
  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.025] p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-emerald-500/[0.08] border border-emerald-500/20">
          <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
        </div>
        <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">Growth Drivers</span>
      </div>

      {drivers.length === 0 ? (
        <p className="text-[12px] text-slate-400 leading-5">No data available</p>
      ) : (
        <div className="space-y-3">
          {drivers.map((d, i) => {
            const style = IMPACT_STYLES[d.impact];
            return (
              <div
                key={i}
                className="rounded-[16px] border border-white/[0.06] bg-white/[0.02] p-4 hover:border-emerald-400/20 transition-all"
              >
                <div className="flex items-start justify-between gap-3 mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                    <p className="text-[13px] font-semibold text-white">{d.title}</p>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold capitalize ${style.pill}`}>
                    {d.impact}
                  </span>
                </div>
                <p className="text-[12px] text-slate-400 leading-5 ml-4 mb-2">{d.description}</p>
                <div className="ml-4">
                  <span className="inline-flex items-center rounded-full border border-sky-500/20 bg-sky-500/[0.06] px-2 py-0.5 text-[10px] text-sky-400">
                    {d.timeframe}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
