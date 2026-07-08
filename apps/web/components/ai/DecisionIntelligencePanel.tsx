"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeftRight, Brain, Scale, ShieldAlert, TrendingUp, TrendingDown,
  Minus, ChevronDown, ChevronUp, CircleDot, CheckCircle2, XCircle,
  HelpCircle, Clock, AlertTriangle, Sparkles, Building2, Target,
  ArrowRight, Zap,
} from "lucide-react";
import { InvestmentThesisCard } from "@/components/intelligence/InvestmentThesis";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface HoldingAnalysis {
  entity: string;
  symbol: string;
  sector: string;
  thesis: string;
  strengths: string[];
  risks: string[];
  catalysts: string[];
  near_term_outlook: "positive" | "cautious" | "neutral" | "negative";
  confidence: number;
  entity_type?: "company" | "sector" | "commodity";
}

export interface ComparisonRow {
  dimension: string;
  holding: string;
  target: string;
  advantage: "holding" | "target" | "neutral";
}

export interface TradeoffData {
  reasons_to_switch: string[];
  reasons_to_hold: string[];
  risks_of_switching: string[];
  risks_of_holding: string[];
  when_to_wait: string;
}

export interface DecisionFramework {
  supports_switch: string[];
  argues_against: string[];
  key_unknowns: string[];
  ai_stance: string;
}

