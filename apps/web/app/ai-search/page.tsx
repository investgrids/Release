"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Bot, BarChart2, CheckCircle2, Sparkles, Bookmark, Plus, Download, Share2, Copy, TrendingUp, TrendingDown, Minus, RotateCcw, Building2, ChevronRight, Target, Truck, Landmark, Factory, Ship, LineChart as LineChartIcon, ShieldAlert, Users, Cpu, Wallet, Scale, Receipt, GitBranch, DollarSign, Package, CreditCard, Eye, ListChecks, ArrowRight, Clock, AlertTriangle, GitCompare, FileText } from "lucide-react";
import { AITransparencyPanel } from "@/components/ai/AITransparencyPanel";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import { DecisionIntelligencePanel, type DecisionIntelligence } from "@/components/ai/DecisionIntelligencePanel";
import { AISearchGraphReveal } from "@/components/ai/AISearchGraphReveal";
import { AISearchFindingsRecap } from "@/components/ai/AISearchFindingsRecap";
import { SearchProgressStages } from "@/components/ai/SearchProgressStages";
import { AISearchHistory, AI_SEARCH_HISTORY_KEY, AI_SEARCH_HISTORY_EVENT } from "@/components/ai/AISearchHistory";
import { InvestmentVerdictHero, weightedShare, clamp01to100, type HeroVerdictData } from "@/components/ai/InvestmentVerdictHero";
import { AISearchFeedback, type AISearchFeedbackMeta } from "@/components/ai/AISearchFeedback";
import { RefineAnalysisPanel, type RefinedDecision } from "@/components/ai/RefineAnalysisPanel";
import { FollowUpIntelligence, type FollowUpGroup } from "@/components/ai/FollowUpIntelligence";
import { useResearchSession, type SessionEntity } from "@/lib/hooks/useResearchSession";
import { ContextChips } from "@/components/ai/ContextChips";
import { ResearchWorkspace } from "@/components/ai/ResearchWorkspace";
import { ClarificationPicker } from "@/components/ai/ClarificationPicker";
import { InvestmentWatchPanel, type WatchSubject } from "@/components/ai/InvestmentWatchPanel";
import { DecisionTimelinePanel, type TimelineIntelligence } from "@/components/ai/DecisionTimelinePanel";
import { ConfidenceBreakdownPanel } from "@/components/ai/ConfidenceBreakdownPanel";
import { openResearchReport, downloadMarkdown } from "@/lib/researchReport";
import type { ResponseMeta } from "@/lib/hooks/useAISearchStream";
import { useAISearchStream } from "@/lib/hooks/useAISearchStream";
import { API_BASE_URL as API } from "@/lib/api";
import { fixMojibake, isRealSymbol } from "@/lib/text";

// Opt-in only — V3's intelligence pipeline hasn't been cut over to
// production traffic yet (see the V3 Phase 1 plan's migration section).
// Toggle locally via NEXT_PUBLIC_AI_SEARCH_V3=1 in .env.local.
const AI_SEARCH_V3_ENABLED = process.env.NEXT_PUBLIC_AI_SEARCH_V3 === "1";


// ── Types ──────────────────────────────────────────────────────────────────────
interface AnswerSection {
  summary: string; bottom_line: string; what_happened: string; why_it_happened: string;
  immediate_impact: string; medium_term: string; long_term: string;
  what_priced_in: string;
  risks: string[]; opportunities: string[];
  confidence: number | null; confidence_level?: string;
  sentiment: "bullish" | "bearish" | "neutral";
  sources_count: number;
}
interface KeyDriver    { icon: string; title: string; explanation: string; confidence: number | null; }
interface Insight      { icon: string; title: string; summary: string; }
interface Company      { symbol: string; name: string; price: string; change: string; positive: boolean; impact_type: string; impact_score: number | null; confidence: number | null; reason: string; chart: number[]; ripple_position?: string; why_it_matters?: string; }
interface Sector       { name: string; score: number | null; confidence: number | null; outlook: string; positive: boolean; status?: string; time_horizon?: string; explanation?: string; }
interface RelatedEvent { id: string; title: string; date: string; impact_score: number | null; confidence: number | null; category: string; }
interface NewsItem     { id: string; headline: string; summary: string; source: string; published_at: string; impact_score: number | null; }
interface Policy       { id: number; title: string; ministry: string; status: string; impact_score: number | null; }
interface Timeline     { date: string; title: string; description: string; }
interface HistoricalMove       { symbol: string; name: string; return_1w?: number; return_1m?: number; reason: string; }
interface HistoricalComparison {
  event_title: string; event_date: string; similarity: number; key_lesson: string;
  key_difference: string;
  what_happened: string; sector_reactions: Record<string, number>;
  historical_winners: HistoricalMove[]; historical_losers: HistoricalMove[];
  nifty_1w: number | null; nifty_1m: number | null;
}
interface RippleNode  { id: string; label: string; type: string; direction: string; weight: number; parent_id: string | null; }
interface RippleLevel { depth: number; nodes: RippleNode[]; }
interface Scenario      { probability: number; outcome: string; key_drivers: string[]; supporting_evidence: string; major_catalysts: string[]; expected_evolution: string; confidence: number | null; }
interface Scenarios     { bull?: Scenario; base?: Scenario; bear?: Scenario; degraded?: boolean; }
interface MarketHorizon { horizon: string; window: string; confidence: number | null; direction: string; description: string; }
interface MonitorItem   { title: string; why_it_matters: string; importance: string; frequency: string; }
interface ReasoningMethod { label: string; used: boolean; }
interface ConfidenceData  { level: string; score: number | null; reasons: string[]; breakdown: Record<string, number>; caveats: string[]; }
interface InvestmentVerdict { rating: string; direction: string; confidence: number | null; horizon: string; top_picks: string[]; risks: string[]; catalysts: string[]; opportunity_score: number | null; risk_level?: string; suitable_for?: string; }
interface ChartSeries  { name: string; data: number[]; color: string; }
interface MarketChart  { labels: string[]; series: ChartSeries[]; }
interface GraphNode    { id: string; label: string; type: string; x: number; y: number; }
interface GraphEdge    { id: string; source: string; target: string; label: string; }

// ── V3-only fields (Phase 1) ─────────────────────────────────────────────────
// Absent on V2 responses — every consumer must treat these as optional and
// degrade gracefully (see InvestmentVerdictHero, which renders nothing when
// decision_engine_v2/ai_conclusion are missing rather than showing empty UI).
interface DecisionEngineV2 {
  verdict_scale: string; // one of VERDICT_SCALE (schema.py) — already research-framed, never "Buy/Sell/Hold"
  why: string;
  what_changes_the_view: string[];
  what_invalidates_the_thesis: string[];
  explain_why_not?: { alternative: string; reason_rejected: string } | null;
}
interface AIConclusion {
  current_view: string; reason: string;
  biggest_opportunity: string; biggest_risk: string;
  investor_action_note: string;
}
interface EvidenceScoreV3 { stars: number; checklist: Record<string, boolean>; source_count: number; }
interface ConfidenceBreakdown {
  evidence_quality: number; market_confirmation: number; historical_similarity: number;
  data_freshness: number; reasoning_confidence: number; final_confidence: number;
  level: string; reasons: string[];
}
interface OpportunityRiskMatrix {
  opportunity: { high?: string[]; medium?: string[]; low?: string[] };
  risk: { high?: string[]; medium?: string[]; low?: string[] };
}

interface SearchResult {
  type?: "search";
  query: string; synthesis_incomplete?: boolean; answer: AnswerSection; key_drivers: KeyDriver[]; insights: Insight[];
  companies: Company[]; sectors: Sector[]; related_events: RelatedEvent[];
  news: NewsItem[]; policies: Policy[]; timeline: Timeline[];
  historical_comparison: HistoricalComparison[];
  ripple_chain: RippleLevel[];
  scenarios: Scenarios;
  market_impact_horizons: MarketHorizon[];
  what_to_monitor: MonitorItem[];
  ai_reasoning_methods: ReasoningMethod[];
  follow_up_questions: string[];
  follow_up_groups?: FollowUpGroup[];
  investment_verdict: InvestmentVerdict; market_chart: MarketChart;
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  citations: string[];
  decision_intelligence: DecisionIntelligence | null;
  confidence_data?: ConfidenceData;
  // V3 Phase 1 additions — all optional, all absent on V2 responses.
  response_id?: string;
  schema_version?: string;
  specialist?: string;
  decision_engine_v2?: DecisionEngineV2;
  ai_conclusion?: AIConclusion;
  timeline_intelligence?: TimelineIntelligence;
  evidence_score?: EvidenceScoreV3;
  confidence_breakdown?: ConfidenceBreakdown;
  opportunity_risk_matrix?: OpportunityRiskMatrix;
  // Phase 1.7 — what (if anything) the research session contributed to
  // this specific answer; see session_context.resolve_context on the backend.
  context_used?: { companies: string[]; sectors: string[] };
  // Phase 2B — the single company/sector this response resolves to, if
  // any (null for comparisons/multi-subject queries); see pipeline.py's
  // subject_for docstring. Drives the Investment Watch panel directly —
  // the frontend never re-derives which subject a query was "about".
  watch_subject?: WatchSubject | null;
}

// ── Market Pulse types ───────────────────────────────────────────────────────
// A distinct response shape for "which stocks performed well" / "best
// sector" / "market summary" style queries — real market data fetched
// before any LLM call (market_intelligence_service.py), the model only
// explains it. Never merged into SearchResult: the two answer different
// questions and mixing their rendering would blur that distinction.
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
interface MarketPulseResult {
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
}

// ── Constants ──────────────────────────────────────────────────────────────────
// Qualitative only — no counts/percentages, since none are known until the
// real response arrives. Loops indefinitely (see SearchWaitingState) so a
// slow provider-fallback request never looks "finished" and stuck.
const WAITING_PHRASES: string[] = [
  "Understanding the market context…",
  "Scanning today's events and news…",
  "Connecting today's events…",
  "Checking historical market reactions…",
  "Weighing sector and company impact…",
  "Structuring the intelligence graph…",
  "Drafting the analysis…",
  "Almost there — finalizing the report…",
];

const EXAMPLES = [
  "Should I invest in defence stocks after the latest budget?",
  "I hold Manappuram Finance. Should I switch to Natco Pharma?",
  "Should I continue holding BEL or switch to HAL?",
  "What is the impact of RBI rate cut on banking stocks?",
  "Which is better for 6 months: HAL or BEL?",
  "Should I rotate from Banking to Pharma right now?",
];

const CATEGORY_COLOR: Record<string, string> = {
  Government:          "bg-violet-500/20 text-violet-600 dark:text-violet-300 border-violet-500/30",
  "Government Policy": "bg-violet-500/20 text-violet-600 dark:text-violet-300 border-violet-500/30",
  Policy:              "bg-sky-500/20 text-sky-600 dark:text-sky-300 border-sky-500/30",
  Corporate:           "bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border-emerald-500/30",
  "Economic Event":    "bg-teal-500/20 text-teal-600 dark:text-teal-300 border-teal-500/30",
  "Industry Update":   "bg-amber-500/20 text-amber-600 dark:text-amber-300 border-amber-500/30",
  RBI:                 "bg-indigo-500/20 text-indigo-600 dark:text-indigo-300 border-indigo-500/30",
  Macro:               "bg-amber-500/20 text-amber-600 dark:text-amber-300 border-amber-500/30",
  Market:              "bg-teal-500/20 text-teal-600 dark:text-teal-300 border-teal-500/30",
};

