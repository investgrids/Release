"use client";

import { Zap } from "lucide-react";

interface Catalyst {
  title: string;
  date?: string;
  probability: number;
  impact: "positive" | "negative" | "neutral";
}

interface MarketCatalystsProps {
  catalysts?: Catalyst[];
}

const IMPACT_DOT: Record<string, string> = {
  positive: "bg-emerald-400",
  negative: "bg-rose-400",
  neutral:  "bg-slate-500",
};

const IMPACT_BAR: Record<string, string> = {
  positive: "bg-emerald-500",
  negative: "bg-rose-500",
  neutral:  "bg-slate-500",
};

export function MarketCatalysts({ catalysts = [] }: MarketCatalystsProps) {
  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.025] p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-amber-500/[0.08] border border-amber-500/20">
          <Zap className="h-3.5 w-3.5 text-amber-400" />
        </div>
        <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">Market Catalysts</span>
      </div>

      {catalysts.length === 0 ? (
        <p className="text-[12px] text-slate-400 leading-5">No data available</p>
      ) : (
        <div className="space-y-3">
          {catalysts.map((c, i) => (
            <div key={i} className="flex items-start gap-4">
              {/* Date column */}
              <div className="w-[72px] shrink-0 text-right">
                <span className="text-[11px] font-semibold text-slate-400">
                  {c.date || "Upcoming"}
                </span>
              </div>

              {/* Timeline line + dot */}
              <div className="relative flex flex-col items-center">
                <span className={`mt-0.5 h-3 w-3 shrink-0 rounded-full border-2 border-slate-950 ${IMPACT_DOT[c.impact]}`} />
                {i < catalysts.length - 1 && (
                  <span className="mt-1 w-px flex-1 bg-white/[0.07]" style={{ minHeight: 32 }} />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 pb-3">
                <p className="text-[13px] font-semibold text-white leading-5 mb-2">{c.title}</p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${IMPACT_BAR[c.impact]}`}
                      style={{ width: `${c.probability}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-bold text-slate-400 shrink-0 w-8 text-right">
                    {c.probability}%
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