export interface DecisionIntelligence {
  intent: string;
  detected_holding: string | null;
  detected_target: string | null;
  detected_horizon: string | null;
  detected_risk: string | null;
  context_complete: boolean;
  missing_context: string[];
  decision_summary: string;
  holding_analysis?: HoldingAnalysis;
  target_analysis?: HoldingAnalysis;
  comparison?: ComparisonRow[];
  tradeoff?: TradeoffData;
  decision_framework?: DecisionFramework;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const INTENT_LABELS: Record<string, { label: string; color: string }> = {
  switch:           { label: "Switch Analysis",     color: "text-sky-400 bg-sky-500/10 border-sky-500/30" },
  hold:             { label: "Hold Analysis",       color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" },
  compare:          { label: "Comparison",          color: "text-violet-400 bg-violet-500/10 border-violet-500/30" },
  sell:             { label: "Exit Analysis",       color: "text-amber-400 bg-amber-500/10 border-amber-500/30" },
  buy:              { label: "Entry Analysis",      color: "text-teal-400 bg-teal-500/10 border-teal-500/30" },
  list_picks:       { label: "Stock Picks",         color: "text-orange-400 bg-orange-500/10 border-orange-500/30" },
  news_reaction:    { label: "News Reaction",       color: "text-rose-400 bg-rose-500/10 border-rose-500/30" },
  earnings_preview: { label: "Earnings Preview",    color: "text-amber-400 bg-amber-500/10 border-amber-500/30" },
  entry_timing:     { label: "Entry Timing",        color: "text-teal-400 bg-teal-500/10 border-teal-500/30" },
  portfolio_review: { label: "Portfolio Analysis",  color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/30" },
  decision:         { label: "Decision Analysis",   color: "text-violet-400 bg-violet-500/10 border-violet-500/30" },
};

const OUTLOOK_CONFIG = {
  positive: { label: "Positive",  icon: TrendingUp,   color: "text-emerald-400" },
  cautious: { label: "Cautious",  icon: AlertTriangle, color: "text-amber-400" },
  neutral:  { label: "Neutral",   icon: Minus,        color: "text-slate-400" },
  negative: { label: "Negative",  icon: TrendingDown, color: "text-rose-400" },
};

function ScoreRing({ score, size = 44 }: { score: number; size?: number }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = score >= 75 ? "#34d399" : score >= 55 ? "#60a5fa" : "#f59e0b";
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="4" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.8s ease" }} />
      <text x={size / 2} y={size / 2 + 5} textAnchor="middle" fill="white"
        fontSize={size > 44 ? "13" : "11"} fontWeight="700"
        style={{ transform: `rotate(90deg) translate(0px, -${size}px)` }}>
        {score}
      </text>
    </svg>
  );
}

// ── Intent Badge ──────────────────────────────────────────────────────────────
export function IntentBadge({ intent }: { intent: string }) {
  const cfg = INTENT_LABELS[intent] ?? INTENT_LABELS.decision;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-[0.08em] ${cfg.color}`}>
      <Brain className="h-3 w-3" />
      Decision Intelligence · {cfg.label}
    </span>
  );
}

// ── Follow-up Context Panel ───────────────────────────────────────────────────
const HORIZON_OPTS = ["1 Month", "3 Months", "6 Months", "1 Year", "3–5 Years"];
const RISK_OPTS    = ["Conservative", "Moderate", "Aggressive"];
const GOAL_OPTS    = ["Capital Appreciation", "Wealth Creation", "Dividend Income", "Defensive", "Sector Rotation"];

interface FollowUpContextPanelProps {
  missing: string[];
  query: string;
  onRefine: (q: string) => void;
  detectedHorizon?: string | null;
  detectedRisk?: string | null;
}

function stripRefinements(q: string): string {
  return q
    .replace(/,\s*for a .+? investment horizon/gi, "")
    .replace(/,\s*with a .+? risk appetite/gi, "")
    .replace(/,\s*aiming for .+?(?=,|$)/gi, "")
    .trim();
}

export function FollowUpContextPanel({ missing, query, onRefine, detectedHorizon, detectedRisk }: FollowUpContextPanelProps) {
  const norm = (s: string) => s.toLowerCase().replace(/[–—-]/g, "-").trim();
  const initHorizon = HORIZON_OPTS.find(h => {
    if (!detectedHorizon) return false;
    const d = norm(detectedHorizon), o = norm(h);
    return o === d || o.includes(d) || d.includes(o);
  }) ?? null;
  const initRisk = RISK_OPTS.find(r =>
    detectedRisk && norm(r) === norm(detectedRisk)
  ) ?? null;

  const [horizon, setHorizon] = useState<string | null>(initHorizon);
  const [risk,    setRisk]    = useState<string | null>(initRisk);
  const [goal,    setGoal]    = useState<string | null>(null);

  function buildRefined() {
    const base = stripRefinements(query);
    const parts: string[] = [base];
    if (horizon) parts.push(`for a ${horizon} investment horizon`);
    if (risk)    parts.push(`with a ${risk.toLowerCase()} risk appetite`);
    if (goal)    parts.push(`aiming for ${goal.toLowerCase()}`);
    onRefine(parts.join(", "));
  }

  const anySelected = horizon || risk || goal;

  return (
    <div className="rounded-[20px] border border-amber-500/20 bg-amber-500/[0.04] p-5 space-y-4">
      <div className="flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/10 border border-amber-500/20">
          <HelpCircle className="h-4 w-4 text-amber-400" />
        </div>
        <div>
          <p className="text-[13px] font-semibold text-white">Refine Your Analysis</p>
          <p className="text-[11px] text-slate-400">Adding context improves the quality of the decision intelligence</p>
        </div>
      </div>

      {(missing.includes("investment_horizon") || !missing.length) && (
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.10em] text-slate-500 mb-2">
            <Clock className="inline h-3 w-3 mr-1" />Investment Horizon
          </p>
          <div className="flex flex-wrap gap-2">
            {HORIZON_OPTS.map(h => (
              <button key={h} onClick={() => setHorizon(h === horizon ? null : h)}
                className={`rounded-full border px-3 py-1.5 text-[12px] font-medium transition ${h === horizon ? "border-amber-400 bg-amber-500/20 text-amber-300" : "border-white/[0.08] text-slate-400 hover:border-white/20 hover:text-slate-300"}`}>
                {h}
              </button>
            ))}
          </div>
        </div>
      )}

      {(missing.includes("risk_preference") || !missing.length) && (
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.10em] text-slate-500 mb-2">
            <ShieldAlert className="inline h-3 w-3 mr-1" />Risk Preference
          </p>
          <div className="flex flex-wrap gap-2">
            {RISK_OPTS.map(r => (
              <button key={r} onClick={() => setRisk(r === risk ? null : r)}
                className={`rounded-full border px-3 py-1.5 text-[12px] font-medium transition ${r === risk ? "border-amber-400 bg-amber-500/20 text-amber-300" : "border-white/[0.08] text-slate-400 hover:border-white/20 hover:text-slate-300"}`}>
                {r}
              </button>
            ))}
          </div>
        </div>
      )}

      {(missing.includes("investment_goal") || !missing.length) && (
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.10em] text-slate-500 mb-2">
            <Target className="inline h-3 w-3 mr-1" />Investment Objective
          </p>
          <div className="flex flex-wrap gap-2">
            {GOAL_OPTS.map(g => (
              <button key={g} onClick={() => setGoal(g === goal ? null : g)}
                className={`rounded-full border px-3 py-1.5 text-[12px] font-medium transition ${g === goal ? "border-amber-400 bg-amber-500/20 text-amber-300" : "border-white/[0.08] text-slate-400 hover:border-white/20 hover:text-slate-300"}`}>
                {g}
              </button>
            ))}
          </div>
        </div>
      )}

      {anySelected && (
        <button onClick={buildRefined}
          className="flex items-center gap-2 rounded-[14px] bg-amber-500/20 border border-amber-500/30 px-4 py-2.5 text-[13px] font-semibold text-amber-300 hover:bg-amber-500/30 transition">
          <Sparkles className="h-4 w-4" />
          Regenerate with Context
          <ArrowRight className="h-4 w-4 ml-auto" />
        </button>
      )}
    </div>
  );
}

// ── Single company analysis card ──────────────────────────────────────────────
function CompanyAnalysisCard({
  analysis,
  side,
}: {
  analysis: HoldingAnalysis;
  side: "holding" | "target";
}) {
  const [open, setOpen] = useState(true);
  const isSector    = analysis.entity_type === "sector";
  const isCommodity = analysis.entity_type === "commodity";
  const isNonEquity = isSector || isCommodity;
  const outlookCfg  = OUTLOOK_CONFIG[analysis.near_term_outlook] ?? OUTLOOK_CONFIG.neutral;
  const OutlookIcon = outlookCfg.icon;
  const borderColor = side === "holding" ? "border-l-sky-500"      : "border-l-violet-500";
  const accentBg    = side === "holding" ? "bg-sky-500/[0.04]"     : "bg-violet-500/[0.04]";
  const accentBd    = side === "holding" ? "border-sky-500/20"     : "border-violet-500/20";
  const labelColor  = side === "holding" ? "text-sky-400"          : "text-violet-400";
  const label = isCommodity
    ? (side === "holding" ? "Current Asset" : "Target Asset")
    : isSector
    ? (side === "holding" ? "Current Sector" : "Target Sector")
    : (side === "holding" ? "Current Holding" : "Target Investment");
  const EntityIcon = isCommodity ? TrendingUp : Building2;

  return (
    <div className={`rounded-[20px] border border-l-4 ${accentBd} ${borderColor} ${accentBg} overflow-hidden`}>
      {/* Header */}
      <button onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-5 py-4 text-left">
        <div className="flex items-center gap-3">
          <div className={`flex h-9 w-9 items-center justify-center rounded-xl border ${accentBd} ${accentBg}`}>
            <EntityIcon className={`h-4 w-4 ${labelColor}`} />
          </div>
          <div>
            <p className={`text-[10px] font-bold uppercase tracking-[0.10em] ${labelColor} mb-0.5`}>{label}</p>
            <p className="text-[15px] font-bold text-white leading-tight">{analysis.entity}</p>
            {!isNonEquity && analysis.sector && (
              <p className="text-[11px] text-slate-500">{analysis.sector}</p>
            )}
            {isCommodity && (
              <p className="text-[11px] text-slate-500">Commodity · Asset Class</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className={`flex items-center gap-1 justify-end ${outlookCfg.color} mb-1`}>
              <OutlookIcon className="h-3 w-3" />
              <span className="text-[11px] font-semibold">{outlookCfg.label}</span>
            </div>
            <p className="text-[9px] text-slate-500">Near-term outlook</p>
          </div>
          {!isNonEquity && <ScoreRing score={analysis.confidence} size={48} />}
          {open ? <ChevronUp className="h-4 w-4 text-slate-500 shrink-0" /> : <ChevronDown className="h-4 w-4 text-slate-500 shrink-0" />}
        </div>
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-white/[0.05] pt-4">
          {/* Thesis */}
          <p className="text-[13px] leading-6 text-slate-200">{analysis.thesis}</p>

          {/* Three columns: strengths, catalysts, risks */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <p className="text-[9px] font-bold uppercase tracking-[0.10em] text-emerald-500 mb-2">Strengths</p>
              <ul className="space-y-1.5">
                {analysis.strengths?.slice(0, 3).map((s, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-300 leading-[1.45]">
                    <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-emerald-500" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[9px] font-bold uppercase tracking-[0.10em] text-sky-500 mb-2">Catalysts</p>
              <ul className="space-y-1.5">
                {analysis.catalysts?.slice(0, 3).map((c, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-300 leading-[1.45]">
                    <Zap className="mt-0.5 h-3 w-3 shrink-0 text-sky-400" />
                    {c}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[9px] font-bold uppercase tracking-[0.10em] text-rose-500 mb-2">Risks</p>
              <ul className="space-y-1.5">
                {analysis.risks?.slice(0, 3).map((r, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-300 leading-[1.45]">
                    <XCircle className="mt-0.5 h-3 w-3 shrink-0 text-rose-500" />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Company page link — only for equity entities with a known symbol */}
          {!isNonEquity && analysis.symbol && (
            <Link href={`/companies/${analysis.symbol}`}
              className="inline-flex items-center gap-1.5 text-[11px] text-violet-400 hover:text-violet-300 transition">
              View full analysis for {analysis.symbol}
              <ArrowRight className="h-3 w-3" />
            </Link>
          )}
        </div>
      )}
    </div>
  );
}

// ── Comparison grid ───────────────────────────────────────────────────────────
function ComparisonGrid({
  rows,
  holdingName,
  targetName,
}: {
  rows: ComparisonRow[];
  holdingName: string;
  targetName: string;
}) {
  const advantageBadge = (adv: string, side: "holding" | "target") => {
    if (adv === side)    return "text-emerald-400 font-semibold";
    if (adv === "neutral") return "text-slate-300";
    return "text-slate-400";
  };

  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] overflow-hidden">
      <div className="px-5 py-3.5 border-b border-white/[0.06] flex items-center gap-2.5">
        <Scale className="h-4 w-4 text-violet-400" />
        <p className="text-[14px] font-semibold text-white">Side-by-Side Comparison</p>
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[1fr_1fr_1fr] gap-0 px-5 py-3 border-b border-white/[0.05]">
        <p className="text-[10px] font-bold uppercase tracking-[0.10em] text-slate-500">Dimension</p>
        <p className="text-[10px] font-bold uppercase tracking-[0.10em] text-sky-500 truncate">{holdingName}</p>
        <p className="text-[10px] font-bold uppercase tracking-[0.10em] text-violet-500 truncate">{targetName}</p>
      </div>

      <div className="divide-y divide-white/[0.04]">
        {rows.map((row, i) => (
          <div key={i} className="grid grid-cols-[1fr_1fr_1fr] gap-0 px-5 py-3 hover:bg-white/[0.02] transition">
            <p className="text-[11px] font-semibold text-slate-400 pr-3">{row.dimension}</p>
            <p className={`text-[11px] leading-[1.45] pr-3 ${advantageBadge(row.advantage, "holding")}`}>
              {row.holding}
              {row.advantage === "holding" && <span className="ml-1 text-[9px] text-emerald-500">▲</span>}
            </p>
            <p className={`text-[11px] leading-[1.45] ${advantageBadge(row.advantage, "target")}`}>
              {row.target}
              {row.advantage === "target" && <span className="ml-1 text-[9px] text-emerald-500">▲</span>}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Trade-off analysis ────────────────────────────────────────────────────────
function TradeoffAnalysis({
  tradeoff,
  holdingName,
  targetName,
}: {
  tradeoff: TradeoffData;
  holdingName: string;
  targetName: string;
}) {
  return (
    <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] overflow-hidden">
      <div className="px-5 py-3.5 border-b border-white/[0.06] flex items-center gap-2.5">
        <ArrowLeftRight className="h-4 w-4 text-amber-400" />
        <p className="text-[14px] font-semibold text-white">Trade-off Analysis</p>
      </div>

      <div className="p-5 space-y-5">
        {/* Top row: hold vs switch */}
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-[14px] border border-sky-500/15 bg-sky-500/[0.04] p-4">
            <p className="text-[9px] font-bold uppercase tracking-[0.10em] text-sky-400 mb-3">
              Reasons to Continue Holding {holdingName}
            </p>
            <ul className="space-y-2">
              {tradeoff.reasons_to_hold?.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-[12px] text-slate-300 leading-[1.5]">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" />
                  {r}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-[14px] border border-violet-500/15 bg-violet-500/[0.04] p-4">
            <p className="text-[9px] font-bold uppercase tracking-[0.10em] text-violet-400 mb-3">
              Potential Benefits of Switching to {targetName}
            </p>
            <ul className="space-y-2">
              {tradeoff.reasons_to_switch?.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-[12px] text-slate-300 leading-[1.5]">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400" />
                  {r}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Risk row */}
        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-[14px] border border-rose-500/10 bg-rose-500/[0.03] p-3.5">
            <p className="text-[9px] font-bold uppercase tracking-[0.10em] text-rose-400 mb-2">Risks of Staying</p>
            <ul className="space-y-1.5">
              {tradeoff.risks_of_holding?.map((r, i) => (
                <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-400 leading-[1.45]">
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-rose-500" />{r}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-[14px] border border-amber-500/10 bg-amber-500/[0.03] p-3.5">
            <p className="text-[9px] font-bold uppercase tracking-[0.10em] text-amber-400 mb-2">Risks of Switching</p>
            <ul className="space-y-1.5">
              {tradeoff.risks_of_switching?.map((r, i) => (
                <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-400 leading-[1.45]">
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-500" />{r}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* When to wait */}
        {tradeoff.when_to_wait && (
          <div className="flex items-start gap-3 rounded-[14px] border border-slate-700/50 bg-white/[0.02] p-4">
            <Clock className="h-4 w-4 text-slate-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.10em] text-slate-500 mb-1">When Waiting May Be Appropriate</p>
              <p className="text-[12px] text-slate-300 leading-[1.55]">{tradeoff.when_to_wait}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── AI Decision Framework ─────────────────────────────────────────────────────
function AIDecisionFramework({ framework }: { framework: DecisionFramework }) {
  return (
    <div className="rounded-[20px] border border-violet-500/20 bg-violet-500/[0.04] overflow-hidden">
      <div className="px-5 py-3.5 border-b border-violet-500/10 flex items-center gap-2.5">
        <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-500/10 border border-violet-500/20">
          <Brain className="h-3.5 w-3.5 text-violet-400" />
        </div>
        <p className="text-[14px] font-semibold text-white">AI Decision Framework</p>
      </div>

      <div className="p-5 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          {/* Supports switch */}
          <div>
            <p className="text-[9px] font-bold uppercase tracking-[0.10em] text-emerald-500 mb-2">What Supports a Change</p>
            <ul className="space-y-2">
              {framework.supports_switch?.map((s, i) => (
                <li key={i} className="flex items-start gap-2 text-[12px] text-slate-300 leading-[1.5]">
                  <CircleDot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />{s}
                </li>
              ))}
            </ul>
          </div>

          {/* Argues against */}
          <div>
            <p className="text-[9px] font-bold uppercase tracking-[0.10em] text-rose-400 mb-2">What Argues Against</p>
            <ul className="space-y-2">
              {framework.argues_against?.map((a, i) => (
                <li key={i} className="flex items-start gap-2 text-[12px] text-slate-300 leading-[1.5]">
                  <CircleDot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-400" />{a}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Key unknowns */}
        {framework.key_unknowns?.length > 0 && (
          <div className="rounded-[14px] border border-amber-500/15 bg-amber-500/[0.04] p-4">
            <p className="text-[9px] font-bold uppercase tracking-[0.10em] text-amber-400 mb-2">
              Additional Information That Would Improve Confidence
            </p>
            <ul className="space-y-1.5">
              {framework.key_unknowns.map((k, i) => (
                <li key={i} className="flex items-start gap-2 text-[12px] text-slate-300">
                  <HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />{k}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* AI stance */}
        {framework.ai_stance && (
          <div className="flex items-start gap-3 rounded-[14px] border border-violet-500/15 bg-violet-500/[0.04] p-4">
            <Sparkles className="h-4 w-4 text-violet-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.10em] text-violet-400 mb-1.5">AI Perspective</p>
              <p className="text-[12px] leading-[1.6] text-slate-200">{framework.ai_stance}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Decision Summary Banner ───────────────────────────────────────────────────
function DecisionSummaryBanner({
  di,
}: {
  di: DecisionIntelligence;
}) {
  const { intent, detected_holding, detected_target, decision_summary, detected_horizon, detected_risk } = di;

  return (
    <div className="rounded-[20px] border border-white/[0.10] bg-gradient-to-r from-slate-900 to-slate-900/80 overflow-hidden">
      {/* Top strip */}
      <div className="h-0.5 bg-gradient-to-r from-sky-500 via-violet-500 to-violet-500/0" />

      <div className="p-5">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <IntentBadge intent={intent} />
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {detected_horizon && (
              <span className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] text-slate-400">
                <Clock className="h-3 w-3" />{detected_horizon}
              </span>
            )}
            {detected_risk && (
              <span className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] text-slate-400">
                <ShieldAlert className="h-3 w-3" />{detected_risk}
              </span>
            )}
          </div>
        </div>

        {/* Entity chips */}
        {(detected_holding || detected_target) && (
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            {detected_holding && (
              <span className="flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-[12px] font-semibold text-sky-300">
                <span className="h-2 w-2 rounded-full bg-sky-400" />
                {detected_holding}
              </span>
            )}
            {detected_target && (
              <>
                <ArrowLeftRight className="h-4 w-4 text-slate-500" />
                <span className="flex items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-[12px] font-semibold text-violet-300">
                  <span className="h-2 w-2 rounded-full bg-violet-400" />
                  {detected_target}
                </span>
              </>
            )}
          </div>
        )}

        {/* Summary */}
        {decision_summary && (
          <p className="text-[13px] leading-6 text-slate-300">{decision_summary}</p>
        )}

        <p className="mt-3 text-[11px] text-slate-500 italic">
          MarketRipple explains the trade-offs and evidence. The investment decision is yours.
        </p>
      </div>
    </div>
  );
}

// ── Main Decision Intelligence Panel ─────────────────────────────────────────
interface DecisionIntelligencePanelProps {
  di: DecisionIntelligence;
  query: string;
  onRefine: (q: string) => void;
}

export function DecisionIntelligencePanel({ di, query, onRefine }: DecisionIntelligencePanelProps) {
  const {
    intent,
    context_complete,
    missing_context,
    detected_horizon,
    detected_risk,
    holding_analysis,
    target_analysis,
    comparison,
    tradeoff,
    decision_framework,
  } = di;

  const holdingName = holding_analysis?.entity ?? di.detected_holding ?? "Current Holding";
  const targetName  = target_analysis?.entity  ?? di.detected_target  ?? "Target Investment";

  return (
    <div className="space-y-4">
      {/* Decision summary banner */}
      <DecisionSummaryBanner di={di} />

      {/* Follow-up context when incomplete */}
      {(!context_complete || (missing_context?.length > 0)) && (
        <FollowUpContextPanel
          missing={missing_context ?? []}
          query={query}
          onRefine={onRefine}
          detectedHorizon={detected_horizon}
          detectedRisk={detected_risk}
        />
      )}

      {/* Always show follow-up context as "enhance" option */}
      {context_complete && (
        <FollowUpContextPanel
          missing={[]}
          query={query}
          onRefine={onRefine}
          detectedHorizon={detected_horizon}
          detectedRisk={detected_risk}
        />
      )}

      {/* Company Analysis — two cards */}
      {(holding_analysis || target_analysis) && (
        <div className="space-y-3">
          <p className="text-[15px] font-semibold text-white">Individual Analysis</p>
          <div className="grid grid-cols-1 gap-4">
            {holding_analysis && (
              <CompanyAnalysisCard analysis={holding_analysis} side="holding" />
            )}
            {target_analysis && (
              <CompanyAnalysisCard analysis={target_analysis} side="target" />
            )}
          </div>
        </div>
      )}

      {/* Comparison grid */}
      {comparison && comparison.length > 0 && (
        <ComparisonGrid
          rows={comparison}
          holdingName={holdingName}
          targetName={targetName}
        />
      )}

      {/* Trade-off analysis */}
      {tradeoff && (
        <TradeoffAnalysis
          tradeoff={tradeoff}
          holdingName={holdingName}
          targetName={targetName}
        />
      )}

      {/* AI Decision Framework */}
      {decision_framework && (
        <AIDecisionFramework framework={decision_framework} />
      )}

      {/* InvestmentThesisCard for each company (via self-fetch) */}
      {holding_analysis?.symbol && (
        <div>
          <p className="text-[12px] uppercase tracking-[0.10em] text-slate-500 font-bold mb-3">
            Deep Thesis — {holdingName}
          </p>
          <InvestmentThesisCard
            entityType="company"
            entityId={holding_analysis.symbol}
            entityTitle={holding_analysis.entity}
            entityDescription={holding_analysis.thesis}
            entitySector={holding_analysis.sector}
          />
        </div>
      )}
      {target_analysis?.symbol && (
        <div>
          <p className="text-[12px] uppercase tracking-[0.10em] text-slate-500 font-bold mb-3">
            Deep Thesis — {targetName}
          </p>
          <InvestmentThesisCard
            entityType="company"
            entityId={target_analysis.symbol}
            entityTitle={target_analysis.entity}
            entityDescription={target_analysis.thesis}
            entitySector={target_analysis.sector}
          />
        </div>
      )}

      <AIDisclaimer />
    </div>
  );
}
