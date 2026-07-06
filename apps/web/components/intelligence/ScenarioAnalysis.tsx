"use client";

import { BarChart2 } from "lucide-react";

interface ScenarioBranch {
  probability: number;
  description: string;
  target?: string;
}

interface ScenarioAnalysisProps {
  bull?: ScenarioBranch;
  base?: ScenarioBranch;
  bear?: ScenarioBranch;
}

interface ScenarioCardProps {
  label: string;
  emoji?: string;
  accent: {
    bar:    string;
    border: string;
    bg:     string;
    text:   string;
    badge:  string;
  };
  data?: ScenarioBranch;
}

function ScenarioCard({ label, accent, data }: ScenarioCardProps) {
  if (!data) return null;
  return (
    <div className={`flex flex-col gap-3 rounded-[16px] border ${accent.border} ${accent.bg} p-4`}>
      {/* Label + probability */}
      <div className="flex items-center justify-between">
        <span className={`text-[10px] font-bold uppercase tracking-[0.12em] ${accent.text}`}>{label}</span>
        <span className={`rounded-full border px-2 py-0.5 text-[11px] font-black ${accent.badge}`}>
          {data.probability}%
        </span>
      </div>

      {/* Probability bar */}
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={`h-full rounded-full transition-all duration-700 ${accent.bar}`}
          style={{ width: `${data.probability}%` }}
        />
      </div>

      {/* Description */}
      <p className="text-[12px] text-slate-400 leading-5">{data.description}</p>

      {/* Target price */}
      {data.target && (
        <div className="flex items-center justify-between border-t border-white/[0.05] pt-2">
          <span className="text-[10px] text-slate-600">Target</span>
          <span className={`text-[13px] font-black ${accent.text}`}>{data.target}</span>
        </div>
      )}
    </div>
  );
}

export function ScenarioAnalysis({ bull, base, bear }: ScenarioAnalysisProps) {
  const hasData = bull || base || bear;

  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.025] p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-sky-500/[0.08] border border-sky-500/20">
          <BarChart2 className="h-3.5 w-3.5 text-sky-400" />
        </div>
        <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">Scenario Analysis</span>
      </div>

      {!hasData ? (
        <p className="text-[12px] text-slate-400 leading-5">No data available</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <ScenarioCard
            label="Bull Case"
            data={bull}
            accent={{
              bar:    "bg-emerald-500",
              border: "border-emerald-500/20",
              bg:     "bg-emerald-500/[0.04]",
              text:   "text-emerald-400",
              badge:  "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
            }}
          />
          <ScenarioCard
            label="Base Case"
            data={base}
            accent={{
              bar:    "bg-sky-500",
              border: "border-sky-500/20",
              bg:     "bg-sky-500/[0.04]",
              text:   "text-sky-400",
              badge:  "border-sky-500/30 bg-sky-500/10 text-sky-300",
            }}
          />
          <ScenarioCard
            label="Bear Case"
            data={bear}
            accent={{
              bar:    "bg-rose-500",
              border: "border-rose-500/20",
              bg:     "bg-rose-500/[0.04]",
              text:   "text-rose-400",
              badge:  "border-rose-500/30 bg-rose-500/10 text-rose-300",
            }}
          />
        </div>
      )}
    </div>
  );
}
