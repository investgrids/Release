"use client";

import { Zap, CalendarDays, CalendarRange, Calendar, Hourglass } from "lucide-react";

export interface TimelineIntelligence {
  immediate?: string;
  one_week?: string;
  one_to_three_months?: string;
  six_to_twelve_months?: string;
  one_to_three_years?: string;
}

const STAGES: { key: keyof TimelineIntelligence; label: string; icon: React.ReactNode }[] = [
  { key: "immediate", label: "Immediate", icon: <Zap className="h-3.5 w-3.5" /> },
  { key: "one_week", label: "1 Week", icon: <CalendarDays className="h-3.5 w-3.5" /> },
  { key: "one_to_three_months", label: "1–3 Months", icon: <CalendarRange className="h-3.5 w-3.5" /> },
  { key: "six_to_twelve_months", label: "6–12 Months", icon: <Calendar className="h-3.5 w-3.5" /> },
  { key: "one_to_three_years", label: "1–3 Years", icon: <Hourglass className="h-3.5 w-3.5" /> },
];

/**
 * Decision Timeline (Phase 2C) — renders timeline_intelligence, a V3-only
 * field the backend has computed since Phase 1 but no UI ever surfaced
 * (V2's market_impact_horizons occupied the equivalent slot; V3 doesn't
 * populate that field at all). Each stage is the specialist's own 1-sentence
 * projection for that horizon — real model output, not a fabricated verdict
 * re-scored per stage (the schema only asks the model for narrative text
 * here, not a discrete verdict per horizon).
 */
export function DecisionTimelinePanel({ timeline }: { timeline: TimelineIntelligence | null | undefined }) {
  const stages = STAGES.filter(s => timeline?.[s.key]);
  if (stages.length === 0) return null;

  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
      <p className="mb-5 text-[15px] font-semibold text-text-primary">Decision Timeline</p>

      <div className="relative grid gap-4" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }}>
        <div className="absolute left-0 right-0 top-[15px] hidden h-px bg-text-primary/[0.08] sm:block" />
        {stages.map(s => (
          <div key={s.key} className="relative flex flex-col items-center text-center">
            <div className="z-10 flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full border border-violet-500/30 bg-surface-card text-violet-600 dark:text-violet-300">
              {s.icon}
            </div>
            <p className="mt-2 text-[10px] font-semibold uppercase tracking-wider text-text-secondary">{s.label}</p>
            <p className="mt-1.5 text-[11px] leading-relaxed text-text-secondary">{timeline?.[s.key]}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
