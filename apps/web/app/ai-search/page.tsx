"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Newspaper, Bot, BarChart2, CheckCircle2, Sparkles, Bookmark, Plus, Download, Share2, Copy, TrendingUp, TrendingDown, Minus, RotateCcw } from "lucide-react";
import { AITransparencyPanel } from "@/components/ai/AITransparencyPanel";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import { DecisionIntelligencePanel, type DecisionIntelligence } from "@/components/ai/DecisionIntelligencePanel";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────────
interface AnswerSection {
  summary: string; what_happened: string; why_it_happened: string;
  immediate_impact: string; medium_term: string; long_term: string;
  risks: string[]; opportunities: string[];
  confidence: number; confidence_level?: string;
  sentiment: "bullish" | "bearish" | "neutral";
  sources_count: number;
}
interface Insight      { icon: string; title: string; summary: string; }
interface Company      { symbol: string; name: string; price: string; change: string; positive: boolean; impact_type: string; impact_score: number; confidence: number; reason: string; chart: number[]; }
interface Sector       { name: string; score: number; confidence: number; outlook: string; positive: boolean; }
interface RelatedEvent { id: string; title: string; date: string; impact_score: number; confidence: number; category: string; }
interface NewsItem     { id: string; headline: string; summary: string; source: string; published_at: string; impact_score: number; }
interface Policy       { id: number; title: string; ministry: string; status: string; impact_score: number; }
interface Timeline     { date: string; title: string; description: string; }
interface SimilarEvent { title: string; date: string; outcome: string; winners: string[]; losers: string[]; similarity: number; }
interface InvestmentVerdict { rating: string; direction: string; confidence: number; horizon: string; top_picks: string[]; risks: string[]; catalysts: string[]; opportunity_score: number; }
interface ChartSeries  { name: string; data: number[]; color: string; }
interface MarketChart  { labels: string[]; series: ChartSeries[]; }
interface GraphNode    { id: string; label: string; type: string; x: number; y: number; }
interface GraphEdge    { id: string; source: string; target: string; label: string; }