const EVENT_STATUS_COLORS: Record<string, { dot: string; label: string; bg: string }> = {
  Completed: { dot: "bg-emerald-400", label: "Completed", bg: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
  Ongoing:   { dot: "bg-amber-400 animate-pulse", label: "Ongoing",   bg: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
  Upcoming:  { dot: "bg-sky-400",    label: "Upcoming",  bg: "bg-sky-500/10 text-sky-400 border-sky-500/20" },
};

// Fixed keyword whitelist enforced by the backend prompt for key_drivers[].icon
const DRIVER_ICON_MAP: Record<string, ReactNode> = {
  procurement:   <Package className="h-4 w-4"/>,
  policy:        <Landmark className="h-4 w-4"/>,
  manufacturing: <Factory className="h-4 w-4"/>,
  export:        <Ship className="h-4 w-4"/>,
  valuation:     <LineChartIcon className="h-4 w-4"/>,
  risk:          <ShieldAlert className="h-4 w-4"/>,
  demand:        <Users className="h-4 w-4"/>,
  technology:    <Cpu className="h-4 w-4"/>,
  capex:         <Wallet className="h-4 w-4"/>,
  regulation:    <Scale className="h-4 w-4"/>,
  earnings:      <Receipt className="h-4 w-4"/>,
  "supply-chain": <Truck className="h-4 w-4"/>,
  currency:      <DollarSign className="h-4 w-4"/>,
  commodity:     <Package className="h-4 w-4"/>,
  credit:        <CreditCard className="h-4 w-4"/>,
};

const RIPPLE_TYPE_COLOR: Record<string, string> = {
  policy:    "border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-300",
  sector:    "border-sky-500/30 bg-sky-500/10 text-sky-600 dark:text-sky-300",
  commodity: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-300",
  company:   "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
  event:     "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-300",
};

const RIPPLE_POSITION_COLOR: Record<string, string> = {
  "Primary Beneficiary":   "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border-emerald-500/30",
  "Secondary Beneficiary": "bg-emerald-500/10 text-emerald-400/80 border-emerald-500/20",
  "Primary Pressure":      "bg-rose-500/15 text-rose-600 dark:text-rose-300 border-rose-500/30",
  "Secondary Pressure":    "bg-rose-500/10 text-rose-400/80 border-rose-500/20",
  "Indirect Exposure":     "bg-slate-500/10 text-text-secondary border-surface-border/5",
};

const SECTOR_STATUS_COLOR: Record<string, string> = {
  "Structural Tailwind": "text-emerald-400",
  "Beneficiary":         "text-emerald-400/80",
  "Indirect Benefit":    "text-sky-400",
  "Headwind":            "text-amber-400",
  "Structural Headwind": "text-rose-400",
};

const OUTLOOK_COLOR: Record<string, string> = {
  "Strongly Constructive":    "text-emerald-400",
  "Constructive":             "text-emerald-400",
  "Positive Outlook":         "text-emerald-400/80",
  "Selectively Constructive": "text-sky-400",
  "Neutral":                  "text-amber-400",
  "Cautious":                 "text-amber-400",
  "Elevated Risk":            "text-rose-400",
  "High Uncertainty":         "text-rose-400",
};

// Professional status-dot indicator per outlook label — no emoji.
const OUTLOOK_DOT: Record<string, string> = {
  "Strongly Constructive":    "bg-emerald-400",
  "Constructive":             "bg-emerald-400",
  "Positive Outlook":         "bg-emerald-400/70",
  "Selectively Constructive": "bg-sky-400",
  "Neutral":                  "bg-amber-400",
  "Cautious":                 "bg-amber-400",
  "Elevated Risk":            "bg-rose-500",
  "High Uncertainty":         "bg-rose-500",
};

// ── Micro-components ──────────────────────────────────────────────────────────

/** Large circular gauge SVG — used in right sidebar Investment Verdict */
function BigGauge({ score, size = 120 }: { score: number | null | undefined; size?: number }) {
  const unscored = score === null || score === undefined;
  const r = size * 0.38;
  const cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * r;
  const dash = unscored ? 0 : (score / 100) * circ;
  const color = unscored ? "rgb(var(--text-muted))" : score >= 80 ? "#22c55e" : score >= 60 ? "#60a5fa" : "#f59e0b";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgb(var(--text-primary) / 0.06)" strokeWidth="8"/>
      {!unscored && (
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`}
          style={{ transition: "stroke-dasharray 1s ease" }}/>
      )}
      <text x={cx} y={cy + 6} textAnchor="middle" fill="white"
        fontSize={unscored ? size * 0.14 : size * 0.22} fontWeight="800" fontFamily="inherit">
        {unscored ? "N/A" : `${score}%`}
      </text>
    </svg>
  );
}

/** Small ring used in company cards */
function SmallRing({ score, size = 36 }: { score: number | null | undefined; size?: number }) {
  const unscored = score === null || score === undefined;
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const dash = unscored ? 0 : (score / 100) * circ;
  const color = unscored ? "rgb(var(--text-muted))" : score >= 80 ? "#22c55e" : score >= 60 ? "#60a5fa" : "#f59e0b";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgb(var(--text-primary) / 0.08)" strokeWidth="3"/>
      {!unscored && (
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="3"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
          transform={`rotate(-90 ${size/2} ${size/2})`}/>
      )}
      <text x={size/2} y={size/2 + 4} textAnchor="middle" fill={color}
        fontSize={unscored ? size * 0.18 : size * 0.25} fontWeight="700" fontFamily="inherit">
        {unscored ? "N/A" : score}
      </text>
    </svg>
  );
}

/** Mini sparkline for company chart */
function MiniSparkline({ data, positive, width = 72, height = 28 }: { data: number[]; positive: boolean; width?: number; height?: number }) {
  if (!data?.length) return <div style={{ width, height }} className="rounded bg-text-primary/[0.03]"/>;
  const min = Math.min(...data), max = Math.max(...data), range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / Math.max(data.length - 1, 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(" ");
  const color = positive ? "#22c55e" : "#f43f5e";
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

/** Risk severity badge */
function RiskSeverity({ text }: { text: string }) {
  const t = text.toLowerCase();
  const isHigh = /crash|collapse|severe|major|significant/.test(t);
  const isLow  = /minor|slight|small|low|unlikely/.test(t);
  const level  = isHigh ? "High" : isLow ? "Low" : "Medium";
  const cls    = isHigh
    ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
    : isLow
    ? "bg-sky-500/10 text-sky-400 border-sky-500/20"
    : "bg-amber-500/10 text-amber-400 border-amber-500/20";
  return <span className={`rounded border px-1.5 py-0.5 text-[9px] font-semibold ${cls}`}>{level}</span>;
}

/** Direction icon for the AI Decision card */
function DirectionIcon({ direction, size = 56 }: { direction: string; size?: number }) {
  const isBull = direction === "bullish";
  const isBear = direction === "bearish";
  const color  = isBull ? "#22c55e" : isBear ? "#f43f5e" : "#f59e0b";
  const bg     = isBull ? "rgba(34,197,94,0.12)" : isBear ? "rgba(244,63,94,0.12)" : "rgba(245,158,11,0.12)";
  return (
    <div style={{ width: size, height: size, background: bg, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}>
      {isBull ? <TrendingUp style={{ color, width: size * 0.5, height: size * 0.5 }} strokeWidth={2.5}/>
              : isBear ? <TrendingDown style={{ color, width: size * 0.5, height: size * 0.5 }} strokeWidth={2.5}/>
              : <Minus style={{ color, width: size * 0.5, height: size * 0.5 }} strokeWidth={2.5}/>}
    </div>
  );
}

/** Single canonical confidence number for a SearchResult — every display on
 *  this page (main stats, sidebar gauge, sidebar bar, transparency panel)
 *  must go through this, not re-derive its own fallback chain. Order:
 *  confidence_data.score (the real evidence-based total) is authoritative
 *  when present; answer.confidence and investment_verdict.confidence are
 *  older/narrower fallbacks kept only for results computed before
 *  confidence_data existed. */
function displayConfidence(result: Pick<SearchResult, "confidence_data" | "answer" | "investment_verdict"> | null | undefined): number | null {
  return result?.confidence_data?.score ?? result?.answer?.confidence ?? result?.investment_verdict?.confidence ?? null;
}

/** Derive risk level from confidence */
function riskLevel(confidence: number | null | undefined): { label: string; color: string } {
  if (confidence === null || confidence === undefined) return { label: "Unscored", color: "text-text-muted bg-text-primary/[0.05] border-surface-border/7" };
  if (confidence >= 85) return { label: "Low", color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" };
  if (confidence >= 65) return { label: "Medium", color: "text-amber-400 bg-amber-500/10 border-amber-500/20" };
  return { label: "High", color: "text-rose-400 bg-rose-500/10 border-rose-500/20" };
}

/** Suitable for label from horizon */
function suitableFor(horizon: string): string {
  if (!horizon) return "All investors";
  const h = horizon.toLowerCase();
  if (h.includes("long") || h.includes("year")) return "Long-term investors";
  if (h.includes("medium") || h.includes("month")) return "Medium-term investors";
  return "Short-term traders";
}

/** Infer event status from date string */
function inferStatus(dateStr: string): "Completed" | "Ongoing" | "Upcoming" {
  if (!dateStr) return "Upcoming";
  const d = dateStr.toLowerCase();
  if (d.includes("ongoing") || d.includes("current")) return "Ongoing";
  if (d.includes("upcoming") || d.includes("next") || d.includes("future")) return "Upcoming";
  try {
    const parsed = new Date(dateStr);
    if (!isNaN(parsed.getTime())) {
      if (parsed < new Date()) return "Completed";
      return "Upcoming";
    }
  } catch { /**/ }
  return "Completed";
}

// ── Waiting state ──────────────────────────────────────────────────────────────
// Foreshadows the real Intelligence Graph reveal (see AISearchGraphReveal) with
// an abstract shape — no labels, no counts, purely ambient. Query dot on top,
// a row of sector dots, a row of company dots below, faint connecting lines,
// gentle breathing opacity so it reads as "working," not "frozen."
function AmbientGraphPulse() {
  const sectorX = [-48, -16, 16, 48];
  const companyX = [-64, -32, 0, 32, 64];
  return (
    <svg width="200" height="110" viewBox="-100 -6 200 110" className="overflow-visible">
      {sectorX.map((x, i) => (
        <line key={`qs-${i}`} x1={0} y1={6} x2={x} y2={46} stroke="#334155" strokeWidth={1} strokeOpacity={0.35} />
      ))}
      {companyX.map((x, i) => (
        <line key={`sc-${i}`} x1={sectorX[i % sectorX.length]} y1={46} x2={x} y2={86} stroke="#334155" strokeWidth={1} strokeOpacity={0.35} />
      ))}
      <motion.circle cx={0} cy={6} r={6} fill="#a78bfa"
        animate={{ opacity: [0.35, 0.9, 0.35] }} transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }} />
      {sectorX.map((x, i) => (
        <motion.circle key={`s-${i}`} cx={x} cy={46} r={4} fill="#34d399"
          animate={{ opacity: [0.25, 0.7, 0.25] }} transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut", delay: 0.15 + i * 0.12 }} />
      ))}
      {companyX.map((x, i) => (
        <motion.circle key={`c-${i}`} cx={x} cy={86} r={3.5} fill="#818cf8"
          animate={{ opacity: [0.2, 0.6, 0.2] }} transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut", delay: 0.35 + i * 0.1 }} />
      ))}
    </svg>
  );
}

function SearchWaitingState({ query }: { query: string }) {
  const [phraseIdx, setPhraseIdx] = useState(0);
  const [elapsedSec, setElapsedSec] = useState(0);
  const startRef = useRef(Date.now());

  useEffect(() => {
    startRef.current = Date.now();
    const phraseTimer = setInterval(() => setPhraseIdx(i => (i + 1) % WAITING_PHRASES.length), 2800);
    const clockTimer = setInterval(() => setElapsedSec(Math.floor((Date.now() - startRef.current) / 1000)), 1000);
    return () => { clearInterval(phraseTimer); clearInterval(clockTimer); };
  }, []);

  return (
    <div className="space-y-4 pb-10">
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-6">
        <div className="flex items-start gap-4 mb-6">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-500/20 text-violet-400">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="flex-1">
            <p className="text-[11px] uppercase tracking-widest text-violet-400 mb-1">AI Answer</p>
            <p className="text-sm text-text-secondary">Researching: <span className="text-text-primary font-medium">{query}</span></p>
          </div>
          <span className="text-[10px] text-text-muted tabular-nums shrink-0 mt-1">{elapsedSec}s elapsed</span>
        </div>

        <AnimatePresence mode="wait">
          <motion.p key={phraseIdx}
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.4 }}
            className="flex items-center gap-2 text-[13px] text-text-secondary">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400 animate-pulse" />
            {WAITING_PHRASES[phraseIdx]}
          </motion.p>
        </AnimatePresence>

        <div className="mt-6 flex items-center justify-center">
          <AmbientGraphPulse />
        </div>
      </div>
      {[1, 2].map(i => (
        <div key={i} className="h-40 animate-pulse rounded-[20px] bg-text-primary/[0.03]"/>
      ))}
    </div>
  );
}

// ── Empty state ────────────────────────────────────────────────────────────────
function EmptyState({ onSearch }: { onSearch: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center py-14 text-center space-y-8">
      <div className="relative">
        <div className="h-20 w-20 rounded-full bg-gradient-to-br from-violet-500/20 to-sky-500/10 flex items-center justify-center border border-violet-500/20">
          <Sparkles className="h-9 w-9 text-violet-400" />
        </div>
        <div className="absolute -inset-4 rounded-full bg-violet-500/5 blur-xl"/>
      </div>
      <div>
        <h2 className="text-xl font-semibold text-text-primary mb-2">AI Decision Intelligence Engine</h2>
        <p className="text-sm text-text-secondary max-w-md leading-relaxed">Ask any investment decision question — hold, switch, compare, or analyse. Get explainable AI reasoning, evidence, and trade-offs.</p>
      </div>
      <div className="w-full max-w-xl space-y-2">
        <p className="text-[10px] uppercase tracking-widest text-text-muted mb-3">Try these searches</p>
        {EXAMPLES.map(q => (
          <button key={q} onClick={() => onSearch(q)}
            className="group flex w-full items-center gap-3 rounded-[14px] border border-surface-border/6 bg-text-primary/[0.02] px-4 py-3 text-left text-[13px] text-text-secondary transition hover:border-violet-500/30 hover:bg-violet-500/[0.04] hover:text-text-primary">
            <Search className="h-4 w-4 text-violet-400 shrink-0" />
            {q}
            <span className="ml-auto text-text-muted group-hover:text-violet-400 transition text-sm">→</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Search Results ─────────────────────────────────────────────────────────────
// ── Market Pulse Results ─────────────────────────────────────────────────────
// Hierarchy: Market Summary → Leading Sectors → Top Performing Stocks (each
// with real verified-driver chips) → AI Conclusion → What to Watch Next.
// Every number here came from market_intelligence_service.py before the LLM
// ever ran — this component only formats it. The LLM contributed exactly
// four things: market_summary, sector_narrative, each mover's narrative
// sentence, ai_conclusion, and what_to_watch_summary — never the lists
// themselves.
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
      Generic Analysis
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
      <p className="text-[11.5px] leading-5 text-text-secondary">{m.narrative}</p>
    </div>
  );
}

function MarketPulseResults({ result }: { result: MarketPulseResult }) {
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
          <span className="rounded-full border border-surface-border/8 bg-text-primary/[0.03] px-2.5 py-1 text-[10px] font-semibold text-text-secondary">
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

// Graph + findings recap, played the instant a real result mounts. A
// separate call site from SearchResults's own `companies` filtering below —
// isRealSymbol is reapplied here since this reads `result.companies` fresh.
function ResultReveal({ result }: { result: SearchResult }) {
  const companies = result.companies.filter(c => isRealSymbol(c.symbol));
  const topHistorical = result.historical_comparison?.[0] ?? null;
  return (
    <div className="mb-4 grid gap-4 sm:grid-cols-[1.1fr_1fr]">
      <AISearchGraphReveal nodes={result.graph?.nodes ?? []} edges={result.graph?.edges ?? []} />
      <AISearchFindingsRecap
        sourcesCount={result.answer?.sources_count ?? 0}
        companies={companies}
        sectors={result.sectors ?? []}
        topHistoricalMatch={topHistorical ? { event_title: topHistorical.event_title, similarity: topHistorical.similarity } : null}
      />
    </div>
  );
}

function SearchResults({ result, onFollowUp, resultTime, resultMeta, onRefined }: {
  result: SearchResult;
  onFollowUp: (q: string) => void;
  resultTime: Date;
  resultMeta?: ResponseMeta | null;
  onRefined: (refined: RefinedDecision, newResponseId: string) => void;
}) {
  const [showMore, setShowMore] = useState(false);
  const [saved, setSaved] = useState(false);
  const [activeRippleNode, setActiveRippleNode] = useState<string | null>(null);

  const { answer, key_drivers, companies: rawCompanies, sectors, related_events, news, policies,
          investment_verdict, historical_comparison,
          ripple_chain, scenarios, market_impact_horizons, what_to_monitor,
          ai_reasoning_methods, confidence_data, market_chart,
          follow_up_questions, follow_up_groups, decision_intelligence, context_used,
          decision_engine_v2, ai_conclusion, evidence_score, confidence_breakdown, opportunity_risk_matrix,
          timeline_intelligence } = result;

  // The AI can hallucinate a placeholder ticker ("Not Provided", "N/A") when
  // it can't identify a specific company — filtered here once so every
  // downstream render (avatar, symbol text, compare link, /companies/{symbol}
  // link) never sees one, instead of re-checking at each of the ~6 sites below.
  const companies = rawCompanies.filter(c => isRealSymbol(c.symbol));

  const isDecision = !!decision_intelligence?.intent && decision_intelligence.intent !== "general";

  // Relative time
  const minAgo = Math.max(1, Math.round((Date.now() - resultTime.getTime()) / 60000));

  // Verdict direction — drives the icon only; the label itself is always the
  // research-outlook enum (never Buy/Sell/Hold), colored via OUTLOOK_COLOR.
  const dir = answer?.sentiment ?? investment_verdict?.direction ?? "neutral";
  const isBull = dir === "bullish";
  const isBear = dir === "bearish";
  const outlookLabel = investment_verdict?.rating || "Neutral";
  const verdictColor = OUTLOOK_COLOR[outlookLabel] ?? (isBull ? "text-emerald-400" : isBear ? "text-rose-400" : "text-amber-400");
  const conf = displayConfidence(result);
  const risk = investment_verdict?.risk_level
    ? { label: investment_verdict.risk_level, color:
        investment_verdict.risk_level === "Low" ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
        : investment_verdict.risk_level === "Medium" ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
        : "text-rose-400 bg-rose-500/10 border-rose-500/20" }
    : riskLevel(conf);
  const suitableForLabel = investment_verdict?.suitable_for || suitableFor(investment_verdict?.horizon || "");

  // Hero Decision Panel data — only assembled when the V3 fields it needs
  // are present (decision_engine_v2 + ai_conclusion); render site below
  // checks this and shows nothing on V2 responses rather than a stub.
  const heroData: HeroVerdictData | null = (decision_engine_v2 && ai_conclusion && !result.synthesis_incomplete) ? {
    verdictScale: decision_engine_v2.verdict_scale || "Neutral",
    why: decision_engine_v2.why || "",
    confidence: confidence_breakdown?.final_confidence ?? conf,
    confidenceLevel: confidence_breakdown?.level,
    horizon: investment_verdict?.horizon || "6-12 months",
    suitableFor: suitableForLabel,
    riskLabel: risk.label,
    riskColor: risk.color,
    conclusion: ai_conclusion.reason || ai_conclusion.current_view || "",
    opportunityPct: weightedShare(opportunity_risk_matrix?.opportunity) ?? clamp01to100(investment_verdict?.opportunity_score ?? 50),
    riskPct: weightedShare(opportunity_risk_matrix?.risk) ?? clamp01to100(100 - (confidence_breakdown?.final_confidence ?? conf ?? 50)),
    evidenceStars: evidence_score?.stars ?? 3,
    evidenceChecklist: evidence_score?.checklist ?? {},
    sourceCount: evidence_score?.source_count ?? answer?.sources_count ?? 0,
  } : null;

  // Continue Your Research CTAs
  const topCo   = companies?.[0];
  const topCo2  = companies?.[1];
  const topEv   = related_events?.[0];
  const topFU   = follow_up_questions?.[0];
  const topSec  = sectors?.[0];
  const topPol  = policies?.[0];
  const hasRipple = (ripple_chain?.length ?? 0) > 1;
  const hasContinueResearchCta = !!(topCo || hasRipple || (topCo && topCo2) || topEv || topSec || topPol || topFU);

  // Distinct from the Executive Summary — describes HOW the answer was
  // built (source mix + methodology), never restates WHAT it concluded.
  const methodologySummary = (() => {
    const parts: string[] = [];
    if (news?.length) parts.push(`${news.length} news article${news.length > 1 ? "s" : ""}`);
    if (policies?.length) parts.push(`${policies.length} policy document${policies.length > 1 ? "s" : ""}`);
    if (related_events?.length) parts.push(`${related_events.length} market event${related_events.length > 1 ? "s" : ""}`);
    if (companies?.length) parts.push(`${companies.length} compan${companies.length > 1 ? "ies" : "y"}`);
    let out = parts.length ? `Synthesized from ${parts.join(", ")}` : "Synthesized from available market data";
    if (historical_comparison?.length) out += `, cross-checked against ${historical_comparison.length} historical precedent${historical_comparison.length > 1 ? "s" : ""}`;
    if (hasRipple) out += ", propagated through MarketRipple's Intelligence Graph and Ripple Engine";
    return out + ".";
  })();

  function handleSave() {
    try {
      const key = "ig_saved_searches";
      const existing = JSON.parse(localStorage.getItem(key) ?? "[]");
      const entry = { id: `sv-${Date.now()}`, query: result.query, summary: answer?.summary?.slice(0, 120), timestamp: Date.now() };
      const deduped = existing.filter((e: { query: string }) => e.query !== result.query);
      localStorage.setItem(key, JSON.stringify([entry, ...deduped].slice(0, 50)));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch { /**/ }
  }

  function handleShare() {
    const url = `${window.location.origin}/ai-search?q=${encodeURIComponent(result.query)}`;
    if (navigator.share) {
      navigator.share({ title: "MarketRipple AI Analysis", text: result.query, url }).catch(() => {});
    } else {
      navigator.clipboard.writeText(url).catch(() => {});
    }
  }

  return (
    <div className="space-y-4 pb-36">

      {/* ── Query Header ─────────────────────────────────────────────────────── */}
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">Search Answer</p>
            <h1 className="text-[18px] font-bold text-text-primary leading-snug">{result.query}</h1>
            <p className="mt-1 text-[11px] text-text-muted">
              Generated {minAgo} min ago
              <span className="mx-1.5 text-text-muted">·</span>
              AI Model: MarketRipple Intelligence (v2.7)
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0 mt-0.5">
            <button onClick={() => onFollowUp("")}
              className="flex items-center gap-1.5 rounded-[12px] border border-surface-border/10 bg-text-primary/[0.04] px-3 py-1.5 text-[12px] font-medium text-text-secondary hover:bg-text-primary/[0.08] transition">
              <Plus className="h-3.5 w-3.5"/>
              New Search
            </button>
            <button onClick={handleSave}
              className={`flex h-8 w-8 items-center justify-center rounded-[10px] border transition ${saved ? "border-violet-500/40 bg-violet-500/20 text-violet-600 dark:text-violet-300" : "border-surface-border/10 bg-text-primary/[0.04] text-text-secondary hover:bg-text-primary/[0.08]"}`}>
              <Bookmark className="h-4 w-4"/>
            </button>
          </div>
        </div>
      </div>

      {/* ── Hero Decision Panel ───────────────────────────────────────────────── */}
      {heroData && <InvestmentVerdictHero data={heroData} />}

      {/* ── Context indicator (Phase 1.7) ──────────────────────────────────────
          Only appears when the research session actually contributed
          something to THIS answer — honestly reflects context_used from the
          backend, never a guess about what "probably" happened. */}
      {((context_used?.companies.length ?? 0) + (context_used?.sectors.length ?? 0)) > 0 && (
        <p className="flex items-center gap-1.5 text-[11px] text-text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-violet-400" />
          Using current research context
          {context_used!.companies.length > 0 && <span className="text-text-secondary"> · Companies {context_used!.companies.length}</span>}
          {context_used!.sectors.length > 0 && <span className="text-text-secondary"> · Sectors {context_used!.sectors.length}</span>}
        </p>
      )}

      {/* ── Refine Analysis ────────────────────────────────────────────────────
          Adjusts personal parameters and regenerates only the decision layer
          against the same evidence — response_id comes from whichever answer
          (original or a previous refine) is currently displayed. */}
      <RefineAnalysisPanel
        responseId={resultMeta?.responseId ?? result.response_id ?? null}
        onRefined={onRefined}
      />

      {/* ── Feedback loop ─────────────────────────────────────────────────────
          response_id (and everything else fed into meta) comes straight from
          the search response envelope — never re-derived here. Hides itself
          when there's nothing to attach feedback to (V2 responses). */}
      <AISearchFeedback
        meta={{
          responseId: resultMeta?.responseId ?? result.response_id ?? null,
          query: result.query,
          specialist: result.specialist ?? null,
          schemaVersion: result.schema_version ?? null,
          cached: resultMeta?.cached ?? false,
          latencyMs: resultMeta?.latencyMs ?? null,
          provider: resultMeta?.provider ?? null,
        }}
      />

      {/* ── Reveal: graph + findings recap ───────────────────────────────────── */}
      {!result.synthesis_incomplete && <ResultReveal result={result} />}

      {/* ── Degraded-synthesis notice ──────────────────────────────────────────
          The AI model didn't return a usable response for this query (provider
          quota exhausted, timeout, etc). The sections below still reflect the
          real events/news/sources gathered, but the "verdict" content (Research
          Outlook, Scenarios) is a generic template, not analysis of this query
          — say so plainly rather than presenting it as a completed AI answer. */}
      {result.synthesis_incomplete && (
        <div className="flex items-start gap-3 rounded-[16px] border border-amber-500/25 bg-amber-500/[0.06] px-4 py-3">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-400"/>
          <p className="text-[12.5px] leading-5 text-amber-700/90 dark:text-amber-200/90">
            <span className="font-semibold text-amber-600 dark:text-amber-300">Full AI analysis wasn&apos;t available for this query.</span>{" "}
            The events, news, and sources below are real and were used to inform confidence scoring — but the AI
            reasoning, scenarios, and verdict couldn&apos;t be generated right now. Try again shortly, or rephrase your question.
          </p>
        </div>
      )}

      {/* ── Decision Intelligence Panel ───────────────────────────────────────── */}
      {isDecision && decision_intelligence && (
        <div className={result.synthesis_incomplete ? `rounded-[20px] border ${DEGRADED_CARD_CLS} p-1` : ""}>
          {result.synthesis_incomplete && <div className="px-4 pt-3 pb-1"><DegradedBadge/></div>}
          <DecisionIntelligencePanel di={decision_intelligence} query={result.query} onRefine={onFollowUp}/>
        </div>
      )}

      {/* ── 1. Research Outlook ───────────────────────────────────────────────── */}
      <div className={`rounded-[20px] border p-5 ${result.synthesis_incomplete ? DEGRADED_CARD_CLS : "border-surface-border/7 bg-text-primary/[0.03]"}`}>
        <div className="flex items-center gap-2 mb-4">
          <span className="rounded-full bg-violet-500/20 border border-violet-500/30 px-2.5 py-0.5 text-[10px] font-bold text-violet-600 dark:text-violet-300 uppercase tracking-wider">Research Outlook</span>
          <span className="rounded-full border border-surface-border/8 bg-text-primary/[0.03] px-2.5 py-0.5 text-[10px] font-medium text-text-secondary">Not investment advice</span>
          {result.synthesis_incomplete && <DegradedBadge/>}
        </div>

        <div className="flex items-center gap-4 mb-4">
          <DirectionIcon direction={dir} size={64}/>
          <div className="flex items-center gap-2.5">
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${OUTLOOK_DOT[outlookLabel] ?? "bg-amber-400"}`}/>
            <p className={`text-[26px] font-extrabold leading-tight ${verdictColor}`}>{outlookLabel}</p>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-2">
          {[
            { label: "Confidence", value: conf != null ? `${conf}%` : "Unscored", color: "text-emerald-400" },
            { label: "Time Horizon", value: investment_verdict?.horizon || "Not specified", color: investment_verdict?.horizon ? "text-text-primary" : "text-text-muted" },
            { label: "Risk Level", value: risk.label, color: risk.color.split(" ")[0] },
            { label: "Suitable For", value: suitableForLabel, color: "text-text-primary" },
          ].map(s => (
            <div key={s.label} className="rounded-[12px] border border-surface-border/6 bg-text-primary/[0.02] px-3 py-2">
              <p className="text-[9px] uppercase tracking-wider text-text-muted mb-0.5">{s.label}</p>
              <p className={`text-[12px] font-semibold ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── 2. Executive Summary ──────────────────────────────────────────────── */}
      <div className={`rounded-[20px] border p-5 ${result.synthesis_incomplete ? DEGRADED_CARD_CLS : "border-violet-500/20 bg-gradient-to-br from-violet-500/[0.06] to-transparent"}`}>
        <div className="flex items-center gap-2 mb-2">
          <p className="text-[11px] uppercase tracking-wider text-violet-400 font-semibold">Executive Summary</p>
          {result.synthesis_incomplete && <DegradedBadge/>}
        </div>
        <p className="text-[14px] text-text-primary leading-relaxed">
          {answer?.bottom_line || answer?.summary || "No direct answer generated for this query."}
        </p>
      </div>

      {/* ── 3. Why AI Thinks This ─────────────────────────────────────────────── */}
      {key_drivers?.length > 0 && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[15px] font-semibold text-text-primary mb-4">Why AI Thinks This</p>
          <div className="grid grid-cols-3 gap-3">
            {key_drivers.slice(0, 6).map((kd, i) => (
              <div key={i} className="rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] p-4">
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/15 text-violet-600 dark:text-violet-300">
                    {DRIVER_ICON_MAP[kd.icon] ?? <Sparkles className="h-4 w-4"/>}
                  </div>
                  <p className="text-[12px] font-semibold text-text-primary leading-tight">{kd.title}</p>
                </div>
                <p className="text-[11px] text-text-secondary leading-relaxed">{kd.explanation}</p>
                {/* No per-driver confidence % shown here — unlike Market
                    Pulse's driver_strength (a real formula over driver_type +
                    event urgency), this card's kd.confidence is the model's
                    own unscored guess with no formula behind it. Showing a
                    precise-looking bar/percentage for that would be the
                    exact anti-pattern this app is built to avoid. */}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 3b. Market Chart — real price/index data, computed every request but
          previously never rendered anywhere on this page. ────────────────── */}
      {market_chart?.series?.length > 0 && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[15px] font-semibold text-text-primary mb-1">Price Movement</p>
          <p className="text-[10px] text-text-muted mb-3">Normalized % change — real intraday data for the companies/indices this query concerns.</p>
          <MultiLineChart chart={market_chart}/>
        </div>
      )}

      {/* ── 4. Ripple Analysis ────────────────────────────────────────────────── */}
      {ripple_chain?.length > 1 && (
        <div id="ripple-analysis" className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <div className="flex items-center gap-2 mb-1">
            <GitBranch className="h-4 w-4 text-violet-400"/>
            <p className="text-[15px] font-semibold text-text-primary">Ripple Analysis</p>
          </div>
          <p className="text-[10px] text-text-muted mb-4">How the impact propagates through the economy — first, second and third-order effects, from the intelligence graph.</p>
          <div className="overflow-x-auto pb-1">
            <div className="flex items-stretch gap-2 min-w-max">
              {ripple_chain.map((level, li) => (
                <div key={level.depth} className="flex items-center">
                  <div className="flex flex-col gap-2 justify-center">
                    <p className="text-[8px] uppercase tracking-wider text-text-muted text-center">
                      {li === 0 ? "Source" : li === 1 ? "1st Order" : li === 2 ? "2nd Order" : "3rd Order+"}
                    </p>
                    {level.nodes.map((node, ni) => (
                      <button
                        key={`${level.depth}-${node.id ?? ni}`}
                        onClick={() => setActiveRippleNode(node.id === activeRippleNode ? null : node.id)}
                        className={`rounded-[12px] border px-3 py-2 text-left transition ${RIPPLE_TYPE_COLOR[node.type] ?? "border-surface-border/10 bg-text-primary/[0.03] text-text-secondary"} ${activeRippleNode === node.id ? "ring-2 ring-violet-400/50" : "hover:brightness-125"}`}>
                        <div className="flex items-center gap-1.5">
                          <p className="text-[9px] uppercase tracking-wider opacity-70">{node.type}</p>
                          {node.direction === "positive" && <TrendingUp className="h-2.5 w-2.5 text-emerald-400"/>}
                          {node.direction === "negative" && <TrendingDown className="h-2.5 w-2.5 text-rose-400"/>}
                        </div>
                        <p className="text-[12px] font-semibold whitespace-nowrap">{node.label}</p>
                      </button>
                    ))}
                  </div>
                  {li < ripple_chain.length - 1 && (
                    <ArrowRight className="h-4 w-4 text-text-muted mx-2 shrink-0"/>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── 5. Companies That Matter ──────────────────────────────────────────── */}
      {companies?.length > 0 && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-baseline gap-2">
              <p className="text-[15px] font-semibold text-text-primary">Companies That Matter</p>
              <span className="text-[10px] text-text-muted">Ranked by impact score</span>
            </div>
            <div className="flex items-center gap-3">
              {companies.length >= 2 && (
                <Link
                  href={`/compare?a=${companies[0].symbol}&b=${companies[1].symbol}`}
                  className="flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-[11px] font-semibold text-sky-600 dark:text-sky-300 hover:bg-sky-500/20 transition">
                  ↔ Compare {companies[0].symbol} vs {companies[1].symbol}
                </Link>
              )}
              <Link href="/companies" className="text-[12px] text-violet-400 hover:text-violet-600 dark:text-violet-300 transition">
                View All →
              </Link>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {companies.slice(0, 6).map((co, idx) => {
              const avatarColors = ["bg-red-700", "bg-blue-700", "bg-orange-700", "bg-teal-700", "bg-violet-700", "bg-indigo-700"];
              const av = avatarColors[idx % avatarColors.length];
              return (
                <div key={co.symbol} className="rounded-[16px] border border-surface-border/7 bg-text-primary/[0.02] p-4">
                  {/* Header */}
                  <div className="flex items-center gap-2.5 mb-2.5">
                    <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] ${av} text-[11px] font-bold text-text-primary`}>
                      {co.symbol.slice(0, 2)}
                    </div>
                    <div className="min-w-0">
                      <p className="text-[13px] font-bold text-text-primary truncate">{co.symbol}</p>
                      {co.price && co.price !== "—" ? (
                        <p className="text-[11px] tabular-nums">
                          <span className="text-text-secondary">₹{co.price}</span>
                          <span className={`ml-1 font-semibold ${co.positive ? "text-emerald-400" : "text-rose-400"}`}>{co.change}</span>
                        </p>
                      ) : (
                        <p className="text-[10px] text-text-muted">—</p>
                      )}
                    </div>
                    <div className="ml-auto shrink-0">
                      <MiniSparkline data={co.chart} positive={co.positive}/>
                    </div>
                  </div>

                  {/* Ripple position badge */}
                  {co.ripple_position && (
                    <span className={`inline-block mb-2 rounded border px-1.5 py-0.5 text-[9px] font-semibold ${RIPPLE_POSITION_COLOR[co.ripple_position] ?? "bg-slate-500/10 text-text-secondary border-surface-border/5"}`}>
                      {co.ripple_position}
                    </span>
                  )}

                  {/* Why it matters */}
                  <div className="mb-3">
                    <p className="text-[9px] uppercase tracking-wider text-text-muted mb-1">Why it matters</p>
                    <p className="text-[11px] text-text-secondary leading-relaxed line-clamp-2">{co.why_it_matters || co.reason || "Directly impacted by this event"}</p>
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <SmallRing score={(() => { const v = co.confidence ?? co.impact_score; return v === null || v === undefined ? null : Math.round(v); })()} size={32}/>
                      <p className="text-[10px] text-text-muted">Confidence</p>
                    </div>
                    <Link href={`/companies/${co.symbol}`}
                      className="text-[11px] font-medium text-violet-400 hover:text-violet-600 dark:text-violet-300 transition">
                      Open Analysis →
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── 6. Sector Impact + Related Events Timeline ───────────────────────── */}
      <div className="grid grid-cols-[1.2fr_1.2fr] gap-4">

        {/* Sector Impact */}
        {sectors?.length > 0 && (
          <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
            <p className="text-[14px] font-semibold text-text-primary mb-4">Sector Impact</p>
            <div className="w-full">
              <div className="grid grid-cols-[1.3fr_0.6fr_0.7fr_1fr_0.8fr] gap-x-2 mb-2">
                {["Sector", "Impact", "Confidence", "Status", "Horizon"].map(h => (
                  <p key={h} className="text-[9px] uppercase tracking-wider text-text-muted font-semibold">{h}</p>
                ))}
              </div>
              <div className="space-y-3">
                {sectors.slice(0, 5).map(s => (
                  <div key={s.name}>
                    <div className="grid grid-cols-[1.3fr_0.6fr_0.7fr_1fr_0.8fr] gap-x-2 items-center">
                      <p className="text-[12px] font-medium text-text-primary truncate">{s.name}</p>
                      <p className="text-[12px] font-bold tabular-nums text-text-primary">{s.score === null || s.score === undefined ? "—" : (s.score / 10).toFixed(1)}</p>
                      <p className="text-[11px] tabular-nums text-text-secondary">{s.confidence === null || s.confidence === undefined ? "—" : `${s.confidence}%`}</p>
                      <p className={`text-[11px] font-medium truncate ${SECTOR_STATUS_COLOR[s.status ?? ""] ?? "text-text-secondary"}`}>{s.status || s.outlook || "—"}</p>
                      <p className="text-[10px] text-text-muted">{fixMojibake(s.time_horizon) || "—"}</p>
                    </div>
                    {s.explanation && (
                      <p className="text-[10px] text-text-muted leading-relaxed mt-0.5 line-clamp-1">{s.explanation}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Related Events Timeline */}
        {related_events?.length > 0 && (
          <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Clock className="h-3.5 w-3.5 text-text-secondary"/>
                <p className="text-[14px] font-semibold text-text-primary">Related Events Timeline</p>
              </div>
              <Link href="/events" className="text-[11px] text-violet-400 hover:text-violet-600 dark:text-violet-300 transition">View All Events →</Link>
            </div>
            <div className="relative overflow-x-auto">
              <div className="flex items-start gap-0 min-w-max">
                {related_events.slice(0, 5).map((ev, i) => {
                  const status = inferStatus(ev.date);
                  const sc = EVENT_STATUS_COLORS[status];
                  const isLast = i === related_events.slice(0, 5).length - 1;
                  return (
                    <div key={ev.id} className="flex items-start">
                      <div className="flex flex-col items-center w-32">
                        <div className="flex items-center w-full">
                          {i > 0 && <div className="flex-1 h-px bg-text-primary/[0.08]"/>}
                          <div className={`h-3 w-3 shrink-0 rounded-full border-2 border-[#0d1117] ${sc.dot}`}/>
                          {!isLast && <div className="flex-1 h-px bg-text-primary/[0.08]"/>}
                        </div>
                        <div className="mt-2 px-1 text-center">
                          <Link href={`/events/${ev.id}`}
                            className="block text-[11px] font-medium text-text-primary hover:text-text-primary transition line-clamp-2 leading-tight text-center">
                            {ev.title.length > 35 ? ev.title.slice(0, 32) + "…" : ev.title}
                          </Link>
                          <p className="text-[9px] text-text-muted mt-1">{ev.date?.split(",")[0] || ev.date}</p>
                          <span className={`mt-1 inline-block rounded border px-1.5 py-0.5 text-[9px] font-medium ${sc.bg}`}>
                            {sc.label}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Layer boundary ─────────────────────────────────────────────────────
          Everything above is the Executive Decision layer — what a reader
          needs in under 30 seconds. Everything below is Deep Research —
          historical precedent, scenarios, valuation context, methodology. */}
      <div className="flex items-center gap-3 pt-2 pb-1">
        <div className="h-px flex-1 bg-text-primary/[0.07]"/>
        <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-text-muted">
          <ListChecks className="h-3 w-3"/>
          Deep Research
        </span>
        <div className="h-px flex-1 bg-text-primary/[0.07]"/>
      </div>

      {/* ── 7. Market Context ─────────────────────────────────────────────────── */}
      {answer?.what_priced_in && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <div className="flex items-center gap-2 mb-2">
            <Eye className="h-4 w-4 text-sky-400"/>
            <p className="text-[15px] font-semibold text-text-primary">Market Context</p>
            <span className="text-[10px] text-text-muted">— is this already priced in?</span>
          </div>
          <p className="text-[12px] text-text-secondary leading-relaxed">{answer.what_priced_in}</p>
        </div>
      )}

      {/* ── 8. Market Impact — Immediate / Next Quarter / Long Term ──────────── */}
      {market_impact_horizons?.length > 0 && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[15px] font-semibold text-text-primary mb-4">Market Impact Over Time</p>
          <div className="grid grid-cols-3 gap-3">
            {market_impact_horizons.map(h => {
              const dirColor = h.direction === "positive" ? "text-emerald-400" : h.direction === "negative" ? "text-rose-400" : "text-amber-400";
              const barColor = h.direction === "positive" ? "from-emerald-500 to-emerald-300" : h.direction === "negative" ? "from-rose-500 to-rose-300" : "from-amber-500 to-amber-300";
              return (
                <div key={h.horizon} className="rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] p-4">
                  <p className="text-[12px] font-semibold text-text-primary">{h.horizon}</p>
                  <p className="text-[9px] text-text-muted mb-2">{h.window}</p>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-text-primary/[0.06]">
                      {h.confidence !== null && h.confidence !== undefined && (
                        <div className={`h-full rounded-full bg-gradient-to-r ${barColor}`} style={{ width: `${h.confidence}%` }}/>
                      )}
                    </div>
                    <p className={`text-[10px] font-semibold tabular-nums ${dirColor}`}>{h.confidence === null || h.confidence === undefined ? "Unscored" : `${h.confidence}%`}</p>
                  </div>
                  <p className="text-[10px] text-text-secondary leading-relaxed line-clamp-3">{h.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── 8b. Decision Timeline + Confidence Explainability (Phase 2C) ─────── */}
      {/* V3-only fields (timeline_intelligence / confidence_breakdown) — the
          panels above (Market Impact Over Time) and the evidence checklist
          in the Hero already cover the V2-equivalent ground, so these are
          additive and simply render nothing on a V2 response. */}
      <DecisionTimelinePanel timeline={timeline_intelligence} />
      <ConfidenceBreakdownPanel breakdown={confidence_breakdown ?? null} />

      {/* ── 9. Historical Comparison ──────────────────────────────────────────── */}
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
        <p className="text-[15px] font-semibold text-text-primary mb-4">Historical Comparison</p>
        {historical_comparison?.length > 0 ? (
          <div className="grid grid-cols-2 gap-3">
            {historical_comparison.slice(0, 2).map((h, i) => (
              <div key={i} className="rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] p-4">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-[12px] font-medium text-violet-600 dark:text-violet-300">{h.event_title}</p>
                  <span className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold ${
                    h.similarity >= 60 ? "bg-violet-500/15 text-violet-600 dark:text-violet-300"
                    : h.similarity >= 40 ? "bg-amber-500/15 text-amber-600 dark:text-amber-300"
                    : "bg-rose-500/15 text-rose-600 dark:text-rose-300"
                  }`}>
                    {Math.round(h.similarity)}% match{h.similarity < 40 ? " — weak" : ""}
                  </span>
                </div>
                <p className="text-[9px] text-text-muted mb-2">{h.event_date}</p>
                {h.similarity < 40 && (
                  <p className="mb-2 text-[9.5px] leading-4 text-amber-600/80 dark:text-amber-300/80">
                    Low similarity score — treat this as a loose reference, not a strong precedent.
                  </p>
                )}

                {/* Outcome — real index returns, honestly labeled by the actual window available */}
                {(h.nifty_1w != null || h.nifty_1m != null) && (
                  <div className="flex items-center gap-4 mb-2.5">
                    {h.nifty_1w != null && (
                      <div>
                        <p className="text-[8px] uppercase tracking-wider text-text-muted">Nifty · 1 Week</p>
                        <p className={`text-[13px] font-bold tabular-nums ${h.nifty_1w >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{h.nifty_1w >= 0 ? "+" : ""}{h.nifty_1w}%</p>
                      </div>
                    )}
                    {h.nifty_1m != null && (
                      <div>
                        <p className="text-[8px] uppercase tracking-wider text-text-muted">Nifty · 1 Month</p>
                        <p className={`text-[13px] font-bold tabular-nums ${h.nifty_1m >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{h.nifty_1m >= 0 ? "+" : ""}{h.nifty_1m}%</p>
                      </div>
                    )}
                  </div>
                )}

                <p className="text-[11px] text-text-secondary leading-relaxed mb-3 line-clamp-3">{h.key_lesson || h.what_happened}</p>
                {h.historical_winners?.length > 0 && (
                  <div className="mb-2">
                    <p className="text-[9px] uppercase tracking-wider text-emerald-500/70 mb-1">Winners</p>
                    <div className="flex flex-wrap gap-1.5">
                      {h.historical_winners.slice(0, 4).map(w => {
                        const ret = w.return_1m ?? w.return_1w;
                        return (
                          <span key={w.symbol} title={w.reason} className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-400 tabular-nums">
                            {w.symbol}{ret != null ? ` +${ret}% (${w.return_1m != null ? "1M" : "1W"})` : ""}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}
                {h.historical_losers?.length > 0 && (
                  <div className="mb-3">
                    <p className="text-[9px] uppercase tracking-wider text-rose-500/70 mb-1">Losers</p>
                    <div className="flex flex-wrap gap-1.5">
                      {h.historical_losers.slice(0, 3).map(l => {
                        const ret = l.return_1m ?? l.return_1w;
                        return (
                          <span key={l.symbol} title={l.reason} className="rounded bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-rose-400 tabular-nums">
                            {l.symbol}{ret != null ? ` ${ret}% (${l.return_1m != null ? "1M" : "1W"})` : ""}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}
                {h.key_difference && (
                  <div className="pt-2 border-t border-surface-border/6">
                    <p className="text-[8px] uppercase tracking-wider text-amber-500/70 mb-0.5">Key Difference</p>
                    <p className="text-[10px] text-amber-600/70 dark:text-amber-300/70 leading-relaxed">{h.key_difference}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[12px] text-text-muted text-center py-4">No closely matching historical precedent found for this query.</p>
        )}
      </div>

      {/* ── 10. Scenarios: Bull / Base / Bear ─────────────────────────────────── */}
      {scenarios && !scenarios.degraded && (scenarios.bull || scenarios.base || scenarios.bear) && (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[15px] font-semibold text-text-primary mb-4">Scenarios</p>
          <div className="grid grid-cols-3 gap-3">
            {([
              { key: "bull", label: "Bull Case", data: scenarios.bull, color: "text-emerald-400", bg: "border-emerald-500/20 bg-emerald-500/[0.04]" },
              { key: "base", label: "Base Case", data: scenarios.base, color: "text-sky-400", bg: "border-sky-500/20 bg-sky-500/[0.04]" },
              { key: "bear", label: "Bear Case", data: scenarios.bear, color: "text-rose-400", bg: "border-rose-500/20 bg-rose-500/[0.04]" },
            ] as const).map(sc => sc.data && (
              <div key={sc.key} className={`rounded-[14px] border p-4 ${sc.bg}`}>
                <div className="flex items-center justify-between mb-2">
                  <p className={`text-[12px] font-bold ${sc.color}`}>{sc.label}</p>
                  <p className="text-[10px] tabular-nums text-text-muted">{sc.data.probability}%</p>
                </div>
                <p className="text-[11px] text-text-secondary leading-relaxed line-clamp-4">{sc.data.outcome}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 11. Risks & Counterarguments + What To Monitor + AI Reasoning ────── */}
      <div className="grid grid-cols-3 gap-4">

        {/* Risks & Counterarguments */}
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[13px] font-semibold text-text-primary">Risks & Counterarguments</p>
            {(answer?.risks?.length ?? 0) > 4 && (
              <button onClick={() => setShowMore(v => !v)} className="text-[10px] text-violet-400">View All →</button>
            )}
          </div>
          <div className="space-y-2.5">
            {((answer?.risks?.length ? answer.risks : investment_verdict?.risks || []).slice(0, 4)).map((r, i) => (
              <div key={i} className="flex items-start gap-2">
                <div className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-rose-500/70 mt-1.5"/>
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] text-text-secondary leading-relaxed line-clamp-2">{r}</p>
                </div>
                <RiskSeverity text={r}/>
              </div>
            ))}
            {!(answer?.risks?.length || investment_verdict?.risks?.length) && (
              <p className="text-[11px] text-text-muted">No specific risks identified for this query.</p>
            )}
          </div>
        </div>

        {/* What To Monitor */}
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[13px] font-semibold text-text-primary mb-3">What To Monitor</p>
          <div className="space-y-2.5">
            {(what_to_monitor?.length ? what_to_monitor : []).slice(0, 5).map((m, i) => (
              <div key={i} className="flex items-start gap-2">
                <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/20">
                  <svg className="h-2.5 w-2.5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] text-text-secondary leading-relaxed line-clamp-1">{m.title}</p>
                  <p className="text-[9px] text-text-muted">{m.frequency}{m.frequency && m.importance ? " · " : ""}{m.importance}</p>
                </div>
              </div>
            ))}
            {!what_to_monitor?.length && (
              <p className="text-[11px] text-text-muted">No monitoring checklist generated.</p>
            )}
          </div>
        </div>

        {/* AI Reasoning */}
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <div className="flex items-center gap-2 mb-3">
            <ListChecks className="h-3.5 w-3.5 text-violet-400"/>
            <p className="text-[13px] font-semibold text-text-primary">AI Reasoning</p>
          </div>
          <div className="space-y-1.5">
            {(ai_reasoning_methods ?? []).map((m, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full ${m.used ? "bg-emerald-500/20" : "bg-text-primary/[0.09]"}`}>
                  {m.used
                    ? <svg className="h-2 w-2 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4"><polyline points="20 6 9 17 4 12"/></svg>
                    : <Minus className="h-2 w-2 text-text-muted"/>}
                </div>
                <p className={`text-[10.5px] leading-tight ${m.used ? "text-text-secondary" : "text-text-muted"}`}>{m.label}</p>
              </div>
            ))}
            {!ai_reasoning_methods?.length && (
              <p className="text-[11px] text-text-muted">No reasoning-source breakdown available for this query.</p>
            )}
          </div>
          {(confidence_data?.caveats?.length ?? 0) > 0 && (
            <div className="mt-3 pt-3 border-t border-surface-border/6">
              <p className="text-[9px] uppercase tracking-wider text-amber-500/70 mb-1.5">Lower confidence if</p>
              <div className="space-y-1">
                {confidence_data!.caveats.slice(0, 3).map((c, i) => (
                  <p key={i} className="text-[10px] text-amber-600/70 dark:text-amber-300/70 leading-tight">{c}</p>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 12. Related Actions ───────────────────────────────────────────────
          Navigates elsewhere on MarketRipple (company pages, the compare
          page, in-page ripple scroll) — distinct from section 13's Follow-up
          Intelligence, which starts a new AI search in place. Renamed off
          "Continue Your Research" (2026-07-27) since that title now belongs
          to section 13 per the Follow-up Intelligence spec. Hidden entirely
          when nothing applies, rather than showing an empty card. */}
      {hasContinueResearchCta && (
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
        <p className="text-[11px] uppercase tracking-wider text-text-muted mb-3">Related Actions</p>
        <div className="grid grid-cols-3 gap-3">
          {[
            topCo ? {
              icon: <Building2 size={15} strokeWidth={1.7}/>,
              label: `Open ${topCo.name} Analysis`,
              sub: "Deep dive into company",
              href: `/companies/${topCo.symbol}`,
            } : null,
            hasRipple ? {
              icon: <GitBranch size={15} strokeWidth={1.7}/>,
              label: "View Ripple Graph",
              sub: "See the full propagation chain",
              action: () => document.getElementById("ripple-analysis")?.scrollIntoView({ behavior: "smooth", block: "start" }),
            } : null,
            (topCo && topCo2) ? {
              icon: <GitCompare size={15} strokeWidth={1.7}/>,
              label: `Compare ${topCo.symbol} vs ${topCo2.symbol}`,
              sub: "Side-by-side comparison",
              href: `/compare?a=${topCo.symbol}&b=${topCo2.symbol}`,
            } : null,
            topEv ? {
              icon: <BarChart2 size={15} strokeWidth={1.7}/>,
              label: `Read ${topEv.title.length > 28 ? topEv.title.slice(0, 25) + "…" : topEv.title}`,
              sub: "Understand the event",
              href: `/events/${topEv.id}`,
            } : null,
            topSec ? {
              icon: <Search size={15} strokeWidth={1.7}/>,
              label: `Explore ${topSec.name} Sector`,
              sub: "Sector & theme analysis",
              href: `/sectors`,
            } : null,
            topPol ? {
              icon: <FileText size={15} strokeWidth={1.7}/>,
              label: `View ${topPol.title.length > 26 ? topPol.title.slice(0, 23) + "…" : topPol.title}`,
              sub: "Policy detail",
              href: `/calendar`,
            } : null,
            topFU ? {
              icon: <Sparkles size={15} strokeWidth={1.7}/>,
              label: "Ask Another Question",
              sub: "Continue AI research",
              action: () => onFollowUp(topFU),
            } : null,
          ].filter(Boolean).map((cta, i) => (
            cta!.action ? (
              <button key={i} onClick={cta!.action}
                className="group flex items-center gap-3 rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] px-4 py-3 text-left transition hover:border-violet-500/30 hover:bg-violet-500/[0.04]">
                <span className="text-text-secondary flex items-center">{cta!.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-medium text-text-primary line-clamp-1">{cta!.label}</p>
                  <p className="text-[10px] text-text-muted mt-0.5">{cta!.sub}</p>
                </div>
                <ChevronRight size={13} strokeWidth={1.8} className="text-text-muted group-hover:text-violet-400 transition"/>
              </button>
            ) : (
              <Link key={i} href={(cta as any).href as any}
                className="group flex items-center gap-3 rounded-[14px] border border-surface-border/7 bg-text-primary/[0.02] px-4 py-3 transition hover:border-violet-500/30 hover:bg-violet-500/[0.04]">
                <span className="text-text-secondary flex items-center">{cta!.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-medium text-text-primary line-clamp-1">{cta!.label}</p>
                  <p className="text-[10px] text-text-muted mt-0.5">{cta!.sub}</p>
                </div>
                <ChevronRight size={13} strokeWidth={1.8} className="text-text-muted group-hover:text-violet-400 transition"/>
              </Link>
            )
          ))}
        </div>
      </div>
      )}

      {/* ── 13. Follow-up Intelligence ─────────────────────────────────────────
          Grouped, contextual follow-ups built server-side from this answer's
          own structured evidence (see FollowUpIntelligence's docstring).
          Falls back to the old flat list only for V2 responses, which never
          have follow_up_groups at all. */}
      {follow_up_groups?.length ? (
        <FollowUpIntelligence
          groups={follow_up_groups}
          responseId={resultMeta?.responseId ?? result.response_id ?? null}
          onFollowUp={onFollowUp}
        />
      ) : follow_up_questions?.length > 0 ? (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
          <p className="text-[13px] font-semibold text-text-primary mb-3">Follow-up Questions</p>
          <div className="grid grid-cols-2 gap-2">
            {follow_up_questions.slice(0, 4).map((q, i) => (
              <button key={i} onClick={() => onFollowUp(q)}
                className="group flex items-start gap-2 text-left transition hover:text-violet-600 dark:text-violet-300">
                <span className="mt-0.5 text-text-muted group-hover:text-violet-400 transition text-xs">›</span>
                <p className="text-[11px] text-text-secondary group-hover:text-violet-600 dark:text-violet-300 transition leading-relaxed line-clamp-2">{q}</p>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {/* ── 14. AI Transparency + Disclaimer ──────────────────────────────────── */}
      <AITransparencyPanel
        confidence={conf}
        reasoning={methodologySummary}
        events={(result.related_events ?? []).slice(0, 5).map((e) => ({ title: e.title, href: `/events/${e.id}` }))}
        companies={companies.slice(0, 5).map((c) => ({ name: c.name, symbol: c.symbol, href: `/companies/${c.symbol}` }))}
        assumptions={confidence_data?.reasons ?? []}
        limitations={confidence_data?.caveats ?? []}
        confidenceBreakdown={confidence_data?.breakdown}
      />
      <AIDisclaimer />
    </div>
  );
}

// ── Right Sidebar ──────────────────────────────────────────────────────────────
function RightSidebar({ result, onAction, onReopenSearch, activeQuery, session }: {
  result: SearchResult | null;
  onAction: (type: string) => void;
  onReopenSearch: (query: string) => void;
  activeQuery?: string;
  session: ReturnType<typeof useResearchSession>;
}) {
  const [copied, setCopied] = useState(false);

  const v = result?.investment_verdict;
  // Single canonical confidence number, shown everywhere on the page —
  // never opportunity_score, which is a different metric (upside sizing,
  // not evidence confidence) and must never masquerade as a second
  // "confidence" percentage. Goes through the same displayConfidence()
  // every other confidence display on this page uses — see its definition
  // for the fallback order.
  const score = displayConfidence(result);
  const verdictLabel = v?.rating || "Neutral";
  const verdictColor = OUTLOOK_COLOR[verdictLabel] ?? "text-amber-400";
  const riskInfo = result
    ? (v?.risk_level
        ? { label: v.risk_level, color:
            v.risk_level === "Low" ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
            : v.risk_level === "Medium" ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
            : "text-rose-400 bg-rose-500/10 border-rose-500/20" }
        : riskLevel(score))
    : { label: "—", color: "text-text-secondary" };

  const QUICK_ACTIONS = [
    { icon: <Bot className="h-4 w-4"/>,      label: "Ask Follow-up Question", action: "followup" },
    { icon: <Bookmark className="h-4 w-4"/>,  label: "Save This Answer",       action: "save" },
    { icon: <Download className="h-4 w-4"/>,  label: "Download as PDF",        action: "pdf" },
    { icon: <FileText className="h-4 w-4"/>,  label: "Download as Markdown",   action: "markdown" },
    { icon: <Share2 className="h-4 w-4"/>,    label: "Share Answer",           action: "share" },
    { icon: <Copy className="h-4 w-4"/>,      label: copied ? "Copied!" : "Copy Link", action: "copy" },
  ];

  function handleCopy() {
    const url = `${window.location.origin}/ai-search?q=${encodeURIComponent(result?.query || "")}`;
    navigator.clipboard.writeText(url).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleAction(a: string) {
    if (a === "copy") { handleCopy(); return; }
    if (a === "share") {
      const url = `${window.location.origin}/ai-search?q=${encodeURIComponent(result?.query || "")}`;
      if (navigator.share) navigator.share({ url }).catch(() => {});
      else navigator.clipboard.writeText(url).catch(() => {});
      return;
    }
    onAction(a);
  }

  return (
    <aside className="hidden xl:flex xl:flex-col w-[280px] shrink-0 sticky top-[92px] self-start max-h-[calc(100vh-92px)] overflow-y-auto space-y-3 pr-1" style={{ scrollbarWidth: "none" }}>

      {/* Research Outlook */}
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
        <div className="flex items-center gap-2 mb-4">
          <Target size={14} strokeWidth={1.8} className="text-violet-400"/>
          <p className="text-[13px] font-semibold text-text-primary">Research Outlook</p>
        </div>

        {result ? (
          <>
            {/* Top row: Overall View + Risk */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <p className="text-[9px] uppercase tracking-wider text-text-muted mb-1">Overall View</p>
                <p className={`flex items-center gap-1.5 text-[14px] font-bold leading-tight ${verdictColor}`}>
                  <span className={`h-2 w-2 shrink-0 rounded-full ${OUTLOOK_DOT[verdictLabel] ?? "bg-amber-400"}`}/>
                  {verdictLabel}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase tracking-wider text-text-muted mb-1">Risk</p>
                <p className={`text-[15px] font-bold ${riskInfo.color.split(" ")[0]}`}>{riskInfo.label}</p>
              </div>
            </div>

            {/* Big gauge */}
            <div className="flex justify-center my-2">
              <BigGauge score={score === null || score === undefined ? null : Math.round(score)} size={120}/>
            </div>

            {/* Bottom row: Time Horizon + Best For */}
            <div className="grid grid-cols-2 gap-3 mt-4">
              <div>
                <p className="text-[9px] uppercase tracking-wider text-text-muted mb-1">Time Horizon</p>
                <p className={`text-[12px] font-semibold ${v?.horizon ? "text-text-primary" : "text-text-muted"}`}>{v?.horizon || "Not specified"}</p>
              </div>
              <div>
                <p className="text-[9px] uppercase tracking-wider text-text-muted mb-1">Best For</p>
                <p className="text-[12px] font-semibold text-text-primary">{v?.suitable_for || suitableFor(v?.horizon || "")}</p>
              </div>
            </div>

            {/* Data point count */}
            <p className="mt-3 text-center text-[10px] text-text-muted">
              AI evaluated {(result.related_events?.length ?? 0) + (result.companies?.length ?? 0) + (result.news?.length ?? 0)} data points
            </p>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center my-6 gap-2">
            <BigGauge score={null} size={120}/>
            <p className="text-[10px] uppercase tracking-wider text-text-muted">Awaiting Analysis</p>
          </div>
        )}
      </div>

      {/* Investment Watch — merged Monitoring Dashboard + Verdict Change Explainer (Phase 2B) */}
      <InvestmentWatchPanel subject={result?.watch_subject} />

      {/* Current Research — this browser session's own accumulated state (Phase 1.7) */}
      <ResearchWorkspace
        session={session}
        onReopenQuery={onReopenSearch}
        onExploreCompany={sym => onReopenSearch(`Tell me about ${sym}`)}
        onExploreSector={sector => onReopenSearch(`What is the outlook for the ${sector} sector?`)}
        onClear={session.clear}
      />

      {/* Research History — real past searches (localStorage), reopen instantly */}
      <AISearchHistory onReopen={onReopenSearch} activeQuery={activeQuery} />

      {/* Quick Actions */}
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-4">
        <p className="text-[12px] font-semibold text-text-secondary mb-3">Quick Actions</p>
        <div className="space-y-1">
          {QUICK_ACTIONS.map(a => (
            <button key={a.action} onClick={() => handleAction(a.action)}
              className={`flex w-full items-center gap-3 rounded-[12px] p-2.5 text-left transition hover:bg-text-primary/[0.05] ${!result && a.action !== "copy" ? "opacity-40 pointer-events-none" : ""}`}>
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-text-primary/[0.05] text-text-secondary">
                {a.icon}
              </div>
              <p className="text-[12px] text-text-secondary">{a.label}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Sources & Transparency */}
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-4">
        <p className="text-[12px] font-semibold text-text-secondary mb-3">Sources & Transparency</p>
        <div className="space-y-2.5">
          {[
            { label: "News Articles",       value: result?.news?.length ?? 0 },
            { label: "Government Documents", value: result?.policies?.length ?? 0 },
            { label: "Events",               value: result?.related_events?.length ?? 0 },
            { label: "Companies",            value: result?.companies?.length ?? 0 },
            { label: "Historical Matches",   value: result?.historical_comparison?.length ?? 0 },
          ].map(s => (
            <div key={s.label} className="flex items-center justify-between">
              <p className="text-[11px] text-text-secondary">{s.label}</p>
              <p className="text-[12px] font-bold text-text-primary tabular-nums">{s.value}</p>
            </div>
          ))}
        </div>

        {result && (
          <>
            <div className="mt-3 pt-3 border-t border-surface-border/6">
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-[11px] text-text-secondary">Confidence Score</p>
                <p className="text-[12px] font-bold text-violet-600 dark:text-violet-300 tabular-nums">
                  {score != null ? `${score}%` : "Unscored"}
                </p>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-text-primary/[0.06]">
                {score != null && (
                  <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-sky-400"
                    style={{ width: `${score}%`, transition: "width 0.8s" }}/>
                )}
              </div>
            </div>
            <div className="mt-2.5 flex items-center justify-between">
              <p className="text-[10px] text-text-muted">Last Updated</p>
              <p className="text-[10px] text-text-secondary">just now</p>
            </div>
          </>
        )}
      </div>

      {/* Related news (compact) */}
      {result?.news?.length ? (
        <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[12px] font-semibold text-text-secondary">Sources</p>
            <Link href="/news" className="text-[10px] text-violet-400 hover:text-violet-600 dark:text-violet-300 transition">View All →</Link>
          </div>
          <div className="space-y-2">
            {result.news.slice(0, 4).map(n => (
              <Link key={n.id} href={`/news/${n.id}`}
                className="flex items-start gap-2.5 rounded-[10px] p-1.5 transition hover:bg-text-primary/[0.04]">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-text-primary/[0.07] text-[9px] font-bold text-text-primary">
                  {n.source.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] font-medium text-text-secondary line-clamp-1">{n.source}</p>
                  <p className="text-[9px] text-text-muted line-clamp-1">{n.headline}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      ) : null}

      {/* Empty hint */}
      {!result && (
        <div className="rounded-[20px] border border-violet-500/20 bg-gradient-to-br from-violet-500/[0.06] to-sky-500/[0.02] p-4 text-center">
          <Search className="h-5 w-5 text-violet-400 mb-2 mx-auto" />
          <p className="text-[11px] font-semibold text-text-primary mb-1">Research Engine</p>
          <p className="text-[10px] text-text-secondary leading-5">Search to see AI verdict, evidence, and confidence score</p>
        </div>
      )}
    </aside>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
function AISearchInner() {
  const [query, setQuery]         = useState("");
  const [input, setInput]         = useState("");
  const [result, setResult]       = useState<SearchResult | MarketPulseResult | null>(null);
  const [resultMeta, setResultMeta] = useState<ResponseMeta | null>(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [history, setHistory]     = useState<string[]>([]);
  const [followUp, setFollowUp]   = useState("");
  const [resultTime, setResultTime] = useState(new Date());
  const textareaRef  = useRef<HTMLTextAreaElement>(null);
  const didAutoSearch = useRef(false);
  const searchParams  = useSearchParams();
  const v3Stream = useAISearchStream();
  const session = useResearchSession();
  const [clarification, setClarification] = useState<{
    term: string; candidates: { symbol: string; name: string }[]; originalQuery: string;
  } | null>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const runSearch = useCallback(async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed || loading) return;
    setQuery(trimmed);
    setInput(trimmed);
    setFollowUp("");
    setLoading(true);
    setError(null);
    setResult(null);
    setResultMeta(null);
    setClarification(null);
    setHistory(prev => [trimmed, ...prev.filter(h => h !== trimmed)].slice(0, 10));
    try {
      const existing = JSON.parse(localStorage.getItem(AI_SEARCH_HISTORY_KEY) ?? "[]");
      const entry = { id: `s-${Date.now()}`, title: trimmed, href: `/ai-search?q=${encodeURIComponent(trimmed)}`, timestamp: Date.now() };
      const deduped = existing.filter((e: { title: string }) => e.title !== trimmed);
      localStorage.setItem(AI_SEARCH_HISTORY_KEY, JSON.stringify([entry, ...deduped].slice(0, 20)));
      window.dispatchEvent(new Event(AI_SEARCH_HISTORY_EVENT));
    } catch { /**/ }
    if (AI_SEARCH_V3_ENABLED) {
      // Streaming path — result/error land via the useEffect below that
      // watches v3Stream, so setLoading(false) happens there, not here.
      // session_context (Phase 1.7) lets the backend resolve natural
      // follow-ups ("What about BEML?", "Which is safer?") against
      // whatever this session has already discussed — see
      // useResearchSession.toApiContext.
      v3Stream.run(trimmed, history, session.toApiContext());
      return;
    }
    try {
      const res = await fetch(`${API}/api/ai/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: trimmed, history }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Search failed" }));
        throw new Error(err.detail || "Search failed");
      }
      const data = await res.json();
      setResult(data.result);
      setResultTime(new Date());
    } catch (e: any) {
      setError(e.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [loading, history, v3Stream]);

  // Syncs the streaming hook's terminal state (result/error) back into this
  // component's own state machine, so every downstream consumer (SearchResults,
  // the follow-up flow, resultTime) works identically regardless of which
  // path fetched the data.
  useEffect(() => {
    if (!AI_SEARCH_V3_ENABLED) return;
    if (v3Stream.result) {
      // needs_clarification (Phase 1.7) — a bare conglomerate name ("Tata")
      // that maps to several real companies. Show the picker instead of
      // treating this as a normal answer — nothing to accumulate into the
      // session yet since nothing was actually resolved.
      if (v3Stream.result.needs_clarification) {
        setClarification({
          term: v3Stream.result.ambiguous_term,
          candidates: v3Stream.result.candidates ?? [],
          originalQuery: query,
        });
        setLoading(false);
        return;
      }
      setResult(v3Stream.result);
      setResultMeta(v3Stream.meta);
      setResultTime(new Date());
      setLoading(false);

      const r = v3Stream.result;
      if (r.type !== "market_pulse") {
        session.addFromResult(query, r.response_id ?? null, {
          companies: (r.companies ?? []).map((c: Company) => ({ symbol: c.symbol, name: c.name })).filter((c: SessionEntity) => isRealSymbol(c.symbol)),
          sectors: (r.sectors ?? []).map((s: Sector) => s.name),
          events: (r.related_events ?? []).slice(0, 3).map((e: RelatedEvent) => e.title),
          policies: (r.policies ?? []).slice(0, 2).map((p: Policy) => p.title),
          verdict: r.decision_engine_v2?.verdict_scale ?? r.investment_verdict?.rating ?? null,
        });
      }
    } else if (v3Stream.error) {
      setError(v3Stream.error);
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [v3Stream.result, v3Stream.meta, v3Stream.error]);

  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !didAutoSearch.current) {
      didAutoSearch.current = true;
      setInput(q);
      runSearch(q);
    }
  }, [searchParams, runSearch]);

  // Merges a Refine Analysis result (decision layer only) into the current
  // result in place — companies/evidence/graph/etc. are untouched since the
  // underlying evidence didn't change, only how it's weighed for the user's
  // stated parameters. response_id moves forward so feedback attributes to
  // the refined answer, not the original.
  function handleRefined(refined: RefinedDecision, newResponseId: string) {
    setResult(prev => {
      if (!prev || prev.type === "market_pulse") return prev;
      return {
        ...prev,
        investment_verdict: { ...prev.investment_verdict, ...refined.investment_verdict } as InvestmentVerdict,
        decision_engine_v2: { ...(prev as SearchResult).decision_engine_v2, ...refined.decision_engine_v2 } as DecisionEngineV2,
        ai_conclusion: { ...(prev as SearchResult).ai_conclusion, ...refined.ai_conclusion } as AIConclusion,
        response_id: newResponseId,
      };
    });
    setResultMeta(prev => (prev ? { ...prev, responseId: newResponseId } : prev));
  }

  function handleSubmit(e: React.FormEvent) { e.preventDefault(); runSearch(input); }
  function handleFollowUpSubmit(e: React.FormEvent) { e.preventDefault(); if (followUp.trim()) runSearch(followUp); }
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runSearch(input); }
  }
  function handleSidebarAction(type: string) {
    if (type === "followup") textareaRef.current?.focus();
    if (type === "pdf" && result && result.type !== "market_pulse") openResearchReport(result as SearchResult);
    if (type === "markdown" && result && result.type !== "market_pulse") downloadMarkdown(result as SearchResult);
  }

  return (
    <>
      <div className="mx-auto flex max-w-[1600px] items-start gap-6 px-6 py-6">
      {/* ── Main content column ──────────────────────────────────────────────── */}
      <div className="min-w-0 flex-1 space-y-4 pb-6">
        {/* Current Context — removable chips reflecting the live research session */}
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
        {/* Search bar */}
        <form onSubmit={handleSubmit}>
          <div className="group flex items-end overflow-hidden rounded-[18px] border border-surface-border/8 bg-surface-card shadow-[0_0_0_1px_rgb(var(--text-primary) / 0.04)] transition focus-within:border-violet-500/50 focus-within:shadow-[0_0_0_4px_rgba(139,92,246,0.08)]">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask any market question — hold, switch, compare, or analyse…"
              disabled={loading}
              rows={2}
              className="flex-1 resize-none bg-transparent px-4 py-4 text-[14px] text-text-primary outline-none placeholder:text-text-muted disabled:opacity-50 leading-relaxed"
            />
            <div className="flex items-center gap-2 p-3">
              {query && (
                <button type="button" onClick={() => { setQuery(""); setResult(null); setInput(""); }}
                  className="flex h-8 w-8 items-center justify-center rounded-[12px] border border-surface-border/8 bg-text-primary/[0.03] text-text-secondary hover:text-text-primary transition">
                  <RotateCcw className="h-3.5 w-3.5"/>
                </button>
              )}
              <button type="submit" disabled={!input.trim() || loading}
                className="flex h-9 w-9 items-center justify-center rounded-[14px] bg-violet-600 text-text-primary transition hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg">
                {loading ? (
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25"/>
                    <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
                  </svg>
                ) : (
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
                )}
              </button>
            </div>
          </div>

          {/* Example chips */}
          {!query && (
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              <span className="text-[11px] text-text-muted">Try:</span>
              {EXAMPLES.slice(0, 4).map(ex => (
                <button key={ex} type="button" onClick={() => runSearch(ex)}
                  className="rounded-full border border-surface-border/7 bg-text-primary/[0.02] px-3 py-1.5 text-[11px] text-text-muted transition hover:border-violet-500/30 hover:text-violet-600 dark:text-violet-300">
                  {ex.length > 52 ? ex.slice(0, 49) + "…" : ex}
                </button>
              ))}
            </div>
          )}
        </form>

        {/* Error state */}
        <AnimatePresence>
          {error && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="rounded-[16px] border border-rose-500/20 bg-rose-500/[0.05] p-4 flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-rose-400 shrink-0"/>
              <div>
                <p className="text-[13px] font-medium text-rose-600 dark:text-rose-300">Search failed</p>
                <p className="text-[11px] text-rose-400/70">{error}</p>
              </div>
              <button onClick={() => runSearch(query)}
                className="ml-auto rounded-xl bg-rose-500/20 px-3 py-1.5 text-[11px] text-rose-600 dark:text-rose-300 hover:bg-rose-500/30 transition">
                Retry
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Content area */}
        <AnimatePresence mode="wait">
          {clarification ? (
            <motion.div key="clarification" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <ClarificationPicker
                ambiguousTerm={clarification.term}
                candidates={clarification.candidates}
                onPick={(symbol, name) => {
                  // Substitutes the picked company's name for the bare
                  // ambiguous term in the original query text — turns
                  // "Should I compare with Tata" into "...with Tata Motors",
                  // a fully self-contained query the backend resolves
                  // normally, no special-casing needed on that side.
                  const re = new RegExp(`\\b${clarification.term}\\b`, "i");
                  const substituted = clarification.originalQuery.replace(re, name);
                  setClarification(null);
                  runSearch(substituted);
                }}
              />
            </motion.div>
          ) : loading ? (
            <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              {AI_SEARCH_V3_ENABLED ? (
                <SearchProgressStages
                  query={query}
                  stageHistory={v3Stream.stageHistory}
                  elapsedMs={v3Stream.elapsedMs}
                  loading={v3Stream.loading}
                />
              ) : (
                <SearchWaitingState query={query}/>
              )}
            </motion.div>
          ) : result ? (
            <motion.div key="result" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
              {result.type === "market_pulse"
                ? <MarketPulseResults result={result}/>
                : <SearchResults result={result} onFollowUp={runSearch} resultTime={resultTime} resultMeta={resultMeta} onRefined={handleRefined}/>}
            </motion.div>
          ) : (
            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <EmptyState onSearch={runSearch}/>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Right sidebar ────────────────────────────────────────────────────── */}
      <RightSidebar result={result?.type === "market_pulse" ? null : result} onAction={handleSidebarAction}
        onReopenSearch={runSearch} activeQuery={query || undefined} session={session}/>
      </div>{/* end flex container */}

      {/* ── Fixed bottom follow-up bar ───────────────────────────────────────── */}
      {(result || loading) && (
        <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-surface-border/6 bg-bg/97 backdrop-blur-xl px-6 py-3">
          <div className="mx-auto max-w-[1600px]">
            <form onSubmit={handleFollowUpSubmit}
              className="flex items-center gap-3 rounded-[18px] border border-surface-border/8 bg-surface-card px-4 py-2.5 focus-within:border-violet-500/40 transition">
              <input type="text" value={followUp} onChange={e => setFollowUp(e.target.value)}
                placeholder="Ask a follow-up question…"
                className="flex-1 bg-transparent text-[13px] text-text-primary outline-none placeholder:text-text-muted"/>
              <button type="submit" disabled={!followUp.trim() || loading}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[12px] bg-violet-600 text-text-primary hover:bg-violet-500 disabled:opacity-40 transition">
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
              </button>
            </form>
            {result && result.type !== "market_pulse" && (() => {
              // Same source as the main "Continue Your Research" panel —
              // flattened to the first few items so this quick-chip strip
              // never shows a different set of suggestions than the panel.
              const quick = result.follow_up_groups?.length
                ? result.follow_up_groups.flatMap(g => g.items.map(it => it.query)).slice(0, 4)
                : result.follow_up_questions?.slice(0, 4) ?? [];
              return quick.length > 0 ? (
                <div className="flex items-center gap-2 mt-2 flex-wrap">
                  {quick.map((q: string) => (
                    <button key={q} onClick={() => { setFollowUp(q); runSearch(q); }}
                      className="rounded-full border border-surface-border/7 bg-text-primary/[0.02] px-3 py-1 text-[11px] text-text-muted transition hover:border-violet-500/30 hover:text-violet-600 dark:text-violet-300">
                      {q.length > 55 ? q.slice(0, 52) + "…" : q}
                    </button>
                  ))}
                </div>
              ) : null;
            })()}
          </div>
        </div>
      )}
    </>
  );
}

export default function AISearchPage() {
  return (
    <Suspense fallback={
      <div className="flex h-32 items-center justify-center">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent"/>
      </div>
    }>
      <AISearchInner/>
    </Suspense>
  );
}
