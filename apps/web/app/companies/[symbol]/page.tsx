"use client";

import { use, useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import { TrackPageVisit } from "@/components/TrackPageVisit";
import { InvestmentThesis, ScenarioAnalysis, MonitoringChecklist, PatternIntelligenceCard, OpportunityLifecycleCard, IntelligenceBlock } from "@/components/intelligence";
import { useIntelligence } from "@/hooks/useIntelligence";
import { ShareInsightCard } from "@/components/ShareInsightCard";
import { SmartCTA } from "@/components/SmartCTA";
import { NextSteps } from "@/components/NextSteps";
import { RelatedContent } from "@/components/RelatedContent";
import {
  Star, Check, Sparkles, TrendingUp, IndianRupee, Target, Zap,
  BarChart2, ClipboardList, CheckCircle2, Rocket, Globe2, FlaskConical,
  TrendingDown, Landmark, Briefcase, HardHat, Leaf, Shield, Bot,
  FileText, Mic, FileStack, Bell, Share2, Copy, Clock,
} from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis,
} from "recharts";

const RFlow  = dynamic(() => import("reactflow").then(m => m.default),    { ssr: false });
const RFBg   = dynamic(() => import("reactflow").then(m => m.Background), { ssr: false });
const RFCtrl = dynamic(() => import("reactflow").then(m => m.Controls),   { ssr: false });

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────
interface StockEvent   { title: string; date: string }
interface GovBreak     { label: string; pct: number; color: string }
interface StockDetail  {
  symbol: string; name: string; price: string; prev_close: string;
  open: string; day_high: string; day_low: string; change: string;
  change_abs: string; pct_change: number; week52_high: string; week52_low: string;
  volume: string; avg_volume: string; market_cap: string; industry: string;
  sector: string; description: string; pe: string; forward_pe: string;
  pb: string; eps: string; roe: string; roa: string; beta: string;
  dividend_yield: string; dividend_rate: string; gross_margins: string;
  operating_margins: string; net_margins: string; debt_to_equity: string;
  current_ratio: string; free_cashflow: string; recommendation: string;
  target_mean: string; target_high: string; target_low: string;
  analyst_count: number; held_institutions: string; held_insiders: string;
  quarterly_revenue: { label: string; value: number }[];
  quarterly_net_income: { label: string; value: number }[];
  enterprise_value: string; roce: string;
  annual_financials: { year: string; revenue: number; net_income: number }[];
  dna_scores: Record<string, number>; gov_score: number; gov_level: string;
  gov_breakdown: GovBreak[]; gov_support_areas: string[];
  buy_count: number; hold_count: number; sell_count: number;
  events: StockEvent[]; news: any[]; peers: string[]; chart_data: any[];
}

interface PageProps { params: Promise<{ symbol: string }> }

// ── Design tokens ─────────────────────────────────────────────────────────────
const CARD = "rounded-[28px] border border-white/10 bg-white/[0.04] shadow-[0_20px_60px_rgba(0,0,0,.35)] transition-all duration-300 hover:border-sky-400/20";
const PERIODS = ["1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "Max"];
const DONUT_C = ["#6366f1", "#38bdf8", "#22c55e", "#f59e0b", "#f43f5e"];

const ANALYST_ICONS: React.ReactNode[] = [
  <BarChart2 className="h-3 w-3" />,
  <TrendingUp className="h-3 w-3" />,
  <TrendingDown className="h-3 w-3" />,
  <Landmark className="h-3 w-3" />,
  <Briefcase className="h-3 w-3" />,
];

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.35, delay: i * 0.06, ease: "easeOut" } }),
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const n2 = (v?: string | number) => parseFloat(String(v || "0").replace(/[^0-9.-]/g, "")) || 0;
const scoreColor = (s: number) =>
  s >= 75 ? "#22c55e" : s >= 50 ? "#38bdf8" : s >= 30 ? "#f59e0b" : "#f43f5e";

function impactColor(score: number) {
  if (score >= 75) return { text: "text-rose-400",    bg: "bg-rose-500/15",   ring: "#f43f5e", label: "Very High" };
  if (score >= 55) return { text: "text-amber-400",   bg: "bg-amber-500/15",  ring: "#f59e0b", label: "High"      };
  if (score >= 35) return { text: "text-sky-400",     bg: "bg-sky-500/15",    ring: "#38bdf8", label: "Medium"    };
  return                  { text: "text-slate-400",   bg: "bg-slate-700/20",  ring: "#64748b", label: "Low"       };
}

function metricColor(label: string, value: string) {
  const n = n2(value);
  if (label === "PE Ratio (TTM)") return n < 15 ? "text-emerald-400" : n < 30 ? "text-white" : n < 50 ? "text-amber-400" : "text-rose-400";
  if (label === "PB Ratio")       return n < 1   ? "text-emerald-400" : n < 3  ? "text-white" : "text-amber-400";
  if (label === "ROE" || label === "ROCE") return n > 20 ? "text-emerald-400" : n > 10 ? "text-white" : "text-amber-400";
  if (label === "Beta")           return n < 0.8 ? "text-emerald-400" : n < 1.3 ? "text-white" : "text-rose-400";
  if (label === "D/E Ratio")      return n < 0.3 ? "text-emerald-400" : n < 1   ? "text-white" : "text-rose-400";
  return "text-white";
}

function deriveSegments(sector: string, symbol: string) {
  const base: Record<string, { name: string; pct: number; growth: string; margin: string }[]> = {
    Defence:   [{ name: "Aircraft Manufacturing", pct: 45, growth: "+18%", margin: "22%" }, { name: "Maintenance & Overhaul", pct: 30, growth: "+12%", margin: "18%" }, { name: "Aero Engines", pct: 15, growth: "+25%", margin: "28%" }, { name: "Exports", pct: 10, growth: "+32%", margin: "15%" }],
    Banking:   [{ name: "Retail Banking", pct: 42, growth: "+14%", margin: "35%" }, { name: "Corporate Banking", pct: 28, growth: "+8%", margin: "28%" }, { name: "Treasury", pct: 18, growth: "+5%", margin: "40%" }, { name: "Insurance & Wealth", pct: 12, growth: "+20%", margin: "22%" }],
    IT:        [{ name: "Digital Services", pct: 38, growth: "+22%", margin: "28%" }, { name: "Consulting", pct: 28, growth: "+15%", margin: "24%" }, { name: "Cloud & Infra", pct: 22, growth: "+30%", margin: "32%" }, { name: "BPO", pct: 12, growth: "+8%", margin: "18%" }],
    Energy:    [{ name: "Refining", pct: 40, growth: "+10%", margin: "8%" }, { name: "Retail", pct: 30, growth: "+15%", margin: "12%" }, { name: "E&P", pct: 20, growth: "+5%", margin: "30%" }, { name: "Renewable", pct: 10, growth: "+45%", margin: "20%" }],
    Pharma:    [{ name: "Formulations", pct: 50, growth: "+16%", margin: "32%" }, { name: "API", pct: 25, growth: "+10%", margin: "22%" }, { name: "Biologics", pct: 15, growth: "+28%", margin: "38%" }, { name: "Consumer Health", pct: 10, growth: "+20%", margin: "18%" }],
  };
  return base[sector] ?? [{ name: "Core Business", pct: 60, growth: "+12%", margin: "20%" }, { name: "Adjacent", pct: 25, growth: "+8%", margin: "15%" }, { name: "New Ventures", pct: 15, growth: "+25%", margin: "10%" }];
}

function deriveShareholding(gov_score: number) {
  const promoter = gov_score > 70 ? 74 : gov_score > 40 ? 51 : 35;
  const fii      = Math.round((100 - promoter) * 0.3);
  const dii      = Math.round((100 - promoter) * 0.25);
  const retail   = 100 - promoter - fii - dii;
  return [
    { name: "Promoters",  value: promoter, color: "#6366f1" },
    { name: "FIIs",       value: fii,      color: "#38bdf8" },
    { name: "DIIs",       value: dii,      color: "#22c55e" },
    { name: "Retail",     value: retail,   color: "#f59e0b" },
  ];
}

function deriveGeography(sector: string) {
  if (sector === "IT")      return [{ r: "India", v: 15 }, { r: "North America", v: 55 }, { r: "Europe", v: 20 }, { r: "Rest of World", v: 10 }];
  if (sector === "Pharma")  return [{ r: "India", v: 35 }, { r: "North America", v: 42 }, { r: "Europe", v: 14 }, { r: "Emerging Markets", v: 9 }];
  if (sector === "Defence") return [{ r: "India (Defence)", v: 82 }, { r: "Export Orders", v: 14 }, { r: "MRO Services", v: 4 }];
  return [{ r: "India", v: 72 }, { r: "Asia Pacific", v: 15 }, { r: "Middle East", v: 8 }, { r: "Others", v: 5 }];
}

function deriveNetworkNodes(s: StockDetail) {
  const sym = s.symbol;
  const nodes = [
    { id: "company", data: { label: sym },  position: { x: 300, y: 200 }, style: { background: "#6366f1", color: "#fff", border: "none", borderRadius: 12, fontWeight: "bold", padding: "8px 14px" } },
    { id: "gov",     data: { label: "Government" }, position: { x: 100, y: 80  }, style: { background: "#22c55e30", color: "#22c55e", border: "1px solid #22c55e40", borderRadius: 10, padding: "6px 10px", fontSize: 11 } },
    { id: "policy",  data: { label: "Policy" },     position: { x: 500, y: 80  }, style: { background: "#38bdf830", color: "#38bdf8", border: "1px solid #38bdf840", borderRadius: 10, padding: "6px 10px", fontSize: 11 } },
    { id: "sup1",    data: { label: "Suppliers" },  position: { x: 80,  y: 320 }, style: { background: "#f59e0b20", color: "#f59e0b", border: "1px solid #f59e0b30", borderRadius: 10, padding: "6px 10px", fontSize: 11 } },
    { id: "cust",    data: { label: "Customers" },  position: { x: 520, y: 320 }, style: { background: "#22c55e20", color: "#22c55e", border: "1px solid #22c55e30", borderRadius: 10, padding: "6px 10px", fontSize: 11 } },
    ...s.peers.slice(0, 2).map((p, i) => ({
      id: `peer${i}`, data: { label: p },
      position: { x: 160 + i * 280, y: 360 },
      style: { background: "#f43f5e20", color: "#f43f5e", border: "1px solid #f43f5e30", borderRadius: 10, padding: "6px 10px", fontSize: 11 },
    })),
  ];
  const edges = [
    { id: "e1", source: "gov",    target: "company", style: { stroke: "#22c55e50" }, label: "Policy" },
    { id: "e2", source: "policy", target: "company", style: { stroke: "#38bdf850" }, label: "Budget" },
    { id: "e3", source: "company",target: "cust",    style: { stroke: "#6366f150" }, label: "Revenue" },
    { id: "e4", source: "sup1",   target: "company", style: { stroke: "#f59e0b50" }, label: "Supply" },
    ...s.peers.slice(0, 2).map((_, i) => ({ id: `ep${i}`, source: "company", target: `peer${i}`, style: { stroke: "#f43f5e40" }, label: "Competes" })),
  ];
  return { nodes, edges };
}

