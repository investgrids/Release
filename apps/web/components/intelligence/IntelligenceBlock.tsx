"use client";

import { useState } from "react";
import {
  Sparkles, TrendingUp, TrendingDown, Minus,
  AlertTriangle, Eye, ChevronDown, ChevronUp, History,
} from "lucide-react";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";

// ── Types ─────────────────────────────────────────────────────────────────────
export interface IntelligenceOpportunity {
  title:       string;
  description: string;
  companies:   string[];
  horizon:     "short" | "medium" | "long";
  confidence:  number | null;
}

export interface IntelligenceRisk {
  title:       string;
  description: string;
  severity:    "high" | "medium" | "low";
}

export interface IntelligenceCompany {
  symbol:     string;
  name:       string;
  stance:     "bullish" | "bearish" | "neutral";
  reason:     string;
  confidence: number | null;
}

export interface IntelligenceSector {
  name:    string;
  outlook: "positive" | "negative" | "neutral";
  score:   number | null;
  reason:  string;
}

export interface IntelligenceTheme {
  name:        string;
  strength:    "strong" | "moderate" | "weak";
  description: string;
}

export interface IntelligenceObject {
  market_story:         string;
  key_takeaway:         string;
  opportunities:        IntelligenceOpportunity[];
  risks:                IntelligenceRisk[];
  companies:            IntelligenceCompany[];
  sectors:              IntelligenceSector[];
  themes:               IntelligenceTheme[];
  historical_context:   string;
  monitoring_points:    string[];
  related_intelligence: { type: string; id: string; title: string; relevance_score: number }[];
  confidence:           { level: string; score: number; reasons: string[]; breakdown: Record<string, number> };
  generated_at:         string;
  context_type:         string;
  context_id:           string | null;
}

// ── Palette helpers ───────────────────────────────────────────────────────────
const STANCE_STYLE: Record<string, { icon: React.ReactNode; cls: string; bg: string }> = {
  bullish: {
    icon: <TrendingUp className="h-3.5 w-3.5" />,
    cls:  "text-emerald-400",
    bg:   "bg-emerald-500/10 border-emerald-500/20",
  },
  bearish: {
    icon: <TrendingDown className="h-3.5 w-3.5" />,
    cls:  "text-rose-400",
    bg:   "bg-rose-500/10 border-rose-500/20",
  },
  neutral: {
    icon: <Minus className="h-3.5 w-3.5" />,
    cls:  "text-slate-400",
    bg:   "bg-slate-500/10 border-slate-500/20",
  },
};

const SEV_STYLE: Record<string, string> = {
  high:   "bg-rose-500/15 border-rose-500/25 text-rose-300",
  medium: "bg-amber-500/15 border-amber-500/25 text-amber-300",
  low:    "bg-slate-500/10 border-slate-500/20 text-slate-400",
};

const OUTLOOK_DOT: Record<string, string> = {
  positive: "bg-emerald-500",
  negative: "bg-rose-500",
  neutral:  "bg-slate-500",
};

const HORIZON_LABEL: Record<string, string> = {
  short:  "Short-term",
  medium: "Medium-term",
  long:   "Long-term",
};

const STRENGTH_COLOR: Record<string, string> = {
  strong:   "text-violet-300 bg-violet-500/15",
  moderate: "text-sky-300 bg-sky-500/15",
  weak:     "text-slate-400 bg-slate-500/10",
};

// ── Sub-components ────────────────────────────────────────────────────────────
function SectionHeader({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <div className="text-slate-500">{icon}</div>
      <span className="text-[10px] font-bold uppercase tracking-widest text-slate-600">{label}</span>
    </div>
  );
}

