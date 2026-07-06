"use client";

import { useState } from "react";
import { ClipboardList } from "lucide-react";

interface ChecklistItem {
  label: string;
  priority: "critical" | "high" | "medium";
}

interface MonitoringChecklistProps {
  items?: ChecklistItem[];
}

const PRIORITY_DOT: Record<string, string> = {
  critical: "bg-rose-400",
  high:     "bg-amber-400",
  medium:   "bg-sky-400",
};

const PRIORITY_LABEL: Record<string, string> = {
  critical: "text-rose-400  border-rose-500/30  bg-rose-500/10",
  high:     "text-amber-400 border-amber-500/30 bg-amber-500/10",
  medium:   "text-sky-400   border-sky-500/30   bg-sky-500/10",
};

export function MonitoringChecklist({ items = [] }: MonitoringChecklistProps) {
  const [checked, setChecked] = useState<number[]>([]);

  const toggle = (i: number) =>
    setChecked(prev => prev.includes(i) ? prev.filter(x => x !== i) : [...prev, i]);

  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.025] p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-sky-500/[0.08] border border-sky-500/20">
            <ClipboardList className="h-3.5 w-3.5 text-sky-400" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">Monitoring Checklist</span>
        </div>
        {items.length > 0 && (
          <span className="text-[10px] text-slate-600">
            {checked.length}/{items.length} done
          </span>
        )}
      </div>

      {items.length === 0 ? (
        <p className="text-[12px] text-slate-400 leading-5">No data available</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, i) => {
            const isDone = checked.includes(i);
            return (
              <li key={i}>
                <button
                  onClick={() => toggle(i)}
                  className={`w-full flex items-center gap-3 rounded-[14px] border px-3 py-2.5 text-left transition-all ${
                    isDone
                      ? "border-white/[0.04] bg-white/[0.01] opacity-60"
                      : "border-white/[0.07] bg-white/[0.02] hover:border-sky-400/20 hover:bg-white/[0.04]"
                  }`}
                >
                  {/* Checkbox */}
                  <span
                    className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-all ${
                      isDone
                        ? "border-sky-500 bg-sky-500"
                        : "border-white/20 bg-transparent"
                    }`}
                  >
                    {isDone && (
                      <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 10 10" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M1.5 5l2.5 2.5 4.5-4.5" />
                      </svg>
                    )}
                  </span>

                  {/* Priority dot */}
                  <span className={`h-2 w-2 shrink-0 rounded-full ${PRIORITY_DOT[item.priority]}`} />

                  {/* Label */}
                  <span className={`flex-1 text-[12px] leading-5 ${isDone ? "line-through text-slate-600" : "text-slate-300"}`}>
                    {item.label}
                  </span>

                  {/* Priority badge */}
                  <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase ${PRIORITY_LABEL[item.priority]}`}>
                    {item.priority}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
