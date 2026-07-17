"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Newspaper, Bot, BarChart2, CheckCircle2, Sparkles, Bookmark, Plus, Download, Share2, Copy, TrendingUp, TrendingDown, Minus, RotateCcw, Building2, ChevronRight, Target, Truck, Landmark, Factory, Ship, LineChart as LineChartIcon, ShieldAlert, Users, Cpu, Wallet, Scale, Receipt, GitBranch, DollarSign, Package, CreditCard, Eye, ListChecks, ArrowRight, Clock, AlertTriangle, GitCompare, FileText } from "lucide-react";
import { AITransparencyPanel } from "@/components/ai/AITransparencyPanel";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import { DecisionIntelligencePanel, type DecisionIntelligence } from "@/components/ai/DecisionIntelligencePanel";
import { API_BASE_URL as API } from "@/lib/api";


// ── Types ──────────────────────────────────────────────────────────────────────
interface AnswerSection {
  summary: string; bottom_line: string; what_happened: string; why_it_happened: string;
  immediate_impact: string; medium_term: string; long_term: string;
  what_priced_in: string;
  risks: string[]; opportunities: string[];
  confidence: number; confidence_level?: string;
  sentiment: "bullish" | "bearish" | "neutral";
  sources_count: number;
}
interface KeyDriver    { icon: string; title: string; explanation: string; confidence: number; }
interface Insight      { icon: string; title: string; summary: string; }
interface Company      { symbol: string; name: string; price: string; change: string; positive: boolean; impact_type: string; impact_score: number; confidence: number; reason: string; chart: number[]; ripple_position?: string; why_it_matters?: string; }
interface Sector       { name: string; score: number; confidence: number; outlook: string; positive: boolean; status?: string; time_horizon?: string; explanation?: string; }
interface RelatedEvent { id: string; title: string; date: string; impact_score: number; confidence: number; category: string; }
interface NewsItem     { id: string; headline: string; summary: string; source: string; published_at: string; impact_score: number; }
interface Policy       { id: number; title: string; ministry: string; status: string; impact_score: number; }
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
interface Scenario      { probability: number; outcome: string; key_drivers: string[]; supporting_evidence: string; major_catalysts: string[]; expected_evolution: string; confidence: number; }
interface Scenarios     { bull?: Scenario; base?: Scenario; bear?: Scenario; }
interface MarketHorizon { horizon: string; window: string; confidence: number; direction: string; description: string; }
interface MonitorItem   { title: string; why_it_matters: string; importance: string; frequency: string; }
interface ReasoningMethod { label: string; used: boolean; }
interface ConfidenceData  { level: string; score: number; reasons: string[]; breakdown: Record<string, number>; caveats: string[]; }
interface InvestmentVerdict { rating: string; direction: string; confidence: number; horizon: string; top_picks: string[]; risks: string[]; catalysts: string[]; opportunity_score: number; risk_level?: string; suitable_for?: string; }
interface ChartSeries  { name: string; data: number[]; color: string; }
interface MarketChart  { labels: string[]; series: ChartSeries[]; }
interface GraphNode    { id: string; label: string; type: string; x: number; y: number; }
interface GraphEdge    { id: string; source: string; target: string; label: string; }

interface SearchResult {
  query: string; answer: AnswerSection; key_drivers: KeyDriver[]; insights: Insight[];
  companies: Company[]; sectors: Sector[]; related_events: RelatedEvent[];
  news: NewsItem[]; policies: Policy[]; timeline: Timeline[];
  historical_comparison: HistoricalComparison[];
  ripple_chain: RippleLevel[];
  scenarios: Scenarios;
  market_impact_horizons: MarketHorizon[];
  what_to_monitor: MonitorItem[];
  ai_reasoning_methods: ReasoningMethod[];
  follow_up_questions: string[];
  investment_verdict: InvestmentVerdict; market_chart: MarketChart;
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  citations: string[];
  decision_intelligence: DecisionIntelligence | null;
  confidence_data?: ConfidenceData;
}

// ── Constants ──────────────────────────────────────────────────────────────────
const LOADING_STEPS: { icon: ReactNode; label: string }[] = [
  { icon: <Search className="h-4 w-4" />,       label: "Searching events database…" },
  { icon: <Newspaper className="h-4 w-4" />,    label: "Reading news sources…" },
  { icon: <Bot className="h-4 w-4" />,          label: "Generating AI analysis…" },
  { icon: <BarChart2 className="h-4 w-4" />,    label: "Calculating market impact…" },
  { icon: <CheckCircle2 className="h-4 w-4" />, label: "Preparing your report…" },
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
  Government:          "bg-violet-500/20 text-violet-300 border-violet-500/30",
  "Government Policy": "bg-violet-500/20 text-violet-300 border-violet-500/30",
  Policy:              "bg-sky-500/20 text-sky-300 border-sky-500/30",
  Corporate:           "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  "Economic Event":    "bg-teal-500/20 text-teal-300 border-teal-500/30",
  "Industry Update":   "bg-amber-500/20 text-amber-300 border-amber-500/30",
  RBI:                 "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
  Macro:               "bg-amber-500/20 text-amber-300 border-amber-500/30",
  Market:              "bg-teal-500/20 text-teal-300 border-teal-500/30",
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
  policy:    "border-violet-500/30 bg-violet-500/10 text-violet-300",
  sector:    "border-sky-500/30 bg-sky-500/10 text-sky-300",
  commodity: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  company:   "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  event:     "border-rose-500/30 bg-rose-500/10 text-rose-300",
};