interface SearchResult {
  query: string; answer: AnswerSection; insights: Insight[];
  companies: Company[]; sectors: Sector[]; related_events: RelatedEvent[];
  news: NewsItem[]; policies: Policy[]; timeline: Timeline[];
  similar_events: SimilarEvent[]; follow_up_questions: string[];
  investment_verdict: InvestmentVerdict; market_chart: MarketChart;
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  citations: string[];
  decision_intelligence: DecisionIntelligence | null;
  confidence_data?: unknown;
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

/** Star rating component */
function Stars({ score }: { score: number }) {
  const filled = score >= 85 ? 5 : score >= 70 ? 4 : score >= 50 ? 3 : score >= 35 ? 2 : 1;
  return (
    <div className="flex gap-0.5">
      {[1,2,3,4,5].map(i => (
        <svg key={i} className={`h-3 w-3 ${i <= filled ? "text-amber-400" : "text-slate-700"}`}
          viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
        </svg>
      ))}
    </div>
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

// ── Chart tooltip ──────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/90 px-3 py-2 text-xs backdrop-blur-sm">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }} className="font-semibold">
          {p.name}: {p.value > 0 ? "+" : ""}{p.value?.toFixed(2)}%
        </p>
      ))}
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

  const { answer, companies, sectors, related_events, news,
          investment_verdict, market_chart, similar_events,
          follow_up_questions, decision_intelligence } = result;

  const isDecision = !!decision_intelligence?.intent && decision_intelligence.intent !== "general";

  // Relative time
  const minAgo = Math.max(1, Math.round((Date.now() - resultTime.getTime()) / 60000));

  // Verdict direction label
  const dir = answer?.sentiment ?? investment_verdict?.direction ?? "neutral";
  const isBull = dir === "bullish";
  const isBear = dir === "bearish";
  const verdictColor = isBull ? "text-emerald-400" : isBear ? "text-rose-400" : "text-amber-400";
  const risk = riskLevel(investment_verdict?.confidence ?? answer?.confidence ?? 70);

  // Chart data
  const chartData = (market_chart?.labels || []).map((label, i) => {
    const row: Record<string, any> = { label };
    (market_chart?.series || []).forEach(s => { row[s.name] = s.data[i] ?? 0; });
    return row;
  });

  // Similar event for historical section
  const simEv = similar_events?.[0];

  // Continue Your Research CTAs
  const topCo  = companies?.[0];
  const topEv  = related_events?.[0];
  const topFU  = follow_up_questions?.[0];
  const topSec = sectors?.[0];

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

      {/* ── Row 1: AI Decision + Key Evidence ────────────────────────────────── */}
      <div className="grid grid-cols-[1fr_auto] gap-4 min-h-0">

        {/* AI Decision */}
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center gap-2 mb-4">
            <span className="rounded-full bg-violet-500/20 border border-violet-500/30 px-2.5 py-0.5 text-[10px] font-bold text-violet-300 uppercase tracking-wider">AI Decision</span>
            <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-0.5 text-[10px] font-medium text-slate-400">Bottom Line Up Front</span>
          </div>

          <div className="flex items-start gap-4 mb-4">
            <DirectionIcon direction={dir} size={64}/>
            <div>
              <p className={`text-[26px] font-extrabold leading-tight ${verdictColor}`}>
                {investment_verdict?.rating || (isBull ? "Moderately Bullish" : isBear ? "Moderately Bearish" : "Neutral")}
              </p>
              <p className="text-[12px] text-slate-400 mt-1 leading-relaxed max-w-sm">
                {answer?.summary?.length > 180 ? answer.summary.slice(0, 177) + "…" : answer?.summary}
              </p>
            </div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-4 gap-2">
            {[
              { label: "Confidence", value: `${answer?.confidence ?? investment_verdict?.confidence ?? 0}%`, color: "text-emerald-400" },
              { label: "Time Horizon", value: investment_verdict?.horizon || "6–18 Months", color: "text-slate-200" },
              { label: "Risk Level", value: risk.label, color: risk.color.split(" ")[0] },
              { label: "Suitable For", value: suitableFor(investment_verdict?.horizon || ""), color: "text-slate-200" },
            ].map(s => (
              <div key={s.label} className="rounded-[12px] border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-0.5">{s.label}</p>
                <p className={`text-[12px] font-semibold ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Key Evidence */}
        <div className="w-72 rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[13px] font-semibold text-white">Why? (Key Evidence)</p>
          </div>
          <div className="space-y-2.5">
            {((answer?.opportunities?.length ? answer.opportunities : []).slice(0, 5)).map((op, i) => (
              <div key={i} className="flex items-start gap-2">
                <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/20">
                  <svg className="h-2.5 w-2.5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                </div>
                <div className="min-w-0">
                  <p className="text-[12px] font-medium text-white leading-tight">{op.split(":")[0] || op.slice(0, 40)}</p>
                  {op.includes(":") && <p className="text-[10px] text-slate-500 mt-0.5 line-clamp-1">{op.split(":").slice(1).join(":").trim()}</p>}
                </div>
              </div>
            ))}
            {/* Fallback if no opportunities */}
            {!answer?.opportunities?.length && (answer?.risks || []).slice(0, 3).map((r, i) => (
              <div key={i} className="flex items-start gap-2">
                <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-slate-700/50">
                  <svg className="h-2.5 w-2.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                </div>
                <p className="text-[12px] text-slate-300 leading-tight line-clamp-2">{r}</p>
              </div>
            ))}
          </div>
          <Link href="/events" className="mt-4 flex items-center gap-1 text-[11px] font-medium text-violet-400 hover:text-violet-300 transition">
            View All Evidence <span>→</span>
          </Link>
        </div>
      </div>

      {/* ── Row 2: Companies That Matter ─────────────────────────────────────── */}
      {companies?.length > 0 && (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center justify-between mb-4">
            <p className="text-[15px] font-semibold text-white">Companies That Matter</p>
            <Link href="/companies" className="text-[12px] text-violet-400 hover:text-violet-300 transition">
              View All Companies →
            </Link>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {companies.slice(0, 6).map((co, idx) => {
              const avatarColors = ["bg-red-700", "bg-blue-700", "bg-orange-700", "bg-teal-700", "bg-violet-700", "bg-indigo-700"];
              const av = avatarColors[idx % avatarColors.length];
              return (
                <div key={co.symbol} className="rounded-[16px] border border-white/[0.07] bg-white/[0.02] p-4">
                  {/* Header */}
                  <div className="flex items-center gap-2.5 mb-3">
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

                  {/* Why it matters */}
                  <div className="mb-3">
                    <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1">Why it matters</p>
                    <p className="text-[11px] text-slate-300 leading-relaxed line-clamp-2">{co.reason || "Directly impacted by this event"}</p>
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

      {/* ── Row 3: Sector Impact + Related Events Timeline ───────────────────── */}
      <div className="grid grid-cols-[1fr_1.4fr] gap-4">

        {/* Sector Impact */}
        {sectors?.length > 0 && (
          <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
            <p className="text-[14px] font-semibold text-white mb-4">Sector Impact</p>
            <div className="w-full">
              <div className="grid grid-cols-3 gap-x-2 mb-2">
                {["Sector", "Impact", "Outlook"].map(h => (
                  <p key={h} className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">{h}</p>
                ))}
              </div>
              <div className="space-y-2.5">
                {sectors.slice(0, 5).map(s => {
                  const outlookColor = s.score >= 70 ? "text-emerald-400" : s.score >= 50 ? "text-amber-400" : "text-rose-400";
                  const outlookLabel = s.outlook || (s.score >= 85 ? "Very Positive" : s.score >= 70 ? "Positive" : s.score >= 50 ? "Neutral to Positive" : s.score >= 35 ? "Neutral" : "Neutral to Negative");
                  return (
                    <div key={s.name} className="grid grid-cols-3 gap-x-2 items-center">
                      <p className="text-[12px] font-medium text-slate-200 truncate">{s.name}</p>
                      <Stars score={s.score}/>
                      <p className={`text-[11px] font-medium ${outlookColor}`}>{outlookLabel}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Related Events Timeline */}
        {related_events?.length > 0 && (
          <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-[13px]">⏰</span>
                <p className="text-[14px] font-semibold text-white">Related Events Timeline</p>
              </div>
              <Link href="/events" className="text-[11px] text-violet-400 hover:text-violet-300 transition">View All Events →</Link>
            </div>
            <div className="relative overflow-x-auto">
              {/* Horizontal timeline */}
              <div className="flex items-start gap-0 min-w-max">
                {related_events.slice(0, 5).map((ev, i) => {
                  const status = inferStatus(ev.date);
                  const sc = EVENT_STATUS_COLORS[status];
                  const isLast = i === related_events.slice(0, 5).length - 1;
                  return (
                    <div key={ev.id} className="flex items-start">
                      <div className="flex flex-col items-center w-32">
                        {/* Dot + line */}
                        <div className="flex items-center w-full">
                          {i > 0 && <div className="flex-1 h-px bg-white/[0.08]"/>}
                          <div className={`h-3 w-3 shrink-0 rounded-full border-2 border-[#0d1117] ${sc.dot}`}/>
                          {!isLast && <div className="flex-1 h-px bg-white/[0.08]"/>}
                        </div>
                        {/* Content below dot */}
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

      {/* ── Row 4: Historical + Risks + Monitor + Follow-ups ─────────────────── */}
      <div className="grid grid-cols-4 gap-4">

        {/* Historical Similar Events */}
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[13px] font-semibold text-white">Historical Similar Events</p>
          </div>
          {simEv ? (
            <>
              <p className="text-[11px] font-medium text-violet-300 mb-1">{simEv.title}</p>
              <p className="text-[9px] text-slate-500 mb-3">
                {simEv.date} · <span className="text-violet-400">{Math.round(simEv.similarity * 100)}% match</span>
              </p>
              {/* Mini chart placeholder */}
              {chartData.length > 0 && (
                <div className="mb-3 h-[60px]">
                  <ResponsiveContainer width="100%" height={60}>
                    <LineChart data={chartData.slice(0, 12)} margin={{ top: 2, right: 2, bottom: 0, left: -30 }}>
                      <YAxis tick={false} axisLine={false} tickLine={false}/>
                      {(market_chart?.series || []).slice(0, 2).map(s => (
                        <Line key={s.name} type="monotone" dataKey={s.name} stroke={s.color}
                          strokeWidth={1.5} dot={false}/>
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              {/* Winners */}
              {simEv.winners?.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {simEv.winners.slice(0, 4).map(w => (
                    <span key={w} className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-400">{w}</span>
                  ))}
                </div>
              )}
              <p className="mt-2 text-[10px] text-slate-500 leading-relaxed line-clamp-2">{simEv.outcome}</p>
            </>
          ) : (
            <p className="text-[12px] text-slate-500 text-center py-4">No similar historical events found</p>
          )}
        </div>

        {/* Risks & Counter Arguments */}
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[13px] font-semibold text-white">Risks & Counter Arguments</p>
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
            {(investment_verdict?.catalysts?.length
              ? investment_verdict.catalysts
              : answer?.opportunities?.slice(0, 5) || []
            ).slice(0, 5).map((c, i) => (
              <div key={i} className="flex items-start gap-2">
                <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-500/20">
                  <svg className="h-2.5 w-2.5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                </div>
                <p className="text-[11px] text-slate-300 leading-relaxed line-clamp-2">{c}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Follow-up Questions */}
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[13px] font-semibold text-white">Follow-up Questions</p>
          </div>
          <div className="space-y-2">
            {(follow_up_questions || []).slice(0, 4).map((q, i) => (
              <button key={i} onClick={() => onFollowUp(q)}
                className="group flex w-full items-start gap-2 text-left transition hover:text-violet-300">
                <span className="mt-0.5 text-slate-600 group-hover:text-violet-400 transition text-xs">›</span>
                <p className="text-[11px] text-slate-400 group-hover:text-violet-300 transition leading-relaxed line-clamp-2">{q}</p>
              </button>
            ))}
          </div>
          {(follow_up_questions?.length ?? 0) > 4 && (
            <button onClick={() => onFollowUp(follow_up_questions![4])}
              className="mt-3 text-[11px] text-violet-400 hover:text-violet-300 transition">
              View More →
            </button>
          )}
        </div>
      </div>

      {/* ── Continue Your Research ────────────────────────────────────────────── */}
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
        <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-3">Continue Your Research</p>
        <div className="grid grid-cols-4 gap-3">
          {[
            topCo ? {
              icon: "🏢",
              label: `Open ${topCo.name} Analysis`,
              sub: "Deep dive into company",
              href: `/companies/${topCo.symbol}`,
            } : null,
            topEv ? {
              icon: "📅",
              label: `Read ${topEv.title.length > 28 ? topEv.title.slice(0, 25) + "…" : topEv.title}`,
              sub: "Understand the event",
              href: `/events/${topEv.id}`,
            } : null,
            topSec ? {
              icon: "🔍",
              label: `Explore ${topSec.name} Sector`,
              sub: "Sector & theme analysis",
              href: `/sectors`,
            } : null,
            topFU ? {
              icon: "💬",
              label: "Ask Another Question",
              sub: "Continue AI research",
              action: () => onFollowUp(topFU),
            } : null,
          ].filter(Boolean).map((cta, i) => (
            cta!.action ? (
              <button key={i} onClick={cta!.action}
                className="group flex items-center gap-3 rounded-[14px] border border-white/[0.07] bg-white/[0.02] px-4 py-3 text-left transition hover:border-violet-500/30 hover:bg-violet-500/[0.04]">
                <span className="text-base">{cta!.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-medium text-white line-clamp-1">{cta!.label}</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">{cta!.sub}</p>
                </div>
                <span className="text-slate-600 group-hover:text-violet-400 transition text-sm">→</span>
              </button>
            ) : (
              <Link key={i} href={(cta as any).href as any}
                className="group flex items-center gap-3 rounded-[14px] border border-white/[0.07] bg-white/[0.02] px-4 py-3 transition hover:border-violet-500/30 hover:bg-violet-500/[0.04]">
                <span className="text-base">{cta!.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-medium text-white line-clamp-1">{cta!.label}</p>
                  <p className="text-[10px] text-slate-500 mt-0.5">{cta!.sub}</p>
                </div>
                <span className="text-slate-600 group-hover:text-violet-400 transition text-sm">→</span>
              </Link>
            )
          ))}
        </div>
      </div>

      {/* ── Market Performance Chart (collapsed by default) ───────────────────── */}
      {chartData.length > 0 && (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[14px] font-semibold text-white">Market Impact Overview</p>
            <span className="rounded-lg px-2 py-0.5 text-[10px] font-medium bg-violet-500/20 text-violet-300 border border-violet-500/30">1D</span>
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <XAxis dataKey="label" tick={{ fontSize: 9, fill: "#64748b" }} tickLine={false} axisLine={false} interval="preserveStartEnd"/>
              <YAxis tick={{ fontSize: 9, fill: "#64748b" }} tickLine={false} axisLine={false} tickFormatter={v => `${v > 0 ? "+" : ""}${v}%`}/>
              <ReferenceLine y={0} stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3"/>
              <Tooltip content={<ChartTooltip/>}/>
              {(market_chart?.series || []).map(s => (
                <Line key={s.name} type="monotone" dataKey={s.name} stroke={s.color}
                  strokeWidth={1.5} dot={false} activeDot={{ r: 3, fill: s.color }}/>
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── AI Transparency ───────────────────────────────────────────────────── */}
      <AITransparencyPanel
        confidence={result.answer?.confidence ?? 70}
        reasoning={result.answer?.summary ?? "AI-generated analysis based on your query and current market data."}
        events={(result.related_events ?? []).slice(0, 5).map((e) => ({ title: e.title, href: `/events/${e.id}` }))}
        companies={(result.companies ?? []).slice(0, 5).map((c) => ({ name: c.name, symbol: c.symbol, href: `/companies/${c.symbol}` }))}
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
  const score = v?.opportunity_score ?? v?.confidence ?? result?.answer?.confidence ?? 0;
  const dir   = v?.direction ?? result?.answer?.sentiment ?? "neutral";
  const isBull = dir === "bullish";
  const isBear = dir === "bearish";
  const verdictLabel = isBull ? "Bullish" : isBear ? "Bearish" : "Neutral";
  const verdictColor = isBull ? "text-emerald-400" : isBear ? "text-rose-400" : "text-amber-400";
  const riskInfo = result ? riskLevel(v?.confidence ?? result.answer?.confidence ?? 70) : { label: "—", color: "text-slate-400" };

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
    <aside className="hidden xl:block sticky top-[92px] self-start max-h-[calc(100vh-92px)] overflow-y-auto space-y-3 pr-1" style={{ scrollbarWidth: "none" }}>

      {/* Investment Verdict */}
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-5">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-[13px]">🎯</span>
          <p className="text-[13px] font-semibold text-white">Investment Verdict</p>
        </div>

        {result ? (
          <>
            {/* Top row: Overall View + Risk */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <p className="text-[9px] uppercase tracking-wider text-slate-500 mb-1">Overall View</p>
                <p className={`text-[15px] font-bold ${verdictColor}`}>{verdictLabel}</p>
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
                <p className="text-[12px] font-semibold text-white">{suitableFor(v?.horizon || "")}</p>
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

      {/* Sources & Confidence */}
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-4">
        <p className="text-[12px] font-semibold text-slate-300 mb-3">Sources & Confidence</p>
        <div className="space-y-2.5">
          {[
            { label: "Data Sources",       value: result?.news?.length ?? 0 },
            { label: "Events Analyzed",    value: result?.related_events?.length ?? 0 },
            { label: "Companies Analyzed", value: result?.companies?.length ?? 0 },
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
              <span className="text-rose-400 text-lg">⚠</span>
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
