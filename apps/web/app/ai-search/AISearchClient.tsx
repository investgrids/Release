"use client";

// AI Search page (Step 6). The answer itself is rendered by components/ai/v2/AnswerV2, driven by answer_availability (the final answer contract). This file owns the page chrome: the question box, today's
// example questions, truthful loading stages, the transport (streaming or plain request) and Market Pulse, which keeps its own response shape.
import { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Bot, CheckCircle2, Clock, AlertTriangle, RotateCcw, ArrowRight, BarChart3, Building2, Globe2, Lightbulb, Sparkles } from "lucide-react";
import { IconTile } from "@/components/ai/v2/visuals";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import { ResearchingCard } from "@/components/ai/v2/ResearchingCard";
import { AISearchHistory, AI_SEARCH_HISTORY_KEY, AI_SEARCH_HISTORY_EVENT } from "@/components/ai/AISearchHistory";
import { useResearchSession, type SessionEntity } from "@/lib/hooks/useResearchSession";
import { ContextChips } from "@/components/ai/ContextChips";
import { ClarificationPicker } from "@/components/ai/ClarificationPicker";
import { AnswerV2 } from "@/components/ai/v2/AnswerV2";
import { authorizedVerdict, type V2Result } from "@/components/ai/v2/contract";
import { useAISearchStream } from "@/lib/hooks/useAISearchStream";
import { API_BASE_URL as API } from "@/lib/api";
import { isRealSymbol } from "@/lib/text";
import { EXAMPLES } from "./constants";

// Transport only: with the flag on, answers stream with real stage events; otherwise a plain request. The answer is rendered identically either way.
const AI_SEARCH_V3_ENABLED = process.env.NEXT_PUBLIC_AI_SEARCH_V3 === "1";

// ── Types ─────────────────────────────────────────────────────
export type UIMode =
  | "direct_company_research" | "switch_analysis" | "company_comparison"
  | "factual_lookup" | "policy_macro_impact" | "market_pulse"
  | "event_impact" | "sector_theme_research"
  | "technical_timing" | "company_discovery" | "portfolio_review"
  | "earnings_preview" | "multi_company_comparison";

export interface AnswerAvailability {
  state: "available" | "temporarily_unavailable" | "no_verified_evidence" | "limited_evidence";
  evidence_retrieval_completed: boolean;
  /** Evidence items (events, news, policy items) LISTED in this response. 0 for an educational answer, which rests on no retrieved evidence. */
  evidence_count: number;
  reason?: "evidence_insufficient" | "retrieval_failed" | "retrieval_timeout" | "provider_capacity" | "generation_failed" | "time_budget_exhausted" | "claims_not_authorized" | "unsupported_subject" | "education_not_covered" | "limited_evidence" | null;
  basis?: "retrieved_evidence" | "market_data" | "education" | "none";
  kind?: "research" | "partial_research" | "education" | "product_information" | "unavailable" | "temporarily_unavailable";
  scope?: "full" | "partial" | "none";
  conclusion_authorized?: boolean;
}

/** What the page holds for a non-pulse answer: the contract fields the V2 renderer reads, plus the few extras the page itself uses. */
export type SearchResult = V2Result & { type?: string; needs_clarification?: boolean; ambiguous_term?: string; candidates?: { symbol: string; name: string }[] };

interface ChartSeries  { name: string; data: number[]; color: string; }
interface MarketChart  { labels: string[]; series: ChartSeries[]; }
interface VerifiedDriver {
  driver: string; driver_type: string; confidence_tier: "High" | "Medium" | "Low";
  evidence: string; related_event_ids: string[]; confidence_score: number | null;
  // Phase 2 — Market Intelligence Scoring Engine. driver_strength is always
  // real (market_scoring_engine.score_driver_strength); theme_strength only
  // appears on sector_theme drivers (a direct passthrough of the real,
  // live Theme Engine score — never recomputed on the frontend).
  driver_strength: number; theme_strength?: number;
}
interface PulseMover {
  company: string; ticker: string; value: string; subtitle: string; positive: boolean;
  change_pct: number; verified_drivers: VerifiedDriver[]; narrative: string; isVolume?: boolean;
  evidence_strength: number;
}
interface PulseSector { id: string; name: string; value: string; positive: boolean; momentum_score: number; }
interface PulseIndex  { name: string; ticker: string; value: string; change: string; pct: number; positive: boolean; }
interface PulseCalendarItem { id: string; category: string; title: string; date: string; description: string; }
interface MarketConfidenceScore { score: number; level: string; reasons: string[]; breakdown: Record<string, number>; }
interface PulseScores {
  opportunity_score: number | null; risk_score: number;
  market_confidence: MarketConfidenceScore; catalyst_score: number;
}
export interface MarketPulseResult {
  type: "market_pulse"; query: string; synthesis_incomplete: boolean; generated_at: string | null;
  market_status: { is_open?: boolean; status?: string; time_ist?: string; date?: string };
  indices: PulseIndex[]; market_mood: string | null; market_direction: string | null;
  market_summary: string; sector_narrative: string;
  leading_sectors: PulseSector[]; lagging_sectors: PulseSector[];
  top_gainers: PulseMover[]; top_losers: PulseMover[]; most_active: PulseMover[];
  biggest_opportunity: { id: string; slug?: string; title: string; summary?: string } | null;
  biggest_risk: { headline: string | null; reason: string } | null;
  ai_conclusion: string; what_to_watch_next: PulseCalendarItem[]; what_to_watch_summary: string;
  scores: PulseScores;
  // AEV2 activation-wiring (2026-09-22) — mirrors SearchResult's own
  // optional ui_mode/answer_experience_v2 fields (see that interface's
  // own doc comments). pipeline.py sets ui_mode: "market_pulse" on this
  // exact shape (mp_result["ui_mode"] = "market_pulse"), and
  // response_finalize.py's answer_experience_v2 attachment is shape-
  // agnostic — both fields legitimately appear on the real backend
  // response for a market-pulse-classified query, even though this type
  // stays otherwise deliberately separate from SearchResult.
  ui_mode?: UIMode;
  answer_availability?: AnswerAvailability | null;
}

