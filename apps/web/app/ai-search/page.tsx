"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Newspaper, Bot, BarChart2, CheckCircle2, FileText, Scale, Bell, MessageCircle, Landmark, Sparkles } from "lucide-react";
import { AITransparencyPanel } from "@/components/ai/AITransparencyPanel";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import { DecisionIntelligencePanel, IntentBadge, type DecisionIntelligence } from "@/components/ai/DecisionIntelligencePanel";
import { InvestmentThesisCard, OpportunityLifecycleCard, MultiHorizonOutlookCard, ScenarioAnalysis, MonitoringChecklist, PatternIntelligenceCard } from "@/components/intelligence";
import { ShareInsightCard } from "@/components/ShareInsightCard";
import { SmartCTA } from "@/components/SmartCTA";
import { RelatedContent } from "@/components/RelatedContent";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Legend, ReferenceLine,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────────
interface AnswerSection {
  summary: string; what_happened: string; why_it_happened: string;
  immediate_impact: string; medium_term: string; long_term: string;
  risks: string[]; opportunities: string[];
  confidence: number; sentiment: "bullish" | "bearish" | "neutral";
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
  "I hold Manappuram Finance. Should I switch to Natco Pharma?",
  "Should I continue holding BEL or switch to HAL?",
  "I own Tata Motors. Should I buy Mahindra instead?",
  "Should I move from Gold to Silver?",
  "Which is better for 6 months: HAL or BEL?",
  "Should I rotate from Banking to Pharma?",
];

const CATEGORY_COLOR: Record<string, string> = {
  Government:       "bg-violet-500/20 text-violet-300 border-violet-500/30",
  "Government Policy": "bg-violet-500/20 text-violet-300 border-violet-500/30",
  Policy:           "bg-sky-500/20 text-sky-300 border-sky-500/30",
  Corporate:        "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  "Economic Event": "bg-teal-500/20 text-teal-300 border-teal-500/30",
  "Industry Update":"bg-amber-500/20 text-amber-300 border-amber-500/30",
  RBI:              "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
  Macro:            "bg-amber-500/20 text-amber-300 border-amber-500/30",
  Market:           "bg-teal-500/20 text-teal-300 border-teal-500/30",
};

// Source logo color palette
const SOURCE_COLORS: Record<string, string> = {
  "Economic Times": "bg-orange-500",
  "Business Standard": "bg-red-600",
  "Mint": "bg-emerald-600",
  "PIB India": "bg-blue-600",
  "Google News": "bg-sky-500",
  "Moneycontrol": "bg-blue-700",
  "NDTV Profit": "bg-red-500",
  "Livemint": "bg-teal-600",
};
function sourceColor(name: string) {
  return SOURCE_COLORS[name] || "bg-slate-600";
}
function sourceAbbr(name: string) {
  return name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
}

// Impact level label
function impactLevel(score: number): string {
  if (score >= 85) return "Very High";
  if (score >= 70) return "High";
  if (score >= 50) return "Medium";
  return "Low";
}

// ── Micro-components ──────────────────────────────────────────────────────────
function ScoreRing({ score, size = 44 }: { score: number; size?: number }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = score >= 80 ? "#34d399" : score >= 60 ? "#60a5fa" : "#f59e0b";
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="4"/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.8s ease" }}/>
      <text x={size/2} y={size/2+5} textAnchor="middle" fill="white"
        fontSize={size > 44 ? "13" : "11"} fontWeight="700"
        style={{ transform: `rotate(90deg) translate(0px, -${size}px)` }}>
        {score}
      </text>
    </svg>
  );
}

function SentimentBadge({ sentiment }: { sentiment: string }) {
  const cfg = sentiment === "bullish"
    ? { label: "Bullish", icon: "↑", cls: "text-emerald-300 bg-emerald-500/10 border-emerald-500/25" }
    : sentiment === "bearish"
    ? { label: "Bearish", icon: "↓", cls: "text-rose-300 bg-rose-500/10 border-rose-500/25" }
    : { label: "Neutral", icon: "→", cls: "text-amber-300 bg-amber-500/10 border-amber-500/25" };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${cfg.cls}`}>
      {cfg.icon} {cfg.label}
    </span>
  );
}

function MiniSparkline({ data, positive, width = 80, height = 32 }: { data: number[]; positive: boolean; width?: number; height?: number }) {
  if (!data?.length) return <div style={{ width, height }} className="rounded bg-white/[0.04]"/>;
  const min = Math.min(...data), max = Math.max(...data), range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / Math.max(data.length - 1, 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(" ");
  const color = positive ? "#34d399" : "#f43f5e";
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-[20px] border border-white/[0.07] bg-white/[0.03] backdrop-blur-sm ${className}`}>
      {children}
    </div>
  );
}

// Refresh icon SVG
function RefreshIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10"/>
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
    </svg>
  );
}

// ── Loading state ──────────────────────────────────────────────────────────────
function LoadingState({ query }: { query: string }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep(s => Math.min(s + 1, LOADING_STEPS.length - 1)), 1200);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="space-y-6 pb-10">
      <Card className="p-6">
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
      </Card>
      {[1, 2, 3].map(i => (
        <div key={i} className="h-32 animate-pulse rounded-[20px] bg-white/[0.03]"/>
      ))}
    </div>
  );
}

