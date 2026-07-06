"use client";

import { Activity, TrendingUp } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

export type LifecycleStage =
  | "emerging"
  | "developing"
  | "strong-momentum"
  | "mature"
  | "overheated";

export interface OpportunityLifecycleCardProps {
  /** Current lifecycle stage */
  stage?: LifecycleStage;
  /** Brief description of the current situation */
  description?: string;
  /** Why the AI assigned this particular stage */
  whyAssigned?: string;
  /** A comparable historical opportunity for context */
  historicalComparison?: string;
  /** 0–100 AI confidence in the stage assignment */
  confidence?: number;
  /** What is expected to happen as the opportunity evolves */
  expectedEvolution?: string;
  /** Risks specific to this lifecycle stage */
  risks?: string[];
}

// ── Stage definitions ─────────────────────────────────────────────────────────

interface StageDef {
  id: LifecycleStage;
  label: string;
  shortLabel: string;
  accent: string;
  border: string;
  bg: string;
  ring: string;
  fill: string;
  text: string;
  tagBorder: string;
  tagBg: string;
  blurb: string;
}

const STAGE_DEFS: StageDef[] = [
  {
    id:         "emerging",
    label:      "Emerging",
    shortLabel: "Emerging",
    accent:     "violet",
    border:     "border-violet-500/30",
    bg:         "bg-violet-500/[0.08]",
    ring:       "ring-violet-500/20",
    fill:       "bg-violet-400",
    text:       "text-violet-400",
    tagBorder:  "border-violet-500/30",
    tagBg:      "bg-violet-500/10",
    blurb:      "First signals detected. Low confidence, early positioning possible.",
  },
  {
    id:         "developing",
    label:      "Developing",
    shortLabel: "Developing",
    accent:     "sky",
    border:     "border-sky-500/30",
    bg:         "bg-sky-500/[0.08]",
    ring:       "ring-sky-500/20",
    fill:       "bg-sky-400",
    text:       "text-sky-400",
    tagBorder:  "border-sky-500/30",
    tagBg:      "bg-sky-500/10",
    blurb:      "Multiple confirming signals. Confidence rising, opportunity strengthening.",
  },
  {
    id:         "strong-momentum",
    label:      "Strong Momentum",
    shortLabel: "Momentum",
    accent:     "emerald",
    border:     "border-emerald-500/30",
    bg:         "bg-emerald-500/[0.08]",
    ring:       "ring-emerald-500/20",
    fill:       "bg-emerald-400",
    text:       "text-emerald-400",
    tagBorder:  "border-emerald-500/30",
    tagBg:      "bg-emerald-500/10",
    blurb:      "Maximum catalyst intensity. Highest opportunity score, widest coverage.",
  },
  {
    id:         "mature",
    label:      "Mature",
    shortLabel: "Mature",
    accent:     "amber",
    border:     "border-amber-500/30",
    bg:         "bg-amber-500/[0.08]",
    ring:       "ring-amber-500/20",
    fill:       "bg-amber-400",
    text:       "text-amber-400",
    tagBorder:  "border-amber-500/30",
    tagBg:      "bg-amber-500/10",
    blurb:      "Opportunity well-known, consensus forming. Alpha potential declining.",
  },
  {
    id:         "overheated",
    label:      "Overheated",
    shortLabel: "Overheated",
    accent:     "rose",
    border:     "border-rose-500/30",
    bg:         "bg-rose-500/[0.08]",
    ring:       "ring-rose-500/20",
    fill:       "bg-rose-400",
    text:       "text-rose-400",
    tagBorder:  "border-rose-500/30",
    tagBg:      "bg-rose-500/10",
    blurb:      "Catalysts fading, outcome becoming clear. Exit timing relevant.",
  },
];

function confidenceCls(c: number) {
  if (c >= 75) return "text-emerald-400 border-emerald-500/30 bg-emerald-500/10";
  if (c >= 50) return "text-sky-400 border-sky-500/30 bg-sky-500/10";
  if (c >= 30) return "text-amber-400 border-amber-500/30 bg-amber-500/10";
  return "text-rose-400 border-rose-500/30 bg-rose-500/10";
}

// ── Component ─────────────────────────────────────────────────────────────────