// ── Micro components ──────────────────────────────────────────────────────────
function SectionCard({ title, action, children, className = "", noPad = false }: {
  title?: string; action?: React.ReactNode; children: React.ReactNode; className?: string; noPad?: boolean;
}) {
  return (
    <motion.div variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.1 }}
      className={`${CARD} ${noPad ? "" : "p-6"} ${className}`}>
      {(title || action) && (
        <div className={`flex items-center justify-between ${noPad ? "px-6 pt-6 pb-0" : "mb-5"}`}>
          {title && <h2 className="text-[15px] font-bold text-white">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </motion.div>
  );
}

function Pill({ children, color = "slate" }: { children: React.ReactNode; color?: string }) {
  const cls: Record<string, string> = {
    slate: "border-white/10 bg-white/[0.05] text-slate-300",
    green: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    sky:   "border-sky-500/30 bg-sky-500/10 text-sky-300",
    amber: "border-amber-500/30 bg-amber-500/10 text-amber-300",
    violet:"border-violet-500/30 bg-violet-500/10 text-violet-300",
    rose:  "border-rose-500/30 bg-rose-500/10 text-rose-300",
  };
  return <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium ${cls[color] ?? cls.slate}`}>{children}</span>;
}

function ScoreCircle({ score, size = 52 }: { score: number; size?: number }) {
  const col = scoreColor(score);
  const r = (size - 6) / 2, circ = 2 * Math.PI * r, dash = (Math.abs(score) / 100) * circ;
  return (
    <div className="relative flex items-center justify-center shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} stroke="rgba(255,255,255,0.06)" strokeWidth={4} fill="none"/>
        <circle cx={size/2} cy={size/2} r={r} stroke={col} strokeWidth={4} fill="none"
          strokeLinecap="round" strokeDasharray={`${dash} ${circ}`}
          style={{ filter: `drop-shadow(0 0 4px ${col}80)` }}/>
      </svg>
      <span className="absolute text-[11px] font-black leading-none" style={{ color: col }}>{score > 0 ? score : score}</span>
    </div>
  );
}

function KvRow({ label, value, colored = false }: { label: string; value: string; colored?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 py-2 border-b border-white/[0.04] last:border-0">
      <span className="text-[12px] text-slate-500 shrink-0">{label}</span>
      <span className={`text-[13px] font-semibold text-right ${colored ? metricColor(label, value) : "text-white"}`}>{value || "—"}</span>
    </div>
  );
}

function MiniBar({ label, value, max = 100, color }: { label: string; value: number; max?: number; color: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div>
      <div className="mb-1 flex justify-between text-[11px]">
        <span className="text-slate-400">{label}</span>
        <span className="font-bold text-white">{value}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }}/>
      </div>
    </div>
  );
}

// ── Section 1: Company Hero ───────────────────────────────────────────────────
function CompanyHero({ stock, symbol, watchlisted, setWatchlisted }: {
  stock: StockDetail; symbol: string; watchlisted: boolean; setWatchlisted: (v: boolean) => void;
}) {
  const isPos = stock.pct_change >= 0;
  const sign  = isPos ? "+" : "";
  const ai_score = stock.dna_scores
    ? Math.round(Object.values(stock.dna_scores).reduce((a, b) => a + b, 0) / Math.max(Object.values(stock.dna_scores).length, 1))
    : 72;

  return (
    <motion.div variants={fadeUp} initial="hidden" animate="show"
      className={`${CARD} p-6`}>
      {/* Breadcrumb */}
      <div className="mb-4 flex items-center gap-2 text-[11px] text-slate-600">
        <Link href="/companies" className="hover:text-slate-400 transition">Companies</Link>
        <span>›</span>
        <span className="text-slate-400">{stock.name}</span>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-6">
        {/* Left: identity + price */}
        <div>
          {/* Company avatar + name */}
          <div className="flex items-center gap-4 mb-3">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500/30 to-violet-500/20 border border-white/10 text-[18px] font-black text-white">
              {symbol.slice(0, 2)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-[26px] font-black tracking-tight text-white leading-none">{stock.name}</h1>
                <button onClick={() => setWatchlisted(!watchlisted)}
                  className="transition">
                  {watchlisted ? <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" /> : <Star className="h-3.5 w-3.5 text-slate-400" />}
                </button>
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <Pill><span className="font-bold text-sky-300">{symbol.toUpperCase()}</span></Pill>
                <Pill color="green"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400"/>NSE</Pill>
                {stock.sector && stock.sector !== "N/A" && <Pill>{stock.sector}</Pill>}
                {stock.industry && stock.industry !== "N/A" && stock.industry !== stock.sector && <Pill>{stock.industry}</Pill>}
              </div>
            </div>
          </div>

          {/* Price */}
          <div className="flex flex-wrap items-baseline gap-3">
            <span className="text-[40px] font-black text-white leading-none">₹{stock.price}</span>
            <span className={`text-[18px] font-bold ${isPos ? "text-emerald-400" : "text-rose-400"}`}>
              {sign}{stock.change_abs} ({sign}{stock.pct_change.toFixed(2)}%) {isPos ? "▲" : "▼"}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            {new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "long", year: "numeric" })} ·
            <span className="ml-1 text-slate-400">NSE</span>
          </p>
        </div>

        {/* Right: KPI cards + actions */}
        <div className="flex flex-col gap-4 items-end">
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Market Cap",   value: stock.market_cap },
              { label: "PE Ratio",     value: stock.pe },
              { label: "Dividend",     value: stock.dividend_yield },
              { label: "AI Score",     value: `${ai_score}/100` },
            ].map(k => (
              <div key={k.label} className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-center min-w-[90px]">
                <p className="text-[9px] uppercase tracking-widest text-slate-500">{k.label}</p>
                <p className="mt-1 text-[14px] font-black text-white">{k.value || "—"}</p>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <button onClick={() => setWatchlisted(!watchlisted)}
              className={`flex items-center gap-1.5 rounded-xl border px-4 py-2 text-[12px] font-medium transition ${
                watchlisted ? "border-sky-500/40 bg-sky-500/15 text-sky-300" : "border-white/10 bg-white/[0.03] text-slate-300 hover:border-white/20"
              }`}>
              {watchlisted ? <><Check className="h-3.5 w-3.5" />Watchlisted</> : "+ Add to Watchlist"}
            </button>
            <button className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-[12px] font-medium text-slate-300 hover:border-white/20 transition">
              ↔ Compare
            </button>
            <button className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-[12px] font-medium text-violet-300 hover:border-violet-500/30 transition">
              <Sparkles className="h-3.5 w-3.5 text-violet-400" /> Ask AI
            </button>
            <button className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] text-slate-400 hover:text-white transition">⋯</button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// ── Section 2: Price Chart ────────────────────────────────────────────────────
function PriceChart({ symbol, chartData, loadingChart, period, setPeriod, stock }: {
  symbol: string; chartData: any[]; loadingChart: boolean;
  period: string; setPeriod: (p: string) => void; stock: StockDetail;
}) {
  const isPos = stock.pct_change >= 0;
  const chartColor = isPos ? "#22c55e" : "#f43f5e";
  return (
    <SectionCard title="Price Chart" action={
      <div className="flex gap-0.5 bg-white/[0.03] rounded-xl p-0.5">
        {PERIODS.map(p => (
          <button key={p} onClick={() => setPeriod(p)}
            className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
              period === p ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"}`}>
            {p}
          </button>
        ))}
      </div>
    }>
      <div className="h-[260px] mt-4">
        {loadingChart ? (
          <div className="flex h-full items-center justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-sky-400"/>
          </div>
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor={chartColor} stopOpacity={0.25}/>
                  <stop offset="100%" stopColor={chartColor} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <XAxis dataKey="label" tick={{ fill: "#64748b", fontSize: 10 }} tickLine={false} axisLine={false}/>
              <YAxis domain={["auto","auto"]} tick={{ fill: "#64748b", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `₹${v}`} width={60}/>
              <RTooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, fontSize: 11 }}
                formatter={(v: number) => [`₹${v.toLocaleString("en-IN")}`, "Price"]}/>
              <Area type="monotone" dataKey="value" stroke={chartColor} strokeWidth={2} fill="url(#cg)" dot={false}/>
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-slate-600">No chart data for this period</p>
          </div>
        )}
      </div>

      {/* OHLC strip */}
      <div className="mt-4 grid grid-cols-6 gap-3 border-t border-white/[0.05] pt-4">
        {[
          ["Open",     `₹${stock.open}`],
          ["High",     `₹${stock.day_high}`],
          ["Low",      `₹${stock.day_low}`],
          ["Prev. Close",`₹${stock.prev_close}`],
          ["52W High", `₹${stock.week52_high}`],
          ["52W Low",  `₹${stock.week52_low}`],
        ].map(([l, v]) => (
          <div key={l} className="text-center">
            <p className="text-[9px] text-slate-500 uppercase tracking-wide">{l}</p>
            <p className="mt-0.5 text-[12px] font-bold text-white">{v}</p>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Section 3: AI Summary ─────────────────────────────────────────────────────
function AISummary({ stock }: { stock: StockDetail }) {
  const [expanded, setExpanded] = useState(false);
  const bullish = [
    stock.gov_score >= 75 && "Strong government support & policy tailwinds",
    n2(stock.roe) > 15 && `High ROE of ${stock.roe} — superior capital efficiency`,
    stock.dna_scores["Growth"] > 60 && "Robust revenue growth trend in core segments",
    stock.dividend_yield && stock.dividend_yield !== "—" && `Consistent dividend payer (${stock.dividend_yield})`,
    n2(stock.debt_to_equity) < 0.5 && "Low leverage — strong balance sheet",
  ].filter(Boolean).slice(0, 4);
  const risks = [
    n2(stock.pe) > 45 && "Premium valuation — priced for perfection",
    n2(stock.debt_to_equity) > 1 && "High debt-to-equity ratio",
    stock.dna_scores["News Sensitivity"] > 70 && "High sensitivity to macro news",
    "Execution risk on order delivery timelines",
    stock.gov_score >= 75 && "Concentrated revenue dependency on govt. contracts",
  ].filter(Boolean).slice(0, 4);
  const drivers = [
    "Strong order book pipeline driving multi-year revenue visibility",
    `${stock.sector} sector benefiting from structural policy tailwinds`,
    "Management has track record of consistent execution",
    "Margin expansion expected on operating leverage kicking in",
  ];
  return (
    <SectionCard>
      <div className="flex items-start gap-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-500/20">
          <Sparkles className="h-3.5 w-3.5 text-violet-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-[15px] font-bold text-white">AI Company Summary</h2>
            <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-violet-300">AI Generated</span>
          </div>
          <p className="text-[13px] leading-6 text-slate-300 line-clamp-3">
            {stock.description || `${stock.name} is a leading ${stock.sector} company listed on NSE. The company operates across multiple business verticals with a strong focus on operational excellence and shareholder value creation.`}
          </p>
          <AnimatePresence>
            {expanded && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden">
                <div className="mt-5 grid grid-cols-2 gap-5">
                  <div>
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-emerald-400">Bullish Factors</p>
                    <ul className="space-y-1.5">
                      {bullish.map((b, i) => (
                        <li key={i} className="flex items-start gap-1.5 text-[12px] text-slate-300">
                          <span className="mt-0.5 text-emerald-400 shrink-0">•</span>{b}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-rose-400">Key Risks</p>
                    <ul className="space-y-1.5">
                      {risks.map((r, i) => (
                        <li key={i} className="flex items-start gap-1.5 text-[12px] text-slate-300">
                          <span className="mt-0.5 text-rose-400 shrink-0">•</span>{r}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <div className="mt-4">
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-sky-400">Growth Drivers</p>
                  <ul className="grid grid-cols-2 gap-1.5">
                    {drivers.map((d, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-[12px] text-slate-400">
                        <span className="mt-0.5 text-sky-400 shrink-0">→</span>{d}
                      </li>
                    ))}
                  </ul>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          <div className="mt-3 flex gap-2">
            <button onClick={() => setExpanded(!expanded)}
              className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-[12px] font-medium text-sky-400 hover:bg-white/[0.06] transition">
              {expanded ? "Collapse ↑" : "Read Full Analysis →"}
            </button>
            <button className="rounded-xl border border-violet-500/20 bg-violet-500/10 px-4 py-2 text-[12px] font-medium text-violet-300 hover:bg-violet-500/15 transition">
              Ask AI about {stock.name.split(" ")[0]} →
            </button>
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

// ── Section 4: Stock DNA ──────────────────────────────────────────────────────
function StockDNA({ stock }: { stock: StockDetail }) {
  const scores = stock.dna_scores;
  const entries = Object.entries(scores);
  if (!entries.length) return null;
  return (
    <SectionCard title="Stock DNA" action={
      <span className="text-[11px] text-slate-500">What makes this company move?</span>
    }>
      <div className="mt-4 grid grid-cols-3 gap-3 sm:grid-cols-5">
        {entries.map(([k, v], i) => (
          <motion.div key={k} custom={i} variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }}
            className="group flex flex-col items-center gap-2 rounded-3xl border border-white/[0.06] bg-slate-900/60 p-4 text-center hover:border-sky-400/20 hover:-translate-y-0.5 transition-all">
            <div className="relative h-12 w-12">
              <svg className="h-12 w-12" style={{ transform: "rotate(-90deg)" }}>
                <circle cx="24" cy="24" r="19" stroke="rgba(255,255,255,0.06)" strokeWidth={4} fill="none"/>
                <circle cx="24" cy="24" r="19" stroke={scoreColor(v)} strokeWidth={4} fill="none"
                  strokeLinecap="round" strokeDasharray={`${(v / 100) * 2 * Math.PI * 19} ${2 * Math.PI * 19}`}/>
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-[11px] font-black" style={{ color: scoreColor(v) }}>{v}</span>
            </div>
            <p className="text-[10px] text-slate-400 leading-tight">{k}</p>
          </motion.div>
        ))}
      </div>
      {/* Radar mini */}
      <div className="mt-5 flex items-center gap-6">
        <div className="w-48 shrink-0">
          <ResponsiveContainer width="100%" height={180}>
            <RadarChart data={entries.map(([k, v]) => ({ subject: k.split(" ")[0], value: v }))}>
              <PolarGrid stroke="rgba(255,255,255,0.06)"/>
              <PolarAngleAxis dataKey="subject" tick={{ fill: "#64748b", fontSize: 9 }}/>
              <Radar dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2}/>
            </RadarChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1 space-y-2">
          {entries.map(([k, v]) => (
            <div key={k}>
              <div className="mb-0.5 flex justify-between text-[11px]">
                <span className="text-slate-400">{k}</span>
                <span className="font-bold" style={{ color: scoreColor(v) }}>{v}/100</span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full transition-all duration-700" style={{ width: `${v}%`, background: scoreColor(v) }}/>
              </div>
            </div>
          ))}
        </div>
      </div>
    </SectionCard>
  );
}

// ── Section 5: Financial Highlights ──────────────────────────────────────────
function FinancialHighlights({ stock }: { stock: StockDetail }) {
  const kpis: { label: string; value: number; suffix: string; color: string; icon: React.ReactNode }[] = [
    { label: "Revenue",   value: stock.quarterly_revenue.slice(-1)[0]?.value ?? 0,    suffix: " Cr", color: "text-sky-400",     icon: <TrendingUp className="h-4 w-4" /> },
    { label: "Net Profit",value: stock.quarterly_net_income.slice(-1)[0]?.value ?? 0, suffix: " Cr", color: "text-emerald-400", icon: <IndianRupee className="h-4 w-4" /> },
    { label: "ROE",       value: n2(stock.roe),  suffix: "%",   color: "text-violet-400", icon: <Target className="h-4 w-4" /> },
    { label: "ROCE",      value: n2(stock.roce), suffix: "%",   color: "text-amber-400",  icon: <Zap className="h-4 w-4" /> },
    { label: "EPS",       value: n2(stock.eps),  suffix: "",    color: "text-teal-400",   icon: <BarChart2 className="h-4 w-4" /> },
  ];
  return (
    <SectionCard title="Financial Highlights" action={
      <button className="text-[11px] text-sky-400 hover:text-sky-300 transition">View Financials →</button>
    }>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {kpis.map((k, i) => (
          <motion.div key={k.label} custom={i} variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }}
            className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4 hover:border-sky-400/20 hover:-translate-y-0.5 transition-all">
            <div className="mb-2 flex items-center">{k.icon}</div>
            <p className={`text-[22px] font-black leading-none ${k.color}`}>
              {k.value.toLocaleString("en-IN")}{k.suffix}
            </p>
            <p className="mt-1 text-[10px] text-slate-500">{k.label}</p>
            {/* Sparkline */}
            <div className="mt-2 h-8">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={(k.label === "Revenue" ? stock.quarterly_revenue : stock.quarterly_net_income).slice(-6)}>
                  <Line type="monotone" dataKey="value" stroke={k.color.replace("text-","").includes("sky") ? "#38bdf8" : "#22c55e"} strokeWidth={1.5} dot={false}/>
                </LineChart>
              </ResponsiveContainer>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Annual table */}
      {stock.annual_financials.length > 0 && (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-white/[0.06]">
                <th className="pb-2 text-left text-[10px] text-slate-500 font-medium">₹ in Crore</th>
                {stock.annual_financials.map(f => <th key={f.year} className="pb-2 text-right text-[10px] text-slate-500 font-medium">{f.year}</th>)}
                <th className="pb-2 text-right text-[10px] text-violet-400 font-medium">TTM</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.03]">
              <tr>
                <td className="py-2 text-slate-400">Revenue</td>
                {stock.annual_financials.map(f => <td key={f.year} className="py-2 text-right font-semibold text-white">{f.revenue.toLocaleString()}</td>)}
                <td className="py-2 text-right font-bold text-violet-300">{stock.quarterly_revenue.reduce((a, b) => a + b.value, 0).toLocaleString()}</td>
              </tr>
              <tr>
                <td className="py-2 text-slate-400">Net Profit</td>
                {stock.annual_financials.map(f => <td key={f.year} className={`py-2 text-right font-semibold ${f.net_income >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{f.net_income.toLocaleString()}</td>)}
                <td className="py-2 text-right font-bold text-emerald-300">{stock.quarterly_net_income.reduce((a, b) => a + b.value, 0).toLocaleString()}</td>
              </tr>
              <tr>
                <td className="py-2 text-slate-400">ROE (%)</td>
                {stock.annual_financials.map((f, i) => <td key={f.year} className="py-2 text-right text-white">{i === stock.annual_financials.length - 1 ? stock.roe : "—"}</td>)}
                <td className="py-2 text-right text-violet-300">{stock.roe}</td>
              </tr>
              <tr>
                <td className="py-2 text-slate-400">EPS (₹)</td>
                {stock.annual_financials.map((f, i) => <td key={f.year} className="py-2 text-right text-white">{i === stock.annual_financials.length - 1 ? stock.eps : "—"}</td>)}
                <td className="py-2 text-right text-violet-300">{stock.eps}</td>
              </tr>
              <tr>
                <td className="py-2 text-slate-400">Debt/Equity</td>
                {stock.annual_financials.map((f, i) => <td key={f.year} className="py-2 text-right text-white">{i === stock.annual_financials.length - 1 ? stock.debt_to_equity : "—"}</td>)}
                <td className="py-2 text-right text-violet-300">{stock.debt_to_equity}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

// ── Section 6: Key Ratios ─────────────────────────────────────────────────────
function KeyRatios({ stock }: { stock: StockDetail }) {
  const rows = [
    ["PE Ratio (TTM)",  stock.pe,            stock.pe],
    ["Forward PE",      stock.forward_pe,    "—"],
    ["PB Ratio",        stock.pb,            "—"],
    ["ROE",             stock.roe,           "—"],
    ["ROCE",            stock.roce,          "—"],
    ["EPS (TTM)",       stock.eps ? `₹${stock.eps}` : "—", "—"],
    ["Beta",            stock.beta,          "—"],
    ["D/E Ratio",       stock.debt_to_equity,"—"],
    ["Dividend Yield",  stock.dividend_yield,"—"],
    ["Current Ratio",   stock.current_ratio, "—"],
  ];
  return (
    <SectionCard title="Key Ratios" action={<span className="text-[10px] text-slate-600">vs Industry Avg</span>}>
      <div className="mt-3 grid grid-cols-2 gap-x-8 divide-x divide-white/[0.04]">
        <div>{rows.slice(0, 5).map(([l, v]) => <KvRow key={l} label={l} value={v} colored/>)}</div>
        <div className="pl-8">{rows.slice(5).map(([l, v]) => <KvRow key={l} label={l} value={v} colored/>)}</div>
      </div>
    </SectionCard>
  );
}

// ── Section 7: Event Timeline ─────────────────────────────────────────────────
function EventTimeline({ stock, symbol }: { stock: StockDetail; symbol: string }) {
  const mockScores = [85, 72, -35, 68, 45, 78];
  const events = stock.events.length > 0 ? stock.events : [];
  if (!events.length) return null;
  return (
    <SectionCard title={`Recent Events Impacting ${symbol.toUpperCase()}`} action={
      <Link href="/events" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All Events →</Link>
    }>
      <div className="mt-4 space-y-3">
        {events.map((e, i) => {
          const score = mockScores[i % mockScores.length];
          const ic = impactColor(Math.abs(score));
          const sentiment = score >= 0 ? "Positive" : "Negative";
          return (
            <motion.div key={i} custom={i} variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }}
              className="flex items-start gap-4 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 hover:border-sky-400/20 hover:bg-sky-400/[0.02] transition">
              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${ic.bg}`}>
                <svg className={`h-5 w-5 ${ic.text}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-1.5 mb-1">
                  <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold ${ic.text} border-current/20`}>{ic.label} Impact</span>
                  <span className={`rounded-full px-2 py-0.5 text-[9px] font-semibold ${score >= 0 ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>{sentiment}</span>
                  <span className="text-[10px] text-slate-600">{e.date}</span>
                </div>
                <p className="text-[13px] font-semibold text-white line-clamp-1">{e.title}</p>
              </div>
              <ScoreCircle score={score} size={48}/>
            </motion.div>
          );
        })}
      </div>
    </SectionCard>
  );
}

// ── Section 8: Government Exposure ───────────────────────────────────────────
function GovernmentExposureSection({ stock }: { stock: StockDetail }) {
  const govLevelColor = stock.gov_level === "High" ? "text-emerald-300" : stock.gov_level === "Medium" ? "text-amber-300" : "text-slate-300";
  if (!stock.gov_score) return null;
  return (
    <SectionCard title="Government Exposure" action={
      <span className={`text-[14px] font-bold ${govLevelColor}`}>{stock.gov_level || "—"}</span>
    }>
      <div className="mt-4 grid grid-cols-2 gap-5">
        {/* Left: donut + score */}
        <div>
          <div className="mb-3 flex items-center gap-3">
            <span className="text-[40px] font-black text-white leading-none">{stock.gov_score}</span>
            <div>
              <p className="text-[10px] text-slate-500">out of 100</p>
              <span className={`text-[13px] font-bold ${govLevelColor}`}>{stock.gov_level}</span>
            </div>
          </div>
          <div className="h-[140px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={stock.gov_breakdown.length ? stock.gov_breakdown : [{ label: "Govt", pct: stock.gov_score }, { label: "Other", pct: 100 - stock.gov_score }]}
                  cx="50%" cy="50%" innerRadius={38} outerRadius={58} paddingAngle={2} dataKey="pct" strokeWidth={0}>
                  {(stock.gov_breakdown.length ? stock.gov_breakdown : []).map((b, i) => (
                    <Cell key={i} fill={b.color || DONUT_C[i % DONUT_C.length]}/>
                  ))}
                </Pie>
                <RTooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 10 }} formatter={(v: number, n: any, p: any) => [p.payload.label, `${v}%`]}/>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-1.5">
            {stock.gov_breakdown.map((b, i) => (
              <div key={i} className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <div className="h-2 w-2 rounded-full shrink-0" style={{ background: b.color || DONUT_C[i % DONUT_C.length] }}/>
                  <span className="text-[11px] text-slate-400">{b.label}</span>
                </div>
                <span className="text-[11px] font-bold text-white">{b.pct}%</span>
              </div>
            ))}
          </div>
        </div>
        {/* Right: key areas + schemes */}
        <div>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Key Support Areas</p>
          <div className="flex flex-wrap gap-1.5 mb-4">
            {stock.gov_support_areas.map(a => (
              <span key={a} className="rounded-full border border-sky-500/20 bg-sky-500/8 px-2 py-0.5 text-[10px] text-sky-300">{a}</span>
            ))}
          </div>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Policy Impact Cards</p>
          <div className="space-y-2">
            {[
              { policy: `${stock.sector} Scheme`,         impact: `+₹${Math.round(n2(stock.market_cap) * 0.05)}Cr opportunity`, score: 78 },
              { policy: "PLI Scheme",                      impact: "Revenue uplift in FY26",                                      score: 65 },
              { policy: "Budget Allocation",               impact: `${stock.sector} capex boost`,                                  score: 72 },
            ].map((p, i) => (
              <div key={i} className="flex items-center justify-between rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2">
                <div>
                  <p className="text-[12px] font-medium text-white">{p.policy}</p>
                  <p className="text-[10px] text-slate-500">{p.impact}</p>
                </div>
                <span className="text-[12px] font-black text-emerald-400">{p.score}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

// ── Section 9: Opportunity Radar ──────────────────────────────────────────────
function OpportunityRadarSection({ stock }: { stock: StockDetail }) {
  const opps: { title: string; score: number; confidence: number; revenue: string; timeline: string; icon: React.ReactNode }[] = [
    { title: `${stock.sector} Expansion`, score: 88, confidence: 82, revenue: `₹${Math.round(n2(stock.market_cap) * 0.12)}Cr`, timeline: "12-18 months", icon: <Rocket className="h-4 w-4" /> },
    { title: "Export Opportunity",         score: 74, confidence: 68, revenue: "Incremental", timeline: "18-24 months", icon: <Globe2 className="h-4 w-4" /> },
    { title: "New Product Pipeline",       score: 69, confidence: 71, revenue: "TBD",         timeline: "24-36 months", icon: <FlaskConical className="h-4 w-4" /> },
  ];
  return (
    <SectionCard title="Opportunity Radar" action={<span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-300">AI Powered</span>}>
      <div className="mt-4 grid grid-cols-3 gap-4">
        {opps.map((o, i) => (
          <motion.div key={i} custom={i} variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }}
            className="flex flex-col gap-3 rounded-2xl border border-white/[0.06] bg-gradient-to-b from-white/[0.03] to-transparent p-4 hover:border-emerald-400/20 hover:-translate-y-0.5 transition-all">
            <div className="flex items-center justify-between">
              <span className="flex items-center">{o.icon}</span>
              <div className="text-right">
                <p className="text-[24px] font-black text-white leading-none">{o.score}</p>
                <p className="text-[9px] text-slate-500">Score</p>
              </div>
            </div>
            <div>
              <p className="text-[13px] font-bold text-white">{o.title}</p>
              <p className="text-[10px] text-slate-500 mt-0.5">{o.timeline}</p>
            </div>
            <div className="space-y-1.5">
              <div className="flex justify-between text-[10px]">
                <span className="text-slate-500">Confidence</span>
                <span className="text-emerald-400 font-semibold">{o.confidence}%</span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full bg-emerald-500" style={{ width: `${o.confidence}%` }}/>
              </div>
            </div>
            <div className="flex justify-between text-[10px] pt-1 border-t border-white/[0.04]">
              <span className="text-slate-500">Expected Revenue</span>
              <span className="font-semibold text-sky-300">{o.revenue}</span>
            </div>
            <button className="w-full rounded-xl bg-emerald-500/10 border border-emerald-500/20 py-1.5 text-[11px] font-medium text-emerald-300 hover:bg-emerald-500/20 transition">
              Explore →
            </button>
          </motion.div>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Section 10: News Impact ───────────────────────────────────────────────────
function NewsImpact({ stock, relatedNews }: { stock: StockDetail; relatedNews: any[] }) {
  const articles = relatedNews.length ? relatedNews : stock.news;
  if (!articles.length) return null;
  const sentiments = ["Positive", "Positive", "Negative", "Neutral", "Positive"];
  const scores     = [78, 65, -42, 55, 70];
  return (
    <SectionCard title="News Impact Analysis" action={
      <Link href="/news" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All News →</Link>
    }>
      <div className="mt-4 space-y-3">
        {articles.slice(0, 5).map((a: any, i: number) => {
          const sentiment = sentiments[i % sentiments.length];
          const score     = scores[i % scores.length];
          const ic = impactColor(Math.abs(score));
          return (
            <div key={i} className="flex items-start gap-3 rounded-2xl border border-white/[0.05] bg-white/[0.02] p-4 hover:border-sky-400/10 transition">
              {/* Thumbnail placeholder */}
              <div className={`h-14 w-14 shrink-0 rounded-xl ${["bg-gradient-to-br from-sky-500/20 to-violet-500/10","bg-gradient-to-br from-emerald-500/20 to-teal-500/10","bg-gradient-to-br from-rose-500/20 to-amber-500/10","bg-gradient-to-br from-amber-500/20 to-orange-500/10","bg-gradient-to-br from-violet-500/20 to-indigo-500/10"][i % 5]} flex items-center justify-center text-slate-400`}>
                {([<BarChart2 className="h-6 w-6" />, <TrendingUp className="h-6 w-6" />, <TrendingDown className="h-6 w-6" />, <Landmark className="h-6 w-6" />, <Briefcase className="h-6 w-6" />])[i % 5]}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-1.5 mb-1">
                  <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold ${ic.text} border-current/20`}>{ic.label}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[9px] font-semibold ${sentiment === "Positive" ? "bg-emerald-500/15 text-emerald-300" : sentiment === "Negative" ? "bg-rose-500/15 text-rose-300" : "bg-amber-500/15 text-amber-300"}`}>{sentiment}</span>
                  <span className="text-[10px] text-slate-600">{a.source || "Source"}</span>
                  <span className="text-[10px] text-slate-600">{a.published_at?.slice(0, 10) || ""}</span>
                </div>
                <p className="text-[13px] font-semibold text-white line-clamp-2">{a.headline}</p>
                {a.summary && <p className="mt-0.5 text-[11px] text-slate-500 line-clamp-1">{a.summary}</p>}
              </div>
              <ScoreCircle score={score} size={44}/>
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}

// ── Section 11: AI Sentiment ──────────────────────────────────────────────────
function AISentiment({ stock }: { stock: StockDetail }) {
  const bullPct = stock.buy_count
    ? Math.round((stock.buy_count / (stock.buy_count + stock.hold_count + stock.sell_count || 1)) * 100)
    : 62;
  const bearPct = stock.sell_count
    ? Math.round((stock.sell_count / (stock.buy_count + stock.hold_count + stock.sell_count || 1)) * 100)
    : 15;
  const neutPct = 100 - bullPct - bearPct;
  const trend = [{ w: "5W ago", v: 55 }, { w: "4W ago", v: 58 }, { w: "3W ago", v: 62 }, { w: "2W ago", v: 60 }, { w: "1W ago", v: bullPct }, { w: "Now", v: bullPct }];

  return (
    <SectionCard title="AI Sentiment Analysis">
      <div className="mt-4 grid grid-cols-2 gap-5">
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="relative h-24 w-24">
              <svg className="h-24 w-24" style={{ transform: "rotate(-90deg)" }} viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="32" stroke="rgba(255,255,255,0.06)" strokeWidth={8} fill="none"/>
                <circle cx="40" cy="40" r="32" stroke="#22c55e" strokeWidth={8} fill="none"
                  strokeLinecap="round" strokeDasharray={`${(bullPct / 100) * 2 * Math.PI * 32} ${2 * Math.PI * 32}`}/>
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-[18px] font-black text-emerald-400">{bullPct}%</span>
                <span className="text-[8px] text-slate-500">Bullish</span>
              </div>
            </div>
            <div className="space-y-2">
              <div><div className="flex justify-between text-[11px] mb-0.5"><span className="text-emerald-400">Bullish</span><span className="text-white font-bold">{bullPct}%</span></div><div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${bullPct}%` }}/></div></div>
              <div><div className="flex justify-between text-[11px] mb-0.5"><span className="text-amber-400">Neutral</span><span className="text-white font-bold">{neutPct}%</span></div><div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden"><div className="h-full rounded-full bg-amber-500" style={{ width: `${neutPct}%` }}/></div></div>
              <div><div className="flex justify-between text-[11px] mb-0.5"><span className="text-rose-400">Bearish</span><span className="text-white font-bold">{bearPct}%</span></div><div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden"><div className="h-full rounded-full bg-rose-500" style={{ width: `${bearPct}%` }}/></div></div>
            </div>
          </div>
          {stock.analyst_count > 0 && (
            <p className="text-[11px] text-slate-500">Based on {stock.analyst_count} analyst ratings</p>
          )}
        </div>
        <div>
          <p className="mb-2 text-[11px] text-slate-500">Bullish % Weekly Trend</p>
          <div className="h-28">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend}>
                <defs>
                  <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22c55e" stopOpacity={0.3}/>
                    <stop offset="100%" stopColor="#22c55e" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="w" tick={{ fill: "#64748b", fontSize: 9 }} tickLine={false} axisLine={false}/>
                <YAxis domain={[0, 100]} hide/>
                <RTooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 10 }} formatter={(v: number) => [`${v}%`, "Bullish"]}/>
                <Area type="monotone" dataKey="v" stroke="#22c55e" strokeWidth={1.5} fill="url(#sg)"/>
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

// ── Section 12: Network Graph ─────────────────────────────────────────────────
function NetworkGraph({ stock }: { stock: StockDetail }) {
  const { nodes, edges } = useMemo(() => deriveNetworkNodes(stock), [stock.symbol]);
  return (
    <SectionCard title="Business Network Graph" action={<span className="text-[10px] text-slate-600">Zoom / Pan / Click</span>}>
      <div className="mt-4 h-[380px] w-full overflow-hidden rounded-2xl border border-white/[0.06]">
        <RFlow nodes={nodes} edges={edges} fitView>
          <RFBg color="#1e293b" gap={20}/>
          <RFCtrl style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 8 }}/>
        </RFlow>
      </div>
    </SectionCard>
  );
}

// ── Section 13: Business Segments ─────────────────────────────────────────────
function BusinessSegments({ stock }: { stock: StockDetail }) {
  const segments = useMemo(() => deriveSegments(stock.sector, stock.symbol), [stock.sector]);
  return (
    <SectionCard title="Business Segments">
      <div className="mb-3 flex items-center gap-2">
        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-400">
          Indicative · Sector Averages
        </span>
        <span className="text-[10px] text-slate-600">Based on sector benchmarks, not company-reported data</span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {segments.map((s, i) => (
          <motion.div key={s.name} custom={i} variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }}
            className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4 hover:-translate-y-0.5 transition-all">
            <div className="mb-2 flex items-center justify-between">
              <div className="h-2 w-2 rounded-full" style={{ background: DONUT_C[i % DONUT_C.length] }}/>
              <span className="text-[22px] font-black text-white">{s.pct}%</span>
            </div>
            <p className="text-[12px] font-semibold text-white line-clamp-2">{s.name}</p>
            <div className="mt-2 space-y-0.5">
              <p className="text-[10px] text-emerald-400">Growth: {s.growth}</p>
              <p className="text-[10px] text-sky-400">Margin: {s.margin}</p>
            </div>
            <div className="mt-2 h-1 rounded-full bg-white/[0.06]">
              <div className="h-full rounded-full transition-all" style={{ width: `${s.pct}%`, background: DONUT_C[i % DONUT_C.length] }}/>
            </div>
          </motion.div>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Section 14: Revenue Geography ─────────────────────────────────────────────
function RevenueGeography({ stock }: { stock: StockDetail }) {
  const geo = useMemo(() => deriveGeography(stock.sector), [stock.sector]);
  return (
    <SectionCard title="Revenue Geography">
      <div className="mb-3 flex items-center gap-2">
        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-400">
          Indicative · Sector Averages
        </span>
        <span className="text-[10px] text-slate-600">Based on sector benchmarks, not company-reported data</span>
      </div>
      <div className="mt-4 space-y-3">
        {geo.map((g, i) => (
          <div key={g.r}>
            <div className="mb-1 flex justify-between text-[12px]">
              <span className="text-slate-300">{g.r}</span>
              <span className="font-bold text-white">{g.v}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
              <motion.div className="h-full rounded-full" style={{ background: DONUT_C[i % DONUT_C.length] }}
                initial={{ width: 0 }} whileInView={{ width: `${g.v}%` }} transition={{ duration: 0.7, delay: i * 0.1 }} viewport={{ once: true }}/>
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Section 15: Order Book ─────────────────────────────────────────────────────
function OrderBook({ stock }: { stock: StockDetail }) {
  const mc = n2(stock.market_cap);
  const orders: { label: string; value: string; icon: React.ReactNode; color: string }[] = [
    { label: "Total Order Book",  value: `₹${(mc * 2.8).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`, icon: <ClipboardList className="h-5 w-5" />, color: "text-sky-400" },
    { label: "Orders Pending",    value: `₹${(mc * 1.9).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`, icon: <Clock className="h-5 w-5" />,        color: "text-amber-400" },
    { label: "Completed FY24",    value: `₹${(mc * 0.9).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`, icon: <CheckCircle2 className="h-5 w-5" />, color: "text-emerald-400" },
    { label: "Execution Rate",    value: "68%",                                                                        icon: <Zap className="h-5 w-5" />,          color: "text-violet-400" },
  ];
  return (
    <SectionCard title="Order Book">
      <div className="mt-4 grid grid-cols-2 gap-3">
        {orders.map((o, i) => (
          <div key={o.label} className="rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4">
            <div className="mb-2 text-slate-400">{o.icon}</div>
            <p className={`text-[18px] font-black leading-none ${o.color}`}>{o.value}</p>
            <p className="mt-1 text-[11px] text-slate-500">{o.label}</p>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Section 16: Shareholding ──────────────────────────────────────────────────
function Shareholding({ stock }: { stock: StockDetail }) {
  const data = useMemo(() => deriveShareholding(stock.gov_score), [stock.gov_score]);
  return (
    <SectionCard title="Shareholding Pattern">
      <div className="mt-4 grid grid-cols-2 gap-5">
        <div className="h-[180px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={2} dataKey="value" strokeWidth={0}>
                {data.map((d, i) => <Cell key={i} fill={d.color}/>)}
              </Pie>
              <RTooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 10 }}/>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-3">
          {data.map(d => (
            <div key={d.name}>
              <div className="flex justify-between text-[12px] mb-1">
                <div className="flex items-center gap-1.5">
                  <div className="h-2 w-2 rounded-full shrink-0" style={{ background: d.color }}/>
                  <span className="text-slate-300">{d.name}</span>
                </div>
                <span className="font-bold text-white">{d.value}%</span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full" style={{ width: `${d.value}%`, background: d.color }}/>
              </div>
            </div>
          ))}
          {stock.held_institutions && stock.held_institutions !== "—" && (
            <div className="mt-2 rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2">
              <p className="text-[10px] text-slate-500">Institutional Hold</p>
              <p className="text-[13px] font-bold text-white">{stock.held_institutions}</p>
            </div>
          )}
        </div>
      </div>
    </SectionCard>
  );
}

// ── Section 17: Peer Comparison ───────────────────────────────────────────────
function PeerComparison({ stock }: { stock: StockDetail }) {
  const [peerData, setPeerData] = useState<Record<string, any>>({});
  const [loading, setLoading]   = useState(false);
  useEffect(() => {
    if (!stock.peers.length) return;
    setLoading(true);
    Promise.all(stock.peers.slice(0, 5).map(p =>
      fetch(`${API}/api/stocks/${p}`).then(r => r.ok ? r.json() : null).catch(() => null)
    )).then(results => {
      const map: Record<string, any> = {};
      stock.peers.slice(0, 5).forEach((p, i) => { if (results[i]) map[p] = results[i]; });
      setPeerData(map);
    }).finally(() => setLoading(false));
  }, [stock.symbol]);

  const rows = [
    { symbol: stock.symbol, name: stock.name, price: `₹${stock.price}`, pe: stock.pe, roe: stock.roe, growth: "+12%", isSelf: true },
    ...stock.peers.slice(0, 5).map(p => {
      const d = peerData[p];
      return { symbol: p, name: d?.name || p, price: d ? `₹${d.price}` : "—", pe: d?.pe || "—", roe: d?.roe || "—", growth: "—", isSelf: false };
    }),
  ];

  return (
    <SectionCard title="Peer Comparison" action={
      <Link href="/compare" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All Peers →</Link>
    }>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-white/[0.06]">
              {["Company", "Price", "PE (TTM)", "ROE (%)", "Revenue Growth", ""].map(h => (
                <th key={h} className="pb-3 text-left text-[10px] text-slate-500 font-medium first:text-left text-right last:text-right">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.03]">
            {rows.map(r => (
              <tr key={r.symbol} className={`hover:bg-white/[0.02] transition ${r.isSelf ? "bg-sky-500/[0.04]" : ""}`}>
                <td className="py-3">
                  <div className="flex items-center gap-2">
                    <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold ${r.isSelf ? "bg-sky-500/20 text-sky-300" : "bg-white/[0.06] text-slate-400"}`}>
                      {r.symbol.slice(0, 2)}
                    </div>
                    <div>
                      <Link href={`/companies/${r.symbol}`} className={`font-semibold hover:text-sky-300 transition ${r.isSelf ? "text-sky-300" : "text-white"}`}>{r.symbol}</Link>
                      <p className="text-[10px] text-slate-500 truncate max-w-[100px]">{r.name}</p>
                    </div>
                    {r.isSelf && <span className="rounded-full bg-sky-500/20 px-1.5 py-0.5 text-[8px] font-bold text-sky-300">YOU</span>}
                  </div>
                </td>
                <td className="py-3 text-right font-semibold text-white">{loading && !r.isSelf ? <div className="ml-auto h-3 w-12 animate-pulse rounded bg-white/[0.06]"/> : r.price}</td>
                <td className="py-3 text-right font-semibold text-white">{r.pe || "—"}</td>
                <td className="py-3 text-right font-semibold text-emerald-300">{r.roe || "—"}</td>
                <td className="py-3 text-right text-emerald-400">{r.growth}</td>
                <td className="py-3 text-right">
                  {!r.isSelf && <Link href={`/companies/${r.symbol}`} className="text-[10px] text-sky-400 hover:text-sky-300 transition">View →</Link>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

// ── Section 18: Historical Performance ───────────────────────────────────────
function HistoricalPerformance({ stock }: { stock: StockDetail }) {
  const [activeMetric, setActiveMetric] = useState<"revenue"|"profit">("revenue");
  const data = stock.annual_financials;
  if (!data.length) return null;
  return (
    <SectionCard title="Historical Performance">
      <div className="mt-4 flex gap-2 mb-4">
        {[["revenue", "Revenue"], ["profit", "Net Profit"]].map(([k, l]) => (
          <button key={k} onClick={() => setActiveMetric(k as any)}
            className={`rounded-lg px-3 py-1.5 text-[12px] font-medium transition ${activeMetric === k ? "bg-sky-500/20 text-sky-300" : "text-slate-500 hover:text-slate-300"}`}>
            {l}
          </button>
        ))}
      </div>
      <div className="h-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
            <XAxis dataKey="year" tick={{ fill: "#64748b", fontSize: 10 }} tickLine={false} axisLine={false}/>
            <YAxis tick={{ fill: "#64748b", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${(v/1000).toFixed(0)}K`} width={40}/>
            <RTooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, fontSize: 11 }} formatter={(v: number) => [`₹${v.toLocaleString()} Cr`, activeMetric === "revenue" ? "Revenue" : "Net Profit"]}/>
            <Bar dataKey={activeMetric === "revenue" ? "revenue" : "net_income"} radius={[6, 6, 0, 0]}
              fill={activeMetric === "revenue" ? "#38bdf8" : "#22c55e"} fillOpacity={0.8}/>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </SectionCard>
  );
}

// ── Section 19: AI Forecast ───────────────────────────────────────────────────
function AIForecast({ stock }: { stock: StockDetail }) {
  const isPos = stock.pct_change >= 0;
  return (
    <SectionCard noPad>
      <div className="p-6 bg-gradient-to-br from-violet-500/10 via-transparent to-sky-500/5 rounded-[28px]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-500/20 text-violet-400">
              <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg>
            </div>
            <h2 className="text-[15px] font-bold text-white">AI Forecast</h2>
          </div>
          <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-violet-300">Premium</span>
        </div>
        <div className="grid grid-cols-3 gap-4 mb-5">
          {[
            { label: "Next Quarter", outlook: "Positive", icon: <TrendingUp className="h-6 w-6 text-emerald-400" />, conf: 78 },
            { label: "Next Year",    outlook: "Bullish",  icon: <Rocket className="h-6 w-6 text-violet-400" />,      conf: 72 },
            { label: "3 Year View",  outlook: "Strong",   icon: <Star className="h-6 w-6 text-amber-400" />,         conf: 68 },
          ].map(f => (
            <div key={f.label} className="rounded-2xl border border-violet-500/20 bg-violet-500/[0.06] p-4 text-center">
              <div className="mb-1 flex justify-center">{f.icon}</div>
              <p className="text-[13px] font-bold text-emerald-300">{f.outlook}</p>
              <p className="text-[10px] text-slate-500 mt-0.5">{f.label}</p>
              <div className="mt-2 h-1 rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full bg-violet-500" style={{ width: `${f.conf}%` }}/>
              </div>
              <p className="text-[9px] text-slate-600 mt-0.5">{f.conf}% confidence</p>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-sky-400">Catalysts</p>
            {["Order book expansion","Government policy support","Margin improvement","Sector tailwinds"].map((c, i) => (
              <p key={i} className="flex items-start gap-1.5 text-[12px] text-slate-300 mb-1"><span className="text-emerald-400 mt-0.5">+</span>{c}</p>
            ))}
          </div>
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-rose-400">Risks</p>
            {["Execution delays","Input cost pressures","Regulatory changes","Global macro headwinds"].map((r, i) => (
              <p key={i} className="flex items-start gap-1.5 text-[12px] text-slate-300 mb-1"><span className="text-rose-400 mt-0.5">-</span>{r}</p>
            ))}
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between rounded-2xl border border-violet-500/20 bg-violet-500/[0.06] px-5 py-4">
          <div>
            <p className="text-[11px] text-slate-500">AI Investment Rating</p>
            <p className="text-[22px] font-black text-white mt-0.5">Strong {isPos ? "Buy" : "Hold"}</p>
          </div>
          <div className="text-[52px] font-black text-violet-400">{Math.round((n2(stock.roe) + stock.gov_score) / 2) || 74}</div>
        </div>
      </div>
    </SectionCard>
  );
}

// ── Section 20: Related Stories ────────────────────────────────────────────────
function RelatedStories({ stock }: { stock: StockDetail }) {
  const stories: { title: string; tag: string; icon: React.ReactNode; grad: string }[] = [
    { title: `${stock.sector} Boom 2025`, tag: stock.sector, icon: <HardHat className="h-7 w-7" />, grad: "from-sky-500/20 to-violet-500/10" },
    { title: "Defence Indigenisation",    tag: "Defence",    icon: <Shield className="h-7 w-7" />,  grad: "from-emerald-500/20 to-teal-500/10" },
    { title: "Green Energy Transition",   tag: "Energy",     icon: <Leaf className="h-7 w-7" />,    grad: "from-amber-500/20 to-orange-500/10" },
    { title: "AI Infrastructure Push",    tag: "Technology", icon: <Bot className="h-7 w-7" />,     grad: "from-rose-500/20 to-pink-500/10" },
  ];
  return (
    <SectionCard title="Related Stories" action={<Link href="/stories" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>}>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stories.map((s, i) => (
          <Link key={i} href="/stories"
            className={`group relative flex h-32 flex-col justify-end overflow-hidden rounded-2xl bg-gradient-to-br ${s.grad} border border-white/[0.06] p-4 hover:-translate-y-0.5 hover:border-sky-400/20 transition-all`}>
            <span className="absolute right-3 top-3 text-slate-400">{s.icon}</span>
            <span className="text-[9px] uppercase tracking-widest text-slate-500 mb-1">{s.tag}</span>
            <p className="text-[12px] font-bold text-white leading-snug line-clamp-2">{s.title}</p>
          </Link>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Section 21: Economic Calendar ─────────────────────────────────────────────
function EconomicCalendarSection({ stock }: { stock: StockDetail }) {
  const events = [
    { date: "15 Jul", title: "Q1 Results",        type: "results",  color: "bg-sky-500/20 text-sky-300" },
    { date: "05 Aug", title: "RBI Policy",         type: "rbi",      color: "bg-violet-500/20 text-violet-300" },
    { date: "10 Aug", title: "Dividend Ex-Date",   type: "dividend", color: "bg-emerald-500/20 text-emerald-300" },
    { date: "30 Sep", title: "Budget Review",      type: "budget",   color: "bg-amber-500/20 text-amber-300" },
    { date: "15 Oct", title: "Q2 Results",         type: "results",  color: "bg-sky-500/20 text-sky-300" },
  ];
  return (
    <SectionCard title="Upcoming Catalysts">
      <div className="mt-4 space-y-2">
        {events.map((e, i) => (
          <div key={i} className="flex items-center gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2.5">
            <div className={`flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-xl ${e.color}`}>
              <span className="text-[9px] font-bold leading-none">{e.date.split(" ")[1]}</span>
              <span className="text-[10px] font-black leading-none">{e.date.split(" ")[0]}</span>
            </div>
            <div>
              <p className="text-[12px] font-semibold text-white">{e.title}</p>
              <p className="text-[10px] capitalize text-slate-500">{e.type}</p>
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Section 22: Similar Companies ─────────────────────────────────────────────
function SimilarCompanies({ stock }: { stock: StockDetail }) {
  if (!stock.peers.length) return null;
  const similarities = [92, 88, 84, 79, 74];
  const reasons = [
    "Same sector + government exposure",
    "Similar order book pattern",
    "Comparable revenue mix",
    "Overlapping customer base",
    "Similar capex cycle",
  ];
  return (
    <SectionCard title="Similar Companies">
      <div className="mt-4 flex gap-3 overflow-x-auto pb-2 scrollbar-hide">
        {stock.peers.slice(0, 5).map((p, i) => (
          <Link key={p} href={`/companies/${p}`}
            className="group flex min-w-[160px] flex-col gap-2 rounded-2xl border border-white/[0.06] bg-slate-900/50 p-4 hover:border-sky-400/20 hover:-translate-y-0.5 transition-all">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-[11px] font-bold text-slate-300">
                {p.slice(0, 2)}
              </div>
              <div className="min-w-0">
                <p className="text-[12px] font-bold text-white group-hover:text-sky-300 transition truncate">{p}</p>
                <p className="text-[10px] text-emerald-400">{similarities[i] || 78}% similar</p>
              </div>
            </div>
            <p className="text-[10px] text-slate-500 leading-snug">{reasons[i] || "Sector peer"}</p>
            <p className="mt-auto text-[10px] text-sky-400">Compare →</p>
          </Link>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Section 23: Documents ──────────────────────────────────────────────────────
function Documents({ stock }: { stock: StockDetail }) {
  const docs: { title: string; type: string; icon: React.ReactNode; size: string }[] = [
    { title: "Annual Report FY24",         type: "PDF",  icon: <FileText className="h-5 w-5 text-slate-400" />,  size: "4.2 MB" },
    { title: "Q4 Investor Presentation",   type: "PDF",  icon: <BarChart2 className="h-5 w-5 text-slate-400" />, size: "2.1 MB" },
    { title: "Concall Transcript Q4",      type: "PDF",  icon: <Mic className="h-5 w-5 text-slate-400" />,       size: "890 KB" },
    { title: "Exchange Filing (NSE)",      type: "PDF",  icon: <Landmark className="h-5 w-5 text-slate-400" />,  size: "1.3 MB" },
    { title: "Sustainability Report 2024", type: "PDF",  icon: <Leaf className="h-5 w-5 text-slate-400" />,      size: "3.8 MB" },
    { title: "Quarterly Results Q4 FY24",  type: "XLSX", icon: <FileStack className="h-5 w-5 text-slate-400" />, size: "540 KB" },
  ];
  return (
    <SectionCard title="Documents & Reports">
      <div className="mt-4 grid grid-cols-2 gap-3">
        {docs.map((d, i) => (
          <div key={i} className="flex items-center gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02] p-3 hover:border-sky-400/10 hover:bg-white/[0.03] transition cursor-pointer">
            <span className="shrink-0 text-slate-400">{d.icon}</span>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-medium text-white truncate">{d.title}</p>
              <p className="text-[10px] text-slate-600">{d.type} · {d.size}</p>
            </div>
            <button className="shrink-0 text-[10px] text-sky-400 hover:text-sky-300 transition">↓</button>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Section 24: Ask AI ─────────────────────────────────────────────────────────
function AskAI({ stock }: { stock: StockDetail }) {
  const [q, setQ] = useState("");
  const suggestions = [
    `Why is ${stock.symbol} rising?`,
    "Key government policies affecting this stock",
    "What are the main risks?",
    "Compare with peers",
    "Future opportunities",
    "Historical events impact",
  ];
  return (
    <SectionCard>
      <div className="flex items-center gap-2 mb-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-500/20 text-violet-400">
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg>
        </div>
        <h2 className="text-[15px] font-bold text-white">Ask AI About {stock.name.split(" ")[0]}</h2>
      </div>
      <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 focus-within:border-violet-500/30 transition">
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5 text-slate-500"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg>
        <input value={q} onChange={e => setQ(e.target.value)}
          placeholder={`Ask anything about ${stock.symbol}...`}
          className="flex-1 bg-transparent text-[13px] text-white outline-none placeholder:text-slate-600"/>
        {q && <button className="shrink-0 rounded-xl bg-violet-500/20 px-3 py-1.5 text-[12px] text-violet-300 hover:bg-violet-500/30 transition">Ask →</button>}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {suggestions.map((s, i) => (
          <button key={i} onClick={() => setQ(s)}
            className="rounded-full border border-white/[0.06] bg-white/[0.02] px-3 py-1 text-[11px] text-slate-400 hover:border-violet-500/30 hover:text-violet-300 transition">
            {s}
          </button>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Section 25: Right Sticky Intelligence Panel ────────────────────────────────
function IntelligencePanel({ stock }: { stock: StockDetail }) {
  const isPos = stock.pct_change >= 0;
  const ai_score = stock.dna_scores
    ? Math.round(Object.values(stock.dna_scores).reduce((a, b) => a + b, 0) / Math.max(Object.values(stock.dna_scores).length, 1))
    : 72;
  const col = scoreColor(ai_score);
  const rec_label = stock.recommendation.charAt(0).toUpperCase() + stock.recommendation.slice(1);
  const recommendations: { label: string; icon: React.ReactNode }[] = [
    { label: "Add to Watchlist",     icon: <Star className="h-4 w-4" /> },
    { label: "Set Price Alert",      icon: <Bell className="h-4 w-4" /> },
    { label: "Compare with Peers",   icon: <BarChart2 className="h-4 w-4" /> },
    { label: "Download Report",      icon: <FileText className="h-4 w-4" /> },
  ];
  return (
    <div className="space-y-5">

      {/* Quick Stats */}
      <div className={`${CARD} p-5`}>
        <h3 className="mb-3 text-[12px] font-bold uppercase tracking-wider text-slate-500">Quick Stats</h3>
        <div className="space-y-0">
          <KvRow label="Market Cap"        value={stock.market_cap}/>
          <KvRow label="Enterprise Value"  value={stock.enterprise_value}/>
          <KvRow label="PE Ratio (TTM)"    value={stock.pe}           colored/>
          <KvRow label="PB Ratio"          value={stock.pb}           colored/>
          <KvRow label="ROE"               value={stock.roe}          colored/>
          <KvRow label="ROCE"              value={stock.roce}         colored/>
          <KvRow label="Dividend Yield"    value={stock.dividend_yield}/>
          <KvRow label="Face Value"        value="₹1.00"/>
          <KvRow label="52W High"          value={`₹${stock.week52_high}`}/>
          <KvRow label="52W Low"           value={`₹${stock.week52_low}`}/>
        </div>
        <button className="mt-3 w-full text-center text-[11px] text-sky-400 hover:text-sky-300 transition">View More →</button>
      </div>

      {/* AI Rating */}
      <div className={`${CARD} p-5`}>
        <h3 className="mb-3 text-[12px] font-bold uppercase tracking-wider text-slate-500">AI Rating</h3>
        <div className="flex flex-col items-center py-3">
          <div className="relative h-24 w-24">
            <svg className="h-24 w-24" style={{ transform: "rotate(-90deg)" }} viewBox="0 0 80 80">
              <circle cx="40" cy="40" r="30" stroke="rgba(255,255,255,0.06)" strokeWidth={6} fill="none"/>
              <circle cx="40" cy="40" r="30" stroke={col} strokeWidth={6} fill="none"
                strokeLinecap="round" strokeDasharray={`${(ai_score / 100) * 2 * Math.PI * 30} ${2 * Math.PI * 30}`}
                style={{ filter: `drop-shadow(0 0 6px ${col}80)` }}/>
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-[22px] font-black" style={{ color: col }}>{ai_score}</span>
              <span className="text-[8px] text-slate-500">/ 100</span>
            </div>
          </div>
          <p className="mt-2 text-[13px] font-bold text-white">{rec_label}</p>
          <p className="text-[10px] text-slate-500">AI Investment Rating</p>
        </div>
      </div>

      {/* Event Alerts */}
      {stock.events.length > 0 && (
        <div className={`${CARD} p-5`}>
          <h3 className="mb-3 text-[12px] font-bold uppercase tracking-wider text-slate-500">Event Alerts</h3>
          <div className="space-y-2">
            {stock.events.slice(0, 3).map((e, i) => (
              <div key={i} className="flex items-start gap-2 rounded-xl border border-white/[0.05] bg-white/[0.02] p-2.5">
                <div className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400"/>
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-white line-clamp-2">{e.title}</p>
                  <p className="text-[9px] text-slate-600 mt-0.5">{e.date}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Risks */}
      <div className={`${CARD} p-5`}>
        <h3 className="mb-3 text-[12px] font-bold uppercase tracking-wider text-slate-500">Top Risks</h3>
        <div className="space-y-2">
          {[
            { text: "Execution & delivery risk", sev: 72 },
            { text: n2(stock.pe) > 40 ? "Premium valuation risk" : "Market volatility", sev: 58 },
            { text: "Regulatory / policy changes", sev: 45 },
          ].map((r, i) => (
            <div key={i} className="rounded-xl border border-rose-500/10 bg-rose-500/[0.04] p-2.5">
              <div className="flex justify-between mb-1">
                <p className="text-[11px] text-slate-300">{r.text}</p>
                <span className="text-[10px] font-bold text-rose-400">{r.sev}</span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full bg-rose-500" style={{ width: `${r.sev}%` }}/>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Top Opportunities */}
      <div className={`${CARD} p-5`}>
        <h3 className="mb-3 text-[12px] font-bold uppercase tracking-wider text-slate-500">Top Opportunities</h3>
        <div className="space-y-2">
          {[
            { text: `${stock.sector} sector expansion`, sc: 88 },
            { text: "Export order growth", sc: 74 },
            { text: "Margin improvement FY26", sc: 68 },
          ].map((o, i) => (
            <div key={i} className="rounded-xl border border-emerald-500/10 bg-emerald-500/[0.04] p-2.5">
              <div className="flex justify-between mb-1">
                <p className="text-[11px] text-slate-300">{o.text}</p>
                <span className="text-[10px] font-bold text-emerald-400">{o.sc}</span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full bg-emerald-500" style={{ width: `${o.sc}%` }}/>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Actions */}
      <div className={`${CARD} p-5`}>
        <h3 className="mb-3 text-[12px] font-bold uppercase tracking-wider text-slate-500">Quick Actions</h3>
        <div className="space-y-1.5">
          {recommendations.map(a => (
            <button key={a.label} className="flex w-full items-center justify-between rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2.5 hover:border-sky-400/20 hover:bg-white/[0.04] transition">
              <div className="flex items-center gap-2">
                <span className="text-slate-400">{a.icon}</span>
                <span className="text-[12px] text-slate-300">{a.label}</span>
              </div>
              <svg className="h-3.5 w-3.5 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
              </svg>
            </button>
          ))}
        </div>
      </div>

      {/* Export */}
      <div className={`${CARD} p-5`}>
        <h3 className="mb-3 text-[12px] font-bold uppercase tracking-wider text-slate-500">Export</h3>
        <div className="grid grid-cols-3 gap-2">
          {([{ l: "PDF", i: <FileText className="h-4 w-4 text-slate-400" /> }, { l: "Share", i: <Share2 className="h-4 w-4 text-slate-400" /> }, { l: "Copy", i: <Copy className="h-4 w-4 text-slate-400" /> }] as { l: string; i: React.ReactNode }[]).map(e => (
            <button key={e.l} className="flex flex-col items-center gap-1 rounded-xl border border-white/[0.06] bg-white/[0.02] py-2.5 hover:border-sky-400/20 hover:bg-white/[0.04] transition">
              <span className="text-slate-400">{e.i}</span>
              <span className="text-[10px] text-slate-400">{e.l}</span>
            </button>
          ))}
        </div>
      </div>

    </div>
  );
}

// ── Top Loading Bar ───────────────────────────────────────────────────────────
function TopLoader({ active }: { active: boolean }) {
  return (
    <AnimatePresence>
      {active && (
        <motion.div key="tl" initial={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.5 } }}
          className="pointer-events-none fixed left-0 right-0 top-0 z-[100] h-[2px] overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-sky-500 via-violet-500 to-sky-400"
            animate={{ x: ["-100%", "0%", "100%"] }}
            transition={{ repeat: Infinity, duration: 1.3, ease: "easeInOut" }}/>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ── Section Placeholder (while deferred sections haven't mounted yet) ─────────
function SectionSkel({ h = 180 }: { h?: number }) {
  return (
    <div className="animate-pulse rounded-[28px] border border-white/[0.05] bg-white/[0.03]"
      style={{ height: h }}/>
  );
}

// ── Full-page Skeleton (matches 2-col layout) ─────────────────────────────────
function PageSkeleton() {
  return (
    <div className="grid grid-cols-[1fr_320px] gap-6">
      <div className="space-y-6 animate-pulse">
        {/* Hero */}
        <div className="rounded-[28px] border border-white/[0.06] bg-white/[0.04] p-6">
          <div className="flex items-start gap-4">
            <div className="h-14 w-14 shrink-0 rounded-2xl bg-white/[0.06]"/>
            <div className="flex-1 space-y-2.5">
              <div className="h-7 w-56 rounded-xl bg-white/[0.06]"/>
              <div className="flex gap-2">
                {[20, 16, 24].map(w => <div key={w} className="h-5 rounded-md bg-white/[0.04]" style={{ width: `${w * 4}px` }}/>)}
              </div>
            </div>
          </div>
          <div className="mt-5 flex items-baseline gap-3">
            <div className="h-10 w-36 rounded-xl bg-white/[0.06]"/>
            <div className="h-6 w-28 rounded-lg bg-white/[0.04]"/>
          </div>
          <div className="mt-4 grid grid-cols-4 gap-3">
            {[...Array(4)].map((_, i) => <div key={i} className="h-16 rounded-2xl bg-white/[0.04]"/>)}
          </div>
        </div>
        {/* Chart */}
        <div className="rounded-[28px] border border-white/[0.06] bg-white/[0.04] p-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="h-5 w-24 rounded-lg bg-white/[0.06]"/>
            <div className="h-8 w-60 rounded-xl bg-white/[0.04]"/>
          </div>
          <div className="flex h-[260px] items-center justify-center rounded-2xl bg-white/[0.03]">
            <div className="flex items-center gap-2 text-slate-700 text-sm">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-700 border-t-slate-400"/>
              Loading chart…
            </div>
          </div>
          <div className="mt-4 grid grid-cols-6 gap-3">
            {[...Array(6)].map((_, i) => <div key={i} className="h-9 rounded-xl bg-white/[0.03]"/>)}
          </div>
        </div>
        {/* Remaining section skeletons */}
        {[160, 220, 200, 340, 180, 260].map((h, i) => (
          <div key={i} className="rounded-[28px] border border-white/[0.05] bg-white/[0.03]" style={{ height: h }}/>
        ))}
      </div>
      {/* RIGHT panel */}
      <div className="sticky top-[88px] space-y-5 animate-pulse">
        {[200, 170, 160, 150, 160, 110].map((h, i) => (
          <div key={i} className="rounded-[28px] border border-white/[0.05] bg-white/[0.03]" style={{ height: h }}/>
        ))}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function StockPage({ params }: PageProps) {
  const { symbol } = use(params);
  const [stock,        setStock]        = useState<StockDetail | null>(null);
  const [chartData,    setChartData]    = useState<any[]>([]);
  const [loadingInfo,  setLoadingInfo]  = useState(true);
  const [loadingChart, setLoadingChart] = useState(true);
  const [period,       setPeriod]       = useState("1Y");
  const [watchlisted,  setWatchlisted]  = useState(false);
  const [relatedNews,  setRelatedNews]  = useState<any[]>([]);
  const [intelOpen,    setIntelOpen]    = useState(false);

  const { data: intelligence } = useIntelligence("company", symbol?.toUpperCase());
  // Progressive section rendering: 0=nothing, 1=above-fold, 2=mid, 3=all
  const [renderGroup,  setRenderGroup]  = useState(0);

  useEffect(() => {
    setLoadingInfo(true);
    setRenderGroup(0);
    // Kick off stock data + chart + news in parallel
    Promise.all([
      fetch(`${API}/api/stocks/${symbol}`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/stocks/${symbol}/news`).then(r => r.ok ? r.json() : []).catch(() => []),
    ]).then(([data, news]) => {
      setStock(data);
      setRelatedNews(Array.isArray(news) ? news : []);
    }).finally(() => setLoadingInfo(false));
  }, [symbol]);

  // Progressive render: once stock data arrives, reveal sections in 3 waves
  useEffect(() => {
    if (!stock) return;
    setRenderGroup(1);                                    // above-fold immediately
    const t1 = setTimeout(() => setRenderGroup(2), 120); // mid-page after 120ms
    const t2 = setTimeout(() => setRenderGroup(3), 350); // deep sections after 350ms
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [stock]);

  const fetchChart = useCallback((p: string) => {
    setLoadingChart(true);
    fetch(`${API}/api/stocks/${symbol}/chart?period=${p}`)
      .then(r => r.ok ? r.json() : [])
      .then(d => setChartData(Array.isArray(d) ? d : []))
      .catch(() => setChartData([]))
      .finally(() => setLoadingChart(false));
  }, [symbol]);

  useEffect(() => { fetchChart(period); }, [symbol, period, fetchChart]);

  if (loadingInfo) return (
    <main className="min-w-0 pb-10">
      <TopLoader active/>
      <PageSkeleton/>
    </main>
  );

  if (!stock) return (
    <main className="min-w-0 flex flex-col items-center justify-center gap-4 py-24 text-center">
      <TrendingDown className="h-16 w-16 text-slate-500" />
      <h1 className="text-2xl font-semibold text-white">{symbol.toUpperCase()} not found</h1>
      <p className="text-slate-400">Not listed on NSE or backend offline.</p>
      <Link href="/companies" className="mt-2 rounded-full bg-sky-500/15 px-5 py-2 text-sm text-sky-300 hover:bg-sky-500/25 transition">← Back to Companies</Link>
    </main>
  );

  return (
    <main className="min-w-0 pb-16">
      <TrackPageVisit type="company" id={symbol.toUpperCase()} title={stock.name ?? symbol.toUpperCase()} subtitle={`${stock.price} · ${stock.sector}`} href={`/companies/${symbol.toUpperCase()}`} />
      {/* Top loader while chart is still fetching */}
      <TopLoader active={loadingChart}/>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}>
        <div className="grid grid-cols-[1fr_320px] gap-6 items-start">

          {/* ── LEFT: sections rendered in 3 progressive waves ─────── */}
          <div className="min-w-0 space-y-6">

            {/* Wave 1 — above fold: hero, chart, AI summary, DNA, financials, ratios */}
            {renderGroup >= 1 && <>
              <CompanyHero stock={stock} symbol={symbol} watchlisted={watchlisted} setWatchlisted={setWatchlisted}/>
              <PriceChart symbol={symbol} chartData={chartData} loadingChart={loadingChart}
                period={period} setPeriod={p => { setPeriod(p); fetchChart(p); }} stock={stock}/>
              <AISummary stock={stock}/>

              {/* ── Investment Intelligence — collapsed by default ──────────── */}
              <div className="overflow-hidden rounded-[20px] border border-white/[0.06] bg-white/[0.01]">
                <button
                  onClick={() => setIntelOpen(o => !o)}
                  className="flex w-full items-center gap-3 px-5 py-4 text-left transition hover:bg-white/[0.03]"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-[15px] font-bold text-white">Investment Intelligence</p>
                    <p className="mt-0.5 text-[11px] text-slate-500">Thesis · Scenarios · Opportunity stage · Monitoring · Patterns</p>
                  </div>
                  <svg className={`h-4 w-4 shrink-0 text-slate-500 transition-transform duration-200 ${intelOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
                  </svg>
                </button>

                {intelOpen && (
                  <div className="space-y-4 border-t border-white/[0.06] p-4">
                    {intelligence && (
                      <IntelligenceBlock data={intelligence} label={`${stock.name} Intelligence`} compact={false} />
                    )}
                    <InvestmentThesis
                      entityType="company"
                      entityId={stock.symbol}
                      entityTitle={stock.name}
                      entityDescription={stock.description}
                      entitySector={stock.sector}
                      thesis={stock.description ? stock.description.slice(0, 280) : `${stock.name} operates in the ${stock.sector} with analyst consensus at ${stock.recommendation}.`}
                      confidence={stock.buy_count != null && stock.analyst_count
                        ? Math.round((stock.buy_count / Math.max(stock.analyst_count, 1)) * 100)
                        : 60
                      }
                      timeHorizon={
                        (stock.recommendation === "Buy" || stock.recommendation === "Strong Buy") ? "12–18 months" : "6–12 months"
                      }
                      assumptions={[
                        `Sector tailwinds in ${stock.sector || "the sector"} continue`,
                        "Management executes on guidance",
                        "No material adverse regulatory changes",
                      ]}
                      riskFactors={[
                        parseFloat(stock.beta || "0") > 1.2 ? "High beta — elevated market correlation risk" : "Market volatility risk",
                        parseFloat(stock.debt_to_equity || "0") > 1 ? "Elevated leverage may constrain growth" : "Execution risk on growth plan",
                      ]}
                    />

                    <ScenarioAnalysis
                      entityType="company"
                      entityId={stock.symbol}
                      entityTitle={stock.name}
                      entityDescription={stock.description}
                      entitySector={stock.sector}
                      bull={{ probability: 30, description: "Strong earnings growth and sector re-rating drive outperformance.", target: stock.target_high || undefined }}
                      base={{ probability: 50, description: "Company delivers in line with consensus estimates.", target: stock.target_mean || undefined }}
                      bear={{ probability: 20, description: "Earnings miss or macro headwinds compress valuation multiples.", target: stock.target_low || undefined }}
                    />

                    <OpportunityLifecycleCard
                      stage={(() => {
                        const buyPct = stock.buy_count != null && stock.analyst_count
                          ? stock.buy_count / Math.max(stock.analyst_count, 1)
                          : 0.5;
                        const pe = parseFloat(stock.pe || "0");
                        if (buyPct > 0.7) return "strong-momentum" as const;
                        if (buyPct > 0.5) return "developing" as const;
                        if (pe > 40) return "mature" as const;
                        return "emerging" as const;
                      })()}
                      description={`Analyst consensus: ${stock.recommendation ?? "Hold"} · PE: ${stock.pe ?? "N/A"}`}
                      whyAssigned={`${stock.buy_count ?? 0} of ${stock.analyst_count ?? 0} analysts rate this a Buy. ${stock.pe ? `Current PE of ${stock.pe} reflects ` + (parseFloat(stock.pe) > 30 ? "premium valuation" : "reasonable valuation") + "." : ""}`}
                      historicalComparison={`Companies with similar analyst buy ratios in the ${stock.sector ?? "sector"} have historically delivered above-market returns over 12–18 months.`}
                      confidence={stock.analyst_count ? Math.round(Math.min(90, 50 + (stock.buy_count ?? 0) / Math.max(stock.analyst_count, 1) * 40)) : 55}
                      expectedEvolution={`If earnings trajectory holds, the opportunity is expected to ${stock.buy_count != null && stock.analyst_count && stock.buy_count / Math.max(stock.analyst_count, 1) > 0.6 ? "strengthen toward peak momentum" : "consolidate before the next catalyst"}.`}
                      risks={[
                        `Valuation re-rating risk if PE exceeds ${stock.pe ? Math.round(parseFloat(stock.pe) * 1.3) : 40}x`,
                        "Sector rotation out of growth into defensive positions",
                        "Earnings miss relative to elevated analyst expectations",
                      ]}
                    />

                    <MonitoringChecklist
                      entityType="company"
                      entityId={stock.symbol}
                      entityTitle={stock.name}
                      entityDescription={stock.description}
                      entitySector={stock.sector}
                    />
                    <PatternIntelligenceCard
                      entityType="company"
                      entityId={stock.symbol}
                      entityTitle={stock.name}
                      entityDescription={stock.description}
                      entitySector={stock.sector}
                    />

                    <RelatedContent
                      entityType="company"
                      entityId={stock.symbol}
                      title={stock.name}
                      sector={stock.sector}
                    />
                  </div>
                )}
              </div>

              {/* Share */}
              <ShareInsightCard
                entityType="company"
                entityId={stock.symbol}
                title={`${stock.name} (${stock.symbol})`}
                summary={stock.description?.slice(0, 120)}
              />

              {/* Intelligent guidance — derived from company data */}
              <NextSteps config={{
                takeaway: `${stock.name} is rated ${stock.recommendation ?? "—"} with a P/E of ${stock.pe ?? "N/A"}x — understand the valuation context before sizing a position.`,
                primary: {
                  label: `Ask AI: Is ${stock.name} fairly valued right now?`,
                  why:   `Because a P/E of ${stock.pe ?? "N/A"}x needs to be compared against sector peers and growth expectations to be meaningful.`,
                  href:  `/ai-search?q=${encodeURIComponent(`Is ${stock.name} (${stock.symbol}) fairly valued at its current price? How does its PE of ${stock.pe ?? "N/A"} compare to ${stock.sector ?? "sector"} peers and justify the current valuation?`)}`,
                },
                groups: [
                  {
                    label: "Compare",
                    actions: [
                      {
                        label: `Find ${stock.sector ?? "sector"} competitors`,
                        why:   `Because valuation only makes sense relative to alternatives — comparing peers reveals whether any premium or discount is justified.`,
                        href:  `/ai-search?q=${encodeURIComponent(`Compare ${stock.name} with the top 3 competitors in ${stock.sector ?? "its sector"} — valuation, growth rate, and risk`)}`,
                      },
                    ],
                  },
                  {
                    label: "Continue Research",
                    actions: [
                      {
                        label: `View events affecting ${stock.name}`,
                        why:   `Because the investment case must account for macro and company-specific developments — events reveal the 'why' behind price moves.`,
                        href:  `/events`,
                      },
                      {
                        label: "Trace sector ripple effects",
                        why:   `Because ${stock.sector ?? "sector"} moves create upstream and downstream implications that affect the entire thesis.`,
                        href:  `/ripple`,
                      },
                    ],
                  },
                ],
                path: [stock.sector ?? "Sector", stock.name, "Valuation", "Investment Thesis"],
              }} />

              <StockDNA stock={stock}/>
              <FinancialHighlights stock={stock}/>
              <KeyRatios stock={stock}/>
            </>}

            {/* Wave 2 — mid-page: events, gov, opportunity, news, sentiment */}
            {renderGroup >= 2 ? <>
              <EventTimeline stock={stock} symbol={symbol}/>
              <GovernmentExposureSection stock={stock}/>
              <OpportunityRadarSection stock={stock}/>
              <NewsImpact stock={stock} relatedNews={relatedNews}/>
              <AISentiment stock={stock}/>
            </> : renderGroup >= 1 && <>
              <SectionSkel h={260}/>
              <SectionSkel h={260}/>
              <SectionSkel h={220}/>
              <SectionSkel h={280}/>
              <SectionSkel h={200}/>
            </>}

            {/* Wave 3 — deep sections: network, segments, geography, order, shareholding,
                         peers, historical, forecast, stories, calendar, similar, docs, ask AI */}
            {renderGroup >= 3 ? <>
              <NetworkGraph stock={stock}/>
              <BusinessSegments stock={stock}/>
              <RevenueGeography stock={stock}/>
              <OrderBook stock={stock}/>
              <Shareholding stock={stock}/>
              <PeerComparison stock={stock}/>
              <HistoricalPerformance stock={stock}/>
              <AIForecast stock={stock}/>
              <RelatedStories stock={stock}/>
              <EconomicCalendarSection stock={stock}/>
              <SimilarCompanies stock={stock}/>
              <Documents stock={stock}/>
              <AskAI stock={stock}/>
            </> : renderGroup >= 1 && <>
              {[440, 220, 180, 200, 220, 320, 220, 300, 200, 220, 220, 240, 160].map((h, i) => (
                <SectionSkel key={i} h={h}/>
              ))}
            </>}

          </div>

          {/* ── RIGHT: sticky intelligence panel ──────────────────────── */}
          <aside className="sticky top-[88px] max-h-[calc(100vh-100px)] overflow-y-auto scrollbar-hide">
            {renderGroup >= 1
              ? <IntelligencePanel stock={stock}/>
              : <div className="animate-pulse space-y-5">
                  {[200, 170, 160, 150, 160, 110].map((h, i) => <SectionSkel key={i} h={h}/>)}
                </div>
            }
          </aside>

        </div>
      </motion.div>
    </main>
  );
}
