"use client";

import { use, useEffect, useState, useCallback, useMemo, useRef, useId, Suspense } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { TrackPageVisit } from "@/components/TrackPageVisit";
import { PatternIntelligenceCard } from "@/components/intelligence";
import { useIntelligence } from "@/hooks/useIntelligence";
import { ShareInsightCard } from "@/components/ShareInsightCard";
import { SmartCTA } from "@/components/SmartCTA";
import { CompanyIntelligenceSection } from "@/components/CompanyIntelligenceSection";
import { StockExtrasCard } from "@/components/StockExtrasCard";
import { RelatedContent, type RelatedItem } from "@/components/RelatedContent";
import { API_BASE_URL as API } from "@/lib/api";
import { hasCandles } from "@/lib/candles";
import { dedupeEvidence, evidenceBalance } from "@/lib/intelligenceView";
import { aboutHeading, aboutSummary } from "@/lib/companyAbout";
import { scoreToColor, impactToStyle, marketRippleRatingColor, marketRippleScoreDisplayInt } from "@/lib/scoring";
import { labelTone, metricTone, parseMetric } from "@/lib/metricTone";
import {
  Star, Check, Sparkles, TrendingUp,
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
const CandleChart                 = dynamic(() => import("./CandleChart").then(m => m.CandleChart),                    { ssr: false });
const DnaRadarChart               = dynamic(() => import("./CompanyCharts").then(m => m.DnaRadarChart),               { ssr: false });
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
  // Real per-statement reporting currency (2026-09-27 currency-bug fix) —
  // null when yfinance's own financialCurrency is unconfirmed, in which
  // case quarterly_revenue/quarterly_net_income/annual_financials are
  // empty rather than a silently INR-assumed number. NOT the stock's own
  // trading currency (market_cap/enterprise_value are always real-time
  // NSE INR regardless of this).
  statement_currency_prefix?: string | null; statement_currency_unit?: string | null;
  enterprise_value: string; roce: string;
  annual_financials: { year: string; revenue: number; net_income: number }[];
  dna_scores: Record<string, number>; gov_score: number; gov_level: string;
  gov_breakdown: GovBreak[]; gov_support_areas: string[];
  buy_count: number; hold_count: number; sell_count: number;
  events: StockEvent[]; news: any[]; peers: string[]; chart_data: any[];
}

interface PageProps { params: Promise<{ symbol: string }> }