function OpportunityCard({ op }: { op: IntelligenceOpportunity }) {
  return (
    <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.06] p-3.5">
      <div className="mb-1.5 flex items-start justify-between gap-2">
        <p className="text-[12px] font-semibold text-emerald-300 leading-snug">{op.title}</p>
        <span className="shrink-0 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[9px] font-bold uppercase text-emerald-400">
          {HORIZON_LABEL[op.horizon] || op.horizon}
        </span>
      </div>
      <p className="text-[11px] text-slate-400 leading-relaxed">{op.description}</p>
      {op.companies.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {op.companies.map(sym => (
            <span key={sym} className="rounded bg-white/[0.05] px-1.5 py-0.5 text-[10px] font-mono text-slate-300">
              {sym}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function RiskCard({ risk }: { risk: IntelligenceRisk }) {
  return (
    <div className={`rounded-xl border p-3.5 ${SEV_STYLE[risk.severity] || SEV_STYLE.medium}`}>
      <div className="mb-1 flex items-center gap-2">
        <AlertTriangle className="h-3.5 w-3.5 opacity-80 shrink-0" />
        <p className="text-[12px] font-semibold leading-snug">{risk.title}</p>
        <span className="ml-auto shrink-0 text-[9px] font-bold uppercase opacity-70">
          {risk.severity}
        </span>
      </div>
      <p className="text-[11px] opacity-80 leading-relaxed">{risk.description}</p>
    </div>
  );
}

function CompanyPill({ co }: { co: IntelligenceCompany }) {
  const s = STANCE_STYLE[co.stance] || STANCE_STYLE.neutral;
  return (
    <div className={`rounded-xl border p-3 ${s.bg}`}>
      <div className="mb-1 flex items-center gap-1.5">
        <span className={s.cls}>{s.icon}</span>
        <span className="text-[11px] font-bold text-white">{co.symbol}</span>
        <span className="ml-auto text-[10px] tabular-nums text-slate-600">{co.confidence === null || co.confidence === undefined ? "—" : `${co.confidence}%`}</span>
      </div>
      <p className="text-[10px] text-slate-400 leading-snug">{co.reason}</p>
    </div>
  );
}

function SectorBar({ sec }: { sec: IntelligenceSector }) {
  const dot = OUTLOOK_DOT[sec.outlook] || OUTLOOK_DOT.neutral;
  return (
    <div className="flex items-center gap-2.5">
      <div className={`h-2 w-2 shrink-0 rounded-full ${dot}`} />
      <span className="min-w-0 flex-1 truncate text-[11px] text-slate-300">{sec.name}</span>
      <div className="h-1 w-20 overflow-hidden rounded-full bg-white/[0.06]">
        {sec.score !== null && sec.score !== undefined && (
          <div
            className={`h-full rounded-full transition-all ${
              sec.outlook === "positive" ? "bg-emerald-500/70" :
              sec.outlook === "negative" ? "bg-rose-500/70" : "bg-slate-500/50"
            }`}
            style={{ width: `${sec.score}%` }}
          />
        )}
      </div>
      <span className="w-8 shrink-0 text-right text-[10px] tabular-nums text-slate-600">{sec.score === null || sec.score === undefined ? "—" : sec.score}</span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export function IntelligenceBlock({
  data,
  label = "AI Intelligence",
  compact = false,
}: {
  data:     IntelligenceObject;
  label?:   string;
  compact?: boolean;
}) {
  const [expanded, setExpanded] = useState(!compact);
  const hasContent = data.market_story || data.key_takeaway;

  if (!hasContent) return null;

  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/20">
          <Sparkles className="h-3.5 w-3.5 text-violet-400" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold text-white leading-none">{label}</p>
          {data.market_story && (
            <p className="mt-0.5 truncate text-[11px] text-slate-500">{data.market_story.slice(0, 80)}…</p>
          )}
        </div>
        <ConfidenceBadge data={data.confidence as any} />
        <div className="ml-2 text-slate-600">
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </div>
      </button>

      {/* Expandable body */}
      {expanded && (
        <div className="border-t border-white/[0.05] px-5 pb-5 pt-4 space-y-5">
          {/* Key Takeaway */}
          {data.key_takeaway && (
            <div className="rounded-xl border border-violet-500/20 bg-violet-500/[0.06] px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-violet-500 mb-1">Key Takeaway</p>
              <p className="text-[13px] font-medium text-violet-100 leading-relaxed">{data.key_takeaway}</p>
            </div>
          )}

          {/* Market Story */}
          {data.market_story && (
            <div>
              <SectionHeader icon={<Sparkles className="h-3.5 w-3.5" />} label="Market Story" />
              <p className="text-[12px] text-slate-400 leading-relaxed">{data.market_story}</p>
            </div>
          )}

          {/* Opportunities */}
          {data.opportunities.length > 0 && (
            <div>
              <SectionHeader icon={<TrendingUp className="h-3.5 w-3.5" />} label="Opportunities" />
              <div className="space-y-2">
                {data.opportunities.slice(0, 3).map((op, i) => (
                  <OpportunityCard key={i} op={op} />
                ))}
              </div>
            </div>
          )}

          {/* Risks */}
          {data.risks.length > 0 && (
            <div>
              <SectionHeader icon={<AlertTriangle className="h-3.5 w-3.5" />} label="Key Risks" />
              <div className="space-y-2">
                {data.risks.slice(0, 3).map((risk, i) => (
                  <RiskCard key={i} risk={risk} />
                ))}
              </div>
            </div>
          )}

          {/* Companies */}
          {data.companies.length > 0 && (
            <div>
              <SectionHeader icon={<TrendingUp className="h-3.5 w-3.5" />} label="Company Stance" />
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {data.companies.slice(0, 6).map((co, i) => (
                  <CompanyPill key={i} co={co} />
                ))}
              </div>
            </div>
          )}

          {/* Sectors */}
          {data.sectors.length > 0 && (
            <div>
              <SectionHeader icon={<Eye className="h-3.5 w-3.5" />} label="Sectors" />
              <div className="space-y-2">
                {data.sectors.slice(0, 5).map((sec, i) => (
                  <SectorBar key={i} sec={sec} />
                ))}
              </div>
            </div>
          )}

          {/* Themes */}
          {data.themes.length > 0 && (
            <div>
              <SectionHeader icon={<Sparkles className="h-3.5 w-3.5" />} label="Market Themes" />
              <div className="flex flex-wrap gap-2">
                {data.themes.map((t, i) => (
                  <span
                    key={i}
                    className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${STRENGTH_COLOR[t.strength] || STRENGTH_COLOR.moderate}`}
                    title={t.description}
                  >
                    {t.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Historical Context */}
          {data.historical_context && (
            <div>
              <SectionHeader icon={<History className="h-3.5 w-3.5" />} label="Historical Context" />
              <p className="text-[11px] text-slate-500 leading-relaxed italic">{data.historical_context}</p>
            </div>
          )}

          {/* Monitoring Points */}
          {data.monitoring_points.length > 0 && (
            <div>
              <SectionHeader icon={<Eye className="h-3.5 w-3.5" />} label="What to Watch" />
              <ul className="space-y-1">
                {data.monitoring_points.map((pt, i) => (
                  <li key={i} className="flex items-start gap-2 text-[11px] text-slate-400">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-600" />
                    {pt}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Footer */}
          <p className="text-[9px] text-slate-700 border-t border-white/[0.04] pt-3">
            Generated {new Date(data.generated_at).toLocaleTimeString()} · AI intelligence, not financial advice
          </p>
        </div>
      )}
    </div>
  );
}