export function OpportunityLifecycleCard({
  stage,
  description,
  whyAssigned,
  historicalComparison,
  confidence = 0,
  expectedEvolution,
  risks = [],
}: OpportunityLifecycleCardProps) {
  const currentIndex = STAGE_DEFS.findIndex(s => s.id === stage);
  const current = currentIndex >= 0 ? STAGE_DEFS[currentIndex] : null;

  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.025] p-5 space-y-4">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-500/[0.08] border border-violet-500/20"
            aria-hidden="true">
            <Activity className="h-3.5 w-3.5 text-violet-400" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
            Opportunity Lifecycle
          </span>
        </div>
        {confidence > 0 && (
          <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${confidenceCls(confidence)}`}
            aria-label={`AI confidence: ${confidence}%`}>
            {confidence}% Confidence
          </span>
        )}
      </div>

      {!stage ? (
        <p className="text-[12px] text-slate-400 leading-5">No lifecycle data available</p>
      ) : (
        <>
          {/* ── Stage progression ─────────────────────────────────────── */}
          <div
            role="progressbar"
            aria-valuenow={currentIndex + 1}
            aria-valuemin={1}
            aria-valuemax={STAGE_DEFS.length}
            aria-label={`Opportunity lifecycle: ${current?.label ?? "Unknown"}`}
            className="relative flex items-start justify-between"
          >
            {/* Track line */}
            <div className="absolute left-0 right-0 top-3.5 h-px bg-white/[0.07]" aria-hidden="true" />

            {STAGE_DEFS.map((s, i) => {
              const isCurrent = i === currentIndex;
              const isPast    = i < currentIndex;
              const isFuture  = i > currentIndex;

              return (
                <div key={s.id} className="relative z-10 flex flex-1 flex-col items-center gap-2">
                  {/* Dot */}
                  <span
                    aria-hidden="true"
                    className={[
                      "flex items-center justify-center rounded-full border transition-all",
                      isCurrent ? `h-7 w-7 ${s.border} ${s.bg} ring-4 ${s.ring}` :
                      isPast    ? "h-4 w-4 border-slate-500 bg-slate-600" :
                                  "h-4 w-4 border-white/10 bg-transparent",
                    ].join(" ")}
                  >
                    {isCurrent && (
                      <span className={`h-2.5 w-2.5 rounded-full ${s.fill}`} />
                    )}
                  </span>

                  {/* Label */}
                  <span
                    className={[
                      "text-center text-[9px] font-bold uppercase tracking-wide leading-tight max-w-[58px] transition-all",
                      isCurrent ? s.text : isFuture ? "text-slate-700" : "text-slate-500",
                    ].join(" ")}
                  >
                    {s.shortLabel}
                  </span>
                </div>
              );
            })}
          </div>

          {/* ── Current stage pill + blurb ────────────────────────────── */}
          {current && (
            <div className={`rounded-[14px] border ${current.tagBorder} ${current.tagBg} px-4 py-3`}>
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`h-1.5 w-1.5 rounded-full ${current.fill}`} aria-hidden="true" />
                <p className={`text-[10px] font-bold uppercase tracking-[0.10em] ${current.text}`}>
                  Currently: {current.label}
                </p>
              </div>
              <p className="text-[12px] text-slate-300 leading-5">
                {description || current.blurb}
              </p>
            </div>
          )}

          {/* ── Why AI assigned this stage ────────────────────────────── */}
          {whyAssigned && (
            <div>
              <p className="mb-1.5 text-[9px] font-bold uppercase tracking-[0.10em] text-slate-500">
                Why This Stage
              </p>
              <p className="text-[12px] text-slate-400 leading-5">{whyAssigned}</p>
            </div>
          )}

          {/* ── Historical comparison ─────────────────────────────────── */}
          {historicalComparison && (
            <div className="rounded-[12px] border border-white/[0.05] bg-white/[0.02] px-3 py-2.5">
              <p className="mb-1 text-[9px] font-bold uppercase tracking-[0.10em] text-slate-500">
                Historical Comparison
              </p>
              <p className="text-[12px] text-slate-400 leading-5">{historicalComparison}</p>
            </div>
          )}

          {/* ── Expected evolution ────────────────────────────────────── */}
          {expectedEvolution && (
            <div>
              <p className="mb-1.5 text-[9px] font-bold uppercase tracking-[0.10em] text-emerald-500">
                Expected Evolution
              </p>
              <div className="flex items-start gap-2">
                <TrendingUp className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" aria-hidden="true" />
                <p className="text-[12px] text-slate-300 leading-5">{expectedEvolution}</p>
              </div>
            </div>
          )}

          {/* ── Stage-specific risks ──────────────────────────────────── */}
          {risks.length > 0 && (
            <details className="group">
              <summary className="flex cursor-pointer items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 hover:text-slate-400 transition list-none">
                <span className="inline-block transition-transform group-open:rotate-90" aria-hidden="true">›</span>
                Stage Risks ({risks.length})
              </summary>
              <ul className="mt-2 space-y-1.5 pl-3" role="list">
                {risks.map((r, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-[12px] text-slate-400 leading-5">
                    <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-rose-400" aria-hidden="true" />
                    {r}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </div>
  );
}

/** @deprecated Use OpportunityLifecycleCard instead */
export const OpportunityLifecycle = OpportunityLifecycleCard;
