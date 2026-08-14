"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Search, Clock, ChevronRight, Star, TrendingUp, TrendingDown,
  ShieldAlert, ShieldCheck, Landmark, ArrowLeftRight, Info, Share2, ThumbsUp, ThumbsDown,
  Flame, Building2, BarChart3, Target, SlidersHorizontal, ArrowRight,
} from "lucide-react";
import dynamic from "next/dynamic";
import { API_BASE_URL as API } from "@/lib/api";
import { truncateForQuery } from "@/lib/text";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// apps/web/app/events/[id]/EventSidebarCharts.tsx for the full rationale.
const PerformanceChartCard = dynamic(() => import("./PerformanceChartCard").then(m => m.PerformanceChartCard), { ssr: false });

export interface HistoricalListEvent {
  id: string;
  event_title: string;
  event_date: string;
  category: string;
  sentiment: string | null;
  sectors: string[];
  nifty_1w: number | null;
  nifty_1m: number | null;
  opportunity_score: number | null;
  risk_score: number | null;
  historical_score?: HistoricalScore;
}

export interface CategoryStats {
  category: string;
  count: number;
  avgImpact: number | null;
  successRate: number | null;
}

interface WinLoser { symbol: string; name: string; return_1m?: number; return_1w?: number; reason: string }

interface WindowReturns {
  before: { "7d"?: number | null; "30d"?: number | null; "90d"?: number | null };
  after: { "1d"?: number | null; "7d"?: number | null; "30d"?: number | null; "90d"?: number | null };
}

interface PatternCompany { symbol: string; name: string; wins: number; losses: number; appearances: number; avg_return: number; win_rate: number; reason: string | null }

interface ScoreBreakdownItem { label: string; weight: number; score: number }
interface PatternSnapshotScore {
  score: number;
  reliability: { label: string; emoji: string; tone: string };
  breakdown: ScoreBreakdownItem[];
}
export interface HistoricalScore {
  score: number;
  stars: number;
  band: string;
  breakdown: ScoreBreakdownItem[];
}

interface DetailData {
  id: string; event_title: string; event_date: string; category: string;
  sentiment: string | null; sectors: string[]; companies: string[]; tags: string[];
  market_regime: string | null; interest_rate_trend: string | null; crude_trend: string | null;
  vix_level: number | null;
  nifty_1d: number | null; nifty_3d: number | null; nifty_1w: number | null; nifty_1m: number | null;
  sector_reactions: Record<string, number>;
  historical_winners: WinLoser[];
  historical_losers: WinLoser[];
  opportunity_score: number | null; risk_score: number | null; confidence: number | null;
  what_happened: string | null; key_lesson: string | null;
  verdict: { label: string; tone: string; reasoning: string } | null;
  pattern?: {
    holding_period: { label: string; avg_return: number; positive_rate: number } | null;
    category_occurrences: number;
    top_winners: PatternCompany[];
    top_losers: PatternCompany[];
  };
  pattern_snapshot?: PatternSnapshotScore;
  historical_score?: HistoricalScore;
}

const AVATAR_COLORS = [
  "bg-blue-700", "bg-violet-700", "bg-emerald-700", "bg-amber-700",
  "bg-rose-700", "bg-sky-700", "bg-indigo-700", "bg-teal-700",
];
function avatarColor(symbol: string) {
  const idx = [...symbol].reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR_COLORS.length;
  return AVATAR_COLORS[idx];
}

// Real corporate domains for the NSE symbols that actually appear in the
// seeded historical winners/losers data — used to fetch a real logo via
// Clearbit's public logo API. Deliberately not a guessed/generated domain:
// unmapped symbols fall back to the letter-avatar rather than risk showing
// a wrong company's logo. A failed image load also falls back gracefully.
const SYMBOL_DOMAIN: Record<string, string> = {
  ADANIENT: "adanienterprises.com", ADANIGREEN: "adanigreenenergy.com", ADANIPORTS: "adaniports.com",
  ANGELONE: "angelone.in", ASIANPAINT: "asianpaints.com", BAJFINANCE: "bajajfinserv.in",
  BEL: "bel-india.in", BHEL: "bhel.com", BLUEDART: "bluedart.com", BSE: "bseindia.com",
  CHAMBLFERT: "chambalfertilisers.com", CHOLAFIN: "cholamandalam.com", CIPLA: "cipla.com",
  COALINDIA: "coalindia.in", DIVISLAB: "divislabs.com", DIXON: "dixoninfo.com", DLF: "dlf.in",
  DRREDDY: "drreddys.com", EDELWEISS: "edelweissfin.com", GMR: "gmrgroup.in", HAL: "hal-india.co.in",
  HDFC: "hdfc.com", HDFCBANK: "hdfcbank.com", HINDALCO: "hindalco.com", HINDUNILVR: "hul.co.in",
  ICICIBANK: "icicibank.com", INDIGO: "goindigo.in", INFY: "infosys.com", IRCON: "ircon.org",
  IRCTC: "irctc.co.in", ITC: "itcportal.com", JUBLFOOD: "jubilantfoodworks.com", KOTAK: "kotak.com",
  LICHSGFIN: "lichousing.com", LT: "larsentoubro.com", MARUTI: "marutisuzuki.com", MRF: "mrftyres.com",
  NTPC: "ntpc.co.in", OILINDIA: "oil-india.com", ONGC: "ongcindia.com", PAYTM: "paytm.com",
  RELIANCE: "ril.com", RVNL: "rvnl.org", SBIN: "sbi.co.in", SUNPHARMA: "sunpharma.com",
  TATACHEM: "tatachemicals.com", TATAMOTORS: "tatamotors.com", TATASTEEL: "tatasteel.com",
  TCS: "tcs.com", TITAN: "titancompany.in", WIPRO: "wipro.com", YESBANK: "yesbank.in",
};

