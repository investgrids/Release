"use client";

import { use, useEffect, useState, useCallback, useMemo, useRef, Suspense } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { TrackPageVisit } from "@/components/TrackPageVisit";
import { PatternIntelligenceCard } from "@/components/intelligence";
import { useIntelligence } from "@/hooks/useIntelligence";
import { ShareInsightCard } from "@/components/ShareInsightCard";
import { SmartCTA } from "@/components/SmartCTA";
import { CompanyIntelligenceSection } from "@/components/CompanyIntelligenceSection";
import { RelatedContent, type RelatedItem } from "@/components/RelatedContent";
import { API_BASE_URL as API } from "@/lib/api";
import { scoreToColor, impactToStyle } from "@/lib/scoring";
import {
  Star, Check, Sparkles, TrendingUp, IndianRupee, Target, Zap,
  BarChart2, TrendingDown, Landmark, Briefcase, Clock,
} from "lucide-react";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// CompanyCharts.tsx's own header comment for why.
// Company redesign Batch 0 (2026-08-25) — removed the reactflow imports/CSS
// and GovBreakdownDonut/SentimentTrendChart chart imports along with the
// fabricated NetworkGraph/GovernmentExposureSection donut/AISentiment
// weekly-trend sections that were their only callers. See
// artifacts/company_redesign_audit_spec.md §C.
const PriceAreaChart              = dynamic(() => import("./CompanyCharts").then(m => m.PriceAreaChart),              { ssr: false });
const DnaRadarChart               = dynamic(() => import("./CompanyCharts").then(m => m.DnaRadarChart),               { ssr: false });
const Sparkline                   = dynamic(() => import("./CompanyCharts").then(m => m.Sparkline),                   { ssr: false });
const ShareholdingDonut           = dynamic(() => import("./CompanyCharts").then(m => m.ShareholdingDonut),           { ssr: false });
const HistoricalPerformanceBarChart = dynamic(() => import("./CompanyCharts").then(m => m.HistoricalPerformanceBarChart), { ssr: false });


// ── Types ─────────────────────────────────────────────────────────────────────
interface StockEvent   { title: string; date: string; id?: string; slug?: string }
interface GovBreak     { label: string; pct: number; color: string }
export interface StockDetail  {
  symbol: string; canonical_symbol?: string; name: string; price: string; prev_close: string;
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
const CARD = "rounded-[28px] border border-surface-border/10 bg-text-primary/[0.04] shadow-[0_20px_60px_rgba(0,0,0,.35)] transition-all duration-300 hover:border-sky-400/20";
const PERIODS = ["1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "Max"];

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
// Company redesign Batch 3 — EventTimeline now mixes two real date shapes:
// yfinance's stock.events (already a short display string) and the real
// /api/events?company= fetch (an ISO timestamp). Parses when it looks like
// a real date, falls back to the raw string otherwise, rather than risking
// "Invalid Date" on a value that was already display-formatted.
function formatEventDate(raw: string): string {
  if (!raw) return raw;
  const d = new Date(raw);
  if (isNaN(d.getTime())) return raw;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
const scoreColor = scoreToColor;
const impactColor = impactToStyle;

function metricColor(label: string, value: string) {
  const n = n2(value);
  if (label === "PE Ratio (TTM)") return n < 15 ? "text-emerald-400" : n < 30 ? "text-text-primary" : n < 50 ? "text-amber-400" : "text-rose-400";
  if (label === "PB Ratio")       return n < 1   ? "text-emerald-400" : n < 3  ? "text-text-primary" : "text-amber-400";
  if (label === "ROE" || label === "ROCE") return n > 20 ? "text-emerald-400" : n > 10 ? "text-text-primary" : "text-amber-400";
  if (label === "Beta")           return n < 0.8 ? "text-emerald-400" : n < 1.3 ? "text-text-primary" : "text-rose-400";
  if (label === "D/E Ratio")      return n < 0.3 ? "text-emerald-400" : n < 1   ? "text-text-primary" : "text-rose-400";
  return "text-text-primary";
}

// Real, live shareholding split from yfinance (`held_institutions` /
// `held_insiders`, already fetched in market_data.py from
// info.heldPercentInstitutions / heldPercentInsiders). Only two of the
// four SEBI categories are available from this data source — "Insiders"
// approximates Promoters, "Institutions" approximates combined FII+DII —
// so this is intentionally a 3-way split (Insiders / Institutions /
// Public & Others), not a fabricated 4-way Promoter/FII/DII/Retail chart.
// Returns null when yfinance has no holdings data for this stock, so the
// UI can show an honest "unavailable" state instead of guessing.
function deriveShareholding(stock: StockDetail) {
  const insiders     = n2(stock.held_insiders);
  const institutions = n2(stock.held_institutions);
  const hasInsiders     = !!stock.held_insiders && stock.held_insiders !== "—";
  const hasInstitutions = !!stock.held_institutions && stock.held_institutions !== "—";
  if (!hasInsiders && !hasInstitutions) return null;

  const other = Math.max(0, Math.round((100 - insiders - institutions) * 10) / 10);
  return [
    { name: "Insiders (Promoters)",   value: Math.round(insiders * 10) / 10,     color: "#6366f1" },
    { name: "Institutions (FII+DII)", value: Math.round(institutions * 10) / 10, color: "#38bdf8" },
    { name: "Public & Others",        value: other,                              color: "#f59e0b" },
  ].filter(d => d.value > 0);
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
          {title && <h2 className="text-[15px] font-bold text-text-primary">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </motion.div>
  );
}

function Pill({ children, color = "slate" }: { children: React.ReactNode; color?: string }) {
  const cls: Record<string, string> = {
    slate: "border-surface-border/10 bg-text-primary/[0.05] text-text-secondary",
    green: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
    sky:   "border-sky-500/30 bg-sky-500/10 text-sky-600 dark:text-sky-300",
    amber: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-300",
    violet:"border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-300",
    rose:  "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-300",
  };
  return <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium ${cls[color] ?? cls.slate}`}>{children}</span>;
}

function ScoreCircle({ score, size = 52 }: { score: number; size?: number }) {
  const col = scoreColor(score);
  const r = (size - 6) / 2, circ = 2 * Math.PI * r, dash = (Math.abs(score) / 100) * circ;
  return (
    <div className="relative flex items-center justify-center shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} stroke="rgb(var(--text-primary) / 0.08)" strokeWidth={4} fill="none"/>
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
    <div className="flex items-center justify-between gap-2 py-2 border-b border-surface-border/4 last:border-0">
      <span className="text-[12px] text-text-muted shrink-0">{label}</span>
      <span className={`text-[13px] font-semibold text-right ${colored ? metricColor(label, value) : "text-text-primary"}`}>{value || "—"}</span>
    </div>
  );
}

function MiniBar({ label, value, max = 100, color }: { label: string; value: number; max?: number; color: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div>
      <div className="mb-1 flex justify-between text-[11px]">
        <span className="text-text-secondary">{label}</span>
        <span className="font-bold text-text-primary">{value}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-text-primary/[0.06]">
        <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }}/>
      </div>
    </div>
  );
}

// ── Section 1: Company Hero ───────────────────────────────────────────────────
// Batch B (2026-08-25, Company Simplification spec) — this header
// previously showed "AI Score" as the average of Stock DNA sub-scores,
// silently substituting a hardcoded 72 when dna_scores was absent. That
// number had nothing to do with the real, evidence-backed Company Score
// (company_score_engine.py, served at /api/company-scores/{symbol} and
// already shown honestly elsewhere on this page — CompanyScoreContributors,
// OpportunityRadarSection). Worse, IntelligencePanel's sidebar "AI Rating"
// gauge (visible on every tab) duplicated the exact same fabricated
// StockDNA-or-72 number under a second label ("AI Investment Rating") —
// two competing, both-fake headline ratings on every page load. Fixed by
// making the header the single place a real Company Score is shown,
// sourced from the real endpoint, with an honest "Insufficient evidence"
// state instead of a fabricated number — never omitted silently, per the
// owner's spec, so it stays a real, ever-present promise: there IS one
// rating here, and it is either real or explicitly marked as not yet
// available.
function useCompanyRating(symbol: string) {
  const [rating, setRating] = useState<CompanyScoreData | null | undefined>(undefined);
  useEffect(() => {
    let cancelled = false;
    setRating(undefined);
    fetch(`${API}/api/company-scores/${symbol}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (!cancelled) setRating(d); })
      .catch(() => { if (!cancelled) setRating(null); });
    return () => { cancelled = true; };
  }, [symbol]);
  return rating;
}