// ── Design tokens ─────────────────────────────────────────────────────────────
// 2026-08-25 — no box shadows, flat card treatment per owner request.
const CARD = "rounded-2xl border border-surface-border/10 bg-surface-card shadow-[0_1px_2px_rgb(15_23_42/0.04)]";
const PERIODS = ["1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "Max"];

const ANALYST_ICONS: React.ReactNode[] = [
  <BarChart2 className="h-3 w-3" />,
  <TrendingUp className="h-3 w-3" />,
  <TrendingDown className="h-3 w-3" />,
  <Landmark className="h-3 w-3" />,
  <Briefcase className="h-3 w-3" />,
];


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

// Good/neutral/weak/poor colouring keyed
// on the real numeric field (not a formatted display string) — used by
// the Ratios sub-tab under Financials, whose fields are computed period-
// by-period rather than the single latest-value snapshot metricColor was
// built for. A ratio with no fixed "good" direction (EPS — its right
// value is entirely size/valuation-dependent, not a threshold) is left
// uncolored, same as metricColor already leaves it today.
function ratioFieldColor(key: string, value: number | null): string {
  if (value == null) return "text-text-primary";
  const n = value;
  switch (key) {
    case "net_profit_margin":
      return n > 15 ? "text-emerald-600 dark:text-emerald-400" : n >= 5 ? "text-text-primary" : n >= 0 ? "text-amber-600 dark:text-amber-400" : "text-rose-600 dark:text-rose-400";
    case "operating_margin":
      return n > 20 ? "text-emerald-600 dark:text-emerald-400" : n >= 10 ? "text-text-primary" : n >= 0 ? "text-amber-600 dark:text-amber-400" : "text-rose-600 dark:text-rose-400";
    case "roe":
      return n > 20 ? "text-emerald-600 dark:text-emerald-400" : n >= 10 ? "text-text-primary" : n >= 0 ? "text-amber-600 dark:text-amber-400" : "text-rose-600 dark:text-rose-400";
    case "roa":
      return n > 10 ? "text-emerald-600 dark:text-emerald-400" : n >= 5 ? "text-text-primary" : n >= 0 ? "text-amber-600 dark:text-amber-400" : "text-rose-600 dark:text-rose-400";
    case "debt_to_equity":
      return n < 0.3 ? "text-emerald-600 dark:text-emerald-400" : n < 1 ? "text-text-primary" : n < 2 ? "text-amber-600 dark:text-amber-400" : "text-rose-600 dark:text-rose-400";
    default:
      return "text-text-primary";
  }
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
    <section className={`${CARD} ${noPad ? "" : "p-6"} ${className}`}>
      {(title || action) && (
        <div className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-2 ${noPad ? "px-6 pt-6 pb-0" : "mb-4"}`}>
          {title && <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-text-primary">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
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
      <span className="absolute text-[11px] font-semibold leading-none" style={{ color: col }}>{score > 0 ? score : score}</span>
    </div>
  );
}

function KvRow({ label, value, colored = false }: { label: string; value: string; colored?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 py-2 border-b border-surface-border/4 last:border-0">
      <span className="text-[12px] text-text-muted shrink-0">{label}</span>
      <span className={`text-[13px] font-medium tabular-nums text-right ${value === "Not applicable" ? "text-text-muted font-normal" : colored ? labelTone(label, value) : "text-text-primary"}`}>{value || "—"}</span>
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
// S5-C — the real, unified four-pillar MarketRipple Score
// (Financial Strength / Valuation / Market Behaviour / Current
// Intelligence), reading only the persisted snapshot the backend
// computed ahead of time (GET /api/companies/{symbol}/marketripple-score)
// — never a live 27-bank recomputation from this page. "MarketRipple
// Score" is reserved exclusively for this methodology going forward
// (owner decision, 2026-08-29). One-score migration (2026-09-26, owner
// instruction): the older single-engine AI/evidence score no longer has
// its own Overview-tab card/fallback either — MarketRippleScoreSection
// always renders this same card, in whichever state (complete/partial/
// unavailable) the real projection is actually in. The older calculation
// stays real and running internally (it's the Current Intelligence
// pillar's own input, see current_intelligence.py) and still has its own,
// separately-labeled "Recent Intelligence Evidence" home on the
// Intelligence tab (CompanyScoreContributors) — just never as a competing
// headline rating.
export interface MarketRippleScoreData {
  resolved: boolean;
  snapshot?: boolean;
  symbol?: string;
  methodology_version?: string;
  publication_policy_version?: string;
  publishable?: boolean;
  eligible?: boolean;
  score?: number | null;
  rating?: string | null;
  pillars?: {
    financial_strength: number | null; valuation: number | null;
    market_behaviour: number | null; current_intelligence: number | null;
  };
  evidence_coverage_pct?: number;
  financial_data_as_of?: string | null;
  // Comparability interim rule (2026-09-26) — "complete" | "partial" |
  // "insufficient" | null. When "partial", `score`/`rating` are withheld
  // (a renormalized 2-or-3-of-4 blend isn't comparable to a real 4-of-4
  // one) even though individual `pillars` values that WERE computed are
  // still real and present — see engine.py's own field docstring.
  pillar_coverage_status?: "complete" | "partial" | "insufficient" | null;
  pillar_coverage_message?: string | null;
  calculated_at?: string | null;
  block_headline?: string | null;
  block_message?: string | null;
  // 2026-09-28 — why a company has no public number (coverage.py):
  // "scored" | "not_processed" | "needs_refresh" | "insufficient_data" | "unsupported" | "peer_group_review" | "no_peer_group" | "score_hold".
  coverage_state?: string;
  coverage_label?: string;
  coverage_message?: string | null;
  last_calculated_at?: string | null;
  peer_count?: number | null;
  sector?: string | null;
  peer_group?: string | null;
}

function useMarketRippleScore(symbol: string) {
  const [data, setData] = useState<MarketRippleScoreData | null | undefined>(undefined);
  useEffect(() => {
    let cancelled = false;
    setData(undefined);
    fetch(`${API}/api/companies/${symbol}/marketripple-score`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData(null); });
    return () => { cancelled = true; };
  }, [symbol]);
  return data;
}

function CompanyHero({ stock, symbol, watchlisted, setWatchlisted }: {
  stock: StockDetail; symbol: string; watchlisted: boolean; setWatchlisted: (v: boolean) => void;
}) {
  const isPos = stock.pct_change >= 0;
  const sign  = isPos ? "+" : "";
  const mrScore = useMarketRippleScore(stock.symbol);
  // Never renders the internal score for a blocked company (eligible ===
  // false) — the compact header tile shows "Not available yet" for both
  // "no methodology for this sector" and "blocked by evidence quality",
  // the same honest tone either way; the full reason lives in the larger
  // Overview-tab card (MarketRippleScoreSection), not squeezed in here.
  const hasMrScore = !!mrScore?.resolved && !!mrScore?.snapshot && mrScore.eligible === true && mrScore.score != null
    && (mrScore.coverage_state ?? "scored") === "scored";

  // Local unpublished preview, header tile (2026-09-27) — same dev-only
  // gate and safety story as LocalUnpublishedScorePreview below: only
  // ever fetched/rendered when hasMrScore is false (never overrides or
  // competes with the real public number once publishable is true) AND
  // NODE_ENV==="development" (dead code in any real build). Falls back to
  // the same honest "Not available yet" the public tile already shows
  // whenever this data isn't available either.
  const isDev = process.env.NODE_ENV === "development";
  const localPreview = useLocalUnpublishedScorePreview(isDev && !hasMrScore ? stock.symbol : "");
  const hasLocalPreview = isDev && !hasMrScore && !!localPreview?.resolved && !!localPreview?.snapshot
    && localPreview.eligible === true && localPreview.score != null;

  const NAME = "text-[26px] font-semibold leading-tight tracking-[-0.02em] text-text-primary md:text-[30px]";
  const BTN_SECONDARY = "inline-flex h-9 items-center gap-1.5 rounded-lg border border-surface-border/12 bg-surface-card px-3.5 text-[13px] font-medium text-text-secondary transition hover:border-surface-border/25 hover:text-text-primary active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-violet/40";
  const stats: { label: string; value: string | undefined }[] = [
    { label: "Market cap", value: stock.market_cap },
    { label: "P/E (TTM)", value: stock.pe },
    { label: "Dividend yield", value: stock.dividend_yield },
  ];
  const sector = stock.sector && stock.sector !== "N/A" ? stock.sector : null;
  const industry = stock.industry && stock.industry !== "N/A" && stock.industry !== stock.sector ? stock.industry : null;
  const score = hasMrScore ? mrScore! : hasLocalPreview ? localPreview! : null;

  return (
    <section className={`${CARD} p-6 md:p-7`}>
      <div className="flex flex-col gap-7 xl:flex-row xl:items-start xl:justify-between">
        {/* Identity + price */}
        <div className="min-w-0">
          <div className="flex items-center gap-3.5">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-surface-border/10 bg-text-primary/[0.04] text-[14px] font-semibold tracking-tight text-text-secondary" aria-hidden>
              {symbol.slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0">
              {/* The page's single <h1>: the company name. The searchable context (share price, sector, market cap, P/E) lives in the About card, the page title and the meta description. */}
              <h1 className={NAME}>{stock.name}</h1>
              <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[13px] text-text-muted">
                <span className="font-semibold text-text-secondary">{symbol.toUpperCase()}</span>
                <span aria-hidden>·</span><span>NSE</span>
                {sector && <><span aria-hidden>·</span><span>{sector}</span></>}
                {industry && <><span aria-hidden>·</span><span>{industry}</span></>}
              </p>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-baseline gap-x-3 gap-y-1.5">
            <span className="text-[34px] font-semibold leading-none tracking-[-0.03em] tabular-nums text-text-primary md:text-[38px]">₹{stock.price}</span>
            <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[13px] font-medium tabular-nums ${isPos ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" : "bg-rose-500/10 text-rose-700 dark:text-rose-400"}`}>
              {stock.change_abs} ({sign}{stock.pct_change.toFixed(2)}%)
            </span>
          </div>
          {/* No quote timestamp exists on StockDetail — say what the number is
              rather than stamping today's date on a possibly older close. */}
          <p className="mt-2 text-[12px] text-text-muted">Last traded price · NSE</p>
        </div>

        {/* Key stats + actions */}
        <div className="flex w-full flex-col gap-4 xl:w-auto xl:items-end">
          <dl className="grid w-full grid-cols-2 gap-px overflow-hidden rounded-xl border border-surface-border/10 bg-surface-border/10 sm:grid-cols-4 xl:w-[560px]">
            {stats.map(k => (
              <div key={k.label} className="bg-surface-card px-4 py-3">
                <dt className="text-[12px] text-text-muted">{k.label}</dt>
                <dd className={`mt-1 text-[16px] font-semibold tracking-[-0.01em] tabular-nums ${labelTone(k.label, k.value)}`}>{k.value || "—"}</dd>
              </div>
            ))}
            {/* The one primary MarketRipple Score (MARKETRIPPLE_SCORE_V1). The
                dev-only preview (NODE_ENV-gated above; dead code in a real
                build) is marked with its own badge, never passed off as public. */}
            <div className="bg-surface-card px-4 py-3">
              <dt className="whitespace-nowrap text-[12px] text-text-muted">MarketRipple Score</dt>
              {mrScore === undefined ? (
                <dd className="mt-1 h-5 w-14 animate-pulse rounded bg-text-primary/[0.06]" aria-label="Loading" />
              ) : score ? (
                <dd className="mt-1 flex items-baseline gap-1.5">
                  <span className={`text-[16px] font-semibold tabular-nums ${marketRippleRatingColor(score.rating)}`}>{marketRippleScoreDisplayInt(score.score)}</span>
                  <span className="text-[12px] text-text-muted">/100</span>
                  {score.rating && <span className={`text-[12px] font-medium ${marketRippleRatingColor(score.rating)}`}>{score.rating}</span>}
                </dd>
              ) : null}
              {score && hasLocalPreview && (
                <dd className="mt-1 text-[11px] font-medium text-amber-700 dark:text-amber-400" title="Local unpublished preview — never shown in production">Unpublished preview</dd>
              )}
              {mrScore !== undefined && !score && (
                <dd className="mt-1 text-[13px] font-medium text-text-muted" title={mrScore?.coverage_message ?? "MarketRipple Score is not yet available for this company."}>
                  {mrScore?.coverage_label ?? "Not available yet"}
                </dd>
              )}
            </div>
          </dl>

          <div className="flex flex-wrap gap-2">
            <button onClick={() => setWatchlisted(!watchlisted)}
              className={`inline-flex h-9 items-center gap-1.5 rounded-lg px-3.5 text-[13px] font-medium transition active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-violet/40 ${
                watchlisted
                  ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                  : "bg-text-primary text-bg hover:opacity-90"
              }`}>
              {watchlisted ? <><Check className="h-3.5 w-3.5" />In watchlist</> : <><Star className="h-3.5 w-3.5" />Add to watchlist</>}
            </button>
            <Link href={`/companies?tab=compare&a=${symbol}`} className={BTN_SECONDARY}>Compare</Link>
            <Link href={`/ai-search?q=${encodeURIComponent(`Analyse ${stock.name} (${symbol}): current valuation, recent events, and outlook versus sector peers.`)}`} className={BTN_SECONDARY}>
              <Sparkles className="h-3.5 w-3.5 text-accent-violet" /> Ask AI
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Section 2: Price Chart ────────────────────────────────────────────────────
function PriceChart({ symbol, chartData, loadingChart, period, setPeriod, stock }: {
  symbol: string; chartData: any[]; loadingChart: boolean;
  period: string; setPeriod: (p: string) => void; stock: StockDetail;
}) {
  const isPos = stock.pct_change >= 0;
  const chartColor = isPos ? "#22c55e" : "#f43f5e";
  // Line (default) or Candle; the choice is remembered per browser. Storage can be blocked, so every access is guarded.
  const [kind, setKind] = useState<"line" | "candle">("line");
  useEffect(() => {
    try { if (localStorage.getItem("mr_price_chart_kind") === "candle") setKind("candle"); } catch { /* storage unavailable */ }
  }, []);
  const chooseKind = (k: "line" | "candle") => {
    setKind(k);
    try { localStorage.setItem("mr_price_chart_kind", k); } catch { /* storage unavailable */ }
  };
  const showCandles = kind === "candle" && hasCandles(chartData);
  const intraday = typeof chartData[0]?.time === "number";
  return (
    <SectionCard title="Price chart" action={
      <div className="flex flex-wrap items-center justify-end gap-2">
        <div className="flex gap-0.5 bg-text-primary/[0.03] rounded-xl p-0.5" role="group" aria-label="Chart type">
          {(["line", "candle"] as const).map(k => (
            <button key={k} onClick={() => chooseKind(k)} aria-pressed={kind === k}
              className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
                kind === k ? "bg-text-primary/10 text-text-primary" : "text-text-muted hover:text-text-secondary"}`}>
              {k === "line" ? "Line" : "Candle"}
            </button>
          ))}
        </div>
        <div className="flex gap-0.5 bg-text-primary/[0.03] rounded-xl p-0.5">
          {PERIODS.map(p => (
            <button key={p} onClick={() => setPeriod(p)}
              className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
                period === p ? "bg-text-primary/10 text-text-primary" : "text-text-muted hover:text-text-secondary"}`}>
              {p}
            </button>
          ))}
        </div>
      </div>
    }>
      <div className="h-[260px] mt-4">
        {loadingChart ? (
          <div className="flex h-full items-end gap-1.5 animate-pulse" aria-label="Loading price chart">
            {[38, 52, 45, 60, 55, 70, 64, 78, 72, 85, 80, 90].map((h, i) => (
              <div key={i} className="flex-1 rounded-t bg-text-primary/[0.06]" style={{ height: `${h}%` }} />
            ))}
          </div>
        ) : chartData.length > 0 ? (
          showCandles
            ? <CandleChart chartData={chartData} intraday={intraday} />
            : <PriceAreaChart chartData={chartData} chartColor={chartColor} />
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
            <p className="text-[11px] text-text-muted">{l}</p>
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
          <div key={k}
            className="group flex flex-col items-center gap-2 rounded-xl border border-surface-border/6 bg-surface-card p-4 text-center hover:border-sky-400/20 hover:-translate-y-0.5 transition-all">
            <div className="relative h-12 w-12">
              <svg className="h-12 w-12" style={{ transform: "rotate(-90deg)" }}>
                <circle cx="24" cy="24" r="19" stroke="rgb(var(--text-primary) / 0.08)" strokeWidth={4} fill="none"/>
                <circle cx="24" cy="24" r="19" stroke={scoreColor(v)} strokeWidth={4} fill="none"
                  strokeLinecap="round" strokeDasharray={`${(v / 100) * 2 * Math.PI * 19} ${2 * Math.PI * 19}`}/>
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-[11px] font-semibold" style={{ color: scoreColor(v) }}>{v}</span>
            </div>
            <p className="text-[10px] text-text-secondary leading-tight">{k}</p>
          </div>
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
// Currency/unit bug fix (2026-09-27, owner-directed re-audit): this
// component hardcoded "₹ in Crore"/" Cr" for every company, but
// quarterly_revenue/quarterly_net_income/annual_financials are only ever
// real ₹ Crore when the company's real reporting currency (yfinance's
// financialCurrency) is confirmed INR — a USD-reporting company like INFY
// would have these fields empty now (the backend withholds them rather
// than guess), and the currency prefix/unit below reflect whatever real
// currency WAS confirmed. Division by a magnitude scale (1e7/1e6) is never
// a currency conversion, so this label must always match the real backend
// value, never be assumed.
function FinancialHighlights({ stock }: { stock: StockDetail }) {
  const curPrefix = stock.statement_currency_prefix;
  const curUnit = stock.statement_currency_unit;
  const curLabel = curPrefix && curUnit ? `${curPrefix} ${curUnit}` : null;
  const latestQuarterlyRevenue = stock.quarterly_revenue.slice(-1)[0]?.value ?? null;
  const latestQuarterlyProfit = stock.quarterly_net_income.slice(-1)[0]?.value ?? null;
  const kpis: { label: string; value: number | null; suffix: string; color: string }[] = [
    { label: "Revenue",   value: latestQuarterlyRevenue, suffix: curUnit ? ` ${curUnit}` : "", color: "text-text-primary" },
    { label: "Net Profit",value: latestQuarterlyProfit,  suffix: curUnit ? ` ${curUnit}` : "", color: latestQuarterlyProfit != null && latestQuarterlyProfit < 0 ? "text-rose-600 dark:text-rose-400" : "text-text-primary" },
    { label: "ROE",       value: parseMetric(stock.roe),  suffix: "%",   color: metricTone("roe", stock.roe) },
    { label: "ROCE",      value: parseMetric(stock.roce), suffix: "%",   color: metricTone("roce", stock.roce) },
    { label: "EPS",       value: parseMetric(stock.eps),  suffix: "",    color: "text-text-primary" },
  ];
  return (
    <SectionCard title="Financial highlights">
      {/* Batch E (Company Simplification spec, §5) — was a 5-card KPI
          grid (individually bordered, hover-lift, per-card sparkline) —
          exactly the "giant KPI card" pattern the spec calls out to
          remove from this sub-tab in favor of tables. Replaced with the
          same plain, restrained text-strip treatment PriceChart's own
          OHLC row already uses on this page — the annual table right
          below is the real detail; this row is a compact summary of it,
          not a second competing presentation. */}
      <div className="mt-4 grid grid-cols-2 gap-3 border-b border-surface-border/5 pb-4 sm:grid-cols-5">
        {kpis.map(k => (
          <div key={k.label} className="text-center">
            <p className="text-[11px] text-text-muted">{k.label}</p>
            <p className={`mt-0.5 text-[16px] font-bold leading-none ${k.color}`}>
              {k.value == null ? "—" : `${k.value.toLocaleString("en-IN")}${k.suffix}`}
            </p>
          </div>
        ))}
      </div>

      {/* Annual table */}
      {stock.annual_financials.length > 0 && (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-surface-border/6">
                <th className="pb-2 text-left text-[10px] text-text-muted font-medium">{curLabel ?? "Currency unconfirmed"}</th>
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
                <td className="py-2 text-right font-bold text-violet-600 dark:text-violet-300">{stock.quarterly_revenue.length > 0 ? stock.quarterly_revenue.reduce((a, b) => a + b.value, 0).toLocaleString("en-IN") : "—"}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">Net Profit</td>
                {stock.annual_financials.map(f => <td key={f.year} className={`py-2 text-right font-semibold ${f.net_income >= 0 ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300"}`}>{f.net_income.toLocaleString("en-IN")}</td>)}
                <td className="py-2 text-right font-bold text-emerald-600 dark:text-emerald-300">{stock.quarterly_net_income.length > 0 ? stock.quarterly_net_income.reduce((a, b) => a + b.value, 0).toLocaleString("en-IN") : "—"}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">ROE (%, period unconfirmed)</td>
                {stock.annual_financials.map((f, i) => <td key={f.year} className="py-2 text-right text-text-primary">{i === stock.annual_financials.length - 1 ? stock.roe : "—"}</td>)}
                <td className={`py-2 text-right font-semibold ${metricTone("roe", stock.roe)}`}>{stock.roe}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">EPS{curPrefix ? ` (${curPrefix}, TTM)` : ""}</td>
                {stock.annual_financials.map((f, i) => <td key={f.year} className="py-2 text-right text-text-primary">{i === stock.annual_financials.length - 1 ? stock.eps : "—"}</td>)}
                <td className="py-2 text-right text-violet-600 dark:text-violet-300">{stock.eps}</td>
              </tr>
              <tr>
                <td className="py-2 text-text-secondary">Debt/Equity</td>
                {stock.annual_financials.map((f, i) => <td key={f.year} className="py-2 text-right text-text-primary">{i === stock.annual_financials.length - 1 ? stock.debt_to_equity : "—"}</td>)}
                <td className={`py-2 text-right font-semibold ${metricTone("de", stock.debt_to_equity)}`}>{stock.debt_to_equity}</td>
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
// ROCE, debt/equity and the current ratio have no standard meaning for a bank (deposits are its raw material, interest is its operating cost), so they read
// "Not applicable" instead of looking like missing data. Banks are judged on ROE, ROA, NIM and NPAs.
export const isBank = (industry?: string | null) => /^banks?(\s|-|$)/i.test((industry ?? "").trim());
const BANK_NA = new Set(["ROCE", "D/E Ratio", "Current Ratio"]);

function KeyRatios({ stock }: { stock: StockDetail }) {
  const bank = isBank(stock.industry);
  const na = (l: string, v: string) => (bank && BANK_NA.has(l) ? "Not applicable" : v);
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
    <SectionCard title="Key ratios">
      <div className="mt-3 grid grid-cols-2 gap-x-8 divide-x divide-surface-border/4">
        <div>{rows.slice(0, 5).map(([l, v]) => <KvRow key={l} label={l} value={na(l, v)} colored/>)}</div>
        <div className="pl-8">{rows.slice(5).map(([l, v]) => <KvRow key={l} label={l} value={na(l, v)} colored/>)}</div>
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
            <div key={i} className={className}>
              {body}
            </div>
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

// ── Section 9: Recent Intelligence Evidence (Opportunities tab) ─────────────
// Previously "Opportunity Radar" — 3 entirely fabricated cards (invented
// titles like "Export Opportunity", scores/confidence/revenue/timeline that
// were never computed from anything, just hardcoded numbers plus one fake
// formula on market_cap). Replaced with real signals from company_score_
// engine.py — extracted from every published article's companies_affected[]
// and every opportunity's real per-company impact_score, aggregated with
// real recency decay. Hides entirely rather than showing a fabricated
// fallback when a company has no real signals yet.
//
// One-score migration (2026-09-26, owner instruction): this section
// duplicated the same "AI Company Intelligence Score" standalone rating
// already removed from the Intelligence tab's CompanyScoreContributors —
// living on the Opportunities tab under a different title didn't exempt it.
// Renamed and stripped of the same elements (score headline, "AI Powered"
// badge, "Evidence quality" gauge); the real evidence cards themselves
// (per-signal reason, source, date, link, and signed magnitude — the
// individual-signal-level number, not a company rating) are unchanged. The
// real per-opportunity Opportunity Score badges shown in
// RelatedOpportunitiesList directly above this section on the same tab are
// a separate, already-compliant concept and were not touched.
export interface CompanyScoreContributor {
  reason: string | null; source_type: "article" | "opportunity"; href: string | null;
  signed_magnitude: number; signal_at: string | null;
}
interface CompanyScoreVerdict { label: string; tone: string; reasoning: string }
export interface CompanyScoreData {
  symbol: string; score: number | null; confidence: number | null;
  signal_count: number; contributing_signal_count: number; sector: string | null;
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

export function OpportunityRadarSection({ stock }: { stock: StockDetail }) {
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
    <SectionCard title="Recent intelligence evidence">
      <p className="mt-1 text-[11px] leading-5 text-text-muted">
        Based on {data.contributing_signal_count} contributing signal{data.contributing_signal_count === 1 ? "" : "s"} from published analysis and opportunity tracking — this evidence feeds the MarketRipple Score's Current Intelligence pillar; it is not itself a company rating.
      </p>
      {data.top_contributors.length > 0 && (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {data.top_contributors.map((c, i) => {
            // SEO P1-P2, 2026-08-24 — real, backend-resolved link to the
            // opportunity this signal actually came from (was label-only
            // before; the id was always real, just never surfaced as a link).
            const inner = (
              <>
                <div className="flex items-center justify-between">
                  <span className="rounded-full border border-surface-border/10 bg-text-primary/5 px-2 py-0.5 text-[11px] text-text-muted">
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
              <div key={i}>
                <Link href={c.href as any} className={`${className} transition hover:border-emerald-500/25`}>{inner}</Link>
              </div>
            ) : (
              <div key={i} className={className}>
                {inner}
              </div>
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
    <SectionCard title="News impact analysis" action={
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
                  {hasScore && <span className={`rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${ic.text} border-current/20`}>{ic.label}</span>}
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

// ── News tab (queued Company-page request, 2026-08-25) ─────────────────────
// Same real, already-fetched data source NewsImpact/LatestDevelopmentsList
// use — GET /api/stocks/{symbol}/news (Finnhub's real last-7-days company
// news), falling back to stock.news (yfinance's own sparse feed) only when
// the richer fetch has nothing. Deliberately NOT a second, independent
// "company articles" query: MarketRipple's general NewsArticle pipeline has
// no reliable per-company field for RSS-sourced articles (RSSProvider.
// normalize() hardcodes companies=[]), so there is no other real source to
// build a broader feed from without fabricating relevance. No outbound
// links to the original article — see feedback_no_external_links — this is
// attribution-as-text only, same as NewsImpact.
function CompanyNewsTabBody({ stock, relatedNews }: { stock: StockDetail; relatedNews: any[] }) {
  const articles = relatedNews.length ? relatedNews : stock.news;

  if (!articles.length) {
    return (
      <SectionCard title="News">
        <p className="text-sm text-text-secondary">No real news coverage found for {stock.name} in the last 7 days.</p>
      </SectionCard>
    );
  }

  return (
    <SectionCard title={`News — ${stock.name}`}>
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {articles.map((a: any, i: number) => {
          const hasScore = typeof a.impact_score === "number";
          const score = hasScore ? Math.round(a.impact_score * 10) : 0;
          const ic = impactColor(score);
          return (
            <div key={i} className="flex items-start gap-3 rounded-2xl border border-surface-border/5 bg-text-primary/[0.02] p-4 hover:border-sky-400/10 transition">
              <div className={`h-14 w-14 shrink-0 rounded-xl ${["bg-gradient-to-br from-sky-500/20 to-violet-500/10","bg-gradient-to-br from-emerald-500/20 to-teal-500/10","bg-gradient-to-br from-rose-500/20 to-amber-500/10","bg-gradient-to-br from-amber-500/20 to-orange-500/10","bg-gradient-to-br from-violet-500/20 to-indigo-500/10"][i % 5]} flex items-center justify-center text-text-secondary`}>
                {([<BarChart2 className="h-6 w-6" />, <TrendingUp className="h-6 w-6" />, <TrendingDown className="h-6 w-6" />, <Landmark className="h-6 w-6" />, <Briefcase className="h-6 w-6" />])[i % 5]}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-1.5 mb-1">
                  {hasScore && <span className={`rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${ic.text} border-current/20`}>{ic.label}</span>}
                  <span className="text-[10px] text-text-muted">{a.source || "Source"}</span>
                  <span className="text-[10px] text-text-muted">{a.published_at?.slice(0, 10) || ""}</span>
                </div>
                <p className="text-[13px] font-semibold text-text-primary line-clamp-2">{a.headline}</p>
                {a.summary && <p className="mt-0.5 text-[11px] text-text-muted line-clamp-2">{a.summary}</p>}
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
    return <p className="px-1 text-[11.5px] text-text-muted">Analyst consensus: no analyst coverage data is available for this stock.</p>;
  }
  const bullPct = Math.round((stock.buy_count / total) * 100);
  const bearPct = Math.round((stock.sell_count / total) * 100);
  const neutPct = 100 - bullPct - bearPct;

  return (
    <SectionCard title="Analyst consensus">
      <div className="mt-4 flex items-center gap-3">
        <div className="relative h-24 w-24">
          <svg className="h-24 w-24" style={{ transform: "rotate(-90deg)" }} viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="32" stroke="rgb(var(--text-primary) / 0.08)" strokeWidth={8} fill="none"/>
            <circle cx="40" cy="40" r="32" stroke="#22c55e" strokeWidth={8} fill="none"
              strokeLinecap="round" strokeDasharray={`${(bullPct / 100) * 2 * Math.PI * 32} ${2 * Math.PI * 32}`}/>
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[18px] font-semibold text-emerald-400">{bullPct}%</span>
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
      <SectionCard title="Shareholding pattern">
        <p className="mt-4 text-[12px] text-text-muted">Shareholding data unavailable for this stock.</p>
      </SectionCard>
    );
  }
  return (
    <SectionCard title="Shareholding pattern">
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
    <SectionCard title="Peer comparison" action={
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
                <td className={`py-3 text-right font-semibold tabular-nums ${metricTone("pe", r.pe)}`}>{r.pe || "—"}</td>
                <td className={`py-3 text-right font-semibold tabular-nums ${metricTone("roe", r.roe)}`}>{r.roe || "—"}</td>
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
  const data = stock.annual_financials;
  if (!data.length) return null;
  // Revenue and net profit sit on different scales (profit is a fraction of revenue), so each gets its own chart rather than sharing one axis or a toggle.
  const panels: { key: "revenue" | "profit"; label: string; field: "revenue" | "net_income"; tone: string }[] = [
    { key: "revenue", label: "Revenue", field: "revenue", tone: "text-sky-600 dark:text-sky-300" },
    { key: "profit", label: "Net profit", field: "net_income", tone: "text-emerald-600 dark:text-emerald-400" },
  ];
  return (
    <SectionCard title="Historical performance">
      <div className="mt-4 grid grid-cols-1 gap-x-8 gap-y-6 md:grid-cols-2">
        {panels.map(pn => {
          const last = data[data.length - 1] as any, prev = data[data.length - 2] as any;
          const change = yoyPct(last?.[pn.field], prev?.[pn.field]);
          return (
            <div key={pn.key}>
              <div className="mb-2 flex items-baseline justify-between gap-2">
                <span className="text-[12px] text-text-muted">{pn.label}</span>
                {change !== null && (
                  <span className={`text-[12px] font-medium tabular-nums ${change >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
                    {change >= 0 ? "▲" : "▼"} {Math.abs(change).toFixed(1)}% YoY
                  </span>
                )}
              </div>
              <div className="h-[150px]">
                <HistoricalPerformanceBarChart data={data} activeMetric={pn.key}
                  currencyPrefix={stock.statement_currency_prefix} currencyUnit={stock.statement_currency_unit} />
              </div>
            </div>
          );
        })}
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
  comparison_intelligence: "Comparison", ripple_intelligence: "Ripple",
};
const articleTypeTag = (t: string) =>
  ARTICLE_TYPE_TAG[t] ?? (t.replace(/_intelligence$/, "").replace(/_/g, " ").replace(/^./, c => c.toUpperCase()));

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
    <SectionCard title="Latest intelligence" action={<Link href="/newsroom" className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View All →</Link>}>
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
                  className="group flex flex-col justify-between rounded-xl border border-surface-border/10 p-4 transition hover:border-surface-border/25 hover:bg-text-primary/[0.02]">
                  <div>
                    <span className="text-[11px] text-text-mutedst text-text-muted">{articleTypeTag(a.article_type)}</span>
                    <p className="mt-1.5 text-[14px] font-semibold leading-snug tracking-[-0.01em] text-text-primary line-clamp-2">{a.headline}</p>
                  </div>
                  {a.key_takeaway && <p className="mt-2 text-[12px] leading-5 text-text-muted line-clamp-2">{a.key_takeaway}</p>}
                </Link>
              ))}
            </div>
          )}
          {historical.length > 0 && (
            <div className="mt-4 border-t border-surface-border/5 pt-4">
              <p className="mb-2 text-[13px] font-medium text-text-secondary">Historical coverage</p>
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
      <p className="text-[12px] text-text-muted">{label}</p>
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
// Key Data → MarketRipple Score (or Current Intelligence, when the
// unified score isn't available for this company — see
// MarketRippleScoreSection) → Latest Developments → Opportunity preview,
// each answering one distinct question rather than one grid answering
// five at once. Every field here is still the same real data OverviewGrid
// already used — nothing new is fetched or invented, only regrouped and
// given room to be read as a conclusion rather than a cell.

// About — 1-3 real sentences, honest omission when there's no real
// description. This replaced the old "AI Company Summary" card's
// description role; that card's fabricated generic fallback and
// mislabeled "AI Generated" badge (Batch B) and its threshold-derived
// bullish/risk lists (redundant with CompanyScoreContributors' real,
// better-sourced positive/negative evidence on the Intelligence tab) are
// both gone rather than carried forward here.
function AboutSection({ stock }: { stock: StockDetail }) {
  let sentences = (stock.description ?? "").split(/(?<=[.!?])\s+/).filter(Boolean).slice(0, 3);
  // The backend caps descriptions at 600 chars, which can cut mid-word —
  // drop a truncated trailing fragment rather than print "software prod".
  const last = sentences[sentences.length - 1];
  if (last && !/[.!?]["')\]]?$/.test(last)) {
    sentences = sentences.length > 1 ? sentences.slice(0, -1) : [last.replace(/\s+\S*$/, "") + "…"];
  }
  // Always shown (a company without a description still has a name, ticker, sector and price): the first paragraph is what the company does, the second the
  // searchable context that used to sit as a plain-text row above the header (see lib/companyAbout.ts).
  return (
    <SectionCard title={aboutHeading(stock)}>
      {sentences.length > 0 && <p className="mt-2 text-[13px] leading-6 text-text-secondary">{sentences.join(" ")}</p>}
      <p className={`${sentences.length > 0 ? "mt-3" : "mt-2"} text-[13px] leading-6 text-text-secondary`}>{aboutSummary(stock)}</p>
    </SectionCard>
  );
}

// Key Data — compact, real market + financial facts only.
function KeyDataGrid({ stock }: { stock: StockDetail }) {
  return (
    <SectionCard title="Key data">
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[13px] sm:grid-cols-3">
        <div><p className="text-[12px] text-text-muted">Day range</p><p className="mt-0.5 font-semibold text-text-primary">₹{stock.day_low}–₹{stock.day_high}</p></div>
        <div><p className="text-[12px] text-text-muted">52-week range</p><p className="mt-0.5 font-semibold text-text-primary">₹{stock.week52_low}–₹{stock.week52_high}</p></div>
        <div><p className="text-[12px] text-text-muted">Volume</p><p className="mt-0.5 font-semibold text-text-primary">{stock.volume || "—"}</p></div>
        <div><p className="text-[12px] text-text-muted">P/E</p><p className={`mt-0.5 font-semibold tabular-nums ${metricTone("pe", stock.pe)}`}>{stock.pe || "—"}</p></div>
        <div><p className="text-[12px] text-text-muted">ROE</p><p className={`mt-0.5 font-semibold tabular-nums ${metricTone("roe", stock.roe)}`}>{stock.roe || "—"}</p></div>
        <div><p className="text-[12px] text-text-muted">D/E</p><p className={`mt-0.5 font-semibold tabular-nums ${metricTone("de", stock.debt_to_equity)}`}>{stock.debt_to_equity || "—"}</p></div>
        <div><p className="text-[12px] text-text-muted">Margin</p><p className={`mt-0.5 font-semibold tabular-nums ${metricTone("net_margin", stock.net_margins)}`}>{stock.net_margins || "—"}</p></div>
      </div>
    </SectionCard>
  );
}

// MarketRipple Score — the real, unified four-pillar card (S5-C,
// 2026-08-29). Deliberately restrained per owner spec: the headline
// number dominates, the four pillars read as an EXPLANATION of it (a
// compact horizontal row, never four more circular gauges competing with
// the headline), and evidence coverage is one understated line — not a
// second meter, not labeled "confidence" (coverage and confidence are
// different things: this is how much real evidence existed, not how sure
// the model is). No per-pillar weights shown here — that belongs to the
// methodology page (S5-D), not the Company card.
//
// A blocked company (eligible === false) NEVER shows its real internal
// score — that number is operational/debugging information, not a public
// fact. block_headline/block_message are the real, structural,
// server-computed reason (see public_projection.py's priority-ordered
// reason-code mapping) — never re-derived or guessed here.
export function MarketRippleScoreCard({ data, stock, localPreview }: { data: MarketRippleScoreData; stock: StockDetail; localPreview?: LocalPreviewData | null }) {
  const methodologyLink = (
    <Link href="/methodology/marketripple-score" className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">How this score works →</Link>
  );

  const pillars: { label: string; value: number | null | undefined }[] = [
    { label: "Financial strength",    value: data.pillars?.financial_strength },
    { label: "Valuation",             value: data.pillars?.valuation },
    { label: "Market behaviour",      value: data.pillars?.market_behaviour },
    { label: "Current intelligence",  value: data.pillars?.current_intelligence },
  ];
  const updated = data.calculated_at
    ? new Date(data.calculated_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })
    : null;

  // Comparability interim rule (2026-09-26): eligible but withheld because
  // fewer than 4 pillars produced a real number — a renormalized partial
  // blend isn't shown as a headline number/ranking, but whichever real
  // per-pillar values DID compute are still shown, not hidden behind a
  // generic "Unavailable".
  if (data.eligible === true && data.score == null && data.pillar_coverage_status === "partial") {
    return (
      <SectionCard title="MarketRipple Score" action={methodologyLink}>
        <p className="mt-1 text-[12px] leading-5 text-text-muted">
          A combined view of financial strength, valuation, market behaviour and current market intelligence.
        </p>
        <div className="mt-3 flex items-center gap-2">
          <span className="text-[15px] font-bold text-text-primary">Partial coverage</span>
        </div>
        <p className="mt-1 text-[12px] leading-5 text-text-muted">
          {data.pillar_coverage_message ?? "Not enough pillars are available yet for a combined score."} A combined
          number isn't shown until all four pillars are available, so partial results stay comparable to each other.
        </p>
        <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
          {pillars.map(p => (
            <div key={p.label}>
              <p className="text-[11px] text-text-muted">{p.label}</p>
              <p className="mt-1 text-[18px] font-semibold tabular-nums text-text-primary">{p.value != null ? Math.round(p.value) : "—"}</p>
            </div>
          ))}
        </div>
        {updated && <p className="mt-5 border-t border-surface-border/10 pt-3 text-[11px] text-text-muted">Updated {updated}</p>}
      </SectionCard>
    );
  }

  const eligible = data.eligible === true && data.score != null && (data.coverage_state ?? "scored") === "scored";

  // Unified redesign (2026-09-27, owner instruction: "why we showing score
  // unavailable and below we are showing the score... build good ui").
  // Before this, an ineligible/unpublished company rendered TWO stacked,
  // visually contradictory cards: a public "Unavailable" headline
  // immediately followed by a separate dashed-amber box showing the real
  // computed number underneath it. Real information (the score IS
  // computed, just not yet approved for public display) was true in both
  // states at once, but presented as if they disagreed. Below, a
  // dev-only real preview -- when one exists -- REPLACES the contradictory
  // "Unavailable" headline with a single, honest "Preview" state instead
  // of sitting beside it; the true "Unavailable" card only ever renders
  // when there is really nothing to show, in preview or otherwise.
  const isDevPreview = process.env.NODE_ENV === "development";
  const previewEligible = isDevPreview && !eligible
    && !!localPreview?.resolved && !!localPreview?.snapshot
    && localPreview?.eligible === true && localPreview?.score != null;

  if (!eligible && previewEligible && localPreview) {
    const previewUpdated = localPreview.calculated_at
      ? new Date(localPreview.calculated_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })
      : null;
    const previewPillars: { label: string; key: keyof NonNullable<LocalPreviewData["pillars"]> }[] = [
      { label: "Financial strength", key: "financial_strength" },
      { label: "Valuation", key: "valuation" },
      { label: "Market behaviour", key: "market_behaviour" },
      { label: "Current intelligence", key: "current_intelligence" },
    ];
    return (
      <SectionCard title="MarketRipple Score" action={methodologyLink}>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <span className="shrink-0 rounded-md border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-400">
            Preview — not yet published
          </span>
          <span className="text-[12px] text-text-muted">Computed and eligible; awaiting approval before it appears publicly</span>
        </div>

        <div className="mt-3 flex items-baseline gap-3">
          <span className={`text-[36px] font-semibold leading-none ${marketRippleRatingColor(localPreview.rating)}`}>{marketRippleScoreDisplayInt(localPreview.score)}</span>
          <span className="text-[13px] text-text-muted">/ 100</span>
          {localPreview.rating && (
            <span className={`text-[13px] font-medium ${marketRippleRatingColor(localPreview.rating)}`}>{localPreview.rating}</span>
          )}
        </div>

        <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
          {previewPillars.map(p => {
            const isEvidenceOnly = p.key === "current_intelligence";
            const value = localPreview.pillars?.[p.key];
            const weight = localPreview.effective_weights?.[p.key];
            return (
              <div key={p.label}>
                <p className="text-[11px] text-text-muted">
                  {p.label}{isEvidenceOnly && <span className="ml-1 text-text-muted/70">(evidence)</span>}
                </p>
                <p className="mt-1 text-[18px] font-semibold tabular-nums text-text-primary">{value != null ? Math.round(value) : "—"}</p>
                <p className="text-[11px] text-text-muted">
                  {isEvidenceOnly
                    ? "shown separately — not part of this score"
                    : weight != null ? `effective weight ${Math.round(weight * 100)}%` : "not contributing"}
                </p>
              </div>
            );
          })}
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-surface-border/10 pt-3 text-[11px] text-text-muted">
          <span>Financial metrics {localPreview.financial_metrics_used_count ?? "—"}/{localPreview.financial_metrics_total_count ?? "—"}</span>
          <span title="Percentage of available evidence used across the MarketRipple Score pillars. Missing or invalid evidence is not estimated.">
            Evidence coverage {Math.round(localPreview.evidence_coverage_pct ?? 0)}%
          </span>
          <span>Financial data as of {localPreview.financial_data_as_of ?? "—"}</span>
          {previewUpdated && <span>Calculated {previewUpdated}</span>}
        </div>

        <p className="mt-3 rounded-lg bg-amber-500/[0.06] px-3 py-2 text-[10px] leading-4 text-amber-700 dark:text-amber-400">
          Dev-only preview — a real, already-computed score, shown here only for local verification. It will never
          render like this in production; there, this company shows the same public "Unavailable" state as any
          other company still pending approval.
        </p>
      </SectionCard>
    );
  }

  if (!eligible) {
    return (
      <SectionCard title="MarketRipple Score" action={methodologyLink}>
        <p className="mt-2 text-[15px] font-semibold text-text-primary">{data.coverage_label ?? data.block_headline ?? "Not available yet"}</p>
        {(data.coverage_message ?? data.block_message) && (
          <p className="mt-1 max-w-[68ch] text-[13px] leading-6 text-text-muted">{data.coverage_message ?? data.block_message}</p>
        )}
      </SectionCard>
    );
  }

  return (
    <SectionCard title="MarketRipple Score" action={methodologyLink}>
      <p className="mt-1 text-[12px] leading-5 text-text-muted">
        A combined view of financial strength, valuation, market behaviour and current market intelligence.
      </p>
      <div className="mt-3 flex items-baseline gap-3">
        <span className={`text-[36px] font-semibold leading-none ${marketRippleRatingColor(data.rating)}`}>{marketRippleScoreDisplayInt(data.score)}</span>
        <span className="text-[13px] text-text-muted">/ 100</span>
        {data.rating && (
          <span className={`text-[13px] font-medium ${marketRippleRatingColor(data.rating)}`}>{data.rating}</span>
        )}
      </div>

      <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        {pillars.map(p => (
          <div key={p.label}>
            <p className="text-[11px] text-text-muted">{p.label}</p>
            <p className="mt-1 text-[18px] font-semibold tabular-nums text-text-primary">{p.value != null ? Math.round(p.value) : "—"}</p>
          </div>
        ))}
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-surface-border/10 pt-3 text-[11px] text-text-muted">
        <span title="Percentage of available evidence used across the MarketRipple Score pillars. Missing or invalid evidence is not estimated.">
          Evidence coverage {Math.round(data.evidence_coverage_pct ?? 0)}%
        </span>
        {updated && <span>Calculated {updated}</span>}
      </div>
      <p className="mt-2 text-[11px] leading-5 text-text-muted" data-testid="score-peer-note">
        {data.peer_count && (data.peer_group || data.sector) ? <>Ranked against {data.peer_count} {data.peer_group ?? data.sector} companies. </> : null}
        Scores are relative to a sector&apos;s peers, so they can change when companies are added.{" "}
        <Link href="/methodology/marketripple-score#peer-groups-heading" className="text-sky-400 hover:text-sky-600 dark:text-sky-300">Why?</Link>
      </p>
    </SectionCard>
  );
}

// One-score migration (2026-09-26, owner instruction), unified UI redesign
// (2026-09-27): this Overview-tab slot always renders the one canonical
// MarketRippleScoreCard, in whichever real state the projection is
// actually in — complete (eligible, scored), partial (eligible but
// withheld pending full pillar coverage), a dev-only real preview (see
// below), or unavailable (no methodology for this sector yet, no snapshot
// computed yet, blocked, or stale). It never falls back to the older
// single-engine score/verdict as a substitute company rating — the older
// engine's real evidence keeps its own, separately-labeled home on the
// Intelligence tab (CompanyScoreContributors, "Recent Intelligence
// Evidence") — never as a second, competing headline number here.
function MarketRippleScoreSection({ stock }: { stock: StockDetail }) {
  const data = useMarketRippleScore(stock.symbol);
  const eligible = !!data?.resolved && !!data?.snapshot && data.eligible === true && data.score != null;
  const isDev = process.env.NODE_ENV === "development";
  const localPreview = useLocalUnpublishedScorePreview(isDev && !eligible ? stock.symbol : "");
  if (data === undefined) return null; // still loading
  return <MarketRippleScoreCard data={data ?? { resolved: false }} stock={stock} localPreview={localPreview} />;
}

// ── Local unpublished score preview (2026-09-27, folded into
// MarketRippleScoreCard's own "preview" branch the same day per owner
// instruction — see that branch for the real UI this data now renders
// into) ──────────────────────────────────────────────────────────────
// Dev-only: the real, already-computed MarketRippleScoreSnapshot number
// regardless of the S2 phase lock (`publishable`, hardcoded False in
// engine.py — untouched by this hook), so the actual calculated score is
// visible while developing locally. Double-gated for safety: this hook's
// fetch is a no-op unless NODE_ENV==="development" (Next.js's own
// build-time constant — a real `next build` for production sets this to
// "production", so this branch is dead code in any real deployment, not
// just visually hidden), AND its backing endpoint
// (/marketripple-score/local-preview) independently 404s whenever
// settings.is_production is true on the backend. Neither gate depends on
// the other — either one alone already prevents this from ever reaching a
// real user.
export interface LocalPreviewData {
  resolved: boolean;
  snapshot?: boolean;
  local_dev_preview?: boolean;
  methodology_version?: string | null;
  publishable?: boolean;
  eligible?: boolean;
  block_reason_codes?: string[];
  score?: number | null;
  rating?: string | null;
  pillars?: { financial_strength: number | null; valuation: number | null; market_behaviour: number | null; current_intelligence: number | null };
  candidate_weights?: Record<string, number>;
  effective_weights?: Record<string, number | null>;
  evidence_coverage_pct?: number | null;
  financial_coverage_pct?: number | null;
  financial_metrics_used_count?: number | null;
  financial_metrics_total_count?: number | null;
  financial_data_as_of?: string | null;
  pillar_coverage_status?: string | null;
  pillar_coverage_message?: string | null;
  calculated_at?: string | null;
}

function useLocalUnpublishedScorePreview(symbol: string) {
  const [data, setData] = useState<LocalPreviewData | null | undefined>(undefined);
  useEffect(() => {
    if (process.env.NODE_ENV !== "development" || !symbol) return;
    let cancelled = false;
    setData(undefined);
    fetch(`${API}/api/companies/${symbol}/marketripple-score/local-preview`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData(null); });
    return () => { cancelled = true; };
  }, [symbol]);
  return data;
}

// Latest Developments — the most recent real news headline and material
// event, in one small list rather than two separate grid cells.
function LatestDevelopmentsList({ stock, relatedNews }: { stock: StockDetail; relatedNews: any[] }) {
  const latestNews = (relatedNews.length ? relatedNews : stock.news)?.[0];
  const latestEvent = stock.events?.[0];
  if (!latestNews && !latestEvent) return null;
  return (
    <SectionCard title="Latest developments" action={
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
      <h2 className="mb-4 text-[15px] font-semibold tracking-[-0.01em] text-text-primary">Frequently asked questions</h2>
      <div className="space-y-1.5">
        {faqs.map(f => (
          <details key={f.question} className="group rounded-xl border border-surface-border/10 px-4 py-3 transition hover:border-surface-border/20">
            <summary className="cursor-pointer list-none text-[13px] font-medium text-text-primary marker:content-none">
              {f.question}
            </summary>
            <p className="mt-2 max-w-[68ch] text-[13px] leading-6 text-text-secondary">{f.answer}</p>
          </details>
        ))}
      </div>
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

      {/* Key statistics */}
      <div className={`${CARD} p-5`}>
        <h3 className="mb-2 text-[15px] font-semibold tracking-[-0.01em] text-text-primary">Key statistics</h3>
        <div className="space-y-0">
          <KvRow label="Market cap"        value={stock.market_cap}/>
          <KvRow label="Enterprise value"  value={stock.enterprise_value}/>
          <KvRow label="P/E (TTM)"    value={stock.pe}           colored/>
          <KvRow label="P/B"          value={stock.pb}           colored/>
          <KvRow label="ROE"               value={stock.roe}          colored/>
          <KvRow label="ROCE"              value={stock.roce}         colored/>
          <KvRow label="Dividend yield"    value={stock.dividend_yield} colored/>
          <KvRow label="52-week high"          value={`₹${stock.week52_high}`}/>
          <KvRow label="52-week low"           value={`₹${stock.week52_low}`}/>
        </div>
      </div>

      {/* Recent events */}
      {stock.events.length > 0 && (
        <div className={`${CARD} p-5`}>
          <h3 className="mb-3 text-[15px] font-semibold tracking-[-0.01em] text-text-primary">Recent events</h3>
          <div className="space-y-2">
            {stock.events.slice(0, 3).map((e, i) => {
              const href = e.slug || e.id ? `/events/${e.slug || e.id}` : null;
              const inner = (
                <>
                  <div className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400"/>
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium text-text-primary line-clamp-2">{e.title}</p>
                    <p className="mt-0.5 text-[11px] text-text-muted">{e.date}</p>
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

// ── Recent Intelligence Evidence (Batch 2, renamed 2026-09-26) ──────────────────
// Intelligence tab, per the redesign audit: real Company Score
// contributors — including real negative ones — replacing the fabricated
// "Top Risks"/"Top Opportunities" cards removed in Batch 0. Fetches the
// same /api/company-scores/{symbol} endpoint OpportunityRadarSection
// (Opportunities tab) already uses, but renders company_score_engine.py's
// own positive/negative split instead of collapsing everything into one
// |magnitude|-sorted list — the FACT/EVIDENCE (real supporting signal) vs
// COUNTER-SIGNAL (real disagreeing signal) distinction the audit required.
//
// One-score migration (2026-09-26, owner instruction): renamed from "AI
// Company Score" to "Recent Intelligence Evidence" and stripped of every
// standalone numeric score, rating, verdict, and score-based colour gauge
// (the old headline number, the Risk/Trend pills, the "Evidence quality"
// label, and the verdict-reasoning sentence — which itself embedded the
// same score/risk as prose, e.g. "Opportunity score 62/100 · Medium
// risk"). A second, competing public company rating living on a different
// tab under a different name was still a second rating. The real
// calculation is untouched and keeps running internally — it's the
// Current Intelligence pillar's own input (current_intelligence.py) and
// is visible there in the MarketRipple Score card's own pillar
// breakdown — this section now shows only the dated, sourced evidence
// itself: real articles, real opportunities, real reasons, real dates.
function ContributorRow({ c, tone }: { c: CompanyScoreContributor; tone: "positive" | "negative" }) {
  const positive = tone === "positive";
  const inner = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className={`rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${
          positive
            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
            : "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-300"
        }`}>
          {positive ? "Supports" : "Counters"}
        </span>
        <span className={`text-[11px] font-bold ${positive ? "text-emerald-500" : "text-rose-500"}`}
          title="Impact on a 0-100 scale, taken from the source analysis or opportunity. The sign shows which way it points.">
          Impact {c.signed_magnitude >= 0 ? "+" : ""}{Math.round(c.signed_magnitude)}
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

export function CompanyScoreContributors({ stock }: { stock: StockDetail }) {
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
      <SectionCard title="Recent intelligence evidence">
        <p className="text-sm text-text-secondary">No intelligence evidence tracked for {stock.name} yet — built only from real published analysis and opportunity tracking, never estimated.</p>
      </SectionCard>
    );
  }

  const positives = dedupeEvidence(data.positive_reasons);
  const negatives = dedupeEvidence(data.risk_factors);
  const balance = evidenceBalance(positives, negatives);
  const SHOWN = 3;

  return (
    <SectionCard title="Recent intelligence evidence">
      <p className="mt-1 text-[11px] leading-5 text-text-muted">
        Based on {data.contributing_signal_count} contributing signal{data.contributing_signal_count === 1 ? "" : "s"} from published analysis and opportunity tracking — this evidence feeds the MarketRipple Score's Current Intelligence pillar; it is not itself a company rating.
      </p>

      {balance && (
        <div className="mt-4">
          <div className="flex items-center justify-between text-[11.5px]">
            <span className="font-medium text-emerald-700 dark:text-emerald-400">{balance.support} point{balance.support === 1 ? "" : "s"} support</span>
            <span className="font-medium text-rose-700 dark:text-rose-400">{balance.counter} point{balance.counter === 1 ? "" : "s"} counter</span>
          </div>
          <div className="mt-1.5 flex h-2 overflow-hidden rounded-full bg-text-primary/[0.06]" role="img" aria-label={`${balance.support} supporting and ${balance.counter} countering points`}>
            <div className="bg-emerald-500" style={{ width: `${balance.supportPct}%` }} />
            <div className="bg-rose-500" style={{ width: `${100 - balance.supportPct}%` }} />
          </div>
          <p className="mt-1.5 text-[10.5px] text-text-muted">Repeated points are counted once. Impact is on a 0–100 scale from the source analysis; it shows how strongly a point pulls, not a prediction.</p>
        </div>
      )}

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <EvidenceColumn title="What supports it" tone="positive" items={positives} shown={SHOWN} empty="No supporting points in the current evidence."/>
        <EvidenceColumn title="What counters it" tone="negative" items={negatives} shown={SHOWN} empty="No countering points in the current evidence."/>
      </div>
    </SectionCard>
  );
}

function EvidenceColumn({ title, tone, items, shown, empty }: { title: string; tone: "positive" | "negative"; items: CompanyScoreContributor[]; shown: number; empty: string }) {
  const [all, setAll] = useState(false);
  const rows = all ? items : items.slice(0, shown);
  return (
    <div>
      <p className={`mb-2.5 text-[13px] font-medium ${tone === "positive" ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400"}`}>{title}</p>
      {items.length > 0 ? (
        <div className="space-y-2.5">
          {rows.map((c, i) => <ContributorRow key={i} c={c} tone={tone}/>)}
          {items.length > shown && (
            <button type="button" onClick={() => setAll(a => !a)} aria-expanded={all}
              className="w-full rounded-xl border border-surface-border/10 py-2 text-[11.5px] font-medium text-text-secondary transition hover:bg-text-primary/[0.04]">
              {all ? "Show fewer" : `Show ${items.length - shown} more`}
            </button>
          )}
        </div>
      ) : (
        <p className="text-[12px] text-text-muted">{empty}</p>
      )}
    </div>
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
    <SectionCard title="What to watch">
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
// tab's 5 core concepts (the MarketRipple Score / Current Intelligence
// card lives on Overview; Why This View/What Changed/Key Evidence are
// CompanyScoreContributors + CompanyIntelligenceSection; What to Watch is
// above) — tucked behind
// progressive disclosure so they're available without competing with the
// primary read. Collapsed by default.
function MoreAnalysisDisclosure({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <div>
      <button onClick={() => setOpen(o => !o)} aria-expanded={open} aria-controls={panelId}
        className="flex w-full items-center justify-between rounded-xl border border-surface-border/10 bg-text-primary/[0.02] px-4 py-3 text-[12px] font-medium text-text-secondary hover:bg-text-primary/[0.04] transition">
        <span>{open ? "Hide" : "Show"} more analysis (Stock DNA, Pattern Intelligence)</span>
        <span className="text-text-muted" aria-hidden="true">{open ? "▲" : "▼"}</span>
      </button>
      {open && <div id={panelId} className="mt-4 space-y-6">{children}</div>}
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
interface StatementData {
  annual: StatementPeriod[]; quarterly: StatementPeriod[];
  half_yearly?: StatementPeriod[]; nine_months?: StatementPeriod[];
}
interface RatioPeriod {
  period: string; net_profit_margin: number | null; operating_margin: number | null;
  roe: number | null; roa: number | null; debt_to_equity: number | null; eps: number | null;
}
interface CapitalStructureData {
  as_of_period: string | null; shares_outstanding: number | null; face_value: number | null;
  book_value_per_share: number | null; market_cap: number | null;
  total_debt: number | null; shareholders_equity: number | null; debt_to_equity: number | null;
}
interface CompanyFinancialsData {
  symbol: string;
  income_statement: StatementData;
  balance_sheet: StatementData;
  cash_flow: StatementData;
  ratios: { annual: RatioPeriod[]; quarterly: RatioPeriod[] };
  capital_structure: CapitalStructureData;
  // Real per-statement reporting currency (yfinance's own info.financial
  // Currency — confirmed live: INFY reports in USD, most NSE companies in
  // INR) and the display unit its "currency"-unit fields were scaled to.
  // NOT the stock's own trading currency — market_cap is always real-time
  // NSE INR regardless of this.
  statement_currency: string;
  statement_currency_prefix: string;
  statement_currency_unit: string;
}

// The four period views a flow statement (P&L, Cash Flow) can offer —
// Balance Sheet only ever passes the first two, since a snapshot
// statement can't honestly be summed into a Half-Yearly/Nine-Month view.
const STATEMENT_PERIODS = [
  { key: "annual" as const,      label: "Yearly" },
  { key: "quarterly" as const,   label: "Quarterly" },
  { key: "half_yearly" as const, label: "Half Yearly" },
  { key: "nine_months" as const, label: "Nine Months" },
];
type StatementPeriodKey = typeof STATEMENT_PERIODS[number]["key"];

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

// currencyPrefix overrides a field's own "₹" placeholder at render time —
// fields are declared once with "₹" as a marker, but the real prefix
// depends on the company's own real statement currency (see
// statement_currency_prefix — USD "$" for INFY, INR "₹" for most others).
function fmtStatementValue(v: number | null | undefined, field: StatementFieldDef, currencyPrefix?: string): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  const prefix = field.prefix === "₹" ? (currencyPrefix ?? "₹") : (field.prefix ?? "");
  const formatted = field.prefix === "₹" ? v.toFixed(2) : abs >= 1000 ? Math.round(v).toLocaleString("en-IN") : v.toFixed(1);
  return `${prefix}${formatted}${field.suffix ?? ""}`;
}

function StatementTable({ title, data, fields, showYoy, currencyPrefix = "₹", currencyUnit = "Crore" }: {
  title: string; data: StatementData | undefined; fields: StatementFieldDef[]; showYoy?: boolean;
  currencyPrefix?: string; currencyUnit?: string;
}) {
  const available = STATEMENT_PERIODS.filter(p => (data?.[p.key]?.length ?? 0) > 0);
  const [period, setPeriod] = useState<StatementPeriodKey>("annual");
  const activeKey: StatementPeriodKey = available.some(p => p.key === period) ? period : (available[0]?.key ?? "annual");
  const rows = data?.[activeKey] ?? [];

  if (!data || available.length === 0) {
    return (
      <SectionCard title={title}>
        <p className="text-sm text-text-secondary">No real {title.toLowerCase()} data available for this company yet.</p>
      </SectionCard>
    );
  }

  return (
    <SectionCard title={title} action={
      available.length > 1 ? (
        <div className="flex gap-1 rounded-full border border-surface-border/10 bg-text-primary/[0.03] p-0.5">
          {available.map(p => (
            <button key={p.key} onClick={() => setPeriod(p.key)}
              className={`rounded-full px-3 py-1 text-[11px] font-medium transition ${
                activeKey === p.key ? "bg-sky-500/20 text-sky-600 dark:text-sky-300" : "text-text-muted hover:text-text-secondary"
              }`}>
              {p.label}
            </button>
          ))}
        </div>
      ) : null
    }>
      {rows.length === 0 ? (
        <p className="text-sm text-text-secondary">No real data available for this view — try another period above.</p>
      ) : (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-surface-border/6">
                <th className="pb-2 text-left text-[10px] font-medium text-text-muted">{currencyPrefix} in {currencyUnit}</th>
                {rows.map(r => <th key={r.period} className="pb-2 text-right text-[10px] font-medium text-text-muted">{r.period}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/3">
              {fields.map(field => (
                <tr key={field.key}>
                  <td className="py-2 text-text-secondary">{field.label}</td>
                  {rows.map((r, i) => {
                    const v = r[field.key] as number | null;
                    const prevV = activeKey === "annual" ? (rows[i + 1]?.[field.key] as number | null) : null;
                    const yoy = showYoy && activeKey === "annual" && (field.key === "revenue" || field.key === "net_profit") ? yoyPct(v, prevV) : null;
                    return (
                      <td key={r.period} className="py-2 text-right font-semibold text-text-primary">
                        {fmtStatementValue(v, field, currencyPrefix)}
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

const RATIO_FIELDS: StatementFieldDef[] = [
  { key: "net_profit_margin", label: "Net Profit Margin", suffix: "%" },
  { key: "operating_margin",  label: "Operating Margin",  suffix: "%" },
  { key: "roe",                label: "Return on Equity",  suffix: "%" },
  { key: "roa",                label: "Return on Assets",  suffix: "%" },
  { key: "debt_to_equity",     label: "Debt to Equity" },
  { key: "eps",                 label: "EPS", prefix: "₹" },
];

// Real ratios computed period-by-period from the same Income Statement +
// Balance Sheet data already shown above (see market_data.py::_compute_
// ratios) — never a second, independently-fetched ratio source that could
// silently disagree with the statements.
function RatiosTable({ ratios, currencyPrefix = "₹" }: {
  ratios: { annual: RatioPeriod[]; quarterly: RatioPeriod[] } | undefined; currencyPrefix?: string;
}) {
  const [period, setPeriod] = useState<"annual" | "quarterly">("annual");
  const hasAnnual = (ratios?.annual.length ?? 0) > 0;
  const hasQuarterly = (ratios?.quarterly.length ?? 0) > 0;
  const rows = (ratios?.[period] ?? []) as unknown as StatementPeriod[];

  if (!ratios || (!hasAnnual && !hasQuarterly)) {
    return (
      <SectionCard title="Ratios">
        <p className="text-sm text-text-secondary">No real ratio data available for this company yet.</p>
      </SectionCard>
    );
  }

  return (
    <SectionCard title="Ratios" action={
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
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-surface-border/6">
              <th className="pb-2 text-left text-[10px] font-medium text-text-muted">Ratio</th>
              {rows.map(r => <th key={r.period} className="pb-2 text-right text-[10px] font-medium text-text-muted">{r.period}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border/3">
            {RATIO_FIELDS.map(field => (
              <tr key={field.key}>
                <td className="py-2 text-text-secondary">{field.label}</td>
                {rows.map(r => (
                  <td key={r.period} className={`py-2 text-right font-semibold ${ratioFieldColor(field.key, r[field.key] as number | null)}`}>
                    {fmtStatementValue(r[field.key] as number | null, field, currencyPrefix)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

// Real, single latest-snapshot view (shares outstanding/market cap are
// point-in-time facts, not something to show per period) — see market_
// data.py::_compute_capital_structure. face_value stays "—" for the many
// real NSE symbols yfinance doesn't carry it for, never guessed.
// Market Cap is always real-time NSE INR (a .NS listing trades in INR
// regardless of which currency the company files financials in), while
// Total Debt/Shareholders' Equity/Book Value come straight from the
// statement DataFrames — for a USD-reporting company like INFY those are
// genuinely in statementCurrencyPrefix, not INR. Showing both in the same
// hardcoded "₹" would silently mislabel one of them.
function CapitalStructureCard({ data, statementCurrencyPrefix = "₹", statementCurrencyUnit = "Crore" }: {
  data: CapitalStructureData | undefined; statementCurrencyPrefix?: string; statementCurrencyUnit?: string;
}) {
  if (!data || (data.shares_outstanding == null && data.market_cap == null && data.total_debt == null)) {
    return (
      <SectionCard title="Capital structure">
        <p className="text-sm text-text-secondary">No real capital structure data available for this company yet.</p>
      </SectionCard>
    );
  }
  const rows: [string, string, string][] = [
    ["Shares Outstanding", data.shares_outstanding != null ? data.shares_outstanding.toLocaleString("en-IN") : "—", "text-text-primary"],
    ["Face Value", data.face_value != null ? `₹${data.face_value}` : "—", "text-text-primary"],
    ["Book Value / Share", data.book_value_per_share != null ? `${statementCurrencyPrefix}${data.book_value_per_share}` : "—", "text-text-primary"],
    ["Market Cap", data.market_cap != null ? `₹${data.market_cap.toLocaleString("en-IN")} Cr` : "—", "text-text-primary"],
    ["Total Debt", data.total_debt != null ? `${statementCurrencyPrefix}${data.total_debt.toLocaleString("en-IN")} ${statementCurrencyUnit}` : "—", "text-text-primary"],
    ["Shareholders' Equity", data.shareholders_equity != null ? `${statementCurrencyPrefix}${data.shareholders_equity.toLocaleString("en-IN")} ${statementCurrencyUnit}` : "—", "text-text-primary"],
    ["Debt to Equity", data.debt_to_equity != null ? String(data.debt_to_equity) : "—", ratioFieldColor("debt_to_equity", data.debt_to_equity)],
  ];
  return (
    <SectionCard title="Capital structure" action={
      data.as_of_period ? <span className="text-[10px] text-text-muted">as of {data.as_of_period}</span> : null
    }>
      <div className="mt-3 divide-y divide-surface-border/3">
        {rows.map(([label, value, colorClass]) => (
          <div key={label} className="flex items-center justify-between py-2 text-[12px]">
            <span className="text-text-secondary">{label}</span>
            <span className={`font-semibold ${colorClass}`}>{value}</span>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

const FINANCIALS_SUB_TABS = [
  { id: "overview", label: "Overview" },
  { id: "income",   label: "Profit & Loss" },
  { id: "balance",  label: "Balance Sheet" },
  { id: "cashflow", label: "Cash Flow" },
  { id: "ratios",   label: "Ratios" },
  { id: "capital",  label: "Capital Structure" },
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
        <StockExtrasCard symbol={stock.symbol}/>
        <Shareholding stock={stock}/>
        <HistoricalPerformance stock={stock}/>
      </>}
      {subTab === "income" && (
        financials === null
          ? null
          : <StatementTable title="Profit & Loss" data={financials.income_statement} fields={INCOME_STATEMENT_FIELDS} showYoy
              currencyPrefix={financials.statement_currency_prefix} currencyUnit={financials.statement_currency_unit}/>
      )}
      {subTab === "balance" && (
        financials === null
          ? null
          : <StatementTable title="Balance Sheet" data={financials.balance_sheet} fields={BALANCE_SHEET_FIELDS}
              currencyPrefix={financials.statement_currency_prefix} currencyUnit={financials.statement_currency_unit}/>
      )}
      {subTab === "cashflow" && (
        financials === null
          ? null
          : <StatementTable title="Cash Flow" data={financials.cash_flow} fields={CASH_FLOW_FIELDS}
              currencyPrefix={financials.statement_currency_prefix} currencyUnit={financials.statement_currency_unit}/>
      )}
      {subTab === "ratios" && (
        financials === null ? null : <RatiosTable ratios={financials.ratios} currencyPrefix={financials.statement_currency_prefix}/>
      )}
      {subTab === "capital" && (
        financials === null ? null : <CapitalStructureCard data={financials.capital_structure}
          statementCurrencyPrefix={financials.statement_currency_prefix} statementCurrencyUnit={financials.statement_currency_unit}/>
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
  { id: "news",          label: "News" },
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
          <span className="rounded-full border border-surface-border/10 bg-text-primary/5 px-2 py-0.5 text-[11px] text-text-muted">
            {RIPPLE_NODE_TYPE_LABEL[node.node_type] ?? node.node_type}
          </span>
          <span className="text-[11px] text-text-muted text-sky-500">{edge.edge_type.replace(/_/g, " ")}</span>
        </div>
        <p className="mt-1 text-[13px] font-medium leading-5 text-text-primary line-clamp-2">{node.label}</p>
        {edge.description && <p className="mt-0.5 text-[11px] text-text-muted line-clamp-2">{edge.description}</p>}
        {/* CD3-C: "Confidence {edge.confidence}%" removed -- ig_edges.confidence
            is overwhelmingly either upsert_edge()'s hardcoded 0.8 default or a
            hand-seeded constant, not a real per-relationship measurement, same
            finding that removed IntelligenceGraph.tsx's average-edge-confidence
            display earlier this session. */}
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-text-muted">
          <span>Weight {Math.round(edge.weight * 100)}%</span>
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
    return <RippleEmptyState title="Company ripple"
      body="Ripple relationship data is temporarily unavailable. Please try again shortly." />;
  }
  if (!data) return null;

  if (data.status === "no_entity") {
    return <RippleEmptyState title="Company ripple"
      body="Ripple relationship data is unavailable for this company." />;
  }
  if (data.status === "no_node") {
    return <RippleEmptyState title="Company ripple"
      body={`No verified Ripple relationships yet. MarketRipple has not accumulated enough evidence-backed relationships for ${stock.name} yet. This section will expand as new events and evidence are processed.`} />;
  }
  if (data.status === "no_edges") {
    return <RippleEmptyState title="Company ripple"
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
    <SectionCard title="Company ripple" action={
      <Link href="/graph" className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">Explore full graph →</Link>
    }>
      <p className="mb-4 text-[12px] text-text-muted">
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

      {/* ── Persistent header — stays fixed across every tab ─────────── */}
      <CompanyHero stock={stock} symbol={symbol} watchlisted={watchlisted} setWatchlisted={setWatchlisted}/>

      <CompanyTabNav active={activeTab} onChange={setTab}/>

      <div key={activeTab}>
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[1fr_320px]">

          {/* ── LEFT: the active tab's research body ────────────────── */}
          <div className="min-w-0 space-y-6">

            {/* Batch C (Company Simplification spec, §3) — Overview
                rebuilt to the spec's own explicit sequence: About → Key
                Data → MarketRipple Score/Current Intelligence → Latest
                Developments → (curated Latest Intelligence articles, a distinct real
                source from raw news/events) → FAQ moved to the bottom
                (was previously rendered above the entire page in
                page.tsx, repeated on every tab — see faqSection's own
                comment there). Price chart kept high in the flow — a
                real, valuable, non-fabricated element the "Google
                Finance restraint" reference point itself leads with.
                The spec's own "Opportunity preview" step was later
                removed per explicit instruction (2026-08-25) — the
                Opportunities tab already covers it; a preview here was
                duplication, not a distinct real view. */}
            {activeTab === "overview" && <>
              <AboutSection stock={stock}/>
              <PriceChart symbol={symbol} chartData={chartData} loadingChart={loadingChart}
                period={period} setPeriod={p => { setPeriod(p); fetchChart(p); }} stock={stock}/>
              <KeyDataGrid stock={stock}/>
              <MarketRippleScoreSection stock={stock}/>
              <LatestDevelopmentsList stock={stock} relatedNews={relatedNews}/>
              {/* "Current Opportunity" preview removed per explicit
                  instruction (2026-08-25) — the Opportunities tab is
                  already the dedicated real surface for this; a preview
                  here duplicated it rather than adding a distinct real
                  view. */}
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
                tab reduced to its real 5-concept core (the MarketRipple
                Score/Current Intelligence card lives on Overview; the other four are represented here):
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
              <CompanyIntelligenceSection symbol={symbol} govScore={stock.gov_score} pricePositive={stock.pct_change >= 0}
                self={{ name: stock.name, price: stock.price, pct_change: stock.pct_change, market_cap: stock.market_cap, pe: stock.pe, roe: stock.roe }}/>
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

            {activeTab === "news" && (
              <CompanyNewsTabBody stock={stock} relatedNews={relatedNews}/>
            )}

          </div>

          {/* ── RIGHT: sticky intelligence panel — present on every tab ── */}
          <aside className="lg:sticky lg:top-[88px] lg:max-h-[calc(100vh-100px)] lg:overflow-y-auto scrollbar-hide">
            <IntelligencePanel stock={stock}/>
          </aside>

        </div>
      </div>
    </main>
  );
}

export default function StockPage(props: PageProps & { initialStock?: StockDetail | null; initialRelated?: Record<string, RelatedItem[]> | null; faqs?: { question: string; answer: string }[] }) {
  return (
    <Suspense fallback={
      <main className="min-w-0 pb-10">
          <PageSkeleton/>
      </main>
    }>
      <StockPageInner {...props} />
    </Suspense>
  );
}
