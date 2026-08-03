"use client";

import { CheckCircle2, Circle, XCircle, AlertTriangle, ShieldCheck } from "lucide-react";

// ── Compliant verdict-scale mapping ─────────────────────────────────────────
// decision_engine_v2.verdict_scale is one of 6 research-framed labels (see
// backend schema.py's VERDICT_SCALE) — never "Buy/Sell/Hold/Accumulate/
// Reduce". The 4 "quick decision" pills below preserve the decisive,
// color-coded, single-active-pill UX the design called for, using that same
// compliant language rather than investment-advice wording.
const VERDICT_COLOR: Record<string, string> = {
  "Strong Positive": "text-emerald-400",
  "Positive": "text-emerald-400/80",
  "Neutral": "text-amber-400",
  "Cautious": "text-amber-400",
  "Negative": "text-rose-400",
  "Strong Negative": "text-rose-400",
};
const VERDICT_DOT: Record<string, string> = {
  "Strong Positive": "bg-emerald-400",
  "Positive": "bg-emerald-400/70",
  "Neutral": "bg-amber-400",
  "Cautious": "bg-amber-400",
  "Negative": "bg-rose-500",
  "Strong Negative": "bg-rose-500",
};
const VERDICT_BORDER_BG: Record<string, string> = {
  "Strong Positive": "border-emerald-500/30 bg-emerald-500/10",
  "Positive": "border-emerald-500/25 bg-emerald-500/[0.06]",
  "Neutral": "border-amber-500/25 bg-amber-500/[0.06]",
  "Cautious": "border-amber-500/30 bg-amber-500/10",
  "Negative": "border-rose-500/25 bg-rose-500/[0.06]",
  "Strong Negative": "border-rose-500/30 bg-rose-500/10",
};

type PillKey = "favorable" | "neutral" | "watch" | "unfavorable";

const PILLS: { key: PillKey; label: string; icon: typeof CheckCircle2 }[] = [
  { key: "favorable", label: "Favorable Case", icon: CheckCircle2 },
  { key: "neutral", label: "Neutral", icon: Circle },
  { key: "watch", label: "Watch Closely", icon: AlertTriangle },
  { key: "unfavorable", label: "Unfavorable Case", icon: XCircle },
];

function verdictToPill(verdictScale: string): PillKey {
  switch (verdictScale) {
    case "Strong Positive":
    case "Positive":
      return "favorable";
    case "Cautious":
      return "watch";
    case "Negative":
    case "Strong Negative":
      return "unfavorable";
    default:
      return "neutral";
  }
}

const EVIDENCE_LABELS: Record<string, string> = {
  live_market_events: "News",
  historical_precedent: "Historical",
  company_filings: "Financials",
  real_time_price_data: "Market Data",
  government_data: "Policies",
};
// Fixed display order — matches the spec's News / Historical / Financials /
// Market / Policies sequence regardless of the backend dict's key order.
const EVIDENCE_ORDER = ["live_market_events", "historical_precedent", "company_filings", "real_time_price_data", "government_data"];

function clamp01to100(n: number): number {
  return Math.max(0, Math.min(100, Math.round(n)));
}

/** Weighted severity share of a {high,medium,low} bucket, 0-100. Null when
 *  the matrix has no items at all (real "no data" signal, not a fabricated
 *  midpoint) so the caller can fall back to a different real signal. */
function weightedShare(bucket: { high?: string[]; medium?: string[]; low?: string[] } | undefined): number | null {
  if (!bucket) return null;
  const h = bucket.high?.length ?? 0, m = bucket.medium?.length ?? 0, l = bucket.low?.length ?? 0;
  const total = h + m + l;
  if (!total) return null;
  const weighted = h * 3 + m * 2 + l * 1;
  return clamp01to100((weighted / (total * 3)) * 100);
}

export interface HeroVerdictData {
  verdictScale: string;
  why: string;
  confidence: number | null;
  confidenceLevel?: string;
  horizon: string;
  suitableFor: string;
  riskLabel: string;
  riskColor: string;
  conclusion: string; // ai_conclusion.reason, max-2-line one-liner
  opportunityPct: number;
  riskPct: number;
  evidenceStars: number;
  evidenceChecklist: Record<string, boolean>;
  sourceCount: number;
}

/**
 * The signature "understand the answer in under 10 seconds" panel. Renders
 * nothing when the V3 fields it needs aren't present (V2 responses, or a
 * degraded/synthesis_incomplete V3 response) — no placeholder metrics, per
 * the Phase 1.5 Hero spec's engineering rules.
 */
