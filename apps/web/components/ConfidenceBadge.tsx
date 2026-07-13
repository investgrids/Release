"use client";

import { useState } from "react";

export interface ConfidenceData {
  level:      "Low" | "Medium" | "High" | "Very High";
  score:      number;
  reasons:    string[];
  breakdown?: Record<string, number>;
}

const LEVEL: Record<string, { bg: string; text: string; border: string; dot: string }> = {
  "Very High": {
    bg:     "bg-emerald-500/15",
    text:   "text-emerald-300",
    border: "border-emerald-500/30",
    dot:    "bg-emerald-400",
  },
  "High": {
    bg:     "bg-sky-500/15",
    text:   "text-sky-300",
    border: "border-sky-500/30",
    dot:    "bg-sky-400",
  },
  "Medium": {
    bg:     "bg-amber-500/15",
    text:   "text-amber-300",
    border: "border-amber-500/30",
    dot:    "bg-amber-400",
  },
  "Low": {
    bg:     "bg-rose-500/15",
    text:   "text-rose-400",
    border: "border-rose-500/30",
    dot:    "bg-rose-500",
  },
};

export function ConfidenceBadge({ data }: { data?: ConfidenceData | null }) {
  const [open, setOpen] = useState(false);

  if (!data) return null;

  const style = LEVEL[data.level] ?? LEVEL["Medium"];

  return (
    <div className="relative inline-block">
      <button
        onClick={e => { e.stopPropagation(); setOpen(o => !o); }}
        className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-all hover:opacity-90 ${style.bg} ${style.text} ${style.border}`}
      >
        <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
        {data.level}
        <span className="tabular-nums opacity-70">{data.score}%</span>
      </button>

      {open && data.reasons.length > 0 && (
        <div
          className="absolute right-0 top-full z-50 mt-1.5 w-64 rounded-xl border border-white/[0.08] bg-[#0e1826] p-3 shadow-2xl"
          onClick={e => e.stopPropagation()}
        >
          {/* Score bar */}
          <div className="mb-2.5">
            <div className="mb-1 flex items-center justify-between text-[10px]">
              <span className="font-semibold text-slate-400">Confidence Score</span>
              <span className={`font-bold tabular-nums ${style.text}`}>{data.score}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
              <div
                className={`h-full rounded-full transition-all ${style.dot}`}
                style={{ width: `${data.score}%` }}
              />
            </div>
          </div>

          {/* Reasons */}
          <p className="mb-1.5 text-[9px] font-bold uppercase tracking-widest text-slate-600">
            High Confidence Because:
          </p>
          <ul className="space-y-1">
            {data.reasons.map((r, i) => (
              <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-400">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-600" />
                {r}
              </li>
            ))}
          </ul>

          {/* Score breakdown */}
          {data.breakdown && Object.keys(data.breakdown).length > 0 && (
            <div className="mt-2.5 border-t border-white/[0.05] pt-2">
              <p className="mb-1.5 text-[9px] font-bold uppercase tracking-widest text-slate-600">
                Score Breakdown
              </p>
              {Object.entries(data.breakdown).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between text-[10px]">
                  <span className="capitalize text-slate-500">{k.replace(/_/g, " ")}</span>
                  <span className="tabular-nums text-slate-400">+{v.toFixed(1)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