function CompanyAvatar({ symbol, size = "h-6 w-6" }: { symbol: string; size?: string }) {
  const [failed, setFailed] = useState(false);
  const domain = SYMBOL_DOMAIN[symbol];
  if (domain && !failed) {
    return (
      <img
        src={`https://logo.clearbit.com/${domain}?size=64`}
        alt={symbol}
        onError={() => setFailed(true)}
        className={`${size} shrink-0 rounded-full border border-surface-border/10 bg-white object-contain p-0.5`}
      />
    );
  }
  return (
    <span className={`flex ${size} shrink-0 items-center justify-center rounded-full text-[9px] font-bold text-white ${avatarColor(symbol)}`}>
      {symbol.slice(0, 2)}
    </span>
  );
}

function pct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}
function pctCls(v: number | null | undefined): string {
  if (v == null) return "text-text-muted";
  return v >= 0 ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300";
}
// Real, mathematically-derived rating (see compute_historical_score in the
// backend) — not a cosmetic/random assignment. Renders half-stars since the
// banded score→star conversion produces values like 3.5/4.5.
function RatingStars({ historicalScore, size = "h-3 w-3" }: { historicalScore: HistoricalScore | null | undefined; size?: string }) {
  const stars = historicalScore?.stars ?? null;
  const title = historicalScore ? `${historicalScore.stars.toFixed(1)}/5 · ${historicalScore.band} (${historicalScore.score}/100)` : "No score";
  return (
    <span className="flex items-center gap-0.5" title={title}>
      {Array.from({ length: 5 }).map((_, i) => {
        const fill = stars == null ? 0 : Math.max(0, Math.min(1, stars - i));
        if (fill >= 1) return <Star key={i} className={`${size} fill-sky-500 text-sky-500`} />;
        if (fill > 0) {
          return (
            <span key={i} className={`relative ${size} inline-block shrink-0`}>
              <Star className={`${size} absolute inset-0 text-surface-border`} />
              <span className="absolute inset-0 overflow-hidden" style={{ width: "50%" }}>
                <Star className={`${size} fill-sky-500 text-sky-500`} />
              </span>
            </span>
          );
        }
        return <Star key={i} className={`${size} text-surface-border`} />;
      })}
    </span>
  );
}

