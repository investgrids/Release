"use client";

import { Gauge } from "lucide-react";

export interface ConfidenceBreakdown {
  evidence_quality: number;
  market_confirmation: number;
  historical_similarity: number;
  data_freshness: number;
  reasoning_confidence: number;
  final_confidence: number;
  level: string;
  reasons: string[];
}

const FACTORS: { key: keyof ConfidenceBreakdown; label: string; hint: string }[] = [
  { key: "evidence_quality", label: "Evidence Quality", hint: "Sources, company & sector confirmation" },
  { key: "market_confirmation", label: "Market Confirmation", hint: "Does live price/market action agree?" },
  { key: "historical_similarity", label: "Historical Match", hint: "How closely past precedents line up" },
  { key: "data_freshness", label: "Data Freshness", hint: "How recent the underlying evidence is" },
  { key: "reasoning_confidence", label: "AI Reasoning", hint: "The model's own self-rated certainty" },
];

function barColor(v: number) {
  return v >= 70 ? "from-emerald-500 to-emerald-300" : v >= 40 ? "from-amber-500 to-amber-300" : "from-rose-500 to-rose-300";
}

/**
 * Confidence Explainability (Phase 2C) — renders confidence_breakdown,
 * computed server-side by postprocess.py's compute_confidence_breakdown
 * (never LLM-guessed — see that function's docstring: final_confidence IS
 * V2's own calculate_confidence() engine, these 5 factors are a readable
 * view over that engine's real internal signals). Only 5 factors because
 * that's what the engine actually scores — not the 6 an earlier wishlist
 * named (News/Financials/Policy separately), since those aren't separately
 * computed and fabricating a split would misrepresent the real number.
 */
export function ConfidenceBreakdownPanel({ breakdown }: { breakdown: ConfidenceBreakdown | null | undefined }) {
  if (!breakdown) return null;

  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Gauge size={14} strokeWidth={1.8} className="text-violet-400" />
          <p className="text-[15px] font-semibold text-text-primary">Why This Confidence Score</p>
        </div>
        <p className="text-[12px] font-bold tabular-nums text-text-primary">
          {Math.round(breakdown.final_confidence)}% <span className="text-text-muted font-medium">· {breakdown.level}</span>
        </p>
      </div>

      <div className="space-y-3">
        {FACTORS.map(f => {
          const v = Math.max(0, Math.min(100, Number(breakdown[f.key]) || 0));
          return (
            <div key={f.key}>
              <div className="mb-1 flex items-baseline justify-between">
                <p className="text-[11px] font-medium text-text-secondary">{f.label}</p>
                <p className="text-[10px] tabular-nums text-text-muted">{Math.round(v)}%</p>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-text-primary/[0.06]">
                <div className={`h-full rounded-full bg-gradient-to-r ${barColor(v)}`} style={{ width: `${v}%` }} />
              </div>
              <p className="mt-0.5 text-[9.5px] text-text-muted">{f.hint}</p>
            </div>
          );
        })}
      </div>

      {breakdown.reasons?.length > 0 && (
        <div className="mt-4 border-t border-surface-border/6 pt-3">
          <p className="mb-1.5 text-[9px] uppercase tracking-wider text-text-muted">Why</p>
          <ul className="space-y-1">
            {breakdown.reasons.slice(0, 4).map((r, i) => (
              <li key={i} className="text-[11px] leading-snug text-text-secondary">• {r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