// ── Market Pulse (its own response shape; unchanged) ─────────
const TIER_CLS: Record<string, string> = {
  High:   "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
  Medium: "border-sky-500/30 bg-sky-500/10 text-sky-600 dark:text-sky-300",
  Low:    "border-surface-border/7 bg-slate-500/10 text-text-secondary",
};

// Multi-line chart for MarketChart — real data (yfinance-backed, built server
// side from the query's own companies/indices), computed on every request
// but never rendered anywhere on this page until now. A plain inline SVG,
// consistent with this codebase's existing sparkline pattern elsewhere —
// no charting library needed for a handful of normalized %-change lines.
function MultiLineChart({ chart, height = 160 }: { chart: MarketChart; height?: number }) {
  const width = 600;
  const series = (chart.series ?? []).filter(s => s.data?.length > 1);
  if (series.length === 0) return null;
  const allVals = series.flatMap(s => s.data);
  const min = Math.min(...allVals, 0), max = Math.max(...allVals, 0);
  const range = max - min || 1;
  const pad = 8;
  const n = series[0].data.length;
  const x = (i: number) => pad + (i / (n - 1)) * (width - pad * 2);
  const y = (v: number) => pad + (height - pad * 2) - ((v - min) / range) * (height - pad * 2);
  const zeroY = y(0);
  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ height }}>
        <line x1={pad} y1={zeroY} x2={width - pad} y2={zeroY} stroke="rgb(var(--text-primary) / 0.08)" strokeWidth="1"/>
        {series.map((s, si) => (
          <polyline key={si} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"
            points={s.data.map((v, i) => `${x(i)},${y(v)}`).join(" ")}/>
        ))}
      </svg>
      <div className="flex flex-wrap gap-3 mt-1">
        {series.map((s, si) => {
          const last = s.data[s.data.length - 1];
          return (
            <span key={si} className="flex items-center gap-1.5 text-[10px] text-text-secondary">
              <span className="h-2 w-2 rounded-full shrink-0" style={{ background: s.color }}/>
              {s.name} <span className={`tabular-nums font-semibold ${last >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{last >= 0 ? "+" : ""}{last.toFixed(2)}%</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

// Shared degraded-mode indicator — a synthesis_incomplete answer must look
// visibly different everywhere it appears, not just behind one banner near
// the top of the page that a user can easily scroll past.
const DEGRADED_CARD_CLS = "border-amber-500/30 bg-amber-500/[0.04]";
function DegradedBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-300">
      <AlertTriangle className="h-2.5 w-2.5"/>
      Analysis unavailable
    </span>
  );
}

function VerifiedDriverChip({ d }: { d: VerifiedDriver }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${TIER_CLS[d.confidence_tier] ?? TIER_CLS.Medium}`} title={d.evidence}>
      <CheckCircle2 className="h-3 w-3"/>
      {d.driver}
      <span className="opacity-70 tabular-nums">· {Math.round(d.driver_strength)}%</span>
      {d.theme_strength != null && (
        <span className="opacity-70 tabular-nums">· Theme {(d.theme_strength / 10).toFixed(1)}/10</span>
      )}
    </span>
  );
}

function PulseMoverCard({ m }: { m: PulseMover }) {
  return (
    <div className="rounded-[16px] border border-surface-border/7 bg-text-primary/[0.03] p-4">
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div>
          <p className="text-[13px] font-bold text-text-primary">{m.company}</p>
          <p className="text-[10px] text-text-muted">{m.ticker} · {m.subtitle}</p>
        </div>
        <span className={`text-[14px] font-black tabular-nums ${m.positive ? "text-emerald-400" : "text-rose-400"}`}>{m.value}</span>
      </div>
      {m.verified_drivers.length > 0 ? (
        <div className="flex flex-wrap gap-1.5 mb-1.5">
          {m.verified_drivers.map((d, i) => <VerifiedDriverChip key={i} d={d}/>)}
        </div>
      ) : (
        <span className="inline-flex items-center gap-1 rounded-full border border-surface-border/8 bg-text-primary/[0.03] px-2 py-0.5 text-[10px] font-semibold text-text-muted mb-1.5">
          <AlertTriangle className="h-3 w-3"/>
          No verified driver identified
        </span>
      )}
      <p className="mb-2 text-[9px] uppercase tracking-wider text-text-muted">Evidence Strength <span className="tabular-nums text-text-muted">{Math.round(m.evidence_strength)}%</span></p>
      {/* Phase 1 fix (2026-09-21): conditionally rendered — a gate
          violation clears `narrative` to "" (market_pulse_safety.py)
          rather than removing the mover entirely (its real price/ticker/
          verified_drivers data is still shown); an unconditional <p> here
          would have rendered a visible empty line instead of just
          omitting the sentence. */}
      {m.narrative && <p className="text-[11.5px] leading-5 text-text-secondary">{m.narrative}</p>}
    </div>
  );
}

// ── Market Pulse — dedicated degraded renderer ──────────────────────────────
// Phase 1 fix (2026-09-21 intent audit finding 2): mirrors DegradedSearchAnswer's
// architecture exactly — one early return, one self-contained tree, rather than
// scattered per-section conditionals inside MarketPulseResults (which is what
// SearchResults used to do, before that pattern already let two fabrication
// leaks through — see DegradedSearchAnswer's own docstring). Shows only real,
// deterministic data (indices, sector %, mover prices/verified_drivers,
// scheduled calendar items) — no market_summary/sector_narrative/ai_conclusion/
// what_to_watch_summary text, no Market Confidence/Catalyst Score chips (both
// could read as analytical certainty about content that wasn't generated,
// even though they're computed independently of the failed narrative call).
function DegradedMarketPulse({ result }: { result: MarketPulseResult }) {
  return (
    <div className="space-y-4 pb-36" data-testid="degraded-market-pulse">
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] px-5 py-4">
        <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Market Pulse</p>
        <h1 className="text-[18px] font-bold text-text-primary leading-snug">{result.query}</h1>
        <p className="mt-1 text-[11px] text-text-muted">
          {result.market_status?.status ? `Market ${result.market_status.status.replace("_", " ")}` : ""}
          {result.market_status?.time_ist ? ` · ${result.market_status.time_ist} IST` : ""}
        </p>
      </div>

      <div className="flex items-start gap-3 rounded-[16px] border border-amber-500/25 bg-amber-500/[0.06] px-4 py-3">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-400"/>
        <p className="text-[12.5px] leading-5 text-amber-700/90 dark:text-amber-200/90">
          <span className="font-semibold text-amber-600 dark:text-amber-300">AI narrative couldn&apos;t be generated for this query.</span>{" "}
          Every number below is still real, live market data — only the written explanations are unavailable right now.
        </p>
      </div>

      {result.indices.length > 0 && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[13px] font-semibold text-text-primary mb-3">Market Indices</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {result.indices.map(idx => (
              <div key={idx.ticker} className="rounded-[12px] border border-surface-border/6 bg-text-primary/[0.02] px-3 py-2">
                <p className="text-[9px] uppercase tracking-wider text-text-muted">{idx.name}</p>
                <p className="text-[12px] font-bold text-text-primary">{idx.value}</p>
                <p className={`text-[10px] font-semibold ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>{idx.change}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {(result.leading_sectors.length > 0 || result.lagging_sectors.length > 0) && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[13px] font-semibold text-text-primary mb-3">Sector Rotation</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-[9px] uppercase tracking-wider text-emerald-400 font-semibold mb-1.5">Leading</p>
              <div className="space-y-1.5">
                {result.leading_sectors.map(s => (
                  <div key={s.id} className="flex items-center justify-between rounded-lg border border-surface-border/4 bg-text-primary/[0.02] px-2.5 py-1.5">
                    <span className="text-[11px] font-semibold text-text-primary">{s.name}</span>
                    <span className={`text-[11px] font-black tabular-nums ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.value}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[9px] uppercase tracking-wider text-rose-400 font-semibold mb-1.5">Lagging</p>
              <div className="space-y-1.5">
                {result.lagging_sectors.map(s => (
                  <div key={s.id} className="flex items-center justify-between rounded-lg border border-surface-border/4 bg-text-primary/[0.02] px-2.5 py-1.5">
                    <span className="text-[11px] font-semibold text-text-primary">{s.name}</span>
                    <span className={`text-[11px] font-black tabular-nums ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {(result.top_gainers.length > 0 || result.top_losers.length > 0) && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[13px] font-semibold text-text-primary mb-3">Top Movers</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
            {result.top_gainers.map(m => <PulseMoverCard key={m.ticker} m={m}/>)}
          </div>
          {result.top_losers.length > 0 && (
            <>
              <p className="text-[11px] uppercase tracking-wider text-text-muted font-semibold mb-2 mt-4">Losers</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {result.top_losers.map(m => <PulseMoverCard key={m.ticker} m={m}/>)}
              </div>
            </>
          )}
        </div>
      )}

      {result.what_to_watch_next.length > 0 && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[13px] font-semibold text-text-primary mb-3">What to Watch Next</p>
          <div className="space-y-2">
            {result.what_to_watch_next.map(w => (
              <div key={w.id} className="flex items-start gap-3 rounded-lg border border-surface-border/4 bg-text-primary/[0.02] px-3 py-2">
                <Clock className="h-3.5 w-3.5 shrink-0 mt-0.5 text-text-muted"/>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold text-text-primary">{w.title}</span>
                    <span className="text-[9px] uppercase tracking-wider text-text-muted">{w.category}</span>
                  </div>
                  <p className="text-[10px] text-text-muted">{w.date}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <AIDisclaimer/>
    </div>
  );
}

export function MarketPulseResults({ result }: { result: MarketPulseResult }) {
  // Dedicated top-level early return for a degraded Market Pulse response
  // — see DegradedMarketPulse's own docstring. Must come before any of the
  // scattered per-section conditionals below, which stay in place as
  // harmless dead code for the non-degraded path (same precedent as
  // SearchResults/DegradedSearchAnswer).
  if (result.synthesis_incomplete) {
    return <DegradedMarketPulse result={result} />;
  }

  const moodColor = /bull/i.test(result.market_mood || "") ? "text-emerald-400"
    : /bear/i.test(result.market_mood || "") ? "text-rose-400" : "text-amber-400";

  return (
    <div className="space-y-4 pb-36">
      {/* Query header */}
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] px-5 py-4">
        <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Market Pulse</p>
        <h1 className="text-[18px] font-bold text-text-primary leading-snug">{result.query}</h1>
        <p className="mt-1 text-[11px] text-text-muted">
          {result.market_status?.status ? `Market ${result.market_status.status.replace("_", " ")}` : ""}
          {result.market_status?.time_ist ? ` · ${result.market_status.time_ist} IST` : ""}
        </p>
      </div>

      {result.synthesis_incomplete && (
        <div className="flex items-start gap-3 rounded-[16px] border border-amber-500/25 bg-amber-500/[0.06] px-4 py-3">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-400"/>
          <p className="text-[12.5px] leading-5 text-amber-700/90 dark:text-amber-200/90">
            <span className="font-semibold text-amber-600 dark:text-amber-300">AI narrative couldn&apos;t be generated for this query.</span>{" "}
            Every number below is still real, live market data — only the written explanations are unavailable right now.
          </p>
        </div>
      )}

      {/* 1. Market Summary */}
      <div className={`rounded-[20px] border p-5 ${result.synthesis_incomplete ? DEGRADED_CARD_CLS : "border-violet-500/20 bg-gradient-to-br from-violet-500/[0.06] to-transparent"}`}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <p className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold">Market Summary</p>
            {result.synthesis_incomplete && <DegradedBadge/>}
          </div>
          {result.market_mood && <span className={`text-[12px] font-bold ${moodColor}`}>{result.market_mood}</span>}
        </div>
        <p className="text-[14px] text-text-primary leading-relaxed mb-3">{result.market_summary}</p>
        <div className="flex flex-wrap gap-2 mb-3">
          <span
            className="rounded-full border border-surface-border/8 bg-text-primary/[0.03] px-2.5 py-1 text-[10px] font-semibold text-text-secondary"
            title="An evidence-based composite (source/market/sector confirmation, macro alignment) with a minor self-assessed component -- not a fully computed score"
          >
            Market Confidence <span className="tabular-nums text-text-primary">{Math.round(result.scores.market_confidence.score)}%</span> · {result.scores.market_confidence.level}
          </span>
          <span className="rounded-full border border-surface-border/8 bg-text-primary/[0.03] px-2.5 py-1 text-[10px] font-semibold text-text-secondary">
            Catalyst Score <span className="tabular-nums text-text-primary">{Math.round(result.scores.catalyst_score)}%</span>
          </span>
        </div>
        {result.indices.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {result.indices.map(idx => (
              <div key={idx.ticker} className="rounded-[12px] border border-surface-border/6 bg-text-primary/[0.02] px-3 py-2">
                <p className="text-[9px] uppercase tracking-wider text-text-muted">{idx.name}</p>
                <p className="text-[12px] font-bold text-text-primary">{idx.value}</p>
                <p className={`text-[10px] font-semibold ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>{idx.change}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 2. Sector Rotation */}
      {(result.leading_sectors.length > 0 || result.lagging_sectors.length > 0) && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[13px] font-semibold text-text-primary mb-1">Sector Rotation</p>
          {result.sector_narrative && <p className="text-[12px] text-text-secondary mb-3">{result.sector_narrative}</p>}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-[9px] uppercase tracking-wider text-emerald-400 font-semibold mb-1.5">Leading</p>
              <div className="space-y-1.5">
                {result.leading_sectors.map(s => (
                  <div key={s.id} className="flex items-center justify-between rounded-lg border border-surface-border/4 bg-text-primary/[0.02] px-2.5 py-1.5">
                    <span className="text-[11px] font-semibold text-text-primary">{s.name}</span>
                    <span className="flex items-center gap-1.5">
                      <span className={`text-[11px] font-black tabular-nums ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.value}</span>
                      <span className="text-[9px] tabular-nums text-text-muted">({Math.round(s.momentum_score)})</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[9px] uppercase tracking-wider text-rose-400 font-semibold mb-1.5">Lagging</p>
              <div className="space-y-1.5">
                {result.lagging_sectors.map(s => (
                  <div key={s.id} className="flex items-center justify-between rounded-lg border border-surface-border/4 bg-text-primary/[0.02] px-2.5 py-1.5">
                    <span className="text-[11px] font-semibold text-text-primary">{s.name}</span>
                    <span className="flex items-center gap-1.5">
                      <span className={`text-[11px] font-black tabular-nums ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>{s.value}</span>
                      <span className="text-[9px] tabular-nums text-text-muted">({Math.round(s.momentum_score)})</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3. Top Performing Stocks */}
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
        <p className="text-[13px] font-semibold text-text-primary mb-3">Top Performing Stocks</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          {result.top_gainers.map(m => <PulseMoverCard key={m.ticker} m={m}/>)}
        </div>
        {result.top_losers.length > 0 && (
          <>
            <p className="text-[11px] uppercase tracking-wider text-text-muted font-semibold mb-2 mt-4">Biggest Losers</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {result.top_losers.map(m => <PulseMoverCard key={m.ticker} m={m}/>)}
            </div>
          </>
        )}
      </div>

      {/* Opportunity / Risk on record */}
      {(result.biggest_opportunity || result.biggest_risk) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {result.biggest_opportunity && (
            <div className="rounded-[16px] border border-emerald-500/20 bg-emerald-500/[0.04] p-4">
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] uppercase tracking-wider text-emerald-400 font-semibold">Biggest Opportunity on Record</p>
                {result.scores.opportunity_score != null && (
                  <span className="text-[11px] font-black tabular-nums text-emerald-400">{Math.round(result.scores.opportunity_score)}%</span>
                )}
              </div>
              <p className="text-[13px] font-bold text-text-primary">{result.biggest_opportunity.title}</p>
              {result.biggest_opportunity.summary && <p className="text-[11px] text-text-secondary mt-1">{result.biggest_opportunity.summary}</p>}
            </div>
          )}
          {result.biggest_risk && (
            <div className="rounded-[16px] border border-rose-500/20 bg-rose-500/[0.04] p-4">
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] uppercase tracking-wider text-rose-400 font-semibold">Biggest Risk on Record</p>
                <span className="text-[11px] font-black tabular-nums text-rose-400">{Math.round(result.scores.risk_score)}%</span>
              </div>
              <p className="text-[13px] font-bold text-text-primary">{result.biggest_risk.headline || result.biggest_risk.reason}</p>
            </div>
          )}
        </div>
      )}

      {/* 4. AI Conclusion */}
      {result.ai_conclusion && (
        <div className={`rounded-[20px] border p-5 ${result.synthesis_incomplete ? DEGRADED_CARD_CLS : "border-surface-border/7 bg-text-primary/[0.03]"}`}>
          <div className="flex items-center gap-2 mb-2">
            <Bot className="h-4 w-4 text-violet-400"/>
            <p className="text-[13px] font-semibold text-text-primary">AI Conclusion</p>
            {result.synthesis_incomplete && <DegradedBadge/>}
          </div>
          <p className="text-[13px] leading-6 text-text-secondary">{result.ai_conclusion}</p>
        </div>
      )}

      {/* 5. What to Watch Next */}
      {result.what_to_watch_next.length > 0 && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[13px] font-semibold text-text-primary mb-1">What to Watch Next</p>
          {result.what_to_watch_summary && <p className="text-[12px] text-text-secondary mb-3">{result.what_to_watch_summary}</p>}
          <div className="space-y-2">
            {result.what_to_watch_next.map(w => (
              <div key={w.id} className="flex items-start gap-3 rounded-lg border border-surface-border/4 bg-text-primary/[0.02] px-3 py-2">
                <Clock className="h-3.5 w-3.5 shrink-0 mt-0.5 text-text-muted"/>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold text-text-primary">{w.title}</span>
                    <span className="text-[9px] uppercase tracking-wider text-text-muted">{w.category}</span>
                  </div>
                  <p className="text-[10px] text-text-muted">{w.date}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <AIDisclaimer/>
    </div>
  );
}

// ── Landing ───────────────────────────────────────────────────

interface Suggestion { query: string; note: string | null; kind: string }
interface SuggestionData { items: Suggestion[]; asOf: string | null; live: number }

const SUGGESTIONS_WAIT_MS = 5000;

/** Today's example questions, built by the backend from the live market (sector moves, live headlines). `settled` turns true once the request has answered, failed or run out of patience, so the landing shows one set of questions and never swaps a static set for the live one. */
function useSuggestions(): { data: SuggestionData | null; settled: boolean } {
  const [state, setState] = useState<{ data: SuggestionData | null; settled: boolean }>({ data: null, settled: false });
  useEffect(() => {
    let off = false;
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), SUGGESTIONS_WAIT_MS);
    fetch(`${API}/api/ai/search/suggestions`, { signal: ctl.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (!off) setState({ data: j?.items?.length ? { items: j.items, asOf: j.as_of ?? null, live: j.live_count ?? 0 } : null, settled: true }); })
      .catch(() => { if (!off) setState({ data: null, settled: true }); /* static examples are used */ })
      .finally(() => clearTimeout(timer));
    return () => { off = true; ctl.abort(); clearTimeout(timer); };
  }, []);
  return state;
}

const KIND_ICON: Record<string, { icon: React.ComponentType<{ className?: string }>; tone: "violet" | "emerald" | "amber" | "sky" }> = {
  sector: { icon: BarChart3, tone: "violet" },
  company: { icon: Building2, tone: "sky" },
  macro: { icon: Globe2, tone: "amber" },
  evergreen: { icon: Lightbulb, tone: "emerald" },
};

function EmptyState({ onSearch, suggestions, settled, onReopen }: { onSearch: (q: string) => void; suggestions: SuggestionData | null; settled: boolean; onReopen: (q: string) => void }) {
  const items: Suggestion[] = suggestions?.items ?? EXAMPLES.slice(0, 6).map((q) => ({ query: q, note: null, kind: "evergreen" }));
  const live = (suggestions?.live ?? 0) > 0;
  const asOf = suggestions?.asOf ? new Date(suggestions.asOf).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : null;
  return (
    <div className="space-y-8 pt-2" data-testid="ai-search-empty">
      <div className="relative space-y-3 overflow-hidden rounded-3xl border border-surface-border/10 bg-surface-card px-6 py-7 shadow-[0_1px_2px_rgba(16,24,40,0.05)] sm:px-8 sm:py-9">
        <div aria-hidden className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-gradient-to-br from-violet-500/15 via-fuchsia-400/10 to-sky-400/15 blur-2xl" />
        <span className="relative inline-flex items-center gap-1.5 rounded-full border border-violet-500/25 bg-violet-500/10 px-3 py-1 text-[12px] font-medium text-violet-700"><Sparkles className="h-3.5 w-3.5" aria-hidden />Evidence-first market research</span>
        <h1 className="relative text-[30px] font-semibold leading-tight tracking-tight text-text-primary sm:text-[38px]">Ask about the <span className="bg-gradient-to-r from-violet-600 to-sky-500 bg-clip-text text-transparent">Indian market</span></h1>
        <p className="relative max-w-[640px] text-[15px] leading-7 text-text-secondary">
          Answers are built from live news, exchange filings and market data, and they say plainly what the evidence does not establish.
        </p>
      </div>
      {!settled ? (
        <section className="space-y-3" data-testid="suggestions-loading" aria-busy="true" aria-label="Loading example questions">
          <div className="h-3 w-40 rounded bg-surface-border/10" />
          <ul className="grid gap-3 sm:grid-cols-2">
            {[0, 1, 2, 3, 4, 5].map((i) => <li key={i} className="h-[62px] rounded-2xl border border-surface-border/10 bg-surface-card" />)}
          </ul>
        </section>
      ) : (
      <section className="space-y-3" data-testid="suggestions">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-muted">
          {live ? "Today in the market" : "Try asking"}{live && asOf ? <span className="ml-2 font-normal normal-case tracking-normal">updated {asOf}</span> : null}
        </h2>
        <ul className="grid gap-3 sm:grid-cols-2">
          {items.map((s) => (
            <li key={s.query}>
              <button type="button" onClick={() => onSearch(s.query)} className="group flex h-full w-full items-start gap-3 rounded-2xl border border-surface-border/10 bg-surface-card px-4 py-3.5 text-left shadow-[0_1px_2px_rgba(16,24,40,0.05)] transition hover:-translate-y-0.5 hover:border-violet-500/40 hover:shadow-md" data-kind={s.kind}>
                <IconTile icon={(KIND_ICON[s.kind] ?? KIND_ICON.evergreen).icon} tone={(KIND_ICON[s.kind] ?? KIND_ICON.evergreen).tone} />
                <span className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="text-[14.5px] font-medium leading-snug text-text-primary">{s.query}</span>
                  {s.note && <span className="text-[12px] leading-4 text-text-muted">{s.note}</span>}
                </span>
                <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-text-muted transition group-hover:translate-x-0.5 group-hover:text-violet-600" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      </section>
      )}
      <AISearchHistory onReopen={onReopen} />
    </div>
  );
}


// ── Page ──────────────────────────────────────────────────────

export default function AISearchClient() {
  const [query, setQuery] = useState("");
  const [input, setInput] = useState("");
  const [result, setResult] = useState<SearchResult | MarketPulseResult | null>(null);
  const [resultMeta, setResultMeta] = useState<{ responseId: string | null; cached: boolean; latencyMs: number | null; provider: string | null } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const didAutoSearch = useRef(false);
  const handledResult = useRef<unknown>(null);
  const searchParams = useSearchParams();
  const v3Stream = useAISearchStream();
  const session = useResearchSession();
  const { data: suggestions, settled: suggestionsSettled } = useSuggestions();
  const [clarification, setClarification] = useState<{ term: string; candidates: { symbol: string; name: string }[]; originalQuery: string } | null>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); textareaRef.current?.focus(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const runSearch = useCallback(async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed || loading) return;
    setQuery(trimmed);
    setInput(trimmed);
    setLoading(true);
    setError(null);
    setResult(null);
    setResultMeta(null);
    setClarification(null);
    setHistory((prev) => [trimmed, ...prev.filter((h) => h !== trimmed)].slice(0, 10));
    try {
      const existing = JSON.parse(localStorage.getItem(AI_SEARCH_HISTORY_KEY) ?? "[]");
      const entry = { id: `s-${Date.now()}`, title: trimmed, href: `/ai-search?q=${encodeURIComponent(trimmed)}`, timestamp: Date.now() };
      const deduped = existing.filter((e: { title: string }) => e.title !== trimmed);
      localStorage.setItem(AI_SEARCH_HISTORY_KEY, JSON.stringify([entry, ...deduped].slice(0, 20)));
      window.dispatchEvent(new Event(AI_SEARCH_HISTORY_EVENT));
    } catch { /* history is a convenience */ }
    if (AI_SEARCH_V3_ENABLED) {
      // Streaming path: the result or error lands in the effect below.
      v3Stream.run(trimmed, history, session.toApiContext());
      return;
    }
    try {
      const res = await fetch(`${API}/api/ai/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: trimmed, history, session_context: session.toApiContext() ?? null }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Search failed" }));
        throw new Error(err.detail || "Search failed");
      }
      const data = await res.json();
      setResult(data.result);
      setResultMeta({ responseId: data.result?.response_id ?? null, cached: !!data.cached, latencyMs: null, provider: null });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [loading, history, v3Stream, session]);

  const resetToEmptySearch = useCallback(() => {
    setResult(null); setResultMeta(null); setQuery(""); setInput(""); setClarification(null); setError(null);
    textareaRef.current?.focus();
  }, []);

  // Streaming terminal state (result or error) back into the page state, so everything downstream is identical for both transports.
  useEffect(() => {
    if (!AI_SEARCH_V3_ENABLED) return;
    if (v3Stream.result) {
      // Each distinct streamed result is handled once, however many times this effect re-runs.
      if (handledResult.current === v3Stream.result) return;
      handledResult.current = v3Stream.result;
      const r = v3Stream.result as SearchResult & MarketPulseResult;
      if (r.needs_clarification) {
        setClarification({ term: r.ambiguous_term ?? "", candidates: r.candidates ?? [], originalQuery: query });
        setLoading(false);
        return;
      }
      setResult(r);
      setResultMeta(v3Stream.meta);
      setLoading(false);
      if (r.type !== "market_pulse") {
        const a = r as SearchResult;
        session.addFromResult(query, a.response_id ?? null, {
          companies: (a.companies ?? []).map((c) => ({ symbol: c.symbol, name: c.name })).filter((c: SessionEntity) => isRealSymbol(c.symbol)),
          sectors: (a.sectors ?? []).map((s) => s.name),
          events: (a.related_events ?? []).slice(0, 3).map((e) => e.title),
          policies: (a.policies ?? []).slice(0, 2).map((p) => p.title),
          verdict: authorizedVerdict(a)?.rating ?? null,       // no verdict is a null, never a "Not Applicable" the session would remember
        });
      }
    } else if (v3Stream.error) {
      setError(v3Stream.error);
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [v3Stream.result, v3Stream.error]);

  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !didAutoSearch.current) {
      didAutoSearch.current = true;
      setInput(q);
      runSearch(q);
    }
  }, [searchParams, runSearch]);

  function handleSubmit(e: React.FormEvent) { e.preventDefault(); runSearch(input); }
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runSearch(input); }
  }

  return (
    <div className="mx-auto w-full max-w-[1120px] space-y-6 py-6" data-testid="ai-search-page">
      <ContextChips
        companies={session.companies}
        sectors={session.sectors}
        timeHorizon={session.timeHorizon}
        riskTolerance={session.riskTolerance}
        onRemoveCompany={session.removeCompany}
        onRemoveSector={session.removeSector}
        onClearHorizon={() => session.setPreference("timeHorizon", null)}
        onClearRisk={() => session.setPreference("riskTolerance", null)}
      />
      <form onSubmit={handleSubmit}>
        <div className="flex items-end overflow-hidden rounded-2xl border border-surface-border/10 bg-surface-card shadow-sm focus-within:border-violet-500/50">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a market question: a company, a sector, a comparison, or a term"
            aria-label="Ask a market question"
            disabled={loading}
            rows={2}
            className="min-w-0 flex-1 resize-none bg-transparent px-4 py-4 text-[15px] leading-6 text-text-primary outline-none placeholder:text-text-muted disabled:opacity-50"
          />
          <div className="flex items-center gap-2 p-3">
            {query && (
              <button type="button" onClick={resetToEmptySearch} aria-label="Clear" className="flex h-9 w-9 items-center justify-center rounded-xl border border-surface-border/10 text-text-secondary hover:text-text-primary">
                <RotateCcw className="h-4 w-4" />
              </button>
            )}
            <button type="submit" disabled={!input.trim() || loading} className="rounded-xl bg-violet-600 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-violet-500 disabled:opacity-40">
              {loading ? "Working…" : "Ask"}
            </button>
          </div>
        </div>
      </form>

      {error && (
        <div className="flex items-center gap-3 rounded-2xl border border-surface-border/10 border-l-4 border-l-rose-500 bg-surface-card p-4" role="alert" data-testid="ai-search-error">
          <AlertTriangle className="h-5 w-5 shrink-0 text-rose-500" />
          <div className="min-w-0">
            <p className="text-[14px] font-medium text-text-primary">The search didn&apos;t go through</p>
            <p className="text-[12.5px] text-text-muted">{error}</p>
          </div>
          <button onClick={() => runSearch(query)} className="ml-auto shrink-0 rounded-xl border border-surface-border/10 px-3 py-1.5 text-[12px] font-medium text-text-primary hover:border-violet-500/40">Retry</button>
        </div>
      )}

      {clarification ? (
        <ClarificationPicker
          ambiguousTerm={clarification.term}
          candidates={clarification.candidates}
          onPick={(_symbol, name) => {
            const re = new RegExp(`\\b${clarification.term}\\b`, "i");
            const substituted = clarification.originalQuery.replace(re, name);
            setClarification(null);
            runSearch(substituted);
          }}
        />
      ) : loading ? (
        <ResearchingCard query={query} stages={AI_SEARCH_V3_ENABLED ? v3Stream.stageHistory : []} />
      ) : result ? (
        result.type === "market_pulse"
          ? <MarketPulseResults result={result as MarketPulseResult} />
          : (
            <AnswerV2
              result={result as SearchResult}
              onFollowUp={runSearch}
              onRetry={() => runSearch(query)}
              onNewSearch={resetToEmptySearch}
              nextQuestions={suggestions?.items.map((s) => s.query)}
              feedbackMeta={{
                responseId: (result as SearchResult).response_id ?? resultMeta?.responseId ?? null,
                query,
                specialist: (result as SearchResult).specialist ?? null,
                schemaVersion: (result as SearchResult).schema_version ?? null,
                cached: resultMeta?.cached ?? false,
                latencyMs: resultMeta?.latencyMs ?? null,
                provider: resultMeta?.provider ?? null,
              }}
            />
          )
      ) : (
        <EmptyState onSearch={runSearch} suggestions={suggestions} settled={suggestionsSettled} onReopen={runSearch} />
      )}
    </div>
  );
}