// ── Empty state ────────────────────────────────────────────────────────────────
function EmptyState({ onSearch }: { onSearch: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center py-16 text-center space-y-8">
      <div className="relative">
        <div className="h-24 w-24 rounded-full bg-gradient-to-br from-violet-500/20 to-sky-500/10 flex items-center justify-center border border-violet-500/20">
          <Sparkles className="h-10 w-10 text-violet-400" />
        </div>
        <div className="absolute -inset-4 rounded-full bg-violet-500/5 blur-xl"/>
      </div>
      <div>
        <h2 className="text-xl font-semibold text-white mb-2">AI Decision Intelligence Engine</h2>
        <p className="text-sm text-slate-400 max-w-md">Ask any investment decision question — hold, switch, compare, or analyse. Get explainable AI reasoning, trade-offs, and evidence. Never direct advice.</p>
      </div>
      <div className="w-full max-w-lg space-y-3">
        <p className="text-[10px] uppercase tracking-widest text-slate-500">Try these searches</p>
        <div className="grid grid-cols-1 gap-2">
          {EXAMPLES.map(q => (
            <button key={q} onClick={() => onSearch(q)}
              className="group flex items-center gap-3 rounded-[16px] border border-white/[0.06] bg-white/[0.02] px-4 py-3 text-left text-[13px] text-slate-300 transition hover:border-violet-500/30 hover:bg-violet-500/[0.04] hover:text-white">
              <Search className="h-4 w-4 text-violet-400 shrink-0" />
              {q}
              <span className="ml-auto text-slate-600 group-hover:text-violet-400 transition">→</span>
            </button>
          ))}
        </div>
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

// ── Search results ─────────────────────────────────────────────────────────────
function SearchResults({ result, onFollowUp }: { result: SearchResult; onFollowUp: (q: string) => void }) {
  const companiesRef = useRef<HTMLDivElement>(null);
  const { answer, insights, companies, sectors, related_events, news, policies,
          investment_verdict, market_chart, similar_events, timeline, follow_up_questions,
          decision_intelligence } = result;

  const isDecision = !!decision_intelligence?.intent && decision_intelligence.intent !== "general";

  const chartData = (market_chart?.labels || []).map((label, i) => {
    const row: Record<string, any> = { label };
    (market_chart?.series || []).forEach(s => { row[s.name] = s.data[i] ?? 0; });
    return row;
  });

  // Latest values for index panel (last data point)
  const indexValues = (market_chart?.series || []).map(s => ({
    name: s.name, color: s.color,
    pct: s.data[s.data.length - 1] ?? 0,
  }));

  function scrollCompanies(dir: number) {
    if (companiesRef.current) companiesRef.current.scrollLeft += dir * 220;
  }

  return (
    <div className="space-y-5 pb-32">

      {/* ── Decision Intelligence Panel (decision-type queries only) ──────── */}
      {isDecision && decision_intelligence && (
        <DecisionIntelligencePanel
          di={decision_intelligence}
          query={result.query}
          onRefine={onFollowUp}
        />
      )}

      {/* ── AI Answer ──────────────────────────────────────────────────────── */}
      <Card className="overflow-hidden">
        {/* Header */}
        <div className="border-b border-white/[0.06] px-5 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-500/20 text-violet-400"><Sparkles className="h-4 w-4" /></div>
            <div className="flex items-center gap-2">
              <p className="text-[14px] font-semibold text-white">AI Answer</p>
              {isDecision && decision_intelligence && (
                <IntentBadge intent={decision_intelligence.intent} />
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                const url = `${window.location.origin}/ai-search?q=${encodeURIComponent(result.query)}`;
                if (navigator.share) {
                  navigator.share({ title: "InvestGrids AI Analysis", text: result.query, url }).catch(() => {});
                } else {
                  navigator.clipboard.writeText(url).catch(() => {});
                }
              }}
              className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/[0.08] transition">
              <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>
              Share
            </button>
            <button
              onClick={() => {
                try {
                  const SAVED_KEY = "ig_saved_searches";
                  const existing = JSON.parse(localStorage.getItem(SAVED_KEY) ?? "[]");
                  const entry = { id: `sv-${Date.now()}`, query: result.query, summary: answer?.summary?.slice(0, 120), timestamp: Date.now() };
                  const deduped = existing.filter((e: { query: string }) => e.query !== result.query);
                  localStorage.setItem(SAVED_KEY, JSON.stringify([entry, ...deduped].slice(0, 50)));
                } catch { /* localStorage unavailable */ }
              }}
              className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] text-slate-300 hover:bg-white/[0.08] transition">
              <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
              Save
            </button>
          </div>
        </div>

        {/* Summary */}
        <div className="px-5 pt-4 pb-2">
          <p className="text-[14px] leading-7 text-slate-200">{answer.summary}</p>
        </div>

        {/* 4-column insight cards */}
        {insights?.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 px-5 pb-5">
            {insights.slice(0, 4).map((ins, i) => (
              <div key={i} className="rounded-[14px] border border-white/[0.06] bg-white/[0.02] p-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <p className="text-[12px] font-semibold text-white leading-tight">{ins.title}</p>
                </div>
                <p className="text-[11px] leading-[1.55] text-slate-400">{ins.summary}</p>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* ── AI Transparency ──────────────────────────────────────────────── */}
      <AITransparencyPanel
        confidence={result.answer?.confidence ?? 70}
        reasoning={result.answer?.summary ?? "AI-generated analysis based on your query and current market data."}
        events={(result.related_events ?? []).slice(0, 5).map((e) => ({ title: e.title, href: `/events/${e.id}` }))}
        companies={(result.companies ?? []).slice(0, 5).map((c) => ({ name: c.name, symbol: c.symbol, href: `/stocks/${c.symbol}` }))}
      />
      <AIDisclaimer />

      {/* ── Key Impact on Companies ──────────────────────────────────────── */}
      {companies?.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-[15px] font-semibold text-white">Key Impact on Companies</p>
            <Link href="/stocks" className="text-[12px] text-violet-400 hover:text-violet-300 transition">
              View All Companies →
            </Link>
          </div>

          <div className="relative">
            {/* Left arrow */}
            <button onClick={() => scrollCompanies(-1)}
              className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-3 z-10 flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-slate-900/90 text-slate-300 shadow-lg hover:bg-slate-800 transition">
              ‹
            </button>

            <div ref={companiesRef} className="flex gap-3 overflow-x-auto pb-1 scroll-smooth" style={{ scrollbarWidth: "none" }}>
              {companies.map((co, idx) => {
                const level = impactLevel(co.impact_score);
                const levelColor = co.impact_score >= 85 ? "text-emerald-400" : co.impact_score >= 70 ? "text-sky-400" : "text-amber-400";
                // Symbol avatar colors
                const avatarColors = ["bg-red-600", "bg-blue-700", "bg-red-700", "bg-teal-600", "bg-orange-600", "bg-violet-600", "bg-emerald-700", "bg-indigo-600"];
                const av = avatarColors[idx % avatarColors.length];
                return (
                  <Link key={co.symbol} href={`/companies/${co.symbol}`}
                    className="shrink-0 w-[196px] rounded-[18px] border border-white/[0.07] bg-white/[0.03] p-4 transition hover:border-white/[0.14] hover:bg-white/[0.06] flex flex-col gap-2">
                    {/* Company identity */}
                    <div className="flex items-start gap-2.5">
                      <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${av} text-[11px] font-bold text-white`}>
                        {co.symbol.slice(0, 2)}
                      </div>
                      <div className="min-w-0">
                        <p className="text-[13px] font-bold text-white leading-tight">{co.symbol}</p>
                        <p className="text-[10px] text-slate-500 truncate">{co.name}</p>
                      </div>
                    </div>

                    {/* Price + change */}
                    <div className="flex items-baseline gap-2">
                      {co.price && co.price !== "—" ? (
                        <>
                          <p className="text-[14px] font-bold text-white">₹{co.price}</p>
                          <p className={`text-[12px] font-semibold ${co.positive ? "text-emerald-400" : "text-rose-400"}`}>{co.change}</p>
                        </>
                      ) : (
                        <p className="text-[11px] text-slate-500 italic">Price unavailable</p>
                      )}
                    </div>

                    {/* Sparkline */}
                    <div className="h-8">
                      <MiniSparkline data={co.chart} positive={co.positive} width={160} height={32}/>
                    </div>

                    {/* Impact score + level */}
                    <div className="flex items-center justify-between mt-1">
                      <div>
                        <p className="text-[9px] uppercase tracking-widest text-slate-500 mb-0.5">Impact Score</p>
                        <p className={`text-[11px] font-semibold ${levelColor}`}>{level}</p>
                      </div>
                      <ScoreRing score={co.impact_score} size={40}/>
                    </div>
                  </Link>
                );
              })}
            </div>

            {/* Right arrow */}
            <button onClick={() => scrollCompanies(1)}
              className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-3 z-10 flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-slate-900/90 text-slate-300 shadow-lg hover:bg-slate-800 transition">
              ›
            </button>
          </div>
        </div>
      )}

      {/* ── Market Impact + Sector Impact side by side ────────────────────── */}
      <div className="grid grid-cols-[1fr_auto] gap-0 overflow-hidden rounded-[20px] border border-white/[0.07] bg-white/[0.03]">
        {/* Chart section */}
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[14px] font-semibold text-white">Market Impact Overview</p>
            <span className="rounded-lg px-2 py-0.5 text-[10px] font-medium bg-violet-500/20 text-violet-300">1D</span>
          </div>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -22 }}>
                <XAxis dataKey="label" tick={{ fontSize: 9, fill: "#64748b" }} tickLine={false} axisLine={false} interval="preserveStartEnd"/>
                <YAxis tick={{ fontSize: 9, fill: "#64748b" }} tickLine={false} axisLine={false} tickFormatter={v => `${v > 0 ? "+" : ""}${v}%`}/>
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.07)" strokeDasharray="3 3"/>
                <Tooltip content={<ChartTooltip/>}/>
                <Legend iconType="circle" iconSize={6} wrapperStyle={{ fontSize: 10, paddingTop: 6 }}/>
                {(market_chart?.series || []).map(s => (
                  <Line key={s.name} type="monotone" dataKey={s.name} stroke={s.color}
                    strokeWidth={1.5} dot={false} activeDot={{ r: 3, fill: s.color }}/>
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[160px] items-center justify-center text-[12px] text-slate-500">No chart data available</div>
          )}
        </div>

        {/* Live index values panel */}
        <div className="w-[200px] shrink-0 border-l border-white/[0.06] p-4 flex flex-col justify-center gap-4">
          {indexValues.map(idx => (
            <div key={idx.name}>
              <div className="flex items-center gap-1.5 mb-0.5">
                <span className="h-2 w-2 rounded-full shrink-0" style={{ background: idx.color }}/>
                <p className="text-[10px] text-slate-500">{idx.name}</p>
              </div>
              <p className={`text-[13px] font-bold ${idx.pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {idx.pct > 0 ? "+" : ""}{idx.pct.toFixed(2)}%
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Sector Impact ─────────────────────────────────────────────────── */}
      {sectors?.length > 0 && (
        <Card className="p-4">
          <p className="text-[14px] font-semibold text-white mb-3">Sector Impact</p>
          <div className="space-y-2.5">
            {sectors.map(s => {
              const barColor = s.score >= 70
                ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                : s.score >= 50
                ? "bg-gradient-to-r from-amber-500 to-orange-400"
                : "bg-gradient-to-r from-rose-500 to-rose-400";
              const scoreColor = s.score >= 70 ? "text-emerald-400" : s.score >= 50 ? "text-amber-400" : "text-rose-400";
              const label = s.score >= 70 ? "" : s.score >= 50 ? "Medium" : "Low";
              return (
                <div key={s.name} className="flex items-center gap-3">
                  <span className="w-32 shrink-0 text-[12px] text-slate-300 truncate">{s.name}</span>
                  <div className="flex-1 h-2 overflow-hidden rounded-full bg-white/[0.06] relative">
                    <div className={`h-full rounded-full ${barColor} flex items-center`}
                      style={{ width: `${Math.min(100, s.score)}%`, transition: "width 0.8s ease" }}>
                      {label && (
                        <span className="text-[8px] font-semibold text-white ml-1.5 whitespace-nowrap">{label}</span>
                      )}
                    </div>
                  </div>
                  <span className={`w-8 text-right text-[12px] font-bold shrink-0 ${scoreColor}`}>{s.score}</span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* ── Timeline ──────────────────────────────────────────────────────── */}
      {timeline?.length > 0 && (
        <Card className="p-4">
          <p className="text-[14px] font-semibold text-white mb-4">Development Timeline</p>
          <div className="space-y-0">
            {timeline.map((t, i) => (
              <div key={i} className="flex gap-4 pb-5">
                <div className="flex flex-col items-center">
                  <div className="h-2.5 w-2.5 rounded-full bg-violet-500 shrink-0 mt-1"/>
                  {i < timeline.length - 1 && <div className="w-px flex-1 bg-white/[0.06] mt-1"/>}
                </div>
                <div className="pb-1">
                  <p className="text-[10px] text-violet-400 font-semibold">{t.date}</p>
                  <p className="text-[13px] font-medium text-white">{t.title}</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">{t.description}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Related Events ────────────────────────────────────────────────── */}
      {related_events?.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[14px] font-semibold text-white">Related Events</p>
            <Link href="/events" className="text-[11px] text-violet-400 hover:text-violet-300">View All →</Link>
          </div>
          <div className="space-y-2">
            {related_events.slice(0, 5).map(ev => {
              const catCls = CATEGORY_COLOR[ev.category] || CATEGORY_COLOR.Market;
              const dateParts = (ev.date || "").split(" ");
              return (
                <Link key={ev.id} href={`/events/${ev.id}`}
                  className="flex items-center gap-3 rounded-[14px] border border-white/[0.05] bg-white/[0.02] px-3 py-2.5 transition hover:border-white/10 hover:bg-white/[0.04]">
                  {dateParts.length >= 2 && (
                    <div className="shrink-0 text-center w-8">
                      <p className="text-[9px] text-violet-400 font-semibold uppercase">{dateParts[0]}</p>
                      <p className="text-[14px] font-bold text-white leading-tight">{dateParts[1]}</p>
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] font-medium text-slate-200 line-clamp-1">{ev.title}</p>
                    <span className={`mt-0.5 inline-block rounded border px-1.5 py-0.5 text-[9px] font-medium ${catCls}`}>{ev.category}</span>
                  </div>
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-[11px] font-bold text-violet-300">
                    {Math.round(ev.impact_score)}
                  </div>
                </Link>
              );
            })}
          </div>
        </Card>
      )}

      {/* ── Historical Similar Events ──────────────────────────────────────── */}
      {similar_events?.length > 0 && (
        <div>
          <p className="text-[14px] font-semibold text-white mb-3">Historical Similar Events</p>
          <div className="grid grid-cols-2 gap-3">
            {similar_events.map((se, i) => (
              <Card key={i} className="p-4">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <p className="text-[13px] font-semibold text-white line-clamp-2">{se.title}</p>
                  <span className="shrink-0 rounded-full bg-violet-500/20 px-2 py-0.5 text-[10px] font-bold text-violet-300">
                    {Math.round(se.similarity * 100)}% match
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 mb-2">{se.date}</p>
                <p className="text-[12px] text-slate-300 mb-3">{se.outcome}</p>
                <div className="flex gap-3">
                  <div>
                    <p className="text-[9px] uppercase tracking-widest text-emerald-500 mb-1">Winners</p>
                    <div className="flex flex-wrap gap-1">
                      {(se.winners||[]).map(w => (
                        <span key={w} className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-400">{w}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-[9px] uppercase tracking-widest text-rose-500 mb-1">Losers</p>
                    <div className="flex flex-wrap gap-1">
                      {(se.losers||[]).map(l => (
                        <span key={l} className="rounded bg-rose-500/10 px-1.5 py-0.5 text-[10px] text-rose-400">{l}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* ── Network Graph ─────────────────────────────────────────────────── */}
      {(result.graph?.nodes?.length ?? 0) > 0 && (
        <Card className="p-4">
          <p className="text-[14px] font-semibold text-white mb-3">Impact Network</p>
          <NetworkGraph nodes={result.graph.nodes} edges={result.graph.edges}/>
        </Card>
      )}

      {/* ── Investment Thesis (hidden for decision queries — shown in DecisionPanel) */}
      {!isDecision && (investment_verdict?.rating || answer?.why_it_happened) && (
        <InvestmentThesisCard
          entityType="search"
          entityId={result.query.slice(0, 120)}
          entityTitle={result.query}
          entityDescription={answer.summary}
          thesis={investment_verdict?.rating ? `${investment_verdict.rating} — ${answer.summary}` : answer.summary}
          whyItMatters={answer.why_it_happened}
          businessImpact={answer.immediate_impact}
          keyDrivers={(investment_verdict?.catalysts ?? []).slice(0, 4)}
          riskFactors={(investment_verdict?.risks ?? []).slice(0, 3)}
          confidence={investment_verdict?.confidence}
          timeHorizon={investment_verdict?.horizon ? `${investment_verdict.horizon} horizon` : undefined}
        />
      )}

      {/* ── Scenario Analysis ─────────────────────────────────────────────── */}
      {answer?.summary && (
        <ScenarioAnalysis
          entityType="search"
          entityId={result.query.slice(0, 120)}
          entityTitle={result.query}
          entityDescription={answer.summary}
        />
      )}

      {/* ── Monitoring Checklist ──────────────────────────────────────────── */}
      {answer?.summary && (
        <MonitoringChecklist
          entityType="search"
          entityId={result.query.slice(0, 120)}
          entityTitle={result.query}
          entityDescription={answer.summary}
        />
      )}

      {/* ── Pattern Intelligence ──────────────────────────────────────────── */}
      {answer?.summary && (
        <PatternIntelligenceCard
          entityType="search"
          entityId={result.query.slice(0, 120)}
          entityTitle={result.query}
          entityDescription={answer.summary}
        />
      )}

      {/* ── Related Intelligence ──────────────────────────────────────────── */}
      {answer?.summary && (
        <RelatedContent
          entityType="search"
          entityId={result.query.slice(0, 120)}
          title={result.query}
        />
      )}

      {/* ── Share + Smart CTAs ───────────────────────────────────────────── */}
      {answer?.summary && (
        <div className="flex flex-wrap gap-2">
          <ShareInsightCard
            entityType="search"
            entityId={encodeURIComponent(result.query.slice(0, 80))}
            title={result.query}
            summary={answer.summary}
          />
          <SmartCTA variant="view-event" href="/events" />
          <SmartCTA variant="explore-opportunity" href="/radar" />
        </div>
      )}

      {/* ── Investment Verdict ────────────────────────────────────────────── */}
      {investment_verdict?.rating && (
        <Card className="p-4 !border-violet-500/20 !bg-gradient-to-br from-violet-500/[0.06] to-sky-500/[0.03]">
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="text-[10px] uppercase tracking-widest text-violet-400 mb-1">AI Investment Verdict</p>
              <p className="text-xl font-bold text-white">{investment_verdict.rating}</p>
              <div className="flex items-center gap-2 mt-1">
                <SentimentBadge sentiment={investment_verdict.direction}/>
                <span className="text-[11px] text-slate-400">{investment_verdict.horizon} horizon</span>
              </div>
            </div>
            <div className="text-center">
              <ScoreRing score={investment_verdict.opportunity_score} size={56}/>
              <p className="text-[9px] text-slate-500 mt-1">Opportunity</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div>
              <p className="text-[10px] text-slate-500 mb-1.5">Top Picks</p>
              <div className="flex flex-wrap gap-1">
                {(investment_verdict.top_picks||[]).map(p => (
                  <Link key={p} href={`/companies/${p}`}
                    className="rounded-lg bg-violet-500/20 px-2 py-0.5 text-[11px] font-semibold text-violet-300 hover:bg-violet-500/30 transition">{p}</Link>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[10px] text-rose-400 mb-1.5">Key Risks</p>
              <ul className="space-y-0.5">
                {(investment_verdict.risks||[]).slice(0, 3).map((r, i) => (
                  <li key={i} className="text-[11px] text-slate-400 flex gap-1"><span className="text-rose-500">•</span>{r}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-[10px] text-emerald-400 mb-1.5">Catalysts</p>
              <ul className="space-y-0.5">
                {(investment_verdict.catalysts||[]).slice(0, 3).map((c, i) => (
                  <li key={i} className="text-[11px] text-slate-400 flex gap-1"><span className="text-emerald-500">•</span>{c}</li>
                ))}
              </ul>
            </div>
          </div>
          <div className="flex items-center justify-between text-[11px] border-t border-white/[0.05] pt-3">
            <span className="text-slate-500">Confidence</span>
            <div className="flex-1 mx-3 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
              <div className="h-full bg-gradient-to-r from-violet-500 to-sky-400 rounded-full"
                style={{ width: `${investment_verdict.confidence}%`, transition: "width 0.8s" }}/>
            </div>
            <span className="text-violet-300 font-semibold">{investment_verdict.confidence}%</span>
          </div>
        </Card>
      )}

      {/* ── Opportunity Lifecycle ─────────────────────────────────────────── */}
      {(investment_verdict?.rating || answer?.sentiment) && (
        <OpportunityLifecycleCard
          stage={(() => {
            const sentiment = answer?.sentiment;
            const confidence = investment_verdict?.confidence ?? 0;
            const oppScore = investment_verdict?.opportunity_score ?? 50;
            if (sentiment === "bullish" && oppScore > 75) return "strong-momentum" as const;
            if (sentiment === "bullish" && oppScore > 55) return "developing" as const;
            if (sentiment === "bearish" && confidence > 70) return "mature" as const;
            return "emerging" as const;
          })()}
          description={answer?.medium_term || answer?.summary}
          whyAssigned={`AI verdict: ${investment_verdict?.rating ?? answer?.sentiment ?? "Neutral"} with ${investment_verdict?.confidence ?? 0}% confidence. Opportunity score: ${investment_verdict?.opportunity_score ?? "N/A"}/100.`}
          historicalComparison={`Queries with similar sentiment patterns have historically been associated with 10–25% sector-level moves over the ${investment_verdict?.horizon ?? "medium-term"} horizon.`}
          confidence={investment_verdict?.confidence}
          expectedEvolution={answer?.long_term}
          risks={(investment_verdict?.risks ?? []).slice(0, 3)}
        />
      )}

      {/* ── Multi-Horizon Investment Outlook ──────────────────────────────── */}
      <MultiHorizonOutlookCard
        fetchContext={{
          type:    "query",
          title:   result.query,
          context: answer.summary,
          sectors: (sectors ?? []).slice(0, 3).map(s => s.name),
          context_id: `query:${result.query}`,
        }}
      />

      {/* ── Related News ──────────────────────────────────────────────────── */}
      {news?.length > 0 && (
        <div>
          <p className="text-[14px] font-semibold text-white mb-3">Related News</p>
          <div className="grid grid-cols-2 gap-3">
            {news.slice(0, 4).map(n => (
              <Link key={n.id} href={`/news/${n.id}`}
                className="group rounded-[18px] border border-white/[0.06] bg-white/[0.02] p-3.5 transition hover:border-white/10 hover:bg-white/[0.04]">
                <div className="flex items-center gap-2 mb-2">
                  <span className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[9px] text-slate-400">{n.source}</span>
                  <span className="text-[9px] text-slate-600">{n.published_at}</span>
                </div>
                <p className="text-[12px] font-medium text-slate-200 leading-5 line-clamp-2 group-hover:text-white transition">{n.headline}</p>
                {n.summary && <p className="mt-1 text-[10px] text-slate-500 line-clamp-2">{n.summary}</p>}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* ── AI Conclusion ─────────────────────────────────────────────────── */}
      <Card className="p-5 !border-sky-500/20 !bg-gradient-to-br from-sky-500/[0.05] via-transparent to-violet-500/[0.03]">
        <div className="flex items-center gap-2.5 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-sky-500/20 text-sky-400">
            <Sparkles className="h-4 w-4" />
          </div>
          <p className="text-[14px] font-semibold text-white">AI Conclusion</p>
          <span className="ml-auto rounded-full border border-sky-500/25 bg-sky-500/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-sky-400">Summary</span>
        </div>
        <div className="space-y-3.5">
          {/* Current Assessment */}
          <div className="flex gap-4">
            <span className="w-32 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-slate-500 pt-0.5">Current Assessment</span>
            <p className="text-[13px] leading-[1.65] text-slate-200">{answer.summary}</p>
          </div>

          {/* Investment Horizon */}
          {investment_verdict?.horizon && (
            <div className="flex items-center gap-4">
              <span className="w-32 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Suitable Horizon</span>
              <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-0.5 text-[12px] font-semibold text-violet-300">
                {investment_verdict.horizon}
              </span>
            </div>
          )}

          {/* Key Things to Monitor */}
          {((investment_verdict?.catalysts?.length ?? 0) > 0 || (investment_verdict?.risks?.length ?? 0) > 0) && (
            <div className="flex gap-4">
              <span className="w-32 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-slate-500 pt-0.5">Key Monitors</span>
              <div className="flex flex-wrap gap-1.5">
                {[
                  ...(investment_verdict?.catalysts ?? []).slice(0, 2),
                  ...(investment_verdict?.risks ?? []).slice(0, 2),
                ].map((item, i) => (
                  <span key={i} className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-0.5 text-[11px] text-slate-300">{item}</span>
                ))}
              </div>
            </div>
          )}

          {/* Confidence bar */}
          <div className="flex items-center gap-4">
            <span className="w-32 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Confidence</span>
            <div className="flex flex-1 items-center gap-2">
              <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-400"
                  style={{ width: `${investment_verdict?.confidence ?? answer.confidence ?? 70}%`, transition: "width 0.8s ease" }}/>
              </div>
              <span className="text-[12px] font-bold text-sky-300 shrink-0">{investment_verdict?.confidence ?? answer.confidence ?? 70}%</span>
            </div>
          </div>
        </div>

        {/* AI Transparency footer */}
        <div className="mt-4 flex items-start gap-2 rounded-xl border border-amber-500/15 bg-amber-500/[0.05] p-3">
          <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01"/>
          </svg>
          <p className="text-[11px] leading-[1.6] text-amber-200/60">
            AI Transparency: This conclusion is generated by AI using market events, news, and financial data. It is for informational purposes only and does not constitute investment advice. Always consult a qualified financial advisor before making investment decisions.
          </p>
        </div>
      </Card>
    </div>
  );
}

// ── Network graph (SVG) ────────────────────────────────────────────────────────
function NetworkGraph({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const NODE_COLORS: Record<string, { bg: string; border: string }> = {
    query:   { bg: "#4f46e5", border: "#6366f1" },
    sector:  { bg: "#0f766e", border: "#14b8a6" },
    company: { bg: "#1d4ed8", border: "#3b82f6" },
  };
  const W = 860, H = 300;
  return (
    <div className="overflow-x-auto">
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="min-w-[500px]">
        {edges.map(e => {
          const src = nodes.find(n => n.id === e.source);
          const tgt = nodes.find(n => n.id === e.target);
          if (!src || !tgt) return null;
          const sx = (src.x / 900) * W + 40, sy = src.y + 16;
          const tx = (tgt.x / 900) * W + 40, ty = tgt.y + 16;
          return (
            <g key={e.id}>
              <line x1={sx} y1={sy} x2={tx} y2={ty} stroke="rgba(255,255,255,0.08)" strokeWidth="1.5" strokeDasharray="4 4"/>
              <text x={(sx+tx)/2} y={(sy+ty)/2 - 4} textAnchor="middle" fontSize="8" fill="#475569">{e.label}</text>
            </g>
          );
        })}
        {nodes.map(n => {
          const c = NODE_COLORS[n.type] || NODE_COLORS.company;
          const x = (n.x / 900) * W + 40, y = n.y;
          const label = n.label.length > 16 ? n.label.slice(0, 15)+"…" : n.label;
          const w = Math.max(80, label.length * 7.5 + 24);
          return (
            <g key={n.id}>
              <rect x={x-w/2} y={y} width={w} height={32} rx="10"
                fill={c.bg} stroke={c.border} strokeWidth="1" opacity="0.9"/>
              <text x={x} y={y+20} textAnchor="middle" fontSize="11" fontWeight="600" fill="#fff">{label}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Right sidebar ──────────────────────────────────────────────────────────────
function RightSidebar({ result }: { result: SearchResult | null }) {
  const [showAllSources, setShowAllSources] = useState(false);

  const AI_TOOLS: { icon: ReactNode; title: string; sub: string; href?: string }[] = [
    { icon: <FileText className="h-4 w-4" />,       title: "Generate Detailed Report", sub: "Get a comprehensive AI report" },
    { icon: <Scale className="h-4 w-4" />,          title: "Compare Companies",        sub: "Compare key companies side by side", href: "/compare" },
    { icon: <Bell className="h-4 w-4" />,           title: "Track This Theme",          sub: "Get real-time updates and alerts" },
    { icon: <MessageCircle className="h-4 w-4" />,  title: "Ask AI Assistant",          sub: "Chat with AI about this topic" },
  ];

  const allSources = result?.news || [];
  const visibleSources = showAllSources ? allSources : allSources.slice(0, 4);
  const hiddenCount = allSources.length - 4;

  return (
    <aside className="hidden xl:block sticky top-[92px] self-start max-h-[calc(100vh-92px)] overflow-y-auto space-y-4 pr-1">
      {/* Sources */}
      {result && allSources.length > 0 && (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[13px] font-semibold text-white">Sources</p>
            {allSources.length > 4 && (
              <button onClick={() => setShowAllSources(v => !v)} className="text-[11px] text-violet-400 hover:text-violet-300 transition">
                {showAllSources ? "Show less" : "View All →"}
              </button>
            )}
          </div>
          <div className="space-y-2">
            {visibleSources.map(n => (
              <Link key={n.id} href={`/news/${n.id}`}
                className="flex items-start gap-2.5 rounded-[12px] p-2 transition hover:bg-white/[0.04]">
                {/* Source logo circle */}
                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${sourceColor(n.source)} text-[10px] font-bold text-white`}>
                  {sourceAbbr(n.source)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-semibold text-slate-200 leading-tight">{n.source}</p>
                  <p className="text-[10px] text-slate-500 line-clamp-1 mt-0.5">{n.headline}</p>
                  <p className="text-[9px] text-slate-600 mt-0.5">{n.published_at}</p>
                </div>
              </Link>
            ))}
          </div>
          {hiddenCount > 0 && (
            <button onClick={() => setShowAllSources(v => !v)}
              className="mt-2 w-full flex items-center justify-center gap-1.5 text-[11px] text-violet-400 hover:text-violet-300 transition py-1">
              <span>{showAllSources ? `Hide` : `Show ${hiddenCount} more sources`}</span>
              <svg className={`h-3 w-3 transition-transform ${showAllSources ? "rotate-180" : ""}`}
                viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>
          )}
        </div>
      )}

      {/* Related Events */}
      {result && result.related_events?.length > 0 && (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[13px] font-semibold text-white">Related Events</p>
            <Link href="/events" className="text-[11px] text-violet-400 hover:text-violet-300 transition">View All →</Link>
          </div>
          <div className="space-y-2">
            {result.related_events.slice(0, 3).map(ev => {
              const dateParts = (ev.date || "").split(" ");
              return (
                <Link key={ev.id} href={`/events/${ev.id}`}
                  className="flex items-start gap-2.5 rounded-[12px] p-2 transition hover:bg-white/[0.04]">
                  {dateParts.length >= 2 && (
                    <div className="shrink-0 text-center w-8">
                      <p className="text-[9px] text-violet-400 font-semibold uppercase leading-tight">{dateParts[0]}</p>
                      <p className="text-[14px] font-bold text-white leading-tight">{dateParts[1]}</p>
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-medium text-slate-300 line-clamp-2 leading-tight">{ev.title}</p>
                    <span className={`mt-1 inline-block rounded border px-1.5 py-0.5 text-[9px] font-medium ${CATEGORY_COLOR[ev.category] || CATEGORY_COLOR.Market}`}>
                      {ev.category}
                    </span>
                  </div>
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-[10px] font-bold text-violet-300">
                    {Math.round(ev.impact_score)}
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Related Policies */}
      {result && result.policies?.length > 0 && (
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[13px] font-semibold text-white">Related Policies</p>
            <Link href="/events" className="text-[11px] text-violet-400 hover:text-violet-300 transition">View All →</Link>
          </div>
          <div className="space-y-2.5">
            {result.policies.slice(0, 3).map(p => (
              <div key={p.id} className="flex items-start gap-2.5 rounded-[12px] p-2">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sky-500/10 text-sky-400"><Landmark className="h-4 w-4" /></div>
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-medium text-slate-300 line-clamp-2 leading-tight">{p.title}</p>
                  <div className="mt-1 flex items-center gap-1.5">
                    <span className="rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-medium text-emerald-400 border border-emerald-500/20">
                      {p.status}
                    </span>
                  </div>
                </div>
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-sky-500/20 text-[10px] font-bold text-sky-300">
                  {p.impact_score}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Tools */}
      <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-4">
        <p className="text-[13px] font-semibold text-white mb-3">AI Tools</p>
        <div className="space-y-1">
          {AI_TOOLS.map(t => (
            <Link key={t.title} href={(t as any).href ?? "#" as any}
              className="flex items-center gap-3 rounded-[14px] p-2.5 transition hover:bg-white/[0.04]">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-white/[0.06] text-slate-400">{t.icon}</div>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-medium text-slate-300">{t.title}</p>
                <p className="text-[10px] text-slate-500">{t.sub}</p>
              </div>
              <svg className="h-4 w-4 text-slate-600 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </Link>
          ))}
        </div>
      </div>

      {/* Empty state hint */}
      {!result && (
        <div className="rounded-[20px] border border-violet-500/20 bg-gradient-to-br from-violet-500/[0.06] to-sky-500/[0.02] p-4 text-center">
          <Search className="h-6 w-6 text-violet-400 mb-2" />
          <p className="text-[12px] font-semibold text-white mb-1">Research Engine</p>
          <p className="text-[11px] text-slate-400 leading-5">Search to see real-time sources, events, and AI analysis</p>
        </div>
      )}
    </aside>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────
export default function AISearchPage() {
  const [query, setQuery]     = useState("");
  const [input, setInput]     = useState("");
  const [result, setResult]   = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [followUp, setFollowUp] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const didAutoSearch = useRef(false);
  const searchParams = useSearchParams();

  // Ctrl+K focus
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
    // Persist to localStorage for "Continue Research" across sessions
    try {
      const SEARCH_KEY = "recent_ai_searches";
      const existing = JSON.parse(localStorage.getItem(SEARCH_KEY) ?? "[]");
      const entry = { id: `s-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, title: trimmed, href: `/ai-search?q=${encodeURIComponent(trimmed)}`, type: "search", timestamp: Date.now() };
      const deduped = existing.filter((e: { title: string }) => e.title !== trimmed);
      localStorage.setItem(SEARCH_KEY, JSON.stringify([entry, ...deduped].slice(0, 20)));
    } catch { /* localStorage not available */ }
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
    } catch (e: any) {
      setError(e.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [loading, history]);

  // Auto-trigger search from ?q= URL param (e.g. navigated from FloatingAISearch)
  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !didAutoSearch.current) {
      didAutoSearch.current = true;
      setInput(q);
      runSearch(q);
    }
  }, [searchParams, runSearch]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    runSearch(input);
  }

  function handleFollowUpSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (followUp.trim()) runSearch(followUp);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      runSearch(input);
    }
  }

  function refreshExamples() {
    const randomExample = EXAMPLES[Math.floor(Math.random() * EXAMPLES.length)];
    setInput(randomExample);
  }

  return (
    <>
      {/* ── Main content column ─────────────────────────────────────────────── */}
      <main className="min-w-0 space-y-4 pb-10">
        {/* Page header */}
        <div>
          <div className="flex items-center gap-2.5 mb-0.5">
            <h1 className="text-2xl font-bold tracking-tight text-white">AI Decision Intelligence</h1>
            <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-[10px] font-semibold text-violet-300 border border-violet-500/30">Beta</span>
          </div>
          <p className="text-sm text-slate-400">Ask any market question or decision — hold, switch, compare, buy, sell. Get explainable AI reasoning, not direct advice.</p>
        </div>

        {/* Search box — textarea for multi-line */}
        <form onSubmit={handleSubmit}>
          <div className="group flex items-end overflow-hidden rounded-[18px] border border-white/[0.08] bg-[#0d1117] shadow-[0_0_0_1px_rgba(255,255,255,0.04)] transition focus-within:border-violet-500/50 focus-within:shadow-[0_0_0_4px_rgba(139,92,246,0.08)]">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="What is the impact of the Indian government's ₹1.2 Lakh Cr railway infrastructure plan on key companies and the economy?"
              disabled={loading}
              rows={2}
              className="flex-1 resize-none bg-transparent px-4 py-4 text-[14px] text-white outline-none placeholder:text-slate-600 disabled:opacity-50 leading-relaxed"
            />
            <div className="flex items-center gap-2 p-3">
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
              <span className="text-[11px] text-slate-500">Try these examples</span>
              {EXAMPLES.map(ex => (
                <button key={ex} type="button" onClick={() => runSearch(ex)}
                  className="rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-[12px] text-slate-400 transition hover:border-violet-500/30 hover:text-violet-300">
                  {ex}
                </button>
              ))}
              <button type="button" onClick={refreshExamples}
                className="flex h-7 w-7 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.03] text-slate-500 hover:text-slate-300 transition">
                <RefreshIcon className="h-3.5 w-3.5"/>
              </button>
            </div>
          )}
        </form>

        {/* Intent indicator — shown after a result with a detected intent */}
        {result?.decision_intelligence?.intent && result.decision_intelligence.intent !== "general" && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] text-slate-500">Detected:</span>
            <IntentBadge intent={result.decision_intelligence.intent} />
            {result.decision_intelligence.detected_holding && (
              <span className="text-[11px] text-slate-400">
                {result.decision_intelligence.detected_holding}
                {result.decision_intelligence.detected_target && (
                  <> → <span className="text-violet-300">{result.decision_intelligence.detected_target}</span></>
                )}
              </span>
            )}
          </div>
        )}

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
              <button onClick={() => runSearch(query)} className="ml-auto rounded-xl bg-rose-500/20 px-3 py-1.5 text-[11px] text-rose-300 hover:bg-rose-500/30 transition">
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
            <motion.div key="result" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
              <SearchResults result={result} onFollowUp={runSearch}/>
            </motion.div>
          ) : (
            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <EmptyState onSearch={runSearch}/>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* ── Right sidebar column ─────────────────────────────────────────────── */}
      <RightSidebar result={result}/>

      {/* ── Fixed bottom follow-up bar ───────────────────────────────────────── */}
      {(result || loading) && (
        <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-white/[0.06] bg-slate-950/95 px-6 py-3">
          <div className="mx-auto max-w-[1600px]">
            <form onSubmit={handleFollowUpSubmit}
              className="flex items-center gap-3 rounded-[18px] border border-white/[0.08] bg-[#0d1117] px-4 py-2.5">
              <input type="text" value={followUp} onChange={e => setFollowUp(e.target.value)}
                placeholder="Ask a follow-up question…"
                className="flex-1 bg-transparent text-[13px] text-white outline-none placeholder:text-slate-600"/>
              <button type="submit" disabled={!followUp.trim() || loading}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[12px] bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-40 transition">
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
              </button>
            </form>

            {/* Follow-up suggestion chips */}
            {result?.follow_up_questions?.length && (
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                {result.follow_up_questions.slice(0, 4).map(q => (
                  <button key={q} onClick={() => { setFollowUp(q); runSearch(q); }}
                    className="rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] text-slate-400 transition hover:border-violet-500/30 hover:text-violet-300">
                    {q}
                  </button>
                ))}
                <button onClick={() => {}}
                  className="flex h-6 w-6 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.03] text-slate-500 hover:text-slate-300 transition">
                  <RefreshIcon className="h-3 w-3"/>
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