function CompanyHero({ stock, symbol, watchlisted, setWatchlisted, serverRenderedH1 }: {
  stock: StockDetail; symbol: string; watchlisted: boolean; setWatchlisted: (v: boolean) => void; serverRenderedH1: boolean;
}) {
  const isPos = stock.pct_change >= 0;
  const sign  = isPos ? "+" : "";
  const rating = useCompanyRating(stock.symbol);
  const hasRealRating = !!rating && rating.signal_count > 0 && rating.score != null;

  return (
    <motion.div variants={fadeUp} initial="hidden" animate="show"
      className={`${CARD} p-6`}>
      {/* Breadcrumb */}
      <div className="mb-4 flex items-center gap-2 text-[11px] text-text-muted">
        <Link href="/companies" className="hover:text-text-secondary transition">Companies</Link>
        <span>›</span>
        <span className="text-text-secondary">{stock.name}</span>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-6">
        {/* Left: identity + price */}
        <div>
          {/* Company avatar + name */}
          <div className="flex items-center gap-4 mb-3">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500/30 to-violet-500/20 border border-surface-border/10 text-[18px] font-black text-text-primary">
              {symbol.slice(0, 2)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                {/* The server wrapper (page.tsx) renders the real <h1>
                    when it found the stock server-side (the common case) —
                    falls back to rendering it here too if that fetch ever
                    came back empty, so the page is never left with zero
                    <h1>s. */}
                {serverRenderedH1 ? (
                  <p className="text-[26px] font-black tracking-tight text-text-primary leading-none">{stock.name}</p>
                ) : (
                  <h1 className="text-[26px] font-black tracking-tight text-text-primary leading-none">{stock.name}</h1>
                )}
                <button onClick={() => setWatchlisted(!watchlisted)}
                  className="transition">
                  {watchlisted ? <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" /> : <Star className="h-3.5 w-3.5 text-text-secondary" />}
                </button>
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <Pill><span className="font-bold text-sky-600 dark:text-sky-300">{symbol.toUpperCase()}</span></Pill>
                <Pill color="green"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400"/>NSE</Pill>
                {stock.sector && stock.sector !== "N/A" && <Pill>{stock.sector}</Pill>}
                {stock.industry && stock.industry !== "N/A" && stock.industry !== stock.sector && <Pill>{stock.industry}</Pill>}
              </div>
            </div>
          </div>

          {/* Price */}
          <div className="flex flex-wrap items-baseline gap-3">
            <span className="text-[40px] font-black text-text-primary leading-none">₹{stock.price}</span>
            <span className={`text-[18px] font-bold ${isPos ? "text-emerald-400" : "text-rose-400"}`}>
              {sign}{stock.change_abs} ({sign}{stock.pct_change.toFixed(2)}%) {isPos ? "▲" : "▼"}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-text-muted">
            {new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "long", year: "numeric" })} ·
            <span className="ml-1 text-text-secondary">NSE</span>
          </p>
        </div>

        {/* Right: KPI cards + actions */}
        <div className="flex flex-col gap-4 items-end">
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Market Cap",   value: stock.market_cap },
              { label: "PE Ratio",     value: stock.pe },
              { label: "Dividend",     value: stock.dividend_yield },
            ].map(k => (
              <div key={k.label} className="rounded-2xl border border-surface-border/10 bg-text-primary/[0.03] px-4 py-3 text-center min-w-[90px]">
                <p className="text-[9px] uppercase tracking-widest text-text-muted">{k.label}</p>
                <p className="mt-1 text-[14px] font-black text-text-primary">{k.value || "—"}</p>
              </div>
            ))}
            {/* The one real, primary MarketRipple rating for this company —
                see useCompanyRating above for why this replaced the old
                fabricated "AI Score" tile. */}
            <div className={`rounded-2xl border px-4 py-3 text-center min-w-[90px] ${
              hasRealRating ? "border-emerald-500/20 bg-emerald-500/[0.05]" : "border-surface-border/10 bg-text-primary/[0.03]"
            }`}>
              <p className="text-[9px] uppercase tracking-widest text-text-muted">MarketRipple Score</p>
              {rating === undefined ? (
                <p className="mt-1 text-[14px] font-black text-text-muted">···</p>
              ) : hasRealRating ? (
                <p className="mt-1 text-[14px] font-black text-emerald-500">{Math.round(rating!.score!)}/100</p>
              ) : (
                <p className="mt-1 text-[11px] font-semibold text-text-muted" title="No real published analysis or opportunity signal exists for this company yet.">Insufficient evidence</p>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setWatchlisted(!watchlisted)}
              className={`flex items-center gap-1.5 rounded-xl border px-4 py-2 text-[12px] font-medium transition ${
                watchlisted ? "border-sky-500/40 bg-sky-500/15 text-sky-600 dark:text-sky-300" : "border-surface-border/10 bg-text-primary/[0.03] text-text-secondary hover:border-surface-border/20"
              }`}>
              {watchlisted ? <><Check className="h-3.5 w-3.5" />Watchlisted</> : "+ Add to Watchlist"}
            </button>
            <Link href={`/companies?tab=compare&a=${symbol}`}
              className="rounded-xl border border-surface-border/10 bg-text-primary/[0.03] px-4 py-2 text-[12px] font-medium text-text-secondary hover:border-sky-500/30 hover:text-sky-600 dark:text-sky-300 transition">
              ↔ Compare
            </Link>
            <Link href={`/ai-search?q=${encodeURIComponent(`Should I buy ${stock.name} (${symbol}) right now? Analyse its current valuation, recent events, and outlook vs sector peers.`)}`}
              className="flex items-center gap-1.5 rounded-xl border border-surface-border/10 bg-text-primary/[0.03] px-4 py-2 text-[12px] font-medium text-violet-600 dark:text-violet-300 hover:border-violet-500/30 hover:bg-violet-500/[0.06] transition">
              <Sparkles className="h-3.5 w-3.5 text-violet-400" /> Ask AI
            </Link>
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
      <div className="flex gap-0.5 bg-text-primary/[0.03] rounded-xl p-0.5">
        {PERIODS.map(p => (
          <button key={p} onClick={() => setPeriod(p)}
            className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
              period === p ? "bg-text-primary/10 text-text-primary" : "text-text-muted hover:text-text-secondary"}`}>
            {p}
          </button>
        ))}
      </div>
    }>
      <div className="h-[260px] mt-4">
        {loadingChart ? (
          <div className="flex h-full items-center justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-surface-border/20 border-t-sky-400"/>
          </div>
        ) : chartData.length > 0 ? (
          <PriceAreaChart chartData={chartData} chartColor={chartColor} />
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-text-muted">No chart data for this period</p>
          </div>
        )}
      </div>

      {/* OHLC strip */}
      <div className="mt-4 grid grid-cols-6 gap-3 border-t border-surface-border/5 pt-4">
        {[
          ["Open",     `₹${stock.open}`],
          ["High",     `₹${stock.day_high}`],
          ["Low",      `₹${stock.day_low}`],
          ["Prev. Close",`₹${stock.prev_close}`],
          ["52W High", `₹${stock.week52_high}`],
          ["52W Low",  `₹${stock.week52_low}`],
        ].map(([l, v]) => (
          <div key={l} className="text-center">
            <p className="text-[9px] text-text-muted uppercase tracking-wide">{l}</p>
            <p className="mt-0.5 text-[12px] font-bold text-text-primary">{v}</p>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Section 3: About ──────────────────────────────────────────────────────────
// Batch C (2026-08-25) — replaced "AI Company Summary": that card's
// fabricated generic fallback paragraph and false "AI Generated"
// provenance badge (both fixed in Batch B) and its threshold-derived
// "Bullish Factors"/"Key Risks" lists (redundant with
// CompanyScoreContributors' real, better-sourced positive/negative
// evidence on the Intelligence tab) are gone. See AboutSection below,
// defined alongside the rest of Batch C's Overview components.

// ── Section 4: Stock DNA ──────────────────────────────────────────────────────
function StockDNA({ stock }: { stock: StockDetail }) {
  const scores = stock.dna_scores;
  const entries = Object.entries(scores);
  if (!entries.length) return null;
  return (
    <SectionCard title="Stock DNA" action={
      <span className="text-[11px] text-text-muted">What makes this company move?</span>
    }>
      <div className="mt-4 grid grid-cols-3 gap-3 sm:grid-cols-5">
        {entries.map(([k, v], i) => (
          <motion.div key={k} custom={i} variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }}
            className="group flex flex-col items-center gap-2 rounded-3xl border border-surface-border/6 bg-surface-card p-4 text-center hover:border-sky-400/20 hover:-translate-y-0.5 transition-all">
            <div className="relative h-12 w-12">
              <svg className="h-12 w-12" style={{ transform: "rotate(-90deg)" }}>
                <circle cx="24" cy="24" r="19" stroke="rgb(var(--text-primary) / 0.08)" strokeWidth={4} fill="none"/>
                <circle cx="24" cy="24" r="19" stroke={scoreColor(v)} strokeWidth={4} fill="none"
                  strokeLinecap="round" strokeDasharray={`${(v / 100) * 2 * Math.PI * 19} ${2 * Math.PI * 19}`}/>
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-[11px] font-black" style={{ color: scoreColor(v) }}>{v}</span>
            </div>
            <p className="text-[10px] text-text-secondary leading-tight">{k}</p>
          </motion.div>
        ))}
      </div>
      {/* Radar mini */}
      <div className="mt-5 flex items-center gap-6">
        <div className="w-48 shrink-0">
          <DnaRadarChart entries={entries as [string, number][]} />
        </div>
        <div className="flex-1 space-y-2">
          {entries.map(([k, v]) => (
            <div key={k}>
              <div className="mb-0.5 flex justify-between text-[11px]">
                <span className="text-text-secondary">{k}</span>
                <span className="font-bold" style={{ color: scoreColor(v) }}>{v}/100</span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-text-primary/[0.06]">
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
    <SectionCard title="Financial Highlights">
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {kpis.map((k, i) => (
          <motion.div key={k.label} custom={i} variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }}
            className="rounded-2xl border border-surface-border/6 bg-surface-card p-4 hover:border-sky-400/20 hover:-translate-y-0.5 transition-all">
            <div className="mb-2 flex items-center">{k.icon}</div>
            <p className={`text-[22px] font-black leading-none ${k.color}`}>
              {k.value.toLocaleString("en-IN")}{k.suffix}
            </p>
            <p className="mt-1 text-[10px] text-text-muted">{k.label}</p>
            {/* Sparkline */}
            <div className="mt-2 h-8">
              <Sparkline
                data={(k.label === "Revenue" ? stock.quarterly_revenue : stock.quarterly_net_income).slice(-6)}
                stroke={k.color.replace("text-","").includes("sky") ? "#38bdf8" : "#22c55e"}
              />
            </div>
          </motion.div>
        ))}
      </div>

      {/* Annual table */}
      {stock.annual_financials.length > 0 && (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-surface-border/6">
                <th className="pb-2 text-left text-[10px] text-text-muted font-medium">₹ in Crore</th>
                {stock.annual_financials.map(f => <th key={f.year} className="pb-2 text-right text-[10px] text-text-muted font-medium">{f.year}</th>)}
                <th className="pb-2 text-right text-[10px] text-violet-400 font-medium">TTM</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/3">
              <tr>
                <td className="py-2 text-text-secondary">Revenue</td>
                {/* Real, pre-existing hydration bug found live while testing the
                    new Financials sub-tabs (2026-08-25): unqualified
                    toLocaleString() formats digit grouping using the runtime's
                    default locale, which differs between the Node.js SSR pass
                    and the browser (e.g. "877,835" server vs "8,77,835"
                    client), causing React to discard and re-render this whole
                    tree. Explicit locale makes both passes agree. */}
                {stock.annual_financials.map(f => <td key={f.year} className="py-2 text-right font-semibold text-text-primary">{f.revenue.toLocaleString("en-IN")}</td>)}
                <td className="py-2 text-right font-bold text-violet-600 dark:text-violet-300">{stock.quarterly_revenue.reduce((a, b) => a + b.value, 0).toLocaleString("en-IN")}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">Net Profit</td>
                {stock.annual_financials.map(f => <td key={f.year} className={`py-2 text-right font-semibold ${f.net_income >= 0 ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300"}`}>{f.net_income.toLocaleString("en-IN")}</td>)}
                <td className="py-2 text-right font-bold text-emerald-600 dark:text-emerald-300">{stock.quarterly_net_income.reduce((a, b) => a + b.value, 0).toLocaleString("en-IN")}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">ROE (%)</td>
                {stock.annual_financials.map((f, i) => <td key={f.year} className="py-2 text-right text-text-primary">{i === stock.annual_financials.length - 1 ? stock.roe : "—"}</td>)}
                <td className="py-2 text-right text-violet-600 dark:text-violet-300">{stock.roe}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">EPS (₹)</td>
                {stock.annual_financials.map((f, i) => <td key={f.year} className="py-2 text-right text-text-primary">{i === stock.annual_financials.length - 1 ? stock.eps : "—"}</td>)}
                <td className="py-2 text-right text-violet-600 dark:text-violet-300">{stock.eps}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">Debt/Equity</td>
                {stock.annual_financials.map((f, i) => <td key={f.year} className="py-2 text-right text-text-primary">{i === stock.annual_financials.length - 1 ? stock.debt_to_equity : "—"}</td>)}
                <td className="py-2 text-right text-violet-600 dark:text-violet-300">{stock.debt_to_equity}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

// ── Section 6: Key Ratios ─────────────────────────────────────────────────────
// Company redesign Batch 0 (2026-08-25) — removed the "vs Industry Avg"
// action label: no industry-average value was ever fetched or rendered
// anywhere in this section (a dead third array column existed but was
// never read by the JSX below) — the label was purely aspirational text
// with zero backing data. See artifacts/company_redesign_audit_spec.md §C.
function KeyRatios({ stock }: { stock: StockDetail }) {
  const rows = [
    ["PE Ratio (TTM)",  stock.pe],
    ["Forward PE",      stock.forward_pe],
    ["PB Ratio",        stock.pb],
    ["ROE",             stock.roe],
    ["ROCE",            stock.roce],
    ["EPS (TTM)",       stock.eps ? `₹${stock.eps}` : "—"],
    ["Beta",            stock.beta],
    ["D/E Ratio",       stock.debt_to_equity],
    ["Dividend Yield",  stock.dividend_yield],
    ["Current Ratio",   stock.current_ratio],
  ];
  return (
    <SectionCard title="Key Ratios">
      <div className="mt-3 grid grid-cols-2 gap-x-8 divide-x divide-surface-border/4">
        <div>{rows.slice(0, 5).map(([l, v]) => <KvRow key={l} label={l} value={v} colored/>)}</div>
        <div className="pl-8">{rows.slice(5).map(([l, v]) => <KvRow key={l} label={l} value={v} colored/>)}</div>
      </div>
    </SectionCard>
  );
}

// ── Section 7: Event Timeline ─────────────────────────────────────────────────
// Note: StockEvent only carries {title, date} — there is no real per-event
// impact/sentiment score from the backend, so this intentionally does not
// show an impact badge, sentiment badge, or score circle (a previous
// version faked all three from a hardcoded cycling array).
// Company redesign Batch 3 — companyEvents (real, symbol-matched events
// from GET /api/events?company={symbol}, the same real matching logic
// related.py's "company" branch already used) takes priority over
// stock.events (yfinance's own sparse corporate-action list, frequently
// empty — confirmed live for RELIANCE). Falls back to stock.events only
// when the richer real fetch itself returns nothing, so a company still
// covered only by yfinance's own event data doesn't lose it.
function EventTimeline({ stock, symbol, companyEvents }: { stock: StockDetail; symbol: string; companyEvents?: StockEvent[] }) {
  const events = (companyEvents && companyEvents.length > 0) ? companyEvents : stock.events;
  if (!events.length) return null;
  return (
    <SectionCard title={`Recent Events Impacting ${symbol.toUpperCase()}`} action={
      <Link href="/events" className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View All Events →</Link>
    }>
      <div className="mt-4 space-y-3">
        {events.map((e, i) => {
          const href = e.slug || e.id ? `/events/${e.slug || e.id}` : null;
          const body = (
            <>
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-sky-500/15">
                <Clock className="h-5 w-5 text-sky-400"/>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[10px] text-text-muted mb-1">{formatEventDate(e.date)}</p>
                <p className="text-[13px] font-semibold text-text-primary line-clamp-1">{e.title}</p>
              </div>
            </>
          );
          const className = "flex items-start gap-4 rounded-2xl border border-surface-border/6 bg-text-primary/[0.02] p-4 hover:border-sky-400/20 hover:bg-sky-400/[0.02] transition";
          return href ? (
            <Link key={i} href={href} className={className}>{body}</Link>
          ) : (
            <motion.div key={i} custom={i} variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }} className={className}>
              {body}
            </motion.div>
          );
        })}
      </div>
    </SectionCard>
  );
}

// ── Related Opportunities (Batch 3) ─────────────────────────────────────────
// The real gap this closes: the Opportunities tab previously only showed
// an abstract AI Company Score (OpportunityRadarSection, below) with no
// actual list of which real Opportunity records this company is linked
// to. Fetches the same unified /api/related/company/{symbol} contract
// Batch 0 already made canonical (company_intelligence.get_related_
// opportunities — dispatches V1/V2 by settings.opportunity_v2_promoted
// transparently; this tab never branches on that itself, so it already
// satisfies "canonical V2 relationships only, no V1 compatibility UI" —
// there is no V1-shaped UI here, just real title/href/score fields common
// to both sources). Honest empty state when this company has no real
// linked opportunities yet.
function RelatedOpportunitiesList({ stock }: { stock: StockDetail }) {
  const [items, setItems] = useState<RelatedItem[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/related/company/${encodeURIComponent(stock.symbol)}?${new URLSearchParams({ title: stock.name, ...(stock.sector ? { sector: stock.sector } : {}) })}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (!cancelled) setItems(d?.opportunities ?? []); })
      .catch(() => { if (!cancelled) setItems([]); });
    return () => { cancelled = true; };
  }, [stock.symbol, stock.name, stock.sector]);

  if (items === null) return null;

  return (
    <SectionCard title={`Opportunities Connected to ${stock.name}`}>
      {items.length === 0 ? (
        <p className="text-sm text-text-secondary">No real opportunities are currently linked to {stock.name}.</p>
      ) : (
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {items.map((o, i) => (
            <Link key={o.id || i} href={o.href as any}
              className="flex items-center justify-between gap-3 rounded-2xl border border-surface-border/6 bg-text-primary/[0.02] p-4 transition hover:border-emerald-500/25">
              <p className="text-[13px] font-medium leading-5 text-text-primary line-clamp-2">{o.title}</p>
              {o.score != null && (
                <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-bold text-emerald-600 dark:text-emerald-300">{Math.round(o.score)}</span>
              )}
            </Link>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

// ── Section 9: AI Company Intelligence Score ──────────────────────────────────
// Previously "Opportunity Radar" — 3 entirely fabricated cards (invented
// titles like "Export Opportunity", scores/confidence/revenue/timeline that
// were never computed from anything, just hardcoded numbers plus one fake
// formula on market_cap). Replaced with the real AI Company Intelligence
// Score engine (company_score_engine.py) — real signals extracted from
// every published article's companies_affected[] and every opportunity's
// real per-company impact_score, aggregated with real recency decay. Hides
// entirely rather than showing a fabricated fallback when a company has no
// real signals yet.
interface CompanyScoreContributor {
  reason: string | null; source_type: "article" | "opportunity"; href: string | null;
  signed_magnitude: number; signal_at: string | null;
}
interface CompanyScoreVerdict { label: string; tone: string; reasoning: string }
interface CompanyScoreData {
  symbol: string; score: number | null; confidence: number | null;
  signal_count: number; sector: string | null;
  top_contributors: CompanyScoreContributor[];
  // Real fields company_score_engine.py already returns (positive_reasons/
  // risk_factors are the same weighted signals as top_contributors, just
  // split by sign) — added Batch 2 so the Intelligence tab can show real
  // negative contributors instead of the fabricated "Top Risks" removed
  // in Batch 0.
  trend?: "up" | "down" | "neutral";
  risk_level?: "Low" | "Medium" | "High";
  verdict?: CompanyScoreVerdict | null;
  positive_reasons?: CompanyScoreContributor[];
  risk_factors?: CompanyScoreContributor[];
}

function OpportunityRadarSection({ stock }: { stock: StockDetail }) {
  const [data, setData] = useState<CompanyScoreData | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/company-scores/${stock.symbol}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (!cancelled) setData(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [stock.symbol]);

  if (!data || data.signal_count === 0) return null;

  return (
    <SectionCard title="AI Company Intelligence Score" action={<span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-600 dark:text-emerald-300">AI Powered</span>}>
      <div className="mt-2 flex items-center gap-6 rounded-2xl border border-surface-border/6 bg-gradient-to-b from-text-primary/[0.03] to-transparent p-4">
        <div className="text-center">
          <p className="text-[36px] font-black leading-none text-text-primary">{data.score}</p>
          <p className="mt-1 text-[9px] uppercase tracking-wider text-text-muted">AI Score</p>
        </div>
        <div className="flex-1 space-y-1.5">
          <div className="flex justify-between text-[10px]">
            <span className="text-text-muted">Confidence</span>
            <span className="font-semibold text-emerald-400">{data.confidence != null ? `${Math.round(data.confidence * 100)}%` : "—"}</span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-text-primary/[0.06]">
            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${data.confidence != null ? Math.round(data.confidence * 100) : 0}%` }} />
          </div>
          <p className="text-[10px] text-text-muted">Based on {data.signal_count} real signal{data.signal_count === 1 ? "" : "s"} from published analysis and opportunity tracking</p>
        </div>
      </div>
      {data.top_contributors.length > 0 && (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {data.top_contributors.map((c, i) => {
            // SEO P1-P2, 2026-08-24 — real, backend-resolved link to the
            // opportunity this signal actually came from (was label-only
            // before; the id was always real, just never surfaced as a link).
            const inner = (
              <>
                <div className="flex items-center justify-between">
                  <span className="rounded-full border border-surface-border/10 bg-text-primary/5 px-2 py-0.5 text-[9px] uppercase tracking-wide text-text-muted">
                    {c.source_type === "opportunity" ? "Opportunity Radar" : "Published Analysis"}
                  </span>
                  <span className={`text-[11px] font-bold ${c.signed_magnitude >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {c.signed_magnitude >= 0 ? "+" : ""}{Math.round(c.signed_magnitude)}
                  </span>
                </div>
                <p className="text-[12px] leading-5 text-text-secondary">{c.reason || "—"}</p>
                {c.signal_at && (
                  <p className="mt-auto text-[10px] text-text-muted">{new Date(c.signal_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</p>
                )}
              </>
            );
            const className = "flex flex-col gap-2 rounded-2xl border border-surface-border/6 bg-gradient-to-b from-text-primary/[0.03] to-transparent p-4";
            return c.href ? (
              <motion.div key={i} custom={i} variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }}>
                <Link href={c.href as any} className={`${className} transition hover:border-emerald-500/25`}>{inner}</Link>
              </motion.div>
            ) : (
              <motion.div key={i} custom={i} variants={fadeUp} initial="hidden" whileInView="show" viewport={{ once: true }} className={className}>
                {inner}
              </motion.div>
            );
          })}
        </div>
      )}
    </SectionCard>
  );
}

// ── Section 10: News Impact ───────────────────────────────────────────────────
// Note: only `impact_score` is real (deterministic, keyword-based, computed
// server-side in news_fetcher.py). There is no real per-article sentiment
// classification anywhere in the pipeline, so this intentionally does not
// show a Positive/Negative/Neutral badge (a previous version faked both the
// score and the sentiment from hardcoded cycling arrays).
function NewsImpact({ stock, relatedNews }: { stock: StockDetail; relatedNews: any[] }) {
  const articles = relatedNews.length ? relatedNews : stock.news;
  if (!articles.length) return null;
  return (
    <SectionCard title="News Impact Analysis" action={
      <Link href="/news" className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View All News →</Link>
    }>
      <div className="mt-4 space-y-3">
        {articles.slice(0, 5).map((a: any, i: number) => {
          const hasScore = typeof a.impact_score === "number";
          const score = hasScore ? Math.round(a.impact_score * 10) : 0;
          const ic = impactColor(score);
          return (
            <div key={i} className="flex items-start gap-3 rounded-2xl border border-surface-border/5 bg-text-primary/[0.02] p-4 hover:border-sky-400/10 transition">
              {/* Thumbnail placeholder */}
              <div className={`h-14 w-14 shrink-0 rounded-xl ${["bg-gradient-to-br from-sky-500/20 to-violet-500/10","bg-gradient-to-br from-emerald-500/20 to-teal-500/10","bg-gradient-to-br from-rose-500/20 to-amber-500/10","bg-gradient-to-br from-amber-500/20 to-orange-500/10","bg-gradient-to-br from-violet-500/20 to-indigo-500/10"][i % 5]} flex items-center justify-center text-text-secondary`}>
                {([<BarChart2 className="h-6 w-6" />, <TrendingUp className="h-6 w-6" />, <TrendingDown className="h-6 w-6" />, <Landmark className="h-6 w-6" />, <Briefcase className="h-6 w-6" />])[i % 5]}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-1.5 mb-1">
                  {hasScore && <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold ${ic.text} border-current/20`}>{ic.label}</span>}
                  <span className="text-[10px] text-text-muted">{a.source || "Source"}</span>
                  <span className="text-[10px] text-text-muted">{a.published_at?.slice(0, 10) || ""}</span>
                </div>
                <p className="text-[13px] font-semibold text-text-primary line-clamp-2">{a.headline}</p>
                {a.summary && <p className="mt-0.5 text-[11px] text-text-muted line-clamp-1">{a.summary}</p>}
              </div>
              {hasScore && <ScoreCircle score={score} size={44}/>}
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}

// ── Section 11: AI Sentiment ──────────────────────────────────────────────────
// Company redesign Batch 0 (2026-08-25) — was called "AI Sentiment
// Analysis" and showed a "Bullish % Weekly Trend" chart where 4 of its 6
// points were hardcoded literals (55/58/62/60) identical for every
// company, and bullPct/bearPct silently fell back to hardcoded 62%/15%
// for a company with no real analyst data — presented with the same
// styling as fully real sections, no disclosure. Now: real donut only
// (Finnhub buy/hold/sell counts), honest empty state when no analyst
// coverage exists, and relabeled to make clear this is third-party
// analyst consensus, not a MarketRipple-generated sentiment score. See
// artifacts/company_redesign_audit_spec.md §C.
function AISentiment({ stock }: { stock: StockDetail }) {
  const total = stock.buy_count + stock.hold_count + stock.sell_count;
  if (!total) {
    return (
      <SectionCard title="Analyst Consensus">
        <p className="mt-4 text-[12px] text-text-muted">No analyst coverage data available for this stock.</p>
      </SectionCard>
    );
  }
  const bullPct = Math.round((stock.buy_count / total) * 100);
  const bearPct = Math.round((stock.sell_count / total) * 100);
  const neutPct = 100 - bullPct - bearPct;

  return (
    <SectionCard title="Analyst Consensus">
      <div className="mt-4 flex items-center gap-3">
        <div className="relative h-24 w-24">
          <svg className="h-24 w-24" style={{ transform: "rotate(-90deg)" }} viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="32" stroke="rgb(var(--text-primary) / 0.08)" strokeWidth={8} fill="none"/>
            <circle cx="40" cy="40" r="32" stroke="#22c55e" strokeWidth={8} fill="none"
              strokeLinecap="round" strokeDasharray={`${(bullPct / 100) * 2 * Math.PI * 32} ${2 * Math.PI * 32}`}/>
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[18px] font-black text-emerald-400">{bullPct}%</span>
            <span className="text-[8px] text-text-muted">Bullish</span>
          </div>
        </div>
        <div className="space-y-2">
          <div><div className="flex justify-between text-[11px] mb-0.5"><span className="text-emerald-400">Bullish</span><span className="text-text-primary font-bold">{bullPct}%</span></div><div className="h-1.5 rounded-full bg-text-primary/[0.06] overflow-hidden"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${bullPct}%` }}/></div></div>
          <div><div className="flex justify-between text-[11px] mb-0.5"><span className="text-amber-400">Neutral</span><span className="text-text-primary font-bold">{neutPct}%</span></div><div className="h-1.5 rounded-full bg-text-primary/[0.06] overflow-hidden"><div className="h-full rounded-full bg-amber-500" style={{ width: `${neutPct}%` }}/></div></div>
          <div><div className="flex justify-between text-[11px] mb-0.5"><span className="text-rose-400">Bearish</span><span className="text-text-primary font-bold">{bearPct}%</span></div><div className="h-1.5 rounded-full bg-text-primary/[0.06] overflow-hidden"><div className="h-full rounded-full bg-rose-500" style={{ width: `${bearPct}%` }}/></div></div>
        </div>
      </div>
      <p className="mt-3 text-[11px] text-text-muted">Based on {stock.analyst_count} analyst rating{stock.analyst_count === 1 ? "" : "s"} — third-party analyst consensus, not a MarketRipple-generated score.</p>
    </SectionCard>
  );
}

// ── Section 16: Shareholding ──────────────────────────────────────────────────
function Shareholding({ stock }: { stock: StockDetail }) {
  const data = useMemo(() => deriveShareholding(stock), [stock.held_insiders, stock.held_institutions]);
  if (!data) {
    return (
      <SectionCard title="Shareholding Pattern">
        <p className="mt-4 text-[12px] text-text-muted">Shareholding data unavailable for this stock.</p>
      </SectionCard>
    );
  }
  return (
    <SectionCard title="Shareholding Pattern">
      <div className="mt-4 grid grid-cols-2 gap-5">
        <div className="h-[180px]">
          <ShareholdingDonut data={data} />
        </div>
        <div className="space-y-3">
          {data.map(d => (
            <div key={d.name}>
              <div className="flex justify-between text-[12px] mb-1">
                <div className="flex items-center gap-1.5">
                  <div className="h-2 w-2 rounded-full shrink-0" style={{ background: d.color }}/>
                  <span className="text-text-secondary">{d.name}</span>
                </div>
                <span className="font-bold text-text-primary">{d.value}%</span>
              </div>
              <div className="h-1 overflow-hidden rounded-full bg-text-primary/[0.06]">
                <div className="h-full rounded-full" style={{ width: `${d.value}%`, background: d.color }}/>
              </div>
            </div>
          ))}
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

  // Company redesign Batch 0 (2026-08-25) — removed the "Revenue Growth"
  // column: self always showed a hardcoded "+12%", every peer always
  // showed "—" (never fetched/computed) — real for zero of the rows it
  // appeared on. See artifacts/company_redesign_audit_spec.md §C.
  const rows = [
    { symbol: stock.symbol, name: stock.name, price: `₹${stock.price}`, pe: stock.pe, roe: stock.roe, isSelf: true },
    ...stock.peers.slice(0, 5).map(p => {
      const d = peerData[p];
      return { symbol: p, name: d?.name || p, price: d ? `₹${d.price}` : "—", pe: d?.pe || "—", roe: d?.roe || "—", isSelf: false };
    }),
  ];

  return (
    <SectionCard title="Peer Comparison" action={
      <Link href="/companies?tab=compare" className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View All Peers →</Link>
    }>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-surface-border/6">
              {["Company", "Price", "PE (TTM)", "ROE (%)", ""].map(h => (
                <th key={h} className="pb-3 text-left text-[10px] text-text-muted font-medium first:text-left text-right last:text-right">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border/3">
            {rows.map(r => (
              <tr key={r.symbol} className={`hover:bg-text-primary/[0.02] transition ${r.isSelf ? "bg-sky-500/[0.04]" : ""}`}>
                <td className="py-3">
                  <div className="flex items-center gap-2">
                    <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold ${r.isSelf ? "bg-sky-500/20 text-sky-600 dark:text-sky-300" : "bg-text-primary/[0.06] text-text-secondary"}`}>
                      {r.symbol.slice(0, 2)}
                    </div>
                    <div>
                      <Link href={`/companies/${r.symbol}`} className={`font-semibold hover:text-sky-600 dark:text-sky-300 transition ${r.isSelf ? "text-sky-600 dark:text-sky-300" : "text-text-primary"}`}>{r.symbol}</Link>
                      <p className="text-[10px] text-text-muted truncate max-w-[100px]">{r.name}</p>
                    </div>
                    {r.isSelf && <span className="rounded-full bg-sky-500/20 px-1.5 py-0.5 text-[8px] font-bold text-sky-600 dark:text-sky-300">YOU</span>}
                  </div>
                </td>
                <td className="py-3 text-right font-semibold text-text-primary">{loading && !r.isSelf ? <div className="ml-auto h-3 w-12 animate-pulse rounded bg-text-primary/[0.06]"/> : r.price}</td>
                <td className="py-3 text-right font-semibold text-text-primary">{r.pe || "—"}</td>
                <td className="py-3 text-right font-semibold text-emerald-600 dark:text-emerald-300">{r.roe || "—"}</td>
                <td className="py-3 text-right">
                  {!r.isSelf && <Link href={`/companies/${r.symbol}`} className="text-[10px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View →</Link>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

// ── Section 17b: Compare With (real, published research pages only) ─────────
// SEO roadmap — "Compare {symbol} With" surfaces existing comparison_publisher.py
// articles for this company's real peers. Deliberately shows nothing for a
// peer that doesn't have a published comparison yet rather than linking to a
// page that 404s — the comparison scheduler (comparison_scheduler.py) fills
// these in gradually; this section just reflects whatever's real right now.
function CompareWithSection({ stock }: { stock: StockDetail }) {
  const [comparisons, setComparisons] = useState<{ slug: string; headline: string; companies_affected: { symbol: string }[] }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/insights/comparisons?symbol=${stock.symbol}&limit=8`)
      .then(r => r.ok ? r.json() : { items: [] })
      .then(d => setComparisons(d.items ?? []))
      .catch(() => setComparisons([]))
      .finally(() => setLoading(false));
  }, [stock.symbol]);

  if (loading) return null;
  if (comparisons.length === 0) return null;

  return (
    <SectionCard title={`Compare ${stock.symbol} With`} action={
      <Link href="/research/comparisons" className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View All Comparisons →</Link>
    }>
      <div className="mt-3 space-y-2">
        {comparisons.map(c => {
          const other = c.companies_affected?.find(x => x.symbol !== stock.symbol);
          return (
            <Link key={c.slug} href={`/research/${c.slug}`}
              className="flex items-center justify-between rounded-[12px] border border-surface-border/7 bg-text-primary/[0.02] px-4 py-2.5 transition hover:border-violet-500/25 hover:bg-text-primary/[0.04]">
              <span className="flex items-center gap-2.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/15 text-[10px] font-bold text-violet-600 dark:text-violet-300">
                  {(other?.symbol ?? "?").slice(0, 2)}
                </span>
                <span className="text-[13px] font-semibold text-text-primary">{other?.symbol ?? c.headline}</span>
              </span>
              <span className="text-[11px] font-medium text-violet-400">Compare →</span>
            </Link>
          );
        })}
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
            className={`rounded-lg px-3 py-1.5 text-[12px] font-medium transition ${activeMetric === k ? "bg-sky-500/20 text-sky-600 dark:text-sky-300" : "text-text-muted hover:text-text-secondary"}`}>
            {l}
          </button>
        ))}
      </div>
      <div className="h-[180px]">
        <HistoricalPerformanceBarChart data={data} activeMetric={activeMetric} />
      </div>
    </SectionCard>
  );
}

// ── Section 20: Related Stories ────────────────────────────────────────────────
interface CompanyInsightArticle {
  slug: string; headline: string; article_type: string; angle: string;
  key_takeaway: string | null; published_at: string | null;
}
interface CompanyInsightHistorical {
  event: string; date: string | null; category: string | null;
  outcome: number | null; key_lesson: string | null;
}

const ARTICLE_TYPE_TAG: Record<string, string> = {
  company_intelligence: "Company", sector_intelligence: "Sector", theme_intelligence: "Theme",
  policy_intelligence: "Policy", question_intelligence: "Q&A", market_wrap: "Market Wrap",
  morning_intelligence: "Morning Brief", breaking_intelligence: "Breaking",
  historical_intelligence: "Historical", educational_intelligence: "Guide",
};

function RelatedStories({ stock }: { stock: StockDetail }) {
  const [articles, setArticles] = useState<CompanyInsightArticle[]>([]);
  const [historical, setHistorical] = useState<CompanyInsightHistorical[]>([]);
  const [campaignCount, setCampaignCount] = useState(0);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // This page already opens ~18 concurrent same-origin requests plus the
    // app-wide SSE connection (AlertProvider) that never releases its slot —
    // under HTTP/1.1's 6-connections-per-origin cap in dev, a fetch queued
    // this late can starve indefinitely. Bound it so the section fails soft
    // (renders nothing) instead of showing a permanent loading skeleton.
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10_000);
    fetch(`${API}/api/insights/company/${stock.symbol}?limit=6`, { signal: controller.signal })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (cancelled || !d) return;
        setArticles(d.articles || []);
        setHistorical(d.historical_events || []);
        setCampaignCount(d.campaign_count || 0);
      })
      .catch(() => {})
      .finally(() => { clearTimeout(timeout); if (!cancelled) setLoaded(true); });
    return () => { cancelled = true; clearTimeout(timeout); controller.abort(); };
  }, [stock.symbol]);

  if (loaded && articles.length === 0 && historical.length === 0) return null;

  return (
    <SectionCard title="Latest Intelligence" action={<Link href="/newsroom" className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View All →</Link>}>
      {!loaded ? (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {[1, 2, 3].map(i => <div key={i} className="h-24 animate-pulse rounded-2xl bg-text-primary/[0.03]" />)}
        </div>
      ) : (
        <>
          {campaignCount > 0 && (
            <p className="mt-3 text-[11px] text-text-muted">
              {stock.symbol} is covered across {campaignCount} publishing {campaignCount === 1 ? "campaign" : "campaigns"}.
            </p>
          )}
          {articles.length > 0 && (
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              {articles.map(a => (
                <Link key={a.slug} href={`/newsroom/article/${a.slug}` as any}
                  className="group flex flex-col justify-between rounded-2xl border border-surface-border/6 bg-text-primary/[0.02] p-4 hover:-translate-y-0.5 hover:border-sky-400/20 transition-all">
                  <div>
                    <span className="text-[9px] uppercase tracking-widest text-text-muted">{ARTICLE_TYPE_TAG[a.article_type] ?? a.article_type}</span>
                    <p className="mt-1 text-[13px] font-bold leading-snug text-text-primary line-clamp-2 group-hover:text-sky-700 dark:text-sky-200 transition">{a.headline}</p>
                  </div>
                  {a.key_takeaway && <p className="mt-2 text-[11px] text-text-muted line-clamp-2">{a.key_takeaway}</p>}
                </Link>
              ))}
            </div>
          )}
          {historical.length > 0 && (
            <div className="mt-4 border-t border-surface-border/5 pt-4">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-text-muted">Historical Coverage</p>
              <div className="space-y-1.5">
                {historical.slice(0, 4).map((h, i) => (
                  <div key={i} className="flex items-center justify-between text-[11px]">
                    <span className="text-text-secondary line-clamp-1">{h.event}</span>
                    <span className="shrink-0 text-text-muted ml-2">{h.date}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </SectionCard>
  );
}

// ── Section 25: Right Sticky Intelligence Panel ────────────────────────────────
// ── Overview grid (Batch 2) ─────────────────────────────────────────────────
// The compact Overview per the redesign's own target mockup: a scannable
// grid of real facts (market data, most recent real development, a
// financial snapshot, most recent real material event) plus the top real
// opportunity and one real positive/counter-signal pair — never the whole
// deep-dive content those tabs already carry. Every cell hides itself when
// its real data is missing rather than showing a placeholder.
function OverviewCell({ label, children, href }: { label: string; children: React.ReactNode; href?: string | null }) {
  const inner = (
    <>
      <p className="text-[10px] uppercase tracking-wider text-text-muted">{label}</p>
      <div className="mt-1.5">{children}</div>
    </>
  );
  const cls = "rounded-2xl border border-surface-border/6 bg-text-primary/[0.02] p-4";
  return href
    ? <Link href={href as any} className={`${cls} block transition hover:border-sky-400/20`}>{inner}</Link>
    : <div className={cls}>{inner}</div>;
}

// Batch C (Company Simplification spec, §3) — OverviewGrid's 6-cell mixed
// grid (market data + financials + latest news + latest event + top
// opportunity + score reasons, all flattened into one undifferentiated
// grid) is replaced by the spec's own explicit Overview sequence: About →
// Key Data → MarketRipple View → Latest Developments → Opportunity
// preview, each answering one distinct question rather than one grid
// answering five at once. Every field here is still the same real data
// OverviewGrid already used — nothing new is fetched or invented, only
// regrouped and given room to be read as a conclusion rather than a cell.

// About — 1-3 real sentences, honest omission when there's no real
// description. This replaced the old "AI Company Summary" card's
// description role; that card's fabricated generic fallback and
// mislabeled "AI Generated" badge (Batch B) and its threshold-derived
// bullish/risk lists (redundant with CompanyScoreContributors' real,
// better-sourced positive/negative evidence on the Intelligence tab) are
// both gone rather than carried forward here.
function AboutSection({ stock }: { stock: StockDetail }) {
  if (!stock.description) return null;
  const sentences = stock.description.split(/(?<=[.!?])\s+/).filter(Boolean).slice(0, 3);
  return (
    <SectionCard title="About">
      <p className="mt-2 text-[13px] leading-6 text-text-secondary">{sentences.join(" ")}</p>
    </SectionCard>
  );
}

// Key Data — compact, real market + financial facts only.
function KeyDataGrid({ stock }: { stock: StockDetail }) {
  return (
    <SectionCard title="Key Data">
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[13px] sm:grid-cols-3">
        <div><p className="text-[10px] uppercase tracking-wider text-text-muted">Day Range</p><p className="mt-0.5 font-semibold text-text-primary">₹{stock.day_low}–₹{stock.day_high}</p></div>
        <div><p className="text-[10px] uppercase tracking-wider text-text-muted">52W Range</p><p className="mt-0.5 font-semibold text-text-primary">₹{stock.week52_low}–₹{stock.week52_high}</p></div>
        <div><p className="text-[10px] uppercase tracking-wider text-text-muted">Volume</p><p className="mt-0.5 font-semibold text-text-primary">{stock.volume || "—"}</p></div>
        <div><p className="text-[10px] uppercase tracking-wider text-text-muted">P/E</p><p className={`mt-0.5 font-semibold ${metricColor("PE Ratio (TTM)", stock.pe)}`}>{stock.pe || "—"}</p></div>
        <div><p className="text-[10px] uppercase tracking-wider text-text-muted">ROE</p><p className={`mt-0.5 font-semibold ${metricColor("ROE", stock.roe)}`}>{stock.roe || "—"}</p></div>
        <div><p className="text-[10px] uppercase tracking-wider text-text-muted">D/E</p><p className={`mt-0.5 font-semibold ${metricColor("D/E Ratio", stock.debt_to_equity)}`}>{stock.debt_to_equity || "—"}</p></div>
        <div><p className="text-[10px] uppercase tracking-wider text-text-muted">Margin</p><p className="mt-0.5 font-semibold text-text-primary">{stock.net_margins || "—"}</p></div>
      </div>
    </SectionCard>
  );
}

// MarketRipple View — the same real rating useCompanyRating (see
// CompanyHero above) already fetches, presented as a conclusion: score,
// verdict, one real helping/holding-back reason each, link to the full
// Intelligence tab. Honest "insufficient evidence" state when there's no
// real signal — never a second, different number than the header's.
function MarketRippleViewCard({ stock }: { stock: StockDetail }) {
  const rating = useCompanyRating(stock.symbol);
  if (rating === undefined) return null;
  const hasRealRating = !!rating && rating.signal_count > 0 && rating.score != null;
  const helping = rating?.positive_reasons?.find(r => r.reason);
  const holdingBack = rating?.risk_factors?.find(r => r.reason);

  return (
    <SectionCard title="MarketRipple View" action={
      <Link href={`/companies/${stock.symbol}?tab=intelligence` as any} className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View Intelligence →</Link>
    }>
      {!hasRealRating ? (
        <p className="mt-3 text-[13px] text-text-muted">Insufficient evidence for a MarketRipple view on {stock.name} yet — this is built only from real published analysis and opportunity tracking, never estimated.</p>
      ) : (
        <div className="mt-3 space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-[28px] font-black leading-none text-text-primary">{Math.round(rating!.score!)}</span>
            {rating!.verdict?.label && (
              <Pill color={rating!.risk_level === "High" ? "rose" : rating!.risk_level === "Low" ? "green" : "amber"}>{rating!.verdict!.label}</Pill>
            )}
          </div>
          {rating!.verdict?.reasoning && <p className="text-[13px] leading-6 text-text-secondary">{rating!.verdict!.reasoning}</p>}
          {(helping || holdingBack) && (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {helping && (
                <p className="flex items-start gap-1.5 text-[12px] leading-5 text-text-secondary">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400"/> {helping.reason}
                </p>
              )}
              {holdingBack && (
                <p className="flex items-start gap-1.5 text-[12px] leading-5 text-text-secondary">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400"/> {holdingBack.reason}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </SectionCard>
  );
}

// Latest Developments — the most recent real news headline and material
// event, in one small list rather than two separate grid cells.
function LatestDevelopmentsList({ stock, relatedNews }: { stock: StockDetail; relatedNews: any[] }) {
  const latestNews = (relatedNews.length ? relatedNews : stock.news)?.[0];
  const latestEvent = stock.events?.[0];
  if (!latestNews && !latestEvent) return null;
  return (
    <SectionCard title="Latest Developments" action={
      <Link href="/events" className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View all →</Link>
    }>
      <div className="mt-3 space-y-2.5">
        {latestEvent && (
          <OverviewCell label="Latest Material Event" href={latestEvent.slug || latestEvent.id ? `/events/${latestEvent.slug || latestEvent.id}` : null}>
            <p className="text-[13px] font-medium leading-5 text-text-primary line-clamp-2">{latestEvent.title}</p>
            {latestEvent.date && <p className="mt-1 text-[11px] text-text-muted">{latestEvent.date}</p>}
          </OverviewCell>
        )}
        {latestNews && (
          // No external link — headline is real, but the source is
          // third-party; see feedback_no_external_links.md (attribution is
          // plain text only, matching NewsImpact's own existing behavior).
          <OverviewCell label="Latest News">
            <p className="text-[13px] font-medium leading-5 text-text-primary line-clamp-2">{latestNews.headline}</p>
            <p className="mt-1 text-[11px] text-text-muted">
              {latestNews.source || "Source"}{latestNews.published_at ? ` · ${latestNews.published_at.slice(0, 10)}` : ""}
            </p>
          </OverviewCell>
        )}
      </div>
    </SectionCard>
  );
}

// FAQ — moved here (client component) from page.tsx (server component)
// after a real dev-mode React warning ("missing key" on ForwardRef
// (motion.div), owner CompanyPage) traced to passing a pre-built Server
// Component element across the RSC boundary as a prop, then rendering it
// at a conditionally-shifting position deep in a heavily data-dependent
// tree — reproduced only for companies with fewer real FAQ entries
// (0-analyst-coverage companies), never for RELIANCE. Passing the plain
// `faqs` data instead and building the JSX here is the standard, robust
// Next.js pattern; the markup is still fully present in the server-
// rendered initial HTML (Next.js SSRs client components too), so nothing
// about the real SEO/AEO behavior this replaced changes.
function FaqSection({ faqs }: { faqs: { question: string; answer: string }[] }) {
  if (!faqs.length) return null;
  return (
    <SectionCard>
      <h2 className="mb-2 text-[11px] font-bold uppercase tracking-wide text-text-muted">Frequently Asked Questions</h2>
      <div className="space-y-1.5">
        {faqs.map(f => (
          <details key={f.question} className="group rounded-lg border border-surface-border/6 bg-text-primary/[0.015] px-3 py-2">
            <summary className="cursor-pointer list-none text-[12.5px] font-medium text-text-secondary marker:content-none">
              {f.question}
            </summary>
            <p className="mt-1.5 text-[12px] leading-5 text-text-muted">{f.answer}</p>
          </details>
        ))}
      </div>
    </SectionCard>
  );
}

// Opportunity preview — the single top real linked Opportunity, if any.
function OpportunityPreview({ stock }: { stock: StockDetail }) {
  const [related, setRelated] = useState<Record<string, RelatedItem[]> | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/related/company/${encodeURIComponent(stock.symbol)}?${new URLSearchParams({ title: stock.name, ...(stock.sector ? { sector: stock.sector } : {}) })}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (!cancelled) setRelated(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [stock.symbol, stock.name, stock.sector]);

  const topOpportunity = related?.opportunities?.[0];
  if (!topOpportunity) return null;

  return (
    <SectionCard title="Current Opportunity" action={
      <Link href={`/companies/${stock.symbol}?tab=opportunities` as any} className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View all →</Link>
    }>
      <OverviewCell label="Linked Opportunity" href={topOpportunity.href}>
        <p className="text-[13px] font-medium leading-5 text-text-primary line-clamp-2">{topOpportunity.title}</p>
        {topOpportunity.score != null && (
          <p className="mt-1 text-[11px] text-emerald-400">Score {Math.round(topOpportunity.score)}</p>
        )}
      </OverviewCell>
    </SectionCard>
  );
}

// Company redesign Batch 0 (2026-08-25) — removed the hardcoded
// "Face Value: ₹1.00" row (real NSE face values vary widely across
// companies — ₹1/₹2/₹5/₹10 — this was simply wrong for most of them) and
// the dead "View More" button. Removed Top Risks/Top Opportunities
// entirely (fabricated text + hardcoded severities/scores, identical
// structure for every company) rather than carry them into the redesign
// — their real replacement (company_score_engine.py's real weighted
// negative/positive contributors) is Batch 2 work, not a Batch 0 patch.
// Removed Quick Actions (4 dead buttons) and Export (3 dead buttons,
// duplicating the real, working ShareInsightCard already rendered
// elsewhere on this page) entirely. See
// artifacts/company_redesign_audit_spec.md §C.
// Batch B (2026-08-25) — removed the "AI Rating" gauge that used to sit
// here: it computed the exact same fabricated StockDNA-average-or-72
// number as CompanyHero's old "AI Score" tile (see useCompanyRating above
// for the full explanation), labeled "AI Investment Rating", and — because
// this panel is sticky on every tab — sat on screen at the same time as
// the header's rating, presenting two different numbers under two
// different labels as if they were two separate real ratings. The header
// now carries the one real MarketRipple Score; nothing here should
// re-derive a second one.
function IntelligencePanel({ stock }: { stock: StockDetail }) {
  return (
    <div className="space-y-5">

      {/* Quick Stats */}
      <div className={`${CARD} p-5`}>
        <h3 className="mb-3 text-[12px] font-bold uppercase tracking-wider text-text-muted">Quick Stats</h3>
        <div className="space-y-0">
          <KvRow label="Market Cap"        value={stock.market_cap}/>
          <KvRow label="Enterprise Value"  value={stock.enterprise_value}/>
          <KvRow label="PE Ratio (TTM)"    value={stock.pe}           colored/>
          <KvRow label="PB Ratio"          value={stock.pb}           colored/>
          <KvRow label="ROE"               value={stock.roe}          colored/>
          <KvRow label="ROCE"              value={stock.roce}         colored/>
          <KvRow label="Dividend Yield"    value={stock.dividend_yield}/>
          <KvRow label="52W High"          value={`₹${stock.week52_high}`}/>
          <KvRow label="52W Low"           value={`₹${stock.week52_low}`}/>
        </div>
      </div>

      {/* Event Alerts */}
      {stock.events.length > 0 && (
        <div className={`${CARD} p-5`}>
          <h3 className="mb-3 text-[12px] font-bold uppercase tracking-wider text-text-muted">Event Alerts</h3>
          <div className="space-y-2">
            {stock.events.slice(0, 3).map((e, i) => {
              const href = e.slug || e.id ? `/events/${e.slug || e.id}` : null;
              const inner = (
                <>
                  <div className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400"/>
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium text-text-primary line-clamp-2">{e.title}</p>
                    <p className="text-[9px] text-text-muted mt-0.5">{e.date}</p>
                  </div>
                </>
              );
              const cls = "flex items-start gap-2 rounded-xl border border-surface-border/5 bg-text-primary/[0.02] p-2.5";
              return href
                ? <Link key={i} href={href} className={`${cls} hover:border-sky-400/20 transition`}>{inner}</Link>
                : <div key={i} className={cls}>{inner}</div>;
            })}
          </div>
        </div>
      )}

    </div>
  );
}

// ── Company Score Contributors (Batch 2) ───────────────────────────────────────
// Intelligence tab, per the redesign audit: real Company Score
// contributors — including real negative ones — replacing the fabricated
// "Top Risks"/"Top Opportunities" cards removed in Batch 0. Fetches the
// same /api/company-scores/{symbol} endpoint OpportunityRadarSection
// (Opportunities tab) already uses, but renders company_score_engine.py's
// own positive/negative split instead of collapsing everything into one
// |magnitude|-sorted list — the FACT/EVIDENCE (real supporting signal) vs
// COUNTER-SIGNAL (real disagreeing signal) distinction the audit required.
function ContributorRow({ c, tone }: { c: CompanyScoreContributor; tone: "positive" | "negative" }) {
  const positive = tone === "positive";
  const inner = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide ${
          positive
            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
            : "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-300"
        }`}>
          {positive ? "Evidence" : "Counter-Signal"}
        </span>
        <span className={`text-[11px] font-bold ${positive ? "text-emerald-400" : "text-rose-400"}`}>
          {c.signed_magnitude >= 0 ? "+" : ""}{Math.round(c.signed_magnitude)}
        </span>
      </div>
      <p className="mt-1.5 text-[12px] leading-5 text-text-secondary">{c.reason || "—"}</p>
      {c.signal_at && (
        <p className="mt-1.5 text-[10px] text-text-muted">
          {c.source_type === "opportunity" ? "From opportunity tracking" : "From published analysis"} ·{" "}
          {new Date(c.signal_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
        </p>
      )}
    </>
  );
  const cls = "rounded-2xl border border-surface-border/6 bg-text-primary/[0.02] p-3.5";
  return c.href
    ? <Link href={c.href as any} className={`${cls} block transition hover:border-surface-border/[0.15]`}>{inner}</Link>
    : <div className={cls}>{inner}</div>;
}

function CompanyScoreContributors({ stock }: { stock: StockDetail }) {
  const [data, setData] = useState<CompanyScoreData | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/company-scores/${stock.symbol}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (!cancelled) setData(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [stock.symbol]);

  if (!data) return null;

  if (data.signal_count === 0) {
    return (
      <SectionCard title="AI Company Score">
        <p className="text-sm text-text-secondary">No AI Company Score evidence tracked for {stock.name} yet — this score is built only from real published analysis and opportunity tracking, never estimated.</p>
      </SectionCard>
    );
  }

  const positives = data.positive_reasons?.filter(r => r.reason) ?? [];
  const negatives = data.risk_factors?.filter(r => r.reason) ?? [];

  return (
    <SectionCard title="AI Company Score" action={<span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-600 dark:text-emerald-300">AI Powered</span>}>
      <div className="mt-2 flex flex-wrap items-center gap-6 rounded-2xl border border-surface-border/6 bg-gradient-to-b from-text-primary/[0.03] to-transparent p-4">
        <div className="text-center">
          <p className="text-[36px] font-black leading-none text-text-primary">{data.score}</p>
          <p className="mt-1 text-[9px] uppercase tracking-wider text-text-muted">AI Score</p>
        </div>
        <div className="min-w-[160px] flex-1 space-y-1.5">
          <div className="flex justify-between text-[10px]">
            <span className="text-text-muted">Confidence</span>
            <span className="font-semibold text-emerald-400">{data.confidence != null ? `${Math.round(data.confidence * 100)}%` : "—"}</span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-text-primary/[0.06]">
            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${data.confidence != null ? Math.round(data.confidence * 100) : 0}%` }} />
          </div>
          <p className="text-[10px] text-text-muted">Based on {data.signal_count} real signal{data.signal_count === 1 ? "" : "s"} from published analysis and opportunity tracking</p>
        </div>
        <div className="flex gap-2">
          {data.risk_level && <Pill color={data.risk_level === "High" ? "rose" : data.risk_level === "Low" ? "green" : "amber"}>{data.risk_level} Risk</Pill>}
          {data.trend && data.trend !== "neutral" && <Pill color={data.trend === "up" ? "green" : "rose"}>{data.trend === "up" ? "Trending Up" : "Trending Down"}</Pill>}
        </div>
      </div>
      {data.verdict?.reasoning && (
        <p className="mt-3 text-[11px] text-text-muted">{data.verdict.reasoning}</p>
      )}

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div>
          <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-emerald-500">Real Supporting Evidence</p>
          {positives.length > 0 ? (
            <div className="space-y-2.5">
              {positives.map((c, i) => <ContributorRow key={i} c={c} tone="positive"/>)}
            </div>
          ) : (
            <p className="text-[12px] text-text-muted">No positive signals in the current evidence.</p>
          )}
        </div>
        <div>
          <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-rose-500">Real Counter-Signals</p>
          {negatives.length > 0 ? (
            <div className="space-y-2.5">
              {negatives.map((c, i) => <ContributorRow key={i} c={c} tone="negative"/>)}
            </div>
          ) : (
            <p className="text-[12px] text-text-muted">No disagreeing signals in the current evidence.</p>
          )}
        </div>
      </div>
    </SectionCard>
  );
}

// Batch D (Company Simplification spec, §4) — the Intelligence tab
// previously stacked CompanyScoreContributors, CompanyIntelligenceSection,
// StockDNA, AISentiment, a FULL IntelligenceBlock (opportunities, risks,
// company stances, sectors, themes, historical context AND monitoring
// points all rendered at once, compact={false}, single-column — the
// heaviest of its own display modes), InvestmentThesis, ScenarioAnalysis
// (including unsupported 30/50/20 Bull/Base/Bear percentages),
// OpportunityLifecycleCard, and MonitoringChecklist — 9 competing AI
// surfaces on one tab, several fabricated/unsupported (removed below),
// several real but duplicating each other (e.g. IntelligenceBlock's
// "Opportunities"/"Company Stance"/"Sectors" fields — built for
// multi-entity contexts like the homepage or a theme page — showing
// OTHER companies/sectors on a page about ONE company; already covered
// more usefully by the Opportunities tab, Overview's Current Opportunity,
// and CompanyScoreContributors' own real evidence).
//
// What's real and unique in that IntelligenceBlock payload that nothing
// else on this page shows: monitoring_points — genuinely a "What to
// Watch" list, not duplicated anywhere. Pulled out on its own, minimal,
// instead of carrying the rest of that payload along with it.
function WhatToWatchCard({ points }: { points: string[] }) {
  if (!points.length) return null;
  return (
    <SectionCard title="What to Watch">
      <ul className="mt-3 space-y-1.5">
        {points.map((pt, i) => (
          <li key={i} className="flex items-start gap-2 text-[12px] leading-5 text-text-secondary">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" />
            {pt}
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}

// Stock DNA and Pattern Intelligence are real, but neither is one of the
// tab's 5 core concepts (MarketRipple View lives on Overview; Why This
// View/What Changed/Key Evidence are CompanyScoreContributors +
// CompanyIntelligenceSection; What to Watch is above) — tucked behind
// progressive disclosure so they're available without competing with the
// primary read. Collapsed by default.
function MoreAnalysisDisclosure({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between rounded-xl border border-surface-border/10 bg-text-primary/[0.02] px-4 py-3 text-[12px] font-medium text-text-secondary hover:bg-text-primary/[0.04] transition">
        <span>{open ? "Hide" : "Show"} more analysis (Stock DNA, Pattern Intelligence)</span>
        <span className="text-text-muted">{open ? "▲" : "▼"}</span>
      </button>
      {open && <div className="mt-4 space-y-6">{children}</div>}
    </div>
  );
}

// ── Financials sub-tabs (Income Statement / Balance Sheet / Cash Flow) ──────
// Real annual+quarterly data from GET /api/stocks/{symbol}/financials —
// see market_data.py::get_stock_financials's own docstring for the real
// yfinance row labels this is built on and why real coverage varies (a
// smaller company can return entirely empty statements; even RELIANCE
// has zero quarterly cash-flow data from this source). One fetch covers
// all three statements, made only once the Financials tab is opened, not
// on the main company page load.
interface StatementPeriod { period: string; [field: string]: string | number | null }
interface StatementData { annual: StatementPeriod[]; quarterly: StatementPeriod[] }
interface CompanyFinancialsData {
  symbol: string;
  income_statement: StatementData;
  balance_sheet: StatementData;
  cash_flow: StatementData;
}

interface StatementFieldDef { key: string; label: string; suffix?: string; prefix?: string }

const INCOME_STATEMENT_FIELDS: StatementFieldDef[] = [
  { key: "revenue",             label: "Revenue" },
  { key: "ebitda",               label: "EBITDA" },
  { key: "operating_profit",     label: "Operating Profit" },
  { key: "pbt",                  label: "PBT" },
  { key: "tax_expense",          label: "Tax Expense" },
  { key: "effective_tax_rate",   label: "Effective Tax Rate", suffix: "%" },
  { key: "net_profit",           label: "Net Profit" },
  { key: "eps",                  label: "EPS", prefix: "₹" },
];
const BALANCE_SHEET_FIELDS: StatementFieldDef[] = [
  { key: "total_assets",         label: "Total Assets" },
  { key: "cash_and_equivalents", label: "Cash & Equivalents" },
  { key: "receivables",          label: "Receivables" },
  { key: "inventory",            label: "Inventory" },
  { key: "total_debt",           label: "Total Debt" },
  { key: "total_liabilities",    label: "Total Liabilities" },
  { key: "shareholders_equity",  label: "Shareholders' Equity" },
  { key: "net_debt",             label: "Net Debt" },
];
const CASH_FLOW_FIELDS: StatementFieldDef[] = [
  { key: "cash_from_operations", label: "Cash from Operations" },
  { key: "capex",                label: "Capex" },
  { key: "free_cash_flow",       label: "Free Cash Flow" },
  { key: "cash_from_investing",  label: "Cash from Investing" },
  { key: "cash_from_financing",  label: "Cash from Financing" },
  { key: "dividends",            label: "Dividends" },
  { key: "net_change_in_cash",   label: "Net Change in Cash" },
];

// Real, transparent derived trend — a plain YoY % change computed from
// two adjacent real annual values already shown in the table, never a
// fabricated/estimated growth figure. Only rendered when both real
// values exist; never shown for quarterly (adjacent quarters aren't a
// meaningful YoY comparison) or when either side is missing/zero.
function yoyPct(curr: number | null | undefined, prev: number | null | undefined): number | null {
  if (curr == null || prev == null || prev === 0) return null;
  return Math.round(((curr - prev) / Math.abs(prev)) * 1000) / 10;
}

function fmtStatementValue(v: number | null | undefined, field: StatementFieldDef): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  const formatted = field.prefix === "₹" ? v.toFixed(2) : abs >= 1000 ? Math.round(v).toLocaleString("en-IN") : v.toFixed(1);
  return `${field.prefix ?? ""}${formatted}${field.suffix ?? ""}`;
}

function StatementTable({ title, data, fields, showYoy }: {
  title: string; data: StatementData | undefined; fields: StatementFieldDef[]; showYoy?: boolean;
}) {
  const [period, setPeriod] = useState<"annual" | "quarterly">("annual");
  const rows = data?.[period] ?? [];

  if (!data || (data.annual.length === 0 && data.quarterly.length === 0)) {
    return (
      <SectionCard title={title}>
        <p className="text-sm text-text-secondary">No real {title.toLowerCase()} data available for this company yet.</p>
      </SectionCard>
    );
  }

  const hasAnnual = data.annual.length > 0;
  const hasQuarterly = data.quarterly.length > 0;

  return (
    <SectionCard title={title} action={
      hasAnnual && hasQuarterly ? (
        <div className="flex gap-1 rounded-full border border-surface-border/10 bg-text-primary/[0.03] p-0.5">
          {(["annual", "quarterly"] as const).map(p => (
            <button key={p} onClick={() => setPeriod(p)}
              className={`rounded-full px-3 py-1 text-[11px] font-medium capitalize transition ${
                period === p ? "bg-sky-500/20 text-sky-600 dark:text-sky-300" : "text-text-muted hover:text-text-secondary"
              }`}>
              {p}
            </button>
          ))}
        </div>
      ) : null
    }>
      {rows.length === 0 ? (
        <p className="text-sm text-text-secondary">No real {period} {title.toLowerCase()} data available — {hasAnnual ? "annual" : "quarterly"} data is real and shown above.</p>
      ) : (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-surface-border/6">
                <th className="pb-2 text-left text-[10px] font-medium text-text-muted">₹ in Crore</th>
                {rows.map(r => <th key={r.period} className="pb-2 text-right text-[10px] font-medium text-text-muted">{r.period}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/3">
              {fields.map(field => (
                <tr key={field.key}>
                  <td className="py-2 text-text-secondary">{field.label}</td>
                  {rows.map((r, i) => {
                    const v = r[field.key] as number | null;
                    const prevV = period === "annual" ? (rows[i + 1]?.[field.key] as number | null) : null;
                    const yoy = showYoy && period === "annual" && (field.key === "revenue" || field.key === "net_profit") ? yoyPct(v, prevV) : null;
                    return (
                      <td key={r.period} className="py-2 text-right font-semibold text-text-primary">
                        {fmtStatementValue(v, field)}
                        {yoy != null && (
                          <span className={`ml-1.5 text-[10px] font-medium ${yoy >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                            {yoy >= 0 ? "▲" : "▼"}{Math.abs(yoy)}%
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

const FINANCIALS_SUB_TABS = [
  { id: "overview", label: "Overview" },
  { id: "income",   label: "Income Statement" },
  { id: "balance",  label: "Balance Sheet" },
  { id: "cashflow", label: "Cash Flow" },
] as const;
type FinancialsSubTab = typeof FINANCIALS_SUB_TABS[number]["id"];

function FinancialsSubNav({ active, onChange }: { active: FinancialsSubTab; onChange: (t: FinancialsSubTab) => void }) {
  return (
    <nav
      aria-label="Financials sections"
      className="sticky top-[104px] z-20 -mx-1 mb-4 flex gap-1 overflow-x-auto border-b border-surface-border/8 bg-surface-base/90 px-1 py-1 backdrop-blur scrollbar-hide lg:top-[128px]"
    >
      {FINANCIALS_SUB_TABS.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          aria-current={active === t.id ? "page" : undefined}
          className={`shrink-0 whitespace-nowrap rounded-full px-3 py-1.5 text-[12px] font-medium transition-colors ${
            active === t.id
              ? "bg-sky-500/15 text-sky-600 dark:text-sky-300"
              : "text-text-muted hover:bg-text-primary/[0.04] hover:text-text-secondary"
          }`}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}

function FinancialsTabBody({ stock }: { stock: StockDetail }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const requestedSub = searchParams.get("fsub");
  const subTab: FinancialsSubTab = FINANCIALS_SUB_TABS.some(t => t.id === requestedSub)
    ? (requestedSub as FinancialsSubTab)
    : "overview";
  const setSubTab = useCallback((t: FinancialsSubTab) => {
    const base = `${pathname}?tab=financials`;
    router.push(t === "overview" ? base : `${base}&fsub=${t}`, { scroll: false });
  }, [router, pathname]);

  const [financials, setFinancials] = useState<CompanyFinancialsData | null>(null);
  useEffect(() => {
    let cancelled = false;
    setFinancials(null);
    fetch(`${API}/api/stocks/${stock.symbol}/financials`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (!cancelled) setFinancials(d); })
      .catch(() => { if (!cancelled) setFinancials(null); });
    return () => { cancelled = true; };
  }, [stock.symbol]);

  return (
    <>
      <FinancialsSubNav active={subTab} onChange={setSubTab}/>
      {subTab === "overview" && <>
        <FinancialHighlights stock={stock}/>
        <KeyRatios stock={stock}/>
        <Shareholding stock={stock}/>
        <HistoricalPerformance stock={stock}/>
      </>}
      {subTab === "income" && (
        financials === null
          ? null
          : <StatementTable title="Income Statement" data={financials.income_statement} fields={INCOME_STATEMENT_FIELDS} showYoy/>
      )}
      {subTab === "balance" && (
        financials === null
          ? null
          : <StatementTable title="Balance Sheet" data={financials.balance_sheet} fields={BALANCE_SHEET_FIELDS}/>
      )}
      {subTab === "cashflow" && (
        financials === null
          ? null
          : <StatementTable title="Cash Flow" data={financials.cash_flow} fields={CASH_FLOW_FIELDS}/>
      )}
    </>
  );
}

// ── Events tab body (Batch 3) ───────────────────────────────────────────────
// Fetches the real, symbol-matched event set (GET /api/events?company=)
// only while the Events tab is mounted — see EventTimeline's own comment
// for why this exists (yfinance's stock.events is frequently empty).
// Owns the honest empty-state check itself so it reflects what's actually
// being rendered (companyEvents OR the stock.events/news fallback), not
// a pre-fetch snapshot.
function EventsTabBody({ stock, symbol, relatedNews }: { stock: StockDetail; symbol: string; relatedNews: any[] }) {
  const [companyEvents, setCompanyEvents] = useState<StockEvent[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/events/?company=${encodeURIComponent(stock.symbol)}&limit=8`)
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (!cancelled) setCompanyEvents(Array.isArray(d) ? d : []); })
      .catch(() => { if (!cancelled) setCompanyEvents([]); });
    return () => { cancelled = true; };
  }, [stock.symbol]);

  const effectiveEvents = (companyEvents && companyEvents.length > 0) ? companyEvents : stock.events;
  const hasNews = relatedNews.length > 0 || stock.news.length > 0;
  // Still resolving the real fetch — don't flash the empty state before
  // we actually know whether there's real coverage.
  if (companyEvents === null) return null;

  if (effectiveEvents.length === 0 && !hasNews) {
    return (
      <SectionCard title={`Recent Events Impacting ${symbol.toUpperCase()}`}>
        <p className="text-sm text-text-secondary">No recent events or news coverage tracked for {stock.name} yet.</p>
      </SectionCard>
    );
  }

  return (
    <>
      <EventTimeline stock={stock} symbol={symbol} companyEvents={companyEvents}/>
      <NewsImpact stock={stock} relatedNews={relatedNews}/>
    </>
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
    <div className="animate-pulse rounded-[28px] border border-surface-border/5 bg-text-primary/[0.03]"
      style={{ height: h }}/>
  );
}

// ── Full-page Skeleton (matches 2-col layout) ─────────────────────────────────
function PageSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-6 animate-pulse">
        {/* Hero */}
        <div className="rounded-[28px] border border-surface-border/6 bg-text-primary/[0.04] p-6">
          <div className="flex items-start gap-4">
            <div className="h-14 w-14 shrink-0 rounded-2xl bg-text-primary/[0.06]"/>
            <div className="flex-1 space-y-2.5">
              <div className="h-7 w-56 rounded-xl bg-text-primary/[0.06]"/>
              <div className="flex gap-2">
                {[20, 16, 24].map(w => <div key={w} className="h-5 rounded-md bg-text-primary/[0.04]" style={{ width: `${w * 4}px` }}/>)}
              </div>
            </div>
          </div>
          <div className="mt-5 flex items-baseline gap-3">
            <div className="h-10 w-36 rounded-xl bg-text-primary/[0.06]"/>
            <div className="h-6 w-28 rounded-lg bg-text-primary/[0.04]"/>
          </div>
          <div className="mt-4 grid grid-cols-4 gap-3">
            {[...Array(4)].map((_, i) => <div key={i} className="h-16 rounded-2xl bg-text-primary/[0.04]"/>)}
          </div>
        </div>
        {/* Chart */}
        <div className="rounded-[28px] border border-surface-border/6 bg-text-primary/[0.04] p-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="h-5 w-24 rounded-lg bg-text-primary/[0.06]"/>
            <div className="h-8 w-60 rounded-xl bg-text-primary/[0.04]"/>
          </div>
          <div className="flex h-[260px] items-center justify-center rounded-2xl bg-text-primary/[0.03]">
            <div className="flex items-center gap-2 text-text-muted text-sm">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-surface-border/10 border-t-slate-400"/>
              Loading chart…
            </div>
          </div>
          <div className="mt-4 grid grid-cols-6 gap-3">
            {[...Array(6)].map((_, i) => <div key={i} className="h-9 rounded-xl bg-text-primary/[0.03]"/>)}
          </div>
        </div>
        {/* Remaining section skeletons */}
        {[160, 220, 200, 340, 180, 260].map((h, i) => (
          <div key={i} className="rounded-[28px] border border-surface-border/5 bg-text-primary/[0.03]" style={{ height: h }}/>
        ))}
      </div>
      {/* RIGHT panel */}
      <div className="space-y-5 animate-pulse lg:sticky lg:top-[88px]">
        {[200, 170, 160, 150, 160, 110].map((h, i) => (
          <div key={i} className="rounded-[28px] border border-surface-border/5 bg-text-primary/[0.03]" style={{ height: h }}/>
        ))}
      </div>
    </div>
  );
}

// ── Tab navigation shell (Batch 1) ─────────────────────────────────────────────
// Google-Finance-style interaction philosophy (fast, URL-addressable
// switching between research questions), not a visual clone. Selecting a
// tab replaces the research body below the persistent CompanyHero — it
// never just scrolls to an anchor further down the same long page.
const COMPANY_TABS = [
  { id: "overview",      label: "Overview" },
  { id: "intelligence",  label: "Intelligence" },
  { id: "financials",    label: "Financials" },
  { id: "events",        label: "Events" },
  { id: "opportunities", label: "Opportunities" },
  { id: "ripple",        label: "Ripple" },
  { id: "peers",         label: "Peers" },
] as const;
type CompanyTab = typeof COMPANY_TABS[number]["id"];

function CompanyTabNav({ active, onChange }: { active: CompanyTab; onChange: (t: CompanyTab) => void }) {
  return (
    <nav
      aria-label="Company sections"
      className="sticky top-[64px] z-30 -mx-1 mb-6 flex gap-1 overflow-x-auto border-b border-surface-border/10 bg-surface-base/90 px-1 backdrop-blur scrollbar-hide lg:top-[88px]"
    >
      {COMPANY_TABS.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          aria-current={active === t.id ? "page" : undefined}
          className={`shrink-0 whitespace-nowrap border-b-2 px-4 py-3 text-[13px] font-semibold transition-colors ${
            active === t.id
              ? "border-sky-400 text-text-primary"
              : "border-transparent text-text-muted hover:text-text-secondary"
          }`}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}

// ── Company Ripple (Batch 4) ────────────────────────────────────────────────
// Real Intelligence Graph relationships only. /api/ripple/company/{ticker}
// (the endpoint its own name suggests) was traced end to end and found to
// be AI-generated or sector-templated (ripple_service.py: every result is
// tagged source="ai_generated" or "fallback_template", with hardcoded
// per-sector node/edge structures picking up fabricated strength/impact/
// direction values). Disqualified for a surface users read as evidence-
// backed market structure. This instead calls the real, evidence-only
// resolver+subgraph endpoint added for this batch
// (GET /api/companies/{symbol}/ripple -> graph_ripple.py -> the same
// real get_subgraph() BFS over actual IGNode/IGEdge rows coherence.py
// already uses) — never a generated placeholder.
//
// Fetched only while this tab is mounted (StockPageInner never renders
// this component unless activeTab === "ripple"), so a company detail
// page's initial load never pays for graph data, matching the owner's
// explicit performance requirement for this batch.
interface RippleGraphNode { id: string; node_type: string; label: string; ticker?: string | null; description?: string | null }
interface RippleGraphEdge {
  id: string; source: string; target: string; edge_type: string;
  weight: number; confidence: number; lag_days?: number | null;
  description?: string | null; source_event?: string | null;
}
interface CompanyRippleData {
  status: "no_entity" | "no_node" | "no_edges" | "has_edges";
  canonical_symbol: string | null; company_name: string | null; node_id: string | null;
  nodes: RippleGraphNode[]; edges: RippleGraphEdge[];
}

const RIPPLE_NODE_TYPE_LABEL: Record<string, string> = {
  company: "Company", event: "Event", development: "Development", sector: "Sector",
  theme: "Theme", policy: "Policy", commodity: "Commodity", country: "Country",
  index: "Index", currency: "Currency",
};

function RippleConnectionRow({ edge, node, companyNodeId }: { edge: RippleGraphEdge; node: RippleGraphNode; companyNodeId: string }) {
  const outgoing = edge.source === companyNodeId;
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-surface-border/6 bg-text-primary/[0.02] p-3.5">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-sky-500/15 text-[11px] text-sky-400">
        {outgoing ? "→" : "←"}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="rounded-full border border-surface-border/10 bg-text-primary/5 px-2 py-0.5 text-[9px] uppercase tracking-wide text-text-muted">
            {RIPPLE_NODE_TYPE_LABEL[node.node_type] ?? node.node_type}
          </span>
          <span className="text-[9px] uppercase tracking-wide text-sky-500">{edge.edge_type.replace(/_/g, " ")}</span>
        </div>
        <p className="mt-1 text-[13px] font-medium leading-5 text-text-primary line-clamp-2">{node.label}</p>
        {edge.description && <p className="mt-0.5 text-[11px] text-text-muted line-clamp-2">{edge.description}</p>}
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-text-muted">
          <span>Weight {Math.round(edge.weight * 100)}%</span>
          <span>Confidence {Math.round(edge.confidence * 100)}%</span>
          {!!edge.lag_days && <span>~{edge.lag_days}d lag</span>}
        </div>
      </div>
    </div>
  );
}

function RippleEmptyState({ title, body }: { title: string; body: string }) {
  return (
    <SectionCard title={title}>
      <p className="text-sm leading-relaxed text-text-secondary">{body}</p>
    </SectionCard>
  );
}

function RippleTabBody({ stock }: { stock: StockDetail }) {
  const [data, setData] = useState<CompanyRippleData | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setFailed(false);
    fetch(`${API}/api/companies/${stock.symbol}/ripple`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(String(r.status))))
      .then(d => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [stock.symbol]);

  if (failed) {
    return <RippleEmptyState title="Company Ripple"
      body="Ripple relationship data is temporarily unavailable. Please try again shortly." />;
  }
  if (!data) return null;

  if (data.status === "no_entity") {
    return <RippleEmptyState title="Company Ripple"
      body="Ripple relationship data is unavailable for this company." />;
  }
  if (data.status === "no_node") {
    return <RippleEmptyState title="Company Ripple"
      body={`No verified Ripple relationships yet. MarketRipple has not accumulated enough evidence-backed relationships for ${stock.name} yet. This section will expand as new events and evidence are processed.`} />;
  }
  if (data.status === "no_edges") {
    return <RippleEmptyState title="Company Ripple"
      body={`${stock.name} is tracked in the Intelligence Graph, but no verified relationships have been recorded for it yet.`} />;
  }

  const companyNodeId = data.node_id!;
  const nodesById = Object.fromEntries(data.nodes.map(n => [n.id, n]));
  const rows = data.edges
    .map(e => {
      const otherId = e.source === companyNodeId ? e.target : e.source;
      const node = nodesById[otherId];
      return node ? { edge: e, node } : null;
    })
    .filter((r): r is { edge: RippleGraphEdge; node: RippleGraphNode } => r !== null)
    .sort((a, b) => b.edge.weight - a.edge.weight)
    .slice(0, 8);

  return (
    <SectionCard title="Company Ripple" action={
      <Link href="/graph" className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">Explore full graph →</Link>
    }>
      <p className="mb-4 text-[11px] uppercase tracking-wider text-text-muted">
        {data.edges.length} verified relationship{data.edges.length === 1 ? "" : "s"}
      </p>
      <div className="space-y-2.5">
        {rows.map(({ edge, node }) => (
          <RippleConnectionRow key={edge.id} edge={edge} node={node} companyNodeId={companyNodeId}/>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
// initialStock (optional) comes from the server-rendered wrapper (page.tsx),
// which fetches the same /api/stocks/{symbol} endpoint server-side purely so
// crawlers and the first paint see real content instead of a loading
// skeleton — see page.tsx's own docstring. Purely a perceived-perf/SEO
// seed: this component still fetches its own fresh copy (plus news, which
// the server wrapper deliberately doesn't fetch) exactly as before.
//
// Company redesign Batch 1 (2026-08-25) — replaced the old single-scroll,
// 3-wave-reveal page with a persistent CompanyHero + a real
// Overview/Intelligence/Financials/Events/Opportunities/Ripple/Peers tab
// strip (see CompanyTabNav above). The active tab is driven by a `?tab=`
// URL param via next/navigation, not local-only state, so a tab is
// shareable, survives a reload, and back/forward moves between tabs the
// same way it would between pages — see StockPage's Suspense wrapper below
// (useSearchParams requires one). Every section that used to be in the
// 3-wave stack is preserved and reachable, just regrouped by the research
// question it answers rather than stacked in one long scroll — see
// artifacts/company_redesign_audit_spec.md and the Batch 1 completion note
// for the full per-tab mapping and rationale.
function StockPageInner({ params, initialStock, initialRelated, faqs }: PageProps & { initialStock?: StockDetail | null; initialRelated?: Record<string, RelatedItem[]> | null; faqs?: { question: string; answer: string }[] }) {
  const { symbol } = use(params);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const activeTab: CompanyTab = COMPANY_TABS.some(t => t.id === requestedTab)
    ? (requestedTab as CompanyTab)
    : "overview";
  const setTab = useCallback((t: CompanyTab) => {
    router.push(t === "overview" ? pathname : `${pathname}?tab=${t}`, { scroll: false });
  }, [router, pathname]);

  const [stock,        setStock]        = useState<StockDetail | null>(initialStock ?? null);
  const [chartData,    setChartData]    = useState<any[]>([]);
  const [loadingInfo,  setLoadingInfo]  = useState(!initialStock);
  const [loadingChart, setLoadingChart] = useState(true);
  const [period,       setPeriod]       = useState("1Y");
  const [watchlisted,  setWatchlisted]  = useState(false);
  const [relatedNews,  setRelatedNews]  = useState<any[]>([]);

  const { data: intelligence } = useIntelligence("company", symbol?.toUpperCase());
  // Guards the very first effect run only — when the server already handed
  // us real data, don't flash back to the loading/empty state while this
  // effect's own (fresher) fetch is in flight; every subsequent symbol
  // change behaves exactly as it did before this prop existed.
  const skippedFirstResetRef = useRef(!!initialStock);

  useEffect(() => {
    if (skippedFirstResetRef.current) {
      skippedFirstResetRef.current = false;
    } else {
      setLoadingInfo(true);
    }
    // Kick off stock data + chart + news in parallel
    Promise.all([
      fetch(`${API}/api/stocks/${symbol}`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/stocks/${symbol}/news`).then(r => r.ok ? r.json() : []).catch(() => []),
    ]).then(([data, news]) => {
      setStock(data);
      setRelatedNews(Array.isArray(news) ? news : []);
    }).finally(() => setLoadingInfo(false));
  }, [symbol]);

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
      <TrendingDown className="h-16 w-16 text-text-muted" />
      <h1 className="text-2xl font-semibold text-text-primary">{symbol.toUpperCase()} not found</h1>
      <p className="text-text-secondary">Not listed on NSE or backend offline.</p>
      <Link href="/companies" className="mt-2 rounded-full bg-sky-500/15 px-5 py-2 text-sm text-sky-600 dark:text-sky-300 hover:bg-sky-500/25 transition">← Back to Companies</Link>
    </main>
  );

  return (
    <main className="min-w-0 pb-16">
      <TrackPageVisit type="company" id={symbol.toUpperCase()} title={stock.name ?? symbol.toUpperCase()} subtitle={`${stock.price} · ${stock.sector}`} href={`/companies/${symbol.toUpperCase()}`} />
      {/* Top loader while chart is still fetching */}
      <TopLoader active={loadingChart}/>

      {/* ── Persistent header — stays fixed across every tab ─────────── */}
      <CompanyHero stock={stock} symbol={symbol} watchlisted={watchlisted} setWatchlisted={setWatchlisted} serverRenderedH1={!!initialStock}/>

      <CompanyTabNav active={activeTab} onChange={setTab}/>

      <motion.div
        key={activeTab}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: "easeOut" }}>
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[1fr_320px]">

          {/* ── LEFT: the active tab's research body ────────────────── */}
          <div className="min-w-0 space-y-6">

            {/* Batch C (Company Simplification spec, §3) — Overview
                rebuilt to the spec's own explicit sequence: About → Key
                Data → MarketRipple View → Latest Developments →
                Opportunity preview → (curated Latest Intelligence
                articles, a distinct real source from raw news/events) →
                FAQ moved to the bottom (was previously rendered above
                the entire page in page.tsx, repeated on every tab —
                see faqSection's own comment there). Price chart kept
                high in the flow — a real, valuable, non-fabricated
                element the "Google Finance restraint" reference point
                itself leads with. */}
            {activeTab === "overview" && <>
              <AboutSection stock={stock}/>
              <PriceChart symbol={symbol} chartData={chartData} loadingChart={loadingChart}
                period={period} setPeriod={p => { setPeriod(p); fetchChart(p); }} stock={stock}/>
              <KeyDataGrid stock={stock}/>
              <MarketRippleViewCard stock={stock}/>
              <LatestDevelopmentsList stock={stock} relatedNews={relatedNews}/>
              <OpportunityPreview stock={stock}/>
              <ShareInsightCard
                entityType="company"
                entityId={stock.symbol}
                title={`${stock.name} (${stock.symbol})`}
                summary={stock.description?.slice(0, 120)}
              />
              <RelatedStories stock={stock}/>
              <FaqSection faqs={faqs ?? []}/>
            </>}

            {/* Batch D (Company Simplification spec, §4) — Intelligence
                tab reduced to its real 5-concept core (MarketRipple View
                lives on Overview; the other four are represented here):
                Why This View + What Changed (CompanyIntelligenceSection),
                Key Evidence (CompanyScoreContributors), What to Watch
                (WhatToWatchCard, extracted from the old IntelligenceBlock's
                monitoring_points — the rest of that payload was either
                redundant with what's already here or off-topic for a
                single-company page, see WhatToWatchCard's own comment).
                Removed entirely: InvestmentThesis (fabricated-fallback
                "analyst consensus reading neutral" thesis text for
                companies with zero analysts — the exact class of bug
                Batch A/B fixed elsewhere, now deleted rather than patched
                since the spec calls for its outright removal),
                ScenarioAnalysis (unsupported, invariant 30/50/20 Bull/
                Base/Bear percentages — identical for every company,
                zero backtest data behind them), OpportunityLifecycleCard
                (same "Neutral" bug plus a duplicate of the Opportunities
                tab — not moved elsewhere per explicit instruction),
                MonitoringChecklist (entirely templated). Stock DNA and
                Pattern Intelligence are real but neither is one of the 5
                concepts nor competes with the primary score — moved under
                MoreAnalysisDisclosure's progressive disclosure. */}
            {activeTab === "intelligence" && <>
              <CompanyIntelligenceSection symbol={symbol} govScore={stock.gov_score} pricePositive={stock.pct_change >= 0}/>
              <CompanyScoreContributors stock={stock}/>
              <WhatToWatchCard points={intelligence?.monitoring_points ?? []}/>
              <AISentiment stock={stock}/>
              <MoreAnalysisDisclosure>
                <StockDNA stock={stock}/>
                <PatternIntelligenceCard
                  entityType="company"
                  entityId={stock.symbol}
                  entityTitle={stock.name}
                  entityDescription={stock.description}
                  entitySector={stock.sector}
                />
              </MoreAnalysisDisclosure>

              <RelatedContent
                entityType="company"
                entityId={stock.symbol}
                title={stock.name}
                sector={stock.sector}
                initialData={initialRelated}
              />
            </>}

            {/* Company redesign Batch 0 — removed GovernmentExposureSection:
                gov_score/level are a real heuristic from real yfinance
                inputs, but the breakdown donut/pills/"Policy Impact Cards"
                were categorically fabricated (every "High" exposure company
                got the identical 42/28/16/14 split; the cards were formula-
                derived with hardcoded scores) with zero disclosure. See
                artifacts/company_redesign_audit_spec.md §C/§D. */}
            {activeTab === "financials" && <FinancialsTabBody stock={stock}/>}

            {/* Live-verified real gap (Batch 1): EventTimeline/NewsImpact
                both already return null on empty data — correct, no
                fabricated filler — but with Events as its own dedicated
                tab (rather than one of many stacked sections) that used to
                leave the tab visually blank with no explanation. An honest
                one-line empty state is a shell-correctness fix, not new
                content design (full empty/partial-state work across every
                tab is Batch 5's job). */}
            {activeTab === "events" && (
              <EventsTabBody stock={stock} symbol={symbol} relatedNews={relatedNews}/>
            )}

            {activeTab === "opportunities" && <>
              <RelatedOpportunitiesList stock={stock}/>
              <OpportunityRadarSection stock={stock}/>
            </>}

            {/* Company redesign Batch 0 (2026-08-25) — removed NetworkGraph
                (100% fabricated supply-chain graph). Batch 4 wires the
                real replacement — see RippleTabBody's own comment for
                why /api/ripple/company/{ticker} was rejected in favor of
                a real graph-evidence-only endpoint. */}
            {activeTab === "ripple" && <RippleTabBody stock={stock}/>}

            {activeTab === "peers" && <>
              <PeerComparison stock={stock}/>
              <CompareWithSection stock={stock}/>
            </>}

          </div>

          {/* ── RIGHT: sticky intelligence panel — present on every tab ── */}
          <aside className="lg:sticky lg:top-[88px] lg:max-h-[calc(100vh-100px)] lg:overflow-y-auto scrollbar-hide">
            <IntelligencePanel stock={stock}/>
          </aside>

        </div>
      </motion.div>
    </main>
  );
}

export default function StockPage(props: PageProps & { initialStock?: StockDetail | null; initialRelated?: Record<string, RelatedItem[]> | null; faqs?: { question: string; answer: string }[] }) {
  return (
    <Suspense fallback={
      <main className="min-w-0 pb-10">
        <TopLoader active/>
        <PageSkeleton/>
      </main>
    }>
      <StockPageInner {...props} />
    </Suspense>
  );
}