// Answers "why N stars?" with the real breakdown the score is computed
// from (compute_historical_score) — not a second, different explanation.
// Per-factor mini-stars are score/20, a plain visual proxy for the %
// shown right next to it, not a separate rating.
function RatingBreakdownPopover({ historicalScore }: { historicalScore: HistoricalScore }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <div ref={ref} className="relative inline-flex items-center">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1 rounded-full px-1.5 py-0.5 text-text-muted transition hover:bg-text-primary/[0.06] hover:text-sky-600 dark:hover:text-sky-300"
        title="Why this rating?"
      >
        <Info className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-30 mt-2 w-[260px] rounded-xl border border-surface-border/12 bg-surface-card p-4 shadow-xl">
          <p className="mb-3 text-[11px] font-bold uppercase tracking-wide text-text-muted">Historical Rating Breakdown</p>
          <div className="space-y-2.5">
            {historicalScore.breakdown.map(b => (
              <div key={b.label} className="flex items-center justify-between gap-2">
                <span className="text-[11.5px] text-text-secondary">{b.label}</span>
                <span className="flex items-center gap-1.5">
                  <span className="text-[11px] font-bold tabular-nums text-text-primary">{b.score}</span>
                  <RatingStars historicalScore={{ score: b.score, stars: b.score / 20, band: "", breakdown: [] }} size="h-2.5 w-2.5" />
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-surface-border/10 pt-3">
            <span className="text-[11.5px] font-bold text-text-primary">Overall</span>
            <span className="flex items-center gap-1.5">
              <span className="text-[12px] font-black text-sky-600 dark:text-sky-300">{historicalScore.stars.toFixed(1)}/5</span>
              <RatingStars historicalScore={historicalScore} size="h-3 w-3" />
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function impactLabel(v: number | null): { label: string; cls: string } {
  if (v == null) return { label: "Unscored", cls: "text-text-muted" };
  const abs = Math.abs(v);
  if (abs >= 3) return { label: "High Impact", cls: v > 0 ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300" };
  if (abs >= 1) return { label: "Medium Impact", cls: "text-amber-600 dark:text-amber-300" };
  return { label: "Low Impact", cls: "text-text-muted" };
}
function regimeLabel(regime: string | null): string {
  if (!regime) return "—";
  const map: Record<string, string> = { bull: "Bullish", bear: "Bearish", recovery: "Recovering", sideways: "Sideways" };
  return map[regime.toLowerCase()] ?? regime;
}
function daysAgo(dateStr: string): number {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return 9999;
  return Math.floor((Date.now() - d.getTime()) / 86400000);
}
// key_lesson is stored as one narrative paragraph — split into sentence
// bullets for the checklist treatment rather than inventing separate
// bullet content that isn't in the real field.
function toBullets(text: string): string[] {
  return text.split(/(?<=[.!?])\s+/).map(s => s.trim()).filter(s => s.length > 8);
}

// Compact pill label for a real stored category — shortens the display
// text only, never substitutes a different category the data doesn't
// actually have.
const CATEGORY_SHORT: Record<string, string> = {
  "Monetary Policy": "RBI", "Union Budget": "Budget", "Corporate Crisis": "Corporate",
  "Global Market Shock": "Global Shock", "Geopolitical": "Geopolitical", "geopolitics": "Geopolitics",
  "Regulatory": "Regulatory", "Commodity Shock": "Commodity", "Election": "Elections",
  "Infrastructure Policy": "Infra", "Forex Inflows": "Forex", "India-US trade deal": "Trade Deal",
  "Rupee appreciation": "Rupee", "earnings miss": "Earnings", "market volatility": "Volatility",
  "regulatory action": "Regulatory", "regulatory issues": "Regulatory",
};
function shortCategory(c: string): string {
  return CATEGORY_SHORT[c] ?? (c.length > 12 ? c.split(" ")[0] : c);
}

export function HistoricalPatternsMasterDetail({
  events, categoryStats,
}: {
  events: HistoricalListEvent[];
  categoryStats: CategoryStats[];
}) {
  const [query, setQuery] = useState("");
  const [pill, setPill] = useState("All");
  const [selectedId, setSelectedId] = useState(events[0]?.id ?? null);
  const [detail, setDetail] = useState<DetailData | null>(null);
  const [fullSeries, setFullSeries] = useState<{ date: string; value: number }[] | null>(null);
  const [windows, setWindows] = useState<WindowReturns | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  const categoryCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of events) m.set(e.category, (m.get(e.category) ?? 0) + 1);
    return m;
  }, [events]);
  const pills = ["All", ...[...categoryCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([c]) => c)];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return events.filter(e => {
      if (pill !== "All" && e.category !== pill) return false;
      if (q && !e.event_title.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [events, query, pill]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    setLoadingDetail(true);
    setChartLoading(true);
    setFullSeries(null);
    setWindows(null);
    setFeedback(null);
    fetch(`${API}/api/historical/${selectedId}`).then(r => r.ok ? r.json() : null).then(d => {
      if (cancelled) return;
      setDetail(d);
      setLoadingDetail(false);
    });
    fetch(`${API}/api/historical/${selectedId}/chart`).then(r => r.ok ? r.json() : null).then(c => {
      if (cancelled) return;
      setFullSeries(c?.full_series ?? []);
      setWindows(c?.windows ?? null);
      setChartLoading(false);
    });
    return () => { cancelled = true; };
  }, [selectedId]);

  const stats = detail ? categoryStats.find(s => s.category === detail.category) : null;
  const sameCategory = detail ? events.filter(e => e.category === detail.category && e.id !== detail.id) : [];
  const lastOccurred = sameCategory
    .map(e => e.event_date)
    .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0] ?? null;
  const similar = sameCategory.slice(0, 4);

  const summaryBullets = detail?.key_lesson ? toBullets(detail.key_lesson) : [];
  const whatHappenedText = detail?.what_happened ?? null;

  return (
    <div>
      {/* Top actions */}
      <div className="mb-4 flex flex-wrap items-center justify-end gap-2">
        <Link href="#how-it-works" className="flex items-center gap-1.5 rounded-full border border-surface-border/10 bg-surface-card px-3.5 py-1.5 text-[12px] font-semibold text-text-secondary transition hover:border-sky-500/30 hover:text-text-primary">
          <Info className="h-3.5 w-3.5" /> How it works
        </Link>
        <button
          onClick={() => { if (typeof navigator !== "undefined" && navigator.share && detail) navigator.share({ title: detail.event_title, url: window.location.href }).catch(() => {}); }}
          className="flex items-center gap-1.5 rounded-full border border-surface-border/10 bg-surface-card px-3.5 py-1.5 text-[12px] font-semibold text-text-secondary transition hover:border-sky-500/30 hover:text-text-primary"
        >
          <Share2 className="h-3.5 w-3.5" /> Share
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[340px_1fr]">
        {/* ── Left: search + list ─────────────────────────────────────── */}
        <div className="flex flex-col rounded-[20px] border border-surface-border/8 bg-surface-card p-3">
          <div className="relative mb-3">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search historical events..."
              className="w-full rounded-xl border border-surface-border/10 bg-text-primary/[0.02] py-2 pl-9 pr-9 text-[12.5px] text-text-primary outline-none transition placeholder:text-text-muted focus:border-sky-500/40"
            />
            <button
              onClick={() => { setQuery(""); setPill("All"); }}
              title="Reset filters"
              className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-lg text-text-muted transition hover:bg-text-primary/[0.06] hover:text-text-secondary"
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="mb-3 flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:none]">
            {pills.map(p => (
              <button
                key={p}
                onClick={() => setPill(p)}
                className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
                  pill === p ? "bg-sky-500 text-white" : "bg-text-primary/[0.04] text-text-secondary hover:bg-text-primary/[0.07]"
                }`}
              >
                {p === "All" ? "All" : shortCategory(p)}
              </button>
            ))}
          </div>

          <div className="relative max-h-[720px] overflow-y-auto pr-1">
            {filtered.length === 0 ? (
              <p className="py-10 text-center text-[12px] text-text-muted">No events match this search.</p>
            ) : (
              <div className="relative space-y-1.5">
                {/* Timeline rail connecting each occurrence */}
                <div className="absolute bottom-2 left-[15px] top-2 w-px bg-surface-border/20" />
                {filtered.map(e => {
                  const impact = e.nifty_1m ?? e.nifty_1w;
                  const il = impactLabel(impact);
                  const isNew = daysAgo(e.event_date) <= 14;
                  const active = e.id === selectedId;
                  return (
                    <button
                      key={e.id}
                      onClick={() => setSelectedId(e.id)}
                      className={`relative flex w-full items-start gap-2.5 rounded-[14px] border p-3 pl-8 text-left transition ${
                        active ? "border-sky-500/30 bg-sky-500/[0.06]" : "border-transparent hover:bg-text-primary/[0.03]"
                      }`}
                    >
                      <span className={`absolute left-[10px] top-[18px] h-2.5 w-2.5 rounded-full border-2 border-surface-card ${active ? "bg-sky-500" : "bg-text-muted/50"}`} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 text-[10px] text-text-muted">
                          <Clock className="h-2.5 w-2.5" /> {e.event_date}
                          {isNew && <span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 font-bold text-emerald-600 dark:text-emerald-300">New</span>}
                        </div>
                        <p className="mt-1 line-clamp-2 text-[13px] font-bold leading-snug text-text-primary">{e.event_title}</p>
                        <div className="mt-1.5 flex items-center justify-between">
                          <RatingStars historicalScore={e.historical_score} />
                          <span className={`text-[10.5px] font-semibold ${il.cls}`}>{il.label}</span>
                        </div>
                        <p className="mt-1 text-[10.5px] text-text-muted">{e.category}{e.sectors[0] ? ` · ${e.sectors[0]}` : ""}</p>
                      </div>
                      <ChevronRight className="mt-1 h-3.5 w-3.5 shrink-0 text-text-muted" />
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {(query || pill !== "All") && (
            <button
              onClick={() => { setQuery(""); setPill("All"); }}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl border border-surface-border/10 py-2 text-[12px] font-semibold text-sky-600 transition hover:bg-sky-500/[0.06] dark:text-sky-300"
            >
              View All Historical Events <ArrowRight className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* ── Right: detail panel ─────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_300px]">
          <div className="space-y-4">
            {!detail ? (
              <div className="flex h-64 items-center justify-center rounded-[20px] border border-surface-border/8 bg-surface-card">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-sky-500 border-t-transparent" />
              </div>
            ) : (
              <>
                {/* Header */}
                <div className="rounded-[20px] border border-surface-border/8 bg-surface-card p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-sky-500/10 text-sky-600 dark:text-sky-300">
                        <Landmark className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-[17px] font-black text-text-primary">{detail.event_title}</p>
                          {daysAgo(detail.event_date) <= 14 && (
                            <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-600 dark:text-emerald-300">New</span>
                          )}
                        </div>
                        <p className="mt-1 text-[11.5px] text-text-muted">{detail.event_date} · {detail.category}</p>
                        <div className="mt-1.5 flex items-center gap-1.5">
                          <RatingStars historicalScore={detail.historical_score} />
                          {detail.historical_score ? (
                            <>
                              <span className="text-[10.5px] text-text-muted">{detail.historical_score.stars.toFixed(1)}/5 · {detail.historical_score.band}</span>
                              <RatingBreakdownPopover historicalScore={detail.historical_score} />
                            </>
                          ) : (
                            <span className="text-[10.5px] text-text-muted">No score</span>
                          )}
                        </div>
                      </div>
                    </div>
                    {detail.confidence != null && (
                      <div className="rounded-[14px] border border-surface-border/8 bg-text-primary/[0.02] px-4 py-2.5 text-right">
                        <p className="text-[10px] uppercase tracking-wide text-text-muted">Historical Confidence</p>
                        <p className="text-[22px] font-black text-sky-600 dark:text-sky-300">{Math.round(detail.confidence)}%</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* NIFTY chart with real 1M/3M/6M/1Y ranges + Before/During/After zones */}
                <PerformanceChartCard
                  fullSeries={fullSeries ?? []}
                  eventDate={detail.event_date}
                  isLoading={chartLoading || !fullSeries}
                />

                {/* Standardized before/after window returns — real, computed
                    from the same daily series as the chart above. */}
                {windows && (windows.before["7d"] != null || windows.after["1d"] != null) && (
                  <div className="rounded-[20px] border border-surface-border/8 bg-surface-card p-5">
                    <p className="mb-3 text-[13px] font-bold text-text-primary">Historical Pattern Snapshot</p>
                    <div className="grid grid-cols-3 gap-3 sm:grid-cols-7">
                      {([
                        ["7D Before", windows.before["7d"]], ["30D Before", windows.before["30d"]], ["90D Before", windows.before["90d"]],
                        ["1D After", windows.after["1d"]], ["7D After", windows.after["7d"]], ["30D After", windows.after["30d"]], ["90D After", windows.after["90d"]],
                      ] as [string, number | null | undefined][]).map(([label, v]) => (
                        <div key={label} className="text-center">
                          <p className="text-[9px] font-bold uppercase tracking-wide text-text-muted">{label}</p>
                          <p className={`mt-1 text-[14px] font-black tabular-nums ${pctCls(v)}`}>{pct(v)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* AI Summary — checklist bullets from the real key_lesson field */}
                {summaryBullets.length > 0 && (
                  <div className="rounded-[20px] border border-surface-border/8 bg-surface-card p-5">
                    <p className="mb-3 text-[13px] font-bold text-text-primary">AI Summary</p>
                    <ul className="space-y-2">
                      {summaryBullets.map((b, i) => (
                        <li key={i} className="flex items-start gap-2 text-[13px] leading-relaxed text-text-secondary">
                          <span className="mt-0.5 shrink-0 text-emerald-500">✓</span> {b}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Historical Winners / Losers — full company-consistency
                    treatment. Aggregated across every occurrence in this
                    category when there's more than one (real win_rate/
                    appearances from compute_category_pattern); falls back
                    to this single event's own winners/losers otherwise. */}
                {(() => {
                  if (!detail.pattern) return null;
                  const multi = detail.pattern.category_occurrences > 1;
                  const winners = multi
                    ? detail.pattern.top_winners
                    : detail.historical_winners.map(w => ({ symbol: w.symbol, name: w.name || w.symbol, wins: 1, losses: 0, appearances: 1, avg_return: w.return_1m ?? w.return_1w ?? 0, win_rate: 100, reason: w.reason }));
                  const losers = multi
                    ? detail.pattern.top_losers
                    : detail.historical_losers.map(w => ({ symbol: w.symbol, name: w.name || w.symbol, wins: 0, losses: 1, appearances: 1, avg_return: w.return_1m ?? w.return_1w ?? 0, win_rate: 0, reason: w.reason }));
                  if (winners.length === 0 && losers.length === 0) return null;
                  return (
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <div className="rounded-[20px] border border-emerald-500/15 bg-emerald-500/[0.03] p-4">
                        <p className="mb-3 flex items-center gap-1.5 text-[12px] font-bold text-emerald-600 dark:text-emerald-300"><TrendingUp className="h-3.5 w-3.5" /> Historical Winners</p>
                        {winners.length === 0 ? (
                          <p className="text-[11.5px] text-text-muted">No real winners recorded.</p>
                        ) : (
                          <div className="space-y-3.5">
                            {winners.slice(0, 5).map(w => (
                              <div key={w.symbol} className="flex items-center gap-2.5">
                                <CompanyAvatar symbol={w.symbol} />
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center justify-between gap-2">
                                    <p className="truncate text-[12.5px] font-bold text-text-primary">{w.name}</p>
                                    <p className="shrink-0 text-[12.5px] font-bold text-emerald-600 dark:text-emerald-300">{pct(w.avg_return)}</p>
                                  </div>
                                  <div className="mt-0.5 flex items-center justify-between gap-2">
                                    <span className="text-[10px] text-text-muted">{multi ? `Appeared in ${w.appearances} similar event${w.appearances === 1 ? "" : "s"}` : w.reason}</span>
                                    <span className="flex shrink-0 items-center gap-1">
                                      <span className="text-[9.5px] text-text-muted">Consistency</span>
                                      <RatingStars historicalScore={{ score: w.win_rate, stars: w.win_rate / 20, band: "", breakdown: [] }} size="h-2.5 w-2.5" />
                                    </span>
                                  </div>
                                </div>
                              </div>
                            ))}
                            {winners[0] && (
                              <Link href={`/companies/${winners[0].symbol}`} className="mt-1 flex items-center gap-1 text-[11px] font-semibold text-emerald-600 hover:underline dark:text-emerald-300">
                                View History <ArrowRight className="h-3 w-3" />
                              </Link>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="rounded-[20px] border border-rose-500/15 bg-rose-500/[0.03] p-4">
                        <p className="mb-3 flex items-center gap-1.5 text-[12px] font-bold text-rose-600 dark:text-rose-300"><TrendingDown className="h-3.5 w-3.5" /> Historical Losers</p>
                        {losers.length === 0 ? (
                          <p className="text-[11.5px] text-text-muted">No real losers recorded.</p>
                        ) : (
                          <div className="space-y-3.5">
                            {losers.slice(0, 5).map(l => (
                              <div key={l.symbol} className="flex items-center gap-2.5">
                                <CompanyAvatar symbol={l.symbol} />
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center justify-between gap-2">
                                    <p className="truncate text-[12.5px] font-bold text-text-primary">{l.name}</p>
                                    <p className="shrink-0 text-[12.5px] font-bold text-rose-600 dark:text-rose-300">{pct(l.avg_return)}</p>
                                  </div>
                                  <div className="mt-0.5 flex items-center justify-between gap-2">
                                    <span className="text-[10px] text-text-muted">{multi ? `Appeared in ${l.appearances} similar event${l.appearances === 1 ? "" : "s"}` : l.reason}</span>
                                    <span className="flex shrink-0 items-center gap-1">
                                      <span className="text-[9.5px] text-text-muted">Consistency</span>
                                      <RatingStars historicalScore={{ score: 100 - l.win_rate, stars: (100 - l.win_rate) / 20, band: "", breakdown: [] }} size="h-2.5 w-2.5" />
                                    </span>
                                  </div>
                                </div>
                              </div>
                            ))}
                            {losers[0] && (
                              <Link href={`/companies/${losers[0].symbol}`} className="mt-1 flex items-center gap-1 text-[11px] font-semibold text-rose-600 hover:underline dark:text-rose-300">
                                View History <ArrowRight className="h-3 w-3" />
                              </Link>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}

                {/* Sector Impact / AI Verdict */}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="rounded-[20px] border border-surface-border/8 bg-surface-card p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <p className="text-[12px] font-bold text-text-primary">Sector Impact</p>
                      <Link href="/companies?tab=sectors" className="text-[10.5px] font-semibold text-sky-600 dark:text-sky-300 hover:underline">View heatmap</Link>
                    </div>
                    {Object.keys(detail.sector_reactions ?? {}).length === 0 ? (
                      <p className="text-[11.5px] text-text-muted">No real sector-level data for this event.</p>
                    ) : (
                      <div className="space-y-2.5">
                        {Object.entries(detail.sector_reactions).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 4).map(([sector, v]) => {
                          const maxAbs = Math.max(...Object.values(detail.sector_reactions).map(Math.abs), 1);
                          const width = Math.min(100, (Math.abs(v) / maxAbs) * 100);
                          return (
                            <div key={sector}>
                              <div className="flex items-center justify-between text-[11px]">
                                <span className="text-text-secondary">{sector}</span>
                                <span className={`font-bold ${pctCls(v)}`}>{pct(v)}</span>
                              </div>
                              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-text-primary/[0.05]">
                                <div className={`h-full rounded-full ${v >= 0 ? "bg-emerald-500" : "bg-rose-500"}`} style={{ width: `${width}%` }} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div className="rounded-[20px] border border-sky-500/15 bg-sky-500/[0.04] p-4">
                    <p className="mb-3 flex items-center gap-1.5 text-[12px] font-bold text-text-primary"><Target className="h-3.5 w-3.5 text-sky-500" /> AI Investment Verdict</p>
                    {detail.verdict ? (
                      <>
                        <span className={`inline-block rounded-full px-2 py-0.5 text-[10.5px] font-bold ${detail.verdict.tone === "positive" ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" : detail.verdict.tone === "negative" ? "bg-rose-500/15 text-rose-700 dark:text-rose-300" : "bg-text-primary/[0.06] text-text-secondary"}`}>
                          {detail.verdict.label}
                        </span>
                        <p className="mt-2 text-[11.5px] leading-relaxed text-text-secondary">{detail.verdict.reasoning}</p>
                        <Link
                          href={`/ai-search?q=${encodeURIComponent(`How does today's market compare to the conditions around "${truncateForQuery(detail.event_title)}"?`)}`}
                          className="mt-3 inline-flex items-center gap-1 text-[11px] font-semibold text-sky-600 dark:text-sky-300 hover:underline"
                        >
                          Compare with today <ChevronRight className="h-3 w-3" />
                        </Link>
                      </>
                    ) : (
                      <p className="text-[11.5px] text-text-muted">Not enough real signal to compute a verdict for this event.</p>
                    )}
                  </div>
                </div>

                {/* What Happened — real macro context + ripple sequence, not an invented causal chain */}
                <div className="rounded-[20px] border border-surface-border/8 bg-surface-card p-5">
                  <p className="mb-3 text-[13px] font-bold text-text-primary">What Happened</p>
                  {whatHappenedText && <p className="mb-4 text-[12.5px] leading-relaxed text-text-secondary">{whatHappenedText}</p>}
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                    {detail.interest_rate_trend && (
                      <RippleCard icon={<ArrowLeftRight className="h-4 w-4" />} label={`Interest rates ${detail.interest_rate_trend}`} />
                    )}
                    {detail.crude_trend && (
                      <RippleCard icon={<Flame className="h-4 w-4" />} label={`Crude ${detail.crude_trend}`} />
                    )}
                    {Object.entries(detail.sector_reactions ?? {}).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 3).map(([sector, v]) => (
                      <RippleCard key={sector} icon={<Building2 className="h-4 w-4" />} label={sector} sub={pct(v)} tone={v >= 0 ? "positive" : "negative"} />
                    ))}
                    <RippleCard icon={<BarChart3 className="h-4 w-4" />} label="Nifty (1M)" sub={pct(detail.nifty_1m ?? detail.nifty_1w)} tone={(detail.nifty_1m ?? detail.nifty_1w ?? 0) >= 0 ? "positive" : "negative"} />
                  </div>
                </div>

                {/* Footer — real occurrence/success-rate stats + feedback */}
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-[20px] border border-surface-border/8 bg-text-primary/[0.02] px-5 py-3.5 text-[11.5px] text-text-muted">
                  <p>
                    {stats ? `This pattern (${detail.category}) has occurred ${stats.count} time${stats.count === 1 ? "" : "s"}${stats.successRate != null ? ` with a ${Math.round(stats.successRate)}% success rate` : ""}.` : "Category-level pattern statistics unavailable."}
                  </p>
                  <div className="flex items-center gap-3">
                    <span>Was this analysis helpful?</span>
                    <button onClick={() => setFeedback("up")} className={`transition ${feedback === "up" ? "text-emerald-500" : "text-text-muted hover:text-text-secondary"}`}><ThumbsUp className="h-3.5 w-3.5" /></button>
                    <button onClick={() => setFeedback("down")} className={`transition ${feedback === "down" ? "text-rose-500" : "text-text-muted hover:text-text-secondary"}`}><ThumbsDown className="h-3.5 w-3.5" /></button>
                    <span className="text-text-muted/70">MarketRipple Historical Memory Engine</span>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Sidebar: Pattern Snapshot + Similar Events */}
          {detail && (
            <div className="space-y-4">
              <div className="rounded-[20px] border border-surface-border/8 bg-surface-card p-5">
                <div className="mb-1 flex items-center justify-between">
                  <p className="text-[12px] font-bold uppercase tracking-wide text-text-muted">Pattern Snapshot</p>
                  {detail.pattern_snapshot && (
                    <span className="text-[11px] font-semibold">
                      {detail.pattern_snapshot.reliability.emoji} {detail.pattern_snapshot.reliability.label}
                    </span>
                  )}
                </div>
                {stats && (
                  <p className="mb-3 text-[10.5px] text-text-muted">
                    Based on {stats.count} historical {detail.category} event{stats.count === 1 ? "" : "s"}
                  </p>
                )}
                {detail.pattern_snapshot && (
                  <>
                    <div className="mb-4 flex items-end justify-between border-b border-surface-border/8 pb-3">
                      <div>
                        <p className="text-[10px] text-text-muted">Overall Historical Match</p>
                        <p className="text-[28px] font-black text-sky-600 dark:text-sky-300">{detail.pattern_snapshot.score}%</p>
                      </div>
                    </div>
                    <div className="space-y-2 text-[12px]">
                      {detail.pattern_snapshot.breakdown.map(b => (
                        <div key={b.label} className="flex items-center justify-between gap-2">
                          <span className="flex items-center gap-1.5 text-text-secondary">
                            <ShieldCheck className="h-3 w-3 shrink-0 text-emerald-500" /> {b.label}
                          </span>
                          <span className="font-bold text-text-primary tabular-nums">{b.score}%</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
                <div className="mt-4 space-y-2.5 border-t border-surface-border/8 pt-3.5 text-[12.5px]">
                  <Row label="Occurrences" value={stats ? `${stats.count} time${stats.count === 1 ? "" : "s"}` : "—"} />
                  <Row label="Last Occurred" value={lastOccurred ?? "—"} />
                  <Row label="Average Duration" value={detail.pattern?.holding_period?.label ?? "—"} />
                  <Row label="Risk Score" value={detail.risk_score != null ? `${Math.round(detail.risk_score)}/100` : "—"} />
                  <Row label="Volatility (VIX)" value={detail.vix_level != null ? detail.vix_level.toFixed(1) : "—"} />
                  <Row label="Market Regime" value={regimeLabel(detail.market_regime)} />
                </div>
                <button
                  onClick={() => setPill(detail.category)}
                  className="mt-4 w-full rounded-xl border border-surface-border/10 bg-text-primary/[0.02] py-2 text-[11.5px] font-semibold text-text-secondary transition hover:border-sky-500/30 hover:text-text-primary"
                >
                  View Full Statistics
                </button>
              </div>

              {similar.length > 0 && (
                <div className="rounded-[20px] border border-surface-border/8 bg-surface-card p-5">
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-[12px] font-bold uppercase tracking-wide text-text-muted">Similar Historical Events</p>
                    <button onClick={() => setPill(detail.category)} className="text-[10.5px] font-semibold text-sky-600 dark:text-sky-300 hover:underline">View all</button>
                  </div>
                  <div className="space-y-3">
                    {similar.map(e => (
                      <button key={e.id} onClick={() => setSelectedId(e.id)} className="flex w-full items-center justify-between gap-2 text-left transition hover:opacity-80">
                        <span className="line-clamp-1 text-[12px] font-semibold text-text-primary">{e.event_title}</span>
                        <span className="flex shrink-0 items-center gap-2">
                          <RatingStars historicalScore={e.historical_score} size="h-2.5 w-2.5" />
                          <ChevronRight className="h-3.5 w-3.5 text-text-muted" />
                        </span>
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => setPill("All")}
                    className="mt-4 w-full rounded-xl border border-surface-border/10 bg-text-primary/[0.02] py-2 text-[11.5px] font-semibold text-text-secondary transition hover:border-sky-500/30 hover:text-text-primary"
                  >
                    Compare All Events
                  </button>
                </div>
              )}

              <div className="rounded-[20px] border border-amber-500/15 bg-amber-500/[0.04] p-4 text-[11.5px] leading-relaxed text-text-secondary">
                <ShieldAlert className="mb-1.5 h-4 w-4 text-amber-500" />
                Historical patterns are not guarantees of future performance — real past outcomes, shown for research context only.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-surface-border/5 pb-2.5 last:border-0 last:pb-0">
      <span className="text-text-muted">{label}</span>
      <span className={cls ?? "text-text-primary"}>{value}</span>
    </div>
  );
}

function RippleCard({ icon, label, sub, tone }: { icon: React.ReactNode; label: string; sub?: string; tone?: "positive" | "negative" }) {
  const cls = tone === "positive" ? "text-emerald-600 dark:text-emerald-300" : tone === "negative" ? "text-rose-600 dark:text-rose-300" : "text-text-secondary";
  return (
    <div className="flex flex-col items-center gap-1.5 rounded-[14px] border border-surface-border/8 bg-text-primary/[0.02] p-3 text-center">
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-sky-500/10 text-sky-600 dark:text-sky-300">{icon}</span>
      <p className="line-clamp-2 text-[10.5px] font-semibold leading-tight text-text-primary">{label}</p>
      {sub && <p className={`text-[11px] font-bold ${cls}`}>{sub}</p>}
    </div>
  );
}

