"use client";

import { Target, ChevronRight } from "lucide-react";

export interface InvestmentThesisCardProps {
  /** Executive summary — the core investment thesis statement */
  thesis?: string;
  /** Why this matters to investors */
  whyItMatters?: string;
  /** Business or market impact description */
  businessImpact?: string;
  /** Key growth or opportunity drivers */
  keyDrivers?: string[];
  /** 0–100 AI confidence score */
  confidence?: number;
  /** Investment time horizon e.g. "Medium-term (6–18 months)" */
  timeHorizon?: string;
  /** Key assumptions underpinning the thesis (collapsible) */
  assumptions?: string[];
  /** Risk factors that could invalidate the thesis (collapsible) */
  riskFactors?: string[];
  /** ISO date string or human-readable label */
  lastUpdated?: string;
}

function confidenceStyle(c: number) {
  if (c >= 75) return "text-emerald-400 border-emerald-500/30 bg-emerald-500/10";
  if (c >= 50) return "text-sky-400 border-sky-500/30 bg-sky-500/10";
  if (c >= 30) return "text-amber-400 border-amber-500/30 bg-amber-500/10";
  return "text-rose-400 border-rose-500/30 bg-rose-500/10";
}

export function InvestmentThesisCard({
  thesis,
  whyItMatters,
  businessImpact,
  keyDrivers = [],
  confidence = 0,
  timeHorizon,
  assumptions = [],
  riskFactors = [],
  lastUpdated,
}: InvestmentThesisCardProps) {
  const hasContent =
    thesis || whyItMatters || businessImpact ||
    keyDrivers.length > 0 || assumptions.length > 0 || riskFactors.length > 0;

  if (!hasContent) {
    return (
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.025] p-5">
        <div className="flex items-center gap-2 mb-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-500/[0.04] border border-violet-500/20">
            <Target className="h-3.5 w-3.5 text-violet-400" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">Investment Thesis</span>
        </div>
        <p className="text-[12px] text-slate-400 leading-5">No data available</p>
      </div>
    );
  }

  return (
    <div className="rounded-[20px] border border-violet-500/20 bg-violet-500/[0.04] p-5 space-y-4">

      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-500/[0.08] border border-violet-500/20">
            <Target className="h-3.5 w-3.5 text-violet-400" />
          </div>
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">Investment Thesis</span>
        </div>
        {confidence > 0 && (
          <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${confidenceStyle(confidence)}`}>
            {confidence}% Confidence
          </span>
        )}
      </div>

      {/* ── Executive Summary ─────────────────────────────────────────── */}
      {thesis && (
        <p className="text-[13px] text-slate-200 leading-6">{thesis}</p>
      )}

      {/* ── Time horizon ──────────────────────────────────────────────── */}
      {timeHorizon && (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-[11px] font-medium text-violet-300">
          <span className="h-1.5 w-1.5 rounded-full bg-violet-400" />
          {timeHorizon}
        </span>
      )}

      {/* ── Why It Matters + Business Impact ─────────────────────────── */}
      {(whyItMatters || businessImpact) && (
        <div className={`grid gap-3 ${whyItMatters && businessImpact ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1"}`}>
          {whyItMatters && (
            <div className="rounded-[14px] border border-violet-500/15 bg-violet-500/[0.04] p-3">
              <p className="mb-1 text-[9px] font-bold uppercase tracking-[0.10em] text-violet-400">Why It Matters</p>
              <p className="text-[12px] leading-5 text-slate-300">{whyItMatters}</p>
            </div>
          )}
          {businessImpact && (
            <div className="rounded-[14px] border border-sky-500/15 bg-sky-500/[0.04] p-3">
              <p className="mb-1 text-[9px] font-bold uppercase tracking-[0.10em] text-sky-400">Business Impact</p>
              <p className="text-[12px] leading-5 text-slate-300">{businessImpact}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Key Drivers ───────────────────────────────────────────────── */}
      {keyDrivers.length > 0 && (
        <div>
          <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.10em] text-emerald-400">Key Drivers</p>
          <ul className="space-y-1.5">
            {keyDrivers.map((d, i) => (
              <li key={i} className="flex items-start gap-2 text-[12px] text-slate-300 leading-5">
                <ChevronRight className="mt-0.5 h-3 w-3 shrink-0 text-emerald-400" />
                {d}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Assumptions (collapsible) ─────────────────────────────────── */}
      {assumptions.length > 0 && (
        <details className="group">
          <summary className="flex cursor-pointer items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 hover:text-slate-400 transition list-none">
            <span className="inline-block transition-transform group-open:rotate-90">›</span>
            Key Assumptions ({assumptions.length})
          </summary>
          <ul className="mt-2 space-y-1.5 pl-3">
            {assumptions.map((a, i) => (
              <li key={i} className="flex items-start gap-1.5 text-[12px] text-slate-400 leading-5">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-violet-400" />
                {a}
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* ── Risk Factors (collapsible) ────────────────────────────────── */}
      {riskFactors.length > 0 && (
        <details className="group">
          <summary className="flex cursor-pointer items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500 hover:text-slate-400 transition list-none">
            <span className="inline-block transition-transform group-open:rotate-90">›</span>
            Risk Factors ({riskFactors.length})
          </summary>
          <ul className="mt-2 space-y-1.5 pl-3">
            {riskFactors.map((r, i) => (
              <li key={i} className="flex items-start gap-1.5 text-[12px] text-slate-400 leading-5">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-rose-400" />
                {r}
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* ── Last Updated ──────────────────────────────────────────────── */}
      {lastUpdated && (
        <p className="text-[10px] text-slate-600 pt-1 border-t border-white/[0.04]">
          Updated: {lastUpdated}
        </p>
      )}
    </div>
  );
}

/** @deprecated Use InvestmentThesisCard instead */
export const InvestmentThesis = InvestmentThesisCard;