export function InvestmentVerdictHero({ data }: { data: HeroVerdictData }) {
  const pill = verdictToPill(data.verdictScale);
  const verdictColor = VERDICT_COLOR[data.verdictScale] ?? "text-amber-400";
  const verdictDot = VERDICT_DOT[data.verdictScale] ?? "bg-amber-400";
  const verdictBg = VERDICT_BORDER_BG[data.verdictScale] ?? "border-amber-500/25 bg-amber-500/[0.06]";

  return (
    <div className={`rounded-[24px] border p-6 sm:p-7 ${verdictBg}`}>
      {/* Verdict badge row */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 mb-4">
        <span className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12px] font-semibold ${verdictBg} ${verdictColor}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${verdictDot}`} />
          {data.verdictScale}
        </span>
        <span className="text-[11px] text-text-muted">·</span>
        <span className="text-[11px] text-text-secondary">
          Confidence <span className="font-semibold text-text-primary tabular-nums">{data.confidence ?? "—"}%</span>
        </span>
        <span className="text-[11px] text-text-muted">·</span>
        <span className="text-[11px] text-text-secondary">{data.horizon}</span>
        <span className="text-[11px] text-text-muted">·</span>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold ${data.riskColor}`}>{data.riskLabel} Risk</span>
        <span className="text-[11px] text-text-muted">·</span>
        <span className="text-[11px] text-text-secondary">{data.suitableFor}</span>
      </div>

      {/* One-line AI conclusion */}
      {data.conclusion && (
        <p className="text-[16px] sm:text-[17px] font-medium leading-snug text-text-primary mb-5 line-clamp-2">
          {data.conclusion}
        </p>
      )}

      {/* Opportunity vs Risk meter */}
      <div className="grid grid-cols-2 gap-4 mb-5">
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] uppercase tracking-widest text-emerald-400/80 font-semibold">Opportunity</span>
            <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-300 tabular-nums">{data.opportunityPct}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-text-primary/[0.06] overflow-hidden">
            <div className="h-full rounded-full bg-emerald-400 transition-all duration-700" style={{ width: `${data.opportunityPct}%` }} />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] uppercase tracking-widest text-rose-400/80 font-semibold">Risk</span>
            <span className="text-[11px] font-semibold text-rose-600 dark:text-rose-300 tabular-nums">{data.riskPct}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-text-primary/[0.06] overflow-hidden">
            <div className="h-full rounded-full bg-rose-400 transition-all duration-700" style={{ width: `${data.riskPct}%` }} />
          </div>
        </div>
      </div>

      {/* Quick decision pills — only one active, matching the current verdict */}
      <div className="flex flex-wrap gap-2 mb-5">
        {PILLS.map(p => {
          const active = p.key === pill;
          const Icon = p.icon;
          return (
            <span key={p.key}
              className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11.5px] font-medium transition ${
                active ? `${verdictBg} ${verdictColor} border-current/40` : "border-surface-border/6 bg-text-primary/[0.02] text-text-muted"
              }`}>
              <Icon className="h-3 w-3" strokeWidth={2.5} />
              {p.label}
            </span>
          );
        })}
      </div>

      {/* Evidence score */}
      <div className="flex items-center gap-2 flex-wrap pt-4 border-t border-surface-border/6">
        <div className="flex items-center gap-1 mr-1">
          <ShieldCheck className="h-3.5 w-3.5 text-violet-400" />
          <span className="text-[10px] uppercase tracking-widest text-text-muted font-semibold">Evidence</span>
          <span className="text-[11px] font-semibold text-text-secondary tabular-nums ml-0.5">{data.evidenceStars}/5</span>
        </div>
        {EVIDENCE_ORDER.filter(k => k in data.evidenceChecklist).map(key => {
          const backed = data.evidenceChecklist[key];
          return (
            <span key={key}
              className={`rounded-md border px-2 py-0.5 text-[10px] font-medium ${
                backed ? "border-violet-500/25 bg-violet-500/10 text-violet-600 dark:text-violet-300" : "border-surface-border/5 bg-text-primary/[0.02] text-text-muted"
              }`}>
              {EVIDENCE_LABELS[key] ?? key}
            </span>
          );
        })}
        <span className="ml-auto text-[10px] text-text-muted tabular-nums">{data.sourceCount} source{data.sourceCount === 1 ? "" : "s"}</span>
      </div>
    </div>
  );
}

export { weightedShare, clamp01to100 };