const RIPPLE_POSITION_COLOR: Record<string, string> = {
  "Primary Beneficiary":   "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  "Secondary Beneficiary": "bg-emerald-500/10 text-emerald-400/80 border-emerald-500/20",
  "Primary Pressure":      "bg-rose-500/15 text-rose-300 border-rose-500/30",
  "Secondary Pressure":    "bg-rose-500/10 text-rose-400/80 border-rose-500/20",
  "Indirect Exposure":     "bg-slate-500/10 text-slate-400 border-slate-500/20",
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
function BigGauge({ score, size = 120 }: { score: number; size?: number }) {
  const r = size * 0.38;
  const cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = score >= 80 ? "#22c55e" : score >= 60 ? "#60a5fa" : "#f59e0b";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8"/>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="8"
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cy})`}
        style={{ transition: "stroke-dasharray 1s ease" }}/>
      <text x={cx} y={cy + 6} textAnchor="middle" fill="white"
        fontSize={size * 0.22} fontWeight="800" fontFamily="inherit">
        {score}%
      </text>
    </svg>
  );
}

/** Small ring used in company cards */
function SmallRing({ score, size = 36 }: { score: number; size?: number }) {
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = score >= 80 ? "#22c55e" : score >= 60 ? "#60a5fa" : "#f59e0b";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3"/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="3"
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}/>
      <text x={size/2} y={size/2 + 4} textAnchor="middle" fill={color}
        fontSize={size * 0.25} fontWeight="700" fontFamily="inherit">
        {score}
      </text>
    </svg>
  );
}

/** Mini sparkline for company chart */
function MiniSparkline({ data, positive, width = 72, height = 28 }: { data: number[]; positive: boolean; width?: number; height?: number }) {
  if (!data?.length) return <div style={{ width, height }} className="rounded bg-white/[0.03]"/>;
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

/** Derive risk level from confidence */
function riskLevel(confidence: number): { label: string; color: string } {
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

// ── Loading state ──────────────────────────────────────────────────────────────
function LoadingState({ query }: { query: string }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep(s => Math.min(s + 1, LOADING_STEPS.length - 1)), 1200);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="space-y-4 pb-10">
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-6">
        <div className="flex items-start gap-4 mb-6">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-500/20 text-violet-400">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-widest text-violet-400 mb-1">AI Answer</p>
            <p className="text-sm text-slate-400">Researching: <span className="text-white font-medium">{query}</span></p>
          </div>
        </div>
        <div className="space-y-3">
          {LOADING_STEPS.map((s, i) => (
            <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: i <= step ? 1 : 0.25, x: 0 }}
              transition={{ delay: i * 0.15 }}
              className="flex items-center gap-3">
              <span className="w-6 flex justify-center text-slate-400">{s.icon}</span>
              <div className={`flex-1 h-1.5 rounded-full overflow-hidden ${i < step ? "bg-violet-500/30" : "bg-white/[0.05]"}`}>
                {i <= step && (
                  <motion.div className="h-full bg-gradient-to-r from-violet-500 to-sky-400 rounded-full"
                    initial={{ width: "0%" }} animate={{ width: i < step ? "100%" : "60%" }}
                    transition={{ duration: 1.2, ease: "easeInOut" }}/>
                )}
              </div>
              <span className={`text-[12px] w-48 ${i <= step ? "text-slate-300" : "text-slate-600"}`}>{s.label}</span>
            </motion.div>
          ))}
        </div>
      </div>
      {[1, 2].map(i => (
        <div key={i} className="h-40 animate-pulse rounded-[20px] bg-white/[0.03]"/>
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
        <h2 className="text-xl font-semibold text-white mb-2">AI Decision Intelligence Engine</h2>
        <p className="text-sm text-slate-400 max-w-md leading-relaxed">Ask any investment decision question — hold, switch, compare, or analyse. Get explainable AI reasoning, evidence, and trade-offs.</p>
      </div>
      <div className="w-full max-w-xl space-y-2">
        <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-3">Try these searches</p>
        {EXAMPLES.map(q => (
          <button key={q} onClick={() => onSearch(q)}
            className="group flex w-full items-center gap-3 rounded-[14px] border border-white/[0.06] bg-white/[0.02] px-4 py-3 text-left text-[13px] text-slate-300 transition hover:border-violet-500/30 hover:bg-violet-500/[0.04] hover:text-white">
            <Search className="h-4 w-4 text-violet-400 shrink-0" />
            {q}
            <span className="ml-auto text-slate-600 group-hover:text-violet-400 transition text-sm">→</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Search Results ─────────────────────────────────────────────────────────────
function SearchResults({ result, onFollowUp, resultTime }: {
  result: SearchResult;
  onFollowUp: (q: string) => void;
  resultTime: Date;
}) {
  const [showMore, setShowMore] = useState(false);
  const [saved, setSaved] = useState(false);
  const [activeRippleNode, setActiveRippleNode] = useState<string | null>(null);

  const { answer, key_drivers, companies, sectors, related_events, news, policies,
          investment_verdict, historical_comparison,
          ripple_chain, scenarios, market_impact_horizons, what_to_monitor,
          ai_reasoning_methods, confidence_data,
          follow_up_questions, decision_intelligence } = result;

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
  const risk = investment_verdict?.risk_level
    ? { label: investment_verdict.risk_level, color:
        investment_verdict.risk_level === "Low" ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
        : investment_verdict.risk_level === "Medium" ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
        : "text-rose-400 bg-rose-500/10 border-rose-500/20" }
    : riskLevel(answer?.confidence ?? investment_verdict?.confidence ?? 70);
  const suitableForLabel = investment_verdict?.suitable_for || suitableFor(investment_verdict?.horizon || "");

  // Continue Your Research CTAs
  const topCo   = companies?.[0];
  const topCo2  = companies?.[1];
  const topEv   = related_events?.[0];
  const topFU   = follow_up_questions?.[0];
  const topSec  = sectors?.[0];
  const topPol  = policies?.[0];
  const hasRipple = (ripple_chain?.length ?? 0) > 1;

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
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-1.5">Search Answer</p>
            <h1 className="text-[18px] font-bold text-white leading-snug">{result.query}</h1>
            <p className="mt-1 text-[11px] text-slate-500">
              Generated {minAgo} min ago
              <span className="mx-1.5 text-slate-700">·</span>
              AI Model: MarketRipple Intelligence (v2.7)
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0 mt-0.5">
            <button onClick={() => onFollowUp("")}
              className="flex items-center gap-1.5 rounded-[12px] border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[12px] font-medium text-slate-300 hover:bg-white/[0.08] transition">
              <Plus className="h-3.5 w-3.5"/>
              New Search
            </button>
            <button onClick={handleSave}
              className={`flex h-8 w-8 items-center justify-center rounded-[10px] border transition ${saved ? "border-violet-500/40 bg-violet-500/20 text-violet-300" : "border-white/10 bg-white/[0.04] text-slate-400 hover:bg-white/[0.08]"}`}>
              <Bookmark className="h-4 w-4"/>
            </button>
          </div>
        </div>
      </div>

      {/* ── Decision Intelligence Panel ───────────────────────────────────────── */}
      {isDecision && decision_intelligence && (
        <DecisionIntelligencePanel di={decision_intelligence} query={result.query} onRefine={onFollowUp}/>
      )}

      {/* ── 1. Research Outlook ───────────────────────────────────────────────── */}
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
        <div className="flex items-center gap-2 mb-4">
          <span className="rounded-full bg-violet-500/20 border border-violet-500/30 px-2.5 py-0.5 text-[10px] font-bold text-violet-300 uppercase tracking-wider">Research Outlook</span>
          <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-0.5 text-[10px] font-medium text-slate-400">Not investment advice</span>
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
            { label: "Confidence", value: `${answer?.confidence ?? investment_verdict?.confidence ?? 0}%`, color: "text-emerald-400" },
            { label: "Time Horizon", value: investment_verdict?.horizon || "6–18 Months", color: "text-slate-200" },
            { label: "Risk Level", value: risk.label, color: risk.color.split(" ")[0] },
            { label: "Suitable For", value: suitableForLabel, color: "text-slate-200" },
          ].map(s => (
            <div key={s.label} className="rounded-[12px] border border-white/[0.06] bg-white/[0.02] px-3 py-2">
              <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-0.5">{s.label}</p>
              <p className={`text-[12px] font-semibold ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── 2. Executive Summary ──────────────────────────────────────────────── */}
      <div className="rounded-[20px] border border-violet-500/20 bg-gradient-to-br from-violet-500/[0.06] to-transparent p-5">
        <p className="text-[11px] uppercase tracking-wider text-violet-400 mb-2 font-semibold">Executive Summary</p>
        <p className="text-[14px] text-white leading-relaxed">
          {answer?.bottom_line || answer?.summary || "No direct answer generated for this query."}
        </p>
      </div>

      {/* ── 3. Why AI Thinks This ─────────────────────────────────────────────── */}
      {key_drivers?.length > 0 && (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <p className="text-[15px] font-semibold text-white mb-4">Why AI Thinks This</p>
          <div className="grid grid-cols-3 gap-3">
            {key_drivers.slice(0, 6).map((kd, i) => (
              <div key={i} className="rounded-[14px] border border-white/[0.07] bg-white/[0.02] p-4">
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/15 text-violet-300">
                    {DRIVER_ICON_MAP[kd.icon] ?? <Sparkles className="h-4 w-4"/>}
                  </div>
                  <p className="text-[12px] font-semibold text-white leading-tight">{kd.title}</p>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed mb-2">{kd.explanation}</p>
                <div className="flex items-center gap-2">
                  <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                    <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-sky-400" style={{ width: `${kd.confidence}%` }}/>
                  </div>
                  <p className="text-[10px] tabular-nums text-slate-500">{kd.confidence}%</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 4. Ripple Analysis ────────────────────────────────────────────────── */}
      {ripple_chain?.length > 1 && (
        <div id="ripple-analysis" className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center gap-2 mb-1">
            <GitBranch className="h-4 w-4 text-violet-400"/>
            <p className="text-[15px] font-semibold text-white">Ripple Analysis</p>
          </div>
          <p className="text-[10px] text-slate-500 mb-4">How the impact propagates through the economy — first, second and third-order effects, from the intelligence graph.</p>
          <div className="overflow-x-auto pb-1">
            <div className="flex items-stretch gap-2 min-w-max">
              {ripple_chain.map((level, li) => (
                <div key={level.depth} className="flex items-center">
                  <div className="flex flex-col gap-2 justify-center">
                    <p className="text-[8px] uppercase tracking-wider text-slate-600 text-center">
                      {li === 0 ? "Source" : li === 1 ? "1st Order" : li === 2 ? "2nd Order" : "3rd Order+"}
                    </p>
                    {level.nodes.map((node, ni) => (
                      <button
                        key={`${level.depth}-${node.id ?? ni}`}
                        onClick={() => setActiveRippleNode(node.id === activeRippleNode ? null : node.id)}
                        className={`rounded-[12px] border px-3 py-2 text-left transition ${RIPPLE_TYPE_COLOR[node.type] ?? "border-white/10 bg-white/[0.03] text-slate-300"} ${activeRippleNode === node.id ? "ring-2 ring-violet-400/50" : "hover:brightness-125"}`}>
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
                    <ArrowRight className="h-4 w-4 text-slate-700 mx-2 shrink-0"/>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── 5. Companies That Matter ──────────────────────────────────────────── */}
      {companies?.length > 0 && (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-baseline gap-2">
              <p className="text-[15px] font-semibold text-white">Companies That Matter</p>
              <span className="text-[10px] text-slate-500">Ranked by impact score</span>
            </div>
            <div className="flex items-center gap-3">
              {companies.length >= 2 && (
                <Link
                  href={`/compare?a=${companies[0].symbol}&b=${companies[1].symbol}`}
                  className="flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-[11px] font-semibold text-sky-300 hover:bg-sky-500/20 transition">
                  ↔ Compare {companies[0].symbol} vs {companies[1].symbol}
                </Link>
              )}
              <Link href="/companies" className="text-[12px] text-violet-400 hover:text-violet-300 transition">
                View All →
              </Link>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {companies.slice(0, 6).map((co, idx) => {
              const avatarColors = ["bg-red-700", "bg-blue-700", "bg-orange-700", "bg-teal-700", "bg-violet-700", "bg-indigo-700"];
              const av = avatarColors[idx % avatarColors.length];
              return (
                <div key={co.symbol} className="rounded-[16px] border border-white/[0.07] bg-white/[0.02] p-4">
                  {/* Header */}
                  <div className="flex items-center gap-2.5 mb-2.5">
                    <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] ${av} text-[11px] font-bold text-white`}>
                      {co.symbol.slice(0, 2)}
                    </div>
                    <div className="min-w-0">
                      <p className="text-[13px] font-bold text-white truncate">{co.symbol}</p>
                      {co.price && co.price !== "—" ? (
                        <p className="text-[11px] tabular-nums">
                          <span className="text-slate-300">₹{co.price}</span>
                          <span className={`ml-1 font-semibold ${co.positive ? "text-emerald-400" : "text-rose-400"}`}>{co.change}</span>
                        </p>
                      ) : (
                        <p className="text-[10px] text-slate-600">—</p>
                      )}
                    </div>
                    <div className="ml-auto shrink-0">
                      <MiniSparkline data={co.chart} positive={co.positive}/>
                    </div>
                  </div>

                  {/* Ripple position badge */}
                  {co.ripple_position && (
                    <span className={`inline-block mb-2 rounded border px-1.5 py-0.5 text-[9px] font-semibold ${RIPPLE_POSITION_COLOR[co.ripple_position] ?? "bg-slate-500/10 text-slate-400 border-slate-500/20"}`}>
                      {co.ripple_position}
                    </span>
                  )}

                  {/* Why it matters */}
                  <div className="mb-3">
                    <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1">Why it matters</p>
                    <p className="text-[11px] text-slate-300 leading-relaxed line-clamp-2">{co.why_it_matters || co.reason || "Directly impacted by this event"}</p>
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <SmallRing score={Math.round(co.confidence ?? co.impact_score)} size={32}/>
                      <p className="text-[10px] text-slate-500">Confidence</p>
                    </div>
                    <Link href={`/companies/${co.symbol}`}
                      className="text-[11px] font-medium text-violet-400 hover:text-violet-300 transition">
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
          <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
            <p className="text-[14px] font-semibold text-white mb-4">Sector Impact</p>
            <div className="w-full">
              <div className="grid grid-cols-[1.3fr_0.6fr_0.7fr_1fr_0.8fr] gap-x-2 mb-2">
                {["Sector", "Impact", "Confidence", "Status", "Horizon"].map(h => (
                  <p key={h} className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">{h}</p>
                ))}
              </div>
              <div className="space-y-3">
                {sectors.slice(0, 5).map(s => (
                  <div key={s.name}>
                    <div className="grid grid-cols-[1.3fr_0.6fr_0.7fr_1fr_0.8fr] gap-x-2 items-center">
                      <p className="text-[12px] font-medium text-slate-200 truncate">{s.name}</p>
                      <p className="text-[12px] font-bold tabular-nums text-white">{(s.score / 10).toFixed(1)}</p>
                      <p className="text-[11px] tabular-nums text-slate-400">{s.confidence}%</p>
                      <p className={`text-[11px] font-medium truncate ${SECTOR_STATUS_COLOR[s.status ?? ""] ?? "text-slate-300"}`}>{s.status || s.outlook || "—"}</p>
                      <p className="text-[10px] text-slate-500">{s.time_horizon || "—"}</p>
                    </div>
                    {s.explanation && (
                      <p className="text-[10px] text-slate-500 leading-relaxed mt-0.5 line-clamp-1">{s.explanation}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Related Events Timeline */}
        {related_events?.length > 0 && (
          <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Clock className="h-3.5 w-3.5 text-slate-400"/>
                <p className="text-[14px] font-semibold text-white">Related Events Timeline</p>
              </div>
              <Link href="/events" className="text-[11px] text-violet-400 hover:text-violet-300 transition">View All Events →</Link>
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
                          {i > 0 && <div className="flex-1 h-px bg-white/[0.08]"/>}
                          <div className={`h-3 w-3 shrink-0 rounded-full border-2 border-[#0d1117] ${sc.dot}`}/>
                          {!isLast && <div className="flex-1 h-px bg-white/[0.08]"/>}
                        </div>
                        <div className="mt-2 px-1 text-center">
                          <Link href={`/events/${ev.id}`}
                            className="block text-[11px] font-medium text-slate-200 hover:text-white transition line-clamp-2 leading-tight text-center">
                            {ev.title.length > 35 ? ev.title.slice(0, 32) + "…" : ev.title}
                          </Link>
                          <p className="text-[9px] text-slate-600 mt-1">{ev.date?.split(",")[0] || ev.date}</p>
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
        <div className="h-px flex-1 bg-white/[0.07]"/>
        <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
          <ListChecks className="h-3 w-3"/>
          Deep Research
        </span>
        <div className="h-px flex-1 bg-white/[0.07]"/>
      </div>

      {/* ── 7. Market Context ─────────────────────────────────────────────────── */}
      {answer?.what_priced_in && (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center gap-2 mb-2">
            <Eye className="h-4 w-4 text-sky-400"/>
            <p className="text-[15px] font-semibold text-white">Market Context</p>
            <span className="text-[10px] text-slate-500">— is this already priced in?</span>
          </div>
          <p className="text-[12px] text-slate-300 leading-relaxed">{answer.what_priced_in}</p>
        </div>
      )}

      {/* ── 8. Market Impact — Immediate / Next Quarter / Long Term ──────────── */}
      {market_impact_horizons?.length > 0 && (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <p className="text-[15px] font-semibold text-white mb-4">Market Impact Over Time</p>
          <div className="grid grid-cols-3 gap-3">
            {market_impact_horizons.map(h => {
              const dirColor = h.direction === "positive" ? "text-emerald-400" : h.direction === "negative" ? "text-rose-400" : "text-amber-400";
              const barColor = h.direction === "positive" ? "from-emerald-500 to-emerald-300" : h.direction === "negative" ? "from-rose-500 to-rose-300" : "from-amber-500 to-amber-300";
              return (
                <div key={h.horizon} className="rounded-[14px] border border-white/[0.07] bg-white/[0.02] p-4">
                  <p className="text-[12px] font-semibold text-white">{h.horizon}</p>
                  <p className="text-[9px] text-slate-500 mb-2">{h.window}</p>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                      <div className={`h-full rounded-full bg-gradient-to-r ${barColor}`} style={{ width: `${h.confidence}%` }}/>
                    </div>
                    <p className={`text-[10px] font-semibold tabular-nums ${dirColor}`}>{h.confidence}%</p>
                  </div>
                  <p className="text-[10px] text-slate-400 leading-relaxed line-clamp-3">{h.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── 9. Historical Comparison ──────────────────────────────────────────── */}
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
        <p className="text-[15px] font-semibold text-white mb-4">Historical Comparison</p>
        {historical_comparison?.length > 0 ? (
          <div className="grid grid-cols-2 gap-3">
            {historical_comparison.slice(0, 2).map((h, i) => (
              <div key={i} className="rounded-[14px] border border-white/[0.07] bg-white/[0.02] p-4">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-[12px] font-medium text-violet-300">{h.event_title}</p>
                  <span className="shrink-0 rounded bg-violet-500/10 px-1.5 py-0.5 text-[9px] font-semibold text-violet-400">{Math.round(h.similarity)}% match score</span>
                </div>
                <p className="text-[9px] text-slate-500 mb-2">{h.event_date}</p>

                {/* Outcome — real index returns, honestly labeled by the actual window available */}
                {(h.nifty_1w != null || h.nifty_1m != null) && (
                  <div className="flex items-center gap-4 mb-2.5">
                    {h.nifty_1w != null && (
                      <div>
                        <p className="text-[8px] uppercase tracking-wider text-slate-500">Nifty · 1 Week</p>
                        <p className={`text-[13px] font-bold tabular-nums ${h.nifty_1w >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{h.nifty_1w >= 0 ? "+" : ""}{h.nifty_1w}%</p>
                      </div>
                    )}
                    {h.nifty_1m != null && (
                      <div>
                        <p className="text-[8px] uppercase tracking-wider text-slate-500">Nifty · 1 Month</p>
                        <p className={`text-[13px] font-bold tabular-nums ${h.nifty_1m >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{h.nifty_1m >= 0 ? "+" : ""}{h.nifty_1m}%</p>
                      </div>
                    )}
                  </div>
                )}

                <p className="text-[11px] text-slate-400 leading-relaxed mb-3 line-clamp-3">{h.key_lesson || h.what_happened}</p>
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
                  <div className="pt-2 border-t border-white/[0.06]">
                    <p className="text-[8px] uppercase tracking-wider text-amber-500/70 mb-0.5">Key Difference</p>
                    <p className="text-[10px] text-amber-300/70 leading-relaxed">{h.key_difference}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[12px] text-slate-500 text-center py-4">No closely matching historical precedent found for this query.</p>
        )}
      </div>

      {/* ── 10. Scenarios: Bull / Base / Bear ─────────────────────────────────── */}
      {scenarios && (scenarios.bull || scenarios.base || scenarios.bear) && (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <p className="text-[15px] font-semibold text-white mb-4">Scenarios</p>
          <div className="grid grid-cols-3 gap-3">
            {([
              { key: "bull", label: "Bull Case", data: scenarios.bull, color: "text-emerald-400", bg: "border-emerald-500/20 bg-emerald-500/[0.04]" },
              { key: "base", label: "Base Case", data: scenarios.base, color: "text-sky-400", bg: "border-sky-500/20 bg-sky-500/[0.04]" },
              { key: "bear", label: "Bear Case", data: scenarios.bear, color: "text-rose-400", bg: "border-rose-500/20 bg-rose-500/[0.04]" },
            ] as const).map(sc => sc.data && (
              <div key={sc.key} className={`rounded-[14px] border p-4 ${sc.bg}`}>
                <div className="flex items-center justify-between mb-2">
                  <p className={`text-[12px] font-bold ${sc.color}`}>{sc.label}</p>
                  <p className="text-[10px] tabular-nums text-slate-500">{sc.data.probability}%</p>
                </div>
                <p className="text-[11px] text-slate-300 leading-relaxed line-clamp-4">{sc.data.outcome}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 11. Risks & Counterarguments + What To Monitor + AI Reasoning ────── */}
      <div className="grid grid-cols-3 gap-4">

        {/* Risks & Counterarguments */}
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[13px] font-semibold text-white">Risks & Counterarguments</p>
            {(answer?.risks?.length ?? 0) > 4 && (
              <button onClick={() => setShowMore(v => !v)} className="text-[10px] text-violet-400">View All →</button>
            )}
          </div>
          <div className="space-y-2.5">
            {((answer?.risks?.length ? answer.risks : investment_verdict?.risks || []).slice(0, 4)).map((r, i) => (
              <div key={i} className="flex items-start gap-2">
                <div className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-rose-500/70 mt-1.5"/>
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] text-slate-300 leading-relaxed line-clamp-2">{r}</p>
                </div>
                <RiskSeverity text={r}/>
              </div>
            ))}
          </div>
        </div>

        {/* What To Monitor */}
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <p className="text-[13px] font-semibold text-white mb-3">What To Monitor</p>
          <div className="space-y-2.5">
            {(what_to_monitor?.length ? what_to_monitor : []).slice(0, 5).map((m, i) => (
              <div key={i} className="flex items-start gap-2">
                <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/20">
                  <svg className="h-2.5 w-2.5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] text-slate-300 leading-relaxed line-clamp-1">{m.title}</p>
                  <p className="text-[9px] text-slate-500">{m.frequency}{m.frequency && m.importance ? " · " : ""}{m.importance}</p>
                </div>
              </div>
            ))}
            {!what_to_monitor?.length && (
              <p className="text-[11px] text-slate-500">No monitoring checklist generated.</p>
            )}
          </div>
        </div>

        {/* AI Reasoning */}
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center gap-2 mb-3">
            <ListChecks className="h-3.5 w-3.5 text-violet-400"/>
            <p className="text-[13px] font-semibold text-white">AI Reasoning</p>
          </div>
          <div className="space-y-1.5">
            {(ai_reasoning_methods ?? []).map((m, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full ${m.used ? "bg-emerald-500/20" : "bg-slate-700/40"}`}>
                  {m.used
                    ? <svg className="h-2 w-2 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4"><polyline points="20 6 9 17 4 12"/></svg>
                    : <Minus className="h-2 w-2 text-slate-600"/>}
                </div>
                <p className={`text-[10.5px] leading-tight ${m.used ? "text-slate-300" : "text-slate-600"}`}>{m.label}</p>
              </div>
            ))}
          </div>
          {(confidence_data?.caveats?.length ?? 0) > 0 && (
            <div className="mt-3 pt-3 border-t border-white/[0.06]">
              <p className="text-[9px] uppercase tracking-wider text-amber-500/70 mb-1.5">Lower confidence if</p>
              <div className="space-y-1">
                {confidence_data!.caveats.slice(0, 3).map((c, i) => (
                  <p key={i} className="text-[10px] text-amber-300/70 leading-tight">{c}</p>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 12. Continue Your Research ────────────────────────────────────────── */}
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
        <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-3">Continue Your Research</p>
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
              href: `/policies`,
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
                className="group flex items-center gap-3 rounded-[14px] border border-white/[0.07] bg-white/[0.02] px-4 py-3 text-left transition hover:border-violet-500/30 hover:bg-violet-500/[0.04]">
                <span className="text-slate-400 flex items-center">{cta!.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-medium text-white line-clamp-1">{cta!.label}</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">{cta!.sub}</p>
                </div>
                <ChevronRight size={13} strokeWidth={1.8} className="text-slate-600 group-hover:text-violet-400 transition"/>
              </button>
            ) : (
              <Link key={i} href={(cta as any).href as any}
                className="group flex items-center gap-3 rounded-[14px] border border-white/[0.07] bg-white/[0.02] px-4 py-3 transition hover:border-violet-500/30 hover:bg-violet-500/[0.04]">
                <span className="text-slate-400 flex items-center">{cta!.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-medium text-white line-clamp-1">{cta!.label}</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">{cta!.sub}</p>
                </div>
                <ChevronRight size={13} strokeWidth={1.8} className="text-slate-600 group-hover:text-violet-400 transition"/>
              </Link>
            )
          ))}
        </div>
      </div>

      {/* ── 13. Follow-up Questions ───────────────────────────────────────────── */}
      {follow_up_questions?.length > 0 && (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <p className="text-[13px] font-semibold text-white mb-3">Follow-up Questions</p>
          <div className="grid grid-cols-2 gap-2">
            {follow_up_questions.slice(0, 4).map((q, i) => (
              <button key={i} onClick={() => onFollowUp(q)}
                className="group flex items-start gap-2 text-left transition hover:text-violet-300">
                <span className="mt-0.5 text-slate-600 group-hover:text-violet-400 transition text-xs">›</span>
                <p className="text-[11px] text-slate-400 group-hover:text-violet-300 transition leading-relaxed line-clamp-2">{q}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── 14. AI Transparency + Disclaimer ──────────────────────────────────── */}
      <AITransparencyPanel
        confidence={result.answer?.confidence ?? 70}
        reasoning={methodologySummary}
        events={(result.related_events ?? []).slice(0, 5).map((e) => ({ title: e.title, href: `/events/${e.id}` }))}
        companies={(result.companies ?? []).slice(0, 5).map((c) => ({ name: c.name, symbol: c.symbol, href: `/companies/${c.symbol}` }))}
        assumptions={confidence_data?.reasons ?? []}
        limitations={confidence_data?.caveats ?? []}
      />
      <AIDisclaimer />
    </div>
  );
}

// ── Right Sidebar ──────────────────────────────────────────────────────────────
function RightSidebar({ result, onAction }: {
  result: SearchResult | null;
  onAction: (type: string) => void;
}) {
  const [copied, setCopied] = useState(false);

  const v = result?.investment_verdict;
  // Single canonical confidence number, shown everywhere on the page —
  // never opportunity_score, which is a different metric (upside sizing,
  // not evidence confidence) and must never masquerade as a second
  // "confidence" percentage.
  const score = result?.confidence_data?.score ?? result?.answer?.confidence ?? v?.confidence ?? 0;
  const verdictLabel = v?.rating || "Neutral";
  const verdictColor = OUTLOOK_COLOR[verdictLabel] ?? "text-amber-400";
  const riskInfo = result
    ? (v?.risk_level
        ? { label: v.risk_level, color:
            v.risk_level === "Low" ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
            : v.risk_level === "Medium" ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
            : "text-rose-400 bg-rose-500/10 border-rose-500/20" }
        : riskLevel(result.answer?.confidence ?? v?.confidence ?? 70))
    : { label: "—", color: "text-slate-400" };

  const QUICK_ACTIONS = [
    { icon: <Bot className="h-4 w-4"/>,      label: "Ask Follow-up Question", action: "followup" },
    { icon: <Bookmark className="h-4 w-4"/>,  label: "Save This Answer",       action: "save" },
    { icon: <Download className="h-4 w-4"/>,  label: "Download as PDF",        action: "pdf" },
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
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
        <div className="flex items-center gap-2 mb-4">
          <Target size={14} strokeWidth={1.8} className="text-violet-400"/>
          <p className="text-[13px] font-semibold text-white">Research Outlook</p>
        </div>

        {result ? (
          <>
            {/* Top row: Overall View + Risk */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1">Overall View</p>
                <p className={`flex items-center gap-1.5 text-[14px] font-bold leading-tight ${verdictColor}`}>
                  <span className={`h-2 w-2 shrink-0 rounded-full ${OUTLOOK_DOT[verdictLabel] ?? "bg-amber-400"}`}/>
                  {verdictLabel}
                </p>
              </div>
              <div>
                <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1">Risk</p>
                <p className={`text-[15px] font-bold ${riskInfo.color.split(" ")[0]}`}>{riskInfo.label}</p>
              </div>
            </div>

            {/* Big gauge */}
            <div className="flex justify-center my-2">
              <BigGauge score={Math.round(score)} size={120}/>
            </div>

            {/* Bottom row: Time Horizon + Best For */}
            <div className="grid grid-cols-2 gap-3 mt-4">
              <div>
                <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1">Time Horizon</p>
                <p className="text-[12px] font-semibold text-white">{v?.horizon || "6–18 Months"}</p>
              </div>
              <div>
                <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1">Best For</p>
                <p className="text-[12px] font-semibold text-white">{v?.suitable_for || suitableFor(v?.horizon || "")}</p>
              </div>
            </div>

            {/* Data point count */}
            <p className="mt-3 text-center text-[10px] text-slate-500">
              AI evaluated {(result.related_events?.length ?? 0) + (result.companies?.length ?? 0) + (result.news?.length ?? 0)} data points
            </p>
          </>
        ) : (
          <div className="flex justify-center my-6">
            <BigGauge score={0} size={120}/>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-4">
        <p className="text-[12px] font-semibold text-slate-300 mb-3">Quick Actions</p>
        <div className="space-y-1">
          {QUICK_ACTIONS.map(a => (
            <button key={a.action} onClick={() => handleAction(a.action)}
              className={`flex w-full items-center gap-3 rounded-[12px] p-2.5 text-left transition hover:bg-white/[0.05] ${!result && a.action !== "copy" ? "opacity-40 pointer-events-none" : ""}`}>
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/[0.05] text-slate-400">
                {a.icon}
              </div>
              <p className="text-[12px] text-slate-300">{a.label}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Sources & Transparency */}
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-4">
        <p className="text-[12px] font-semibold text-slate-300 mb-3">Sources & Transparency</p>
        <div className="space-y-2.5">
          {[
            { label: "News Articles",       value: result?.news?.length ?? 0 },
            { label: "Government Documents", value: result?.policies?.length ?? 0 },
            { label: "Events",               value: result?.related_events?.length ?? 0 },
            { label: "Companies",            value: result?.companies?.length ?? 0 },
            { label: "Historical Matches",   value: result?.historical_comparison?.length ?? 0 },
            { label: "Graph Nodes",          value: result?.graph?.nodes?.length ?? 0 },
            { label: "Graph Edges",          value: result?.graph?.edges?.length ?? 0 },
          ].map(s => (
            <div key={s.label} className="flex items-center justify-between">
              <p className="text-[11px] text-slate-400">{s.label}</p>
              <p className="text-[12px] font-bold text-white tabular-nums">{s.value}</p>
            </div>
          ))}
        </div>

        {result && (
          <>
            <div className="mt-3 pt-3 border-t border-white/[0.06]">
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-[11px] text-slate-400">Confidence Score</p>
                <p className="text-[12px] font-bold text-violet-300 tabular-nums">
                  {result.answer?.confidence ?? v?.confidence ?? 0}%
                </p>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-sky-400"
                  style={{ width: `${result.answer?.confidence ?? v?.confidence ?? 0}%`, transition: "width 0.8s" }}/>
              </div>
            </div>
            <div className="mt-2.5 flex items-center justify-between">
              <p className="text-[10px] text-slate-500">Last Updated</p>
              <p className="text-[10px] text-slate-400">just now</p>
            </div>
          </>
        )}
      </div>

      {/* Related news (compact) */}
      {result?.news?.length ? (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[12px] font-semibold text-slate-300">Sources</p>
            <Link href="/news" className="text-[10px] text-violet-400 hover:text-violet-300 transition">View All →</Link>
          </div>
          <div className="space-y-2">
            {result.news.slice(0, 4).map(n => (
              <Link key={n.id} href={`/news/${n.id}`}
                className="flex items-start gap-2.5 rounded-[10px] p-1.5 transition hover:bg-white/[0.04]">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-700 text-[9px] font-bold text-white">
                  {n.source.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] font-medium text-slate-300 line-clamp-1">{n.source}</p>
                  <p className="text-[9px] text-slate-600 line-clamp-1">{n.headline}</p>
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
          <p className="text-[11px] font-semibold text-white mb-1">Research Engine</p>
          <p className="text-[10px] text-slate-400 leading-5">Search to see AI verdict, evidence, and confidence score</p>
        </div>
      )}
    </aside>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────
function AISearchInner() {
  const [query, setQuery]         = useState("");
  const [input, setInput]         = useState("");
  const [result, setResult]       = useState<SearchResult | null>(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [history, setHistory]     = useState<string[]>([]);
  const [followUp, setFollowUp]   = useState("");
  const [resultTime, setResultTime] = useState(new Date());
  const textareaRef  = useRef<HTMLTextAreaElement>(null);
  const didAutoSearch = useRef(false);
  const searchParams  = useSearchParams();

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
    setHistory(prev => [trimmed, ...prev.filter(h => h !== trimmed)].slice(0, 10));
    try {
      const key = "recent_ai_searches";
      const existing = JSON.parse(localStorage.getItem(key) ?? "[]");
      const entry = { id: `s-${Date.now()}`, title: trimmed, href: `/ai-search?q=${encodeURIComponent(trimmed)}`, timestamp: Date.now() };
      const deduped = existing.filter((e: { title: string }) => e.title !== trimmed);
      localStorage.setItem(key, JSON.stringify([entry, ...deduped].slice(0, 20)));
    } catch { /**/ }
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
  }, [loading, history]);

  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !didAutoSearch.current) {
      didAutoSearch.current = true;
      setInput(q);
      runSearch(q);
    }
  }, [searchParams, runSearch]);

  function handleSubmit(e: React.FormEvent) { e.preventDefault(); runSearch(input); }
  function handleFollowUpSubmit(e: React.FormEvent) { e.preventDefault(); if (followUp.trim()) runSearch(followUp); }
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runSearch(input); }
  }
  function handleSidebarAction(type: string) {
    if (type === "followup") textareaRef.current?.focus();
  }

  return (
    <>
      <div className="mx-auto flex max-w-[1600px] items-start gap-6 px-6 py-6">
      {/* ── Main content column ──────────────────────────────────────────────── */}
      <div className="min-w-0 flex-1 space-y-4 pb-6">
        {/* Search bar */}
        <form onSubmit={handleSubmit}>
          <div className="group flex items-end overflow-hidden rounded-[18px] border border-white/[0.08] bg-[#0d1117] shadow-[0_0_0_1px_rgba(255,255,255,0.04)] transition focus-within:border-violet-500/50 focus-within:shadow-[0_0_0_4px_rgba(139,92,246,0.08)]">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask any market question — hold, switch, compare, or analyse…"
              disabled={loading}
              rows={2}
              className="flex-1 resize-none bg-transparent px-4 py-4 text-[14px] text-white outline-none placeholder:text-slate-600 disabled:opacity-50 leading-relaxed"
            />
            <div className="flex items-center gap-2 p-3">
              {query && (
                <button type="button" onClick={() => { setQuery(""); setResult(null); setInput(""); }}
                  className="flex h-8 w-8 items-center justify-center rounded-[12px] border border-white/[0.08] bg-white/[0.03] text-slate-400 hover:text-slate-200 transition">
                  <RotateCcw className="h-3.5 w-3.5"/>
                </button>
              )}
              <button type="submit" disabled={!input.trim() || loading}
                className="flex h-9 w-9 items-center justify-center rounded-[14px] bg-violet-600 text-white transition hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg">
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
              <span className="text-[11px] text-slate-600">Try:</span>
              {EXAMPLES.slice(0, 4).map(ex => (
                <button key={ex} type="button" onClick={() => runSearch(ex)}
                  className="rounded-full border border-white/[0.07] bg-white/[0.02] px-3 py-1.5 text-[11px] text-slate-500 transition hover:border-violet-500/30 hover:text-violet-300">
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
                <p className="text-[13px] font-medium text-rose-300">Search failed</p>
                <p className="text-[11px] text-rose-400/70">{error}</p>
              </div>
              <button onClick={() => runSearch(query)}
                className="ml-auto rounded-xl bg-rose-500/20 px-3 py-1.5 text-[11px] text-rose-300 hover:bg-rose-500/30 transition">
                Retry
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Content area */}
        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <LoadingState query={query}/>
            </motion.div>
          ) : result ? (
            <motion.div key="result" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
              <SearchResults result={result} onFollowUp={runSearch} resultTime={resultTime}/>
            </motion.div>
          ) : (
            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <EmptyState onSearch={runSearch}/>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Right sidebar ────────────────────────────────────────────────────── */}
      <RightSidebar result={result} onAction={handleSidebarAction}/>
      </div>{/* end flex container */}

      {/* ── Fixed bottom follow-up bar ───────────────────────────────────────── */}
      {(result || loading) && (
        <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-white/[0.06] bg-slate-950/97 backdrop-blur-xl px-6 py-3">
          <div className="mx-auto max-w-[1600px]">
            <form onSubmit={handleFollowUpSubmit}
              className="flex items-center gap-3 rounded-[18px] border border-white/[0.08] bg-[#0d1117] px-4 py-2.5 focus-within:border-violet-500/40 transition">
              <input type="text" value={followUp} onChange={e => setFollowUp(e.target.value)}
                placeholder="Ask a follow-up question…"
                className="flex-1 bg-transparent text-[13px] text-white outline-none placeholder:text-slate-600"/>
              <button type="submit" disabled={!followUp.trim() || loading}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[12px] bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-40 transition">
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
              </button>
            </form>
            {result?.follow_up_questions?.length && (
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                {result.follow_up_questions.slice(0, 4).map(q => (
                  <button key={q} onClick={() => { setFollowUp(q); runSearch(q); }}
                    className="rounded-full border border-white/[0.07] bg-white/[0.02] px-3 py-1 text-[11px] text-slate-500 transition hover:border-violet-500/30 hover:text-violet-300">
                    {q.length > 55 ? q.slice(0, 52) + "…" : q}
                  </button>
                ))}
              </div>
            )}
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
