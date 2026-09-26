"use client";

import { useState, useEffect, useMemo, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import { Trophy, Shield, ClipboardList, BarChart2, X } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import type { MarketRippleScoreData } from "@/app/companies/[symbol]/CompanyPageClient";

// Recharts split into its own lazy chunk (2026-08 performance audit) — see
// CompareLineChart.tsx's own header comment for why.
const CompareLineChart = dynamic(() => import("./CompareLineChart").then(m => m.CompareLineChart), { ssr: false });

// One-score migration sweep (2026-09-26, owner instruction): this page used
// to run its own client-side "AI Score" — a hardcoded formula (`s = 50 +
// f(roe, pe, debt_to_equity, gross_margins, dividend_yield)`, clamped
// 10-99) with no backend call at all, over a hand-maintained 30-company
// registry that never covered the real ~500+ company universe. Verified the
// underlying financial metrics themselves ARE real/sourced (yfinance/
// Finnhub via /api/stocks/{symbol}, confirmed live for both a bank and a
// non-bank symbol) — the fabrication was specifically the scoring formula
// and the "AI winner" declarations built on top of it, not the inputs.
// Replaced with the same real, approved MarketRipple Score projection the
// Company page itself reads (GET /api/companies/{symbol}/marketripple-
// score) — shown honestly per company (real score, partial coverage, or
// unavailable), never a declared "winner." The hardcoded company registry
// is gone too — the "Add Company" search now calls the real backend
// directory (GET /api/companies/search, the same metadata-only search
// AllCompaniesTab.tsx already uses) instead of filtering a static list
// that had already drifted from the real ~500+ company universe once
// before in this app's history.

const PALETTE = ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7"];
const TABS = ["Overview","Financials","Valuation","Performance","Profitability","Cash Flow","Balance Sheet","Growth","Dividends","Peers","Events","AI Analysis"];
const PERIODS = ["1D","1M","3M","6M","1Y","3Y","5Y","Max"];

// ── Types ─────────────────────────────────────────────────────────────────────

interface StockData {
  symbol: string; name: string; price: string; pct_change: number;
  change_abs: string; market_cap: string; sector: string; industry: string;
  week52_high: string; week52_low: string; open: string; day_high: string; day_low: string;
  pe: string; pb: string; forward_pe: string; eps: string;
  roe: string; roa: string; roce: string; beta: string;
  dividend_yield: string; dividend_rate: string;
  gross_margins: string; operating_margins: string; net_margins: string;
  debt_to_equity: string; current_ratio: string; free_cashflow: string;
  revenue: string; profit: string; revenue_fy: string; enterprise_value: string;
  recommendation: string; target_mean: string; target_high: string; target_low: string;
  analyst_count: number; buy_count: number; hold_count: number; sell_count: number;
  held_institutions: string; held_insiders: string;
  quarterly_revenue: { label: string; value: number }[];
  quarterly_net_income: { label: string; value: number }[];
  annual_financials: { year: string; revenue: number; net_income: number }[];
  events: { title: string; date: string }[];
  peers: string[];
  loading?: boolean;
}

// ── Pure helpers ──────────────────────────────────────────────────────────────

function parseN(s: string | number | undefined): number {
  if (s === undefined || s === null) return 0;
  const str = String(s);
  if (!str || str === "—") return 0;
  const clean = str.replace(/[₹,%×x\s,]/g, "");
  const m = clean.match(/^-?([\d.]+)([BMKTbmkt]?)$/);
  if (!m) return parseFloat(clean) || 0;
  const n = parseFloat(m[1]) * (str.startsWith("-") ? -1 : 1);
  const sfx = m[2]?.toUpperCase();
  if (sfx === "T") return n * 1000;
  if (sfx === "B") return n;
  if (sfx === "M") return n / 1000;
  if (sfx === "K") return n / 1_000_000;
  return n;
}

function color(i: number) { return PALETTE[i % PALETTE.length]; }

function highlight(values: number[], lowerBetter = false): string[] {
  const valid = values.filter(v => v > 0);
  if (valid.length < 2) return values.map(() => "text-text-primary");
  const best = lowerBetter ? Math.min(...valid) : Math.max(...valid);
  const worst = lowerBetter ? Math.max(...valid) : Math.min(...valid);
  return values.map(v =>
    v <= 0 ? "text-text-muted" :
    v === best  ? "text-emerald-400 font-bold" :
    v === worst ? "text-rose-400" : "text-text-primary"
  );
}

// ── Micro-components ──────────────────────────────────────────────────────────

function Spinner() {
  return <div className="h-4 w-4 animate-spin rounded-full border-2 border-surface-border/20 border-t-sky-400" />;
}

function Avatar({ sym, idx, size = 40 }: { sym: string; idx: number; size?: number }) {
  return (
    <div className="flex shrink-0 items-center justify-center rounded-xl text-xs font-bold text-text-primary"
      style={{ width: size, height: size, background: `${color(idx)}28`, border: `1px solid ${color(idx)}44` }}>
      {sym.slice(0, 2)}
    </div>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-surface-border/8 bg-text-primary/[0.025] p-5 backdrop-blur-sm ${className}`}>
      {children}
    </div>
  );
}

function CardTitle({ children, sub }: { children: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <span className="text-sm font-semibold text-text-primary">{children}</span>
      {sub && <span className="text-[11px] text-text-muted">{sub}</span>}
    </div>
  );
}

function KVRow({ label, value, cls = "text-text-primary" }: { label: string; value: string; cls?: string }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-surface-border/4 py-1.5 last:border-0">
      <span className="text-[11px] text-text-muted shrink-0">{label}</span>
      <span className={`text-[12px] font-semibold text-right ${cls}`}>{value || "—"}</span>
    </div>
  );
}

// Period-label honesty note (2026-09-26, owner instruction: "labels ...
// need verified definitions"). Verified against the source contract
// (market_data.py::get_stock_detail): roe/roa/roce/gross_margins/
// operating_margins/net_margins are raw pass-throughs of yfinance's own
// `.info` fields (returnOnEquity, grossMargins, etc.) with no repo-side
// period recomputation — "TTM" reflects the data provider's own
// documented convention for those fields, not something this app
// independently verifies or recalculates.
function TtmNote() {
  return (
    <p className="mt-3 text-[9.5px] leading-4 text-text-muted">
      TTM figures are the data provider's own trailing-twelve-month calculation, not independently recomputed by this app.
    </p>
  );
}

function MiniBar({ pct, col }: { pct: number; col: string }) {
  return (
    <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-text-primary/[0.05]">
      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.min(100, Math.max(0, pct))}%`, background: col }} />
    </div>
  );
}

// ── Custom tooltip for performance chart ─────────────────────────────────────

// ── Comparison table row ──────────────────────────────────────────────────────

function CmpRow({ label, values, fmt, lowerBetter = false }: {
  label: string; values: (string | number)[]; fmt?: (v: string | number) => string; lowerBetter?: boolean;
}) {
  const nums = values.map(v => parseN(String(v)));
  const cls = highlight(nums, lowerBetter);
  const display = fmt ? values.map(fmt) : values.map(v => String(v));
  return (
    <tr className="border-b border-surface-border/4 last:border-0">
      <td className="py-2 pr-4 text-[11px] text-text-muted whitespace-nowrap">{label}</td>
      {display.map((d, i) => (
        <td key={i} className={`py-2 text-right text-[12px] font-medium ${cls[i]}`}>{d || "—"}</td>
      ))}
    </tr>
  );
}

// ── Score ring ────────────────────────────────────────────────────────────────

function ScoreRing({ score, label, col }: { score: number; label: string; col: string }) {
  const r = 30, circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="76" height="76" viewBox="0 0 76 76">
        <circle cx="38" cy="38" r={r} fill="none" stroke="rgb(var(--text-primary) / 0.06)" strokeWidth="6" />
        <circle cx="38" cy="38" r={r} fill="none" stroke={col} strokeWidth="6"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" transform="rotate(-90 38 38)"
          style={{ transition: "stroke-dasharray 1s ease" }} />
        <text x="38" y="42" textAnchor="middle" fill="rgb(var(--text-primary))" fontSize="14" fontWeight="700" fontFamily="sans-serif">{score}</text>
      </svg>
      <span className="text-[10px] text-text-secondary text-center leading-tight">{label}</span>
    </div>
  );
}

// ── MarketRipple Score tile (real, one canonical score — 2026-09-26) ───────────
// Replaces the old client-side "AI Score" ScoreRing: reads the exact same
// projection the Company page's own MarketRippleScoreCard reads, so a
// company's score here always matches its score everywhere else on the
// site. Shows the honest partial/unavailable state per company rather than
// hiding it or substituting a fabricated number — and deliberately never
// highlights or ranks the compared tiles against each other (no declared
// winner), even when every company shown is fully eligible.
function MrScoreTile({ data, label, col }: {
  data: MarketRippleScoreData | null | undefined; label: string; col: string;
}) {
  if (data === undefined) {
    return (
      <div className="flex flex-col items-center gap-1">
        <div className="flex h-[76px] w-[76px] items-center justify-center text-[13px] text-text-muted">···</div>
        <span className="text-[10px] text-text-secondary text-center leading-tight">{label}</span>
      </div>
    );
  }
  if (data?.eligible === true && data.score == null && data.pillar_coverage_status === "partial") {
    return (
      <div className="flex flex-col items-center gap-1">
        <div className="flex h-[76px] w-[76px] flex-col items-center justify-center text-center">
          <span className="text-[12px] font-bold text-text-primary">Partial</span>
          <span className="text-[9px] text-text-muted">coverage</span>
        </div>
        <span className="text-[10px] text-text-secondary text-center leading-tight">{label}</span>
      </div>
    );
  }
  const eligible = !!data?.resolved && !!data?.snapshot && data?.eligible === true && data.score != null;
  if (!eligible) {
    return (
      <div className="flex flex-col items-center gap-1">
        <div className="flex h-[76px] w-[76px] items-center justify-center text-center">
          <span className="text-[12px] font-bold text-text-muted">Unavailable</span>
        </div>
        <span className="text-[10px] text-text-secondary text-center leading-tight">{label}</span>
      </div>
    );
  }
  return <ScoreRing score={Math.round(data.score!)} label={label} col={col} />;
}

// ── Page ──────────────────────────────────────────────────────────────────────

function ComparePageInner({ headingLevel = "h1" }: { headingLevel?: "h1" | "h2" }) {
  const Heading = headingLevel;
  const searchParams = useSearchParams();
  const initSelected = (() => {
    const a = searchParams.get("a")?.toUpperCase();
    const b = searchParams.get("b")?.toUpperCase();
    if (a && b) return [a, b];
    if (a) return [a, "NTPC"];
    return ["TATAPOWER", "NTPC", "ADANIPOWER"];
  })();
  const [selected, setSelected]     = useState<string[]>(initSelected);
  const [stocks,   setStocks]       = useState<Record<string, StockData>>({});
  const [chartMap, setChartMap]     = useState<Record<string, { label: string; value: number }[]>>({});
  const [period,   setPeriod]       = useState("1Y");
  const [activeTab,setActiveTab]    = useState("Overview");
  const [search,   setSearch]       = useState("");
  const [showSearch,setShowSearch]  = useState(false);
  const [loadingChart,setLoadingChart] = useState(false);
  // Real company-directory metadata, populated as search results and stock
  // fetches resolve (2026-09-26 — replaces the hardcoded 30-company
  // COMPANY_LIST; the eventual real /api/stocks/{symbol} fetch already
  // overwrites these the moment it resolves, this is just what a chip
  // shows in the instant before that).
  const [directory, setDirectory]   = useState<Record<string, { name: string; sector: string }>>({});
  const [searchResults, setSearchResults] = useState<{ symbol: string; name: string; sector: string }[]>([]);
  const [searching, setSearching]   = useState(false);
  // Real MarketRipple Score projections — the same one canonical endpoint
  // the Company page itself reads (GET /api/companies/{symbol}/
  // marketripple-score). undefined = loading, null = fetch failed.
  const [mrScores, setMrScores]     = useState<Record<string, MarketRippleScoreData | null | undefined>>({});
  const searchRef = useRef<HTMLDivElement>(null);

  function meta(sym: string) {
    return directory[sym] ?? { symbol: sym, name: sym, sector: "General" };
  }

  // Close search on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setShowSearch(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  // Real company-directory search (2026-09-26) — the same metadata-only
  // GET /api/companies/search AllCompaniesTab.tsx already uses for the
  // /companies directory, replacing the old client-side filter over a
  // hardcoded 30-company list that could never find the other ~470+ real
  // companies this app actually covers.
  useEffect(() => {
    if (!search.trim()) { setSearchResults([]); setSearching(false); return; }
    setSearching(true);
    const t = setTimeout(() => {
      fetch(`${API}/api/companies/search?${new URLSearchParams({ q: search, limit: "8" })}`)
        .then(r => r.ok ? r.json() : null)
        .then(d => setSearchResults((d?.companies ?? []).filter((c: any) => !selected.includes(c.symbol))))
        .catch(() => setSearchResults([]))
        .finally(() => setSearching(false));
    }, 300);
    return () => clearTimeout(t);
  }, [search, selected]);

  // Real MarketRipple Score projections, one fetch per selected symbol —
  // mirrors the Company page's own useMarketRippleScore hook exactly so
  // the same symbol always shows the same score here as everywhere else.
  useEffect(() => {
    selected.forEach(sym => {
      if (sym in mrScores) return;
      setMrScores(prev => ({ ...prev, [sym]: undefined }));
      fetch(`${API}/api/companies/${sym}/marketripple-score`)
        .then(r => r.ok ? r.json() : null)
        .then(d => setMrScores(prev => ({ ...prev, [sym]: d })))
        .catch(() => setMrScores(prev => ({ ...prev, [sym]: null })));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  // Fetch stock info
  useEffect(() => {
    selected.forEach(sym => {
      if (stocks[sym] && !stocks[sym].loading) return;
      setStocks(prev => ({ ...prev, [sym]: { ...fallback(sym), loading: true } }));
      fetch(`${API}/api/stocks/${sym}`)
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (!d) { setStocks(prev => ({ ...prev, [sym]: { ...fallback(sym), loading: false } })); return; }
          // /api/stocks/{symbol} has never actually returned top-level
          // `revenue`/`profit` fields (confirmed live for both a bank and
          // a non-bank symbol, 2026-09-26) — this component was reading
          // fields that don't exist, so "Revenue"/"Net Profit" rows always
          // rendered "—" for every company. The real figures ARE present,
          // just nested in `annual_financials` (which this file already
          // fetches and displays elsewhere) — use the latest fiscal year
          // from there instead of the dead top-level fields.
          //
          // Verified against the source contract (2026-09-26, owner
          // instruction): `annual_financials[].year` is a naive
          // `col.strftime("FY%y")` of yfinance's own statement-column
          // date (market_data.py::get_stock_detail) — it is NOT
          // normalized across companies, so two compared companies can
          // genuinely have different real latest fiscal years (one FY25,
          // another already FY26) depending on when each filed. A
          // generic "Latest FY" label would falsely imply they're the
          // same period — show the real per-company year instead.
          //
          // Also verified: that same backend function unconditionally
          // divides by 1e7 assuming INR, with no `financialCurrency`
          // check — the exact currency-mislabeling bug already found and
          // fixed for the sibling /financials endpoint (INFY reports USD,
          // commit c844920) but NOT fixed here. Flagged as a separate,
          // real, NOT-yet-fixed backend bug in the release package
          // (outside this migration's boundary) rather than silently
          // worked around client-side, since there's no reliable way to
          // detect a company's real reporting currency from this
          // endpoint's response today.
          const latestAnnual = (d.annual_financials || []).slice(-1)[0];
          setStocks(prev => ({
            ...prev,
            [sym]: {
              symbol: sym,
              name:              d.name          || meta(sym).name,
              price:             d.price         || "—",
              pct_change:        d.pct_change    || 0,
              change_abs:        d.change_abs    || "0",
              market_cap:        d.market_cap    || "—",
              sector:            d.sector        || meta(sym).sector,
              industry:          d.industry      || meta(sym).sector,
              week52_high:       d.week52_high   || "—",
              week52_low:        d.week52_low    || "—",
              open:              d.open          || "—",
              day_high:          d.day_high      || "—",
              day_low:           d.day_low       || "—",
              pe:                d.pe_ratio || d.pe || "—",
              pb:                d.pb_ratio || d.pb || "—",
              forward_pe:        d.forward_pe    || "—",
              eps:               d.eps           || "—",
              roe:               d.roe           || "—",
              roa:               d.roa           || "—",
              roce:              d.roce          || "—",
              beta:              d.beta          || "—",
              dividend_yield:    d.dividend_yield|| "—",
              dividend_rate:     d.dividend_rate || "—",
              gross_margins:     d.gross_margins || "—",
              operating_margins: d.operating_margins || "—",
              net_margins:       d.net_margins   || "—",
              debt_to_equity:    d.debt_to_equity|| "—",
              current_ratio:     d.current_ratio || "—",
              free_cashflow:     d.free_cashflow || "—",
              revenue:           latestAnnual ? latestAnnual.revenue.toLocaleString("en-IN") : "—",
              profit:            latestAnnual ? latestAnnual.net_income.toLocaleString("en-IN") : "—",
              revenue_fy:        latestAnnual ? latestAnnual.year : "—",
              enterprise_value:  d.enterprise_value || "—",
              recommendation:    d.recommendation || "hold",
              target_mean:       d.target_mean   || "—",
              target_high:       d.target_high   || "—",
              target_low:        d.target_low    || "—",
              analyst_count:     d.analyst_count || 0,
              buy_count:         d.buy_count     || 0,
              hold_count:        d.hold_count    || 0,
              sell_count:        d.sell_count    || 0,
              held_institutions: d.held_institutions || "—",
              held_insiders:     d.held_insiders || "—",
              quarterly_revenue: d.quarterly_revenue || [],
              quarterly_net_income: d.quarterly_net_income || [],
              annual_financials: d.annual_financials || [],
              events:            d.events  || [],
              peers:             d.peers   || [],
              loading: false,
            },
          }));
        })
        .catch(() => setStocks(prev => ({ ...prev, [sym]: { ...fallback(sym), loading: false } })));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  // Fetch chart data
  useEffect(() => {
    if (!selected.length) return;
    setLoadingChart(true);
    Promise.all(
      selected.map(sym =>
        fetch(`${API}/api/stocks/${sym}/chart?period=${period}`)
          .then(r => r.ok ? r.json() : [])
          .then(d => ({ sym, data: Array.isArray(d) ? d : [] }))
          .catch(() => ({ sym, data: [] }))
      )
    ).then(results => {
      const map: Record<string, { label: string; value: number }[]> = {};
      results.forEach(({ sym, data }) => { map[sym] = data; });
      setChartMap(map);
      setLoadingChart(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, period]);

  function fallback(sym: string): StockData {
    const m = meta(sym);
    return {
      symbol: sym, name: m.name, price: "—", pct_change: 0, change_abs: "0",
      market_cap: "—", sector: m.sector, industry: m.sector,
      week52_high: "—", week52_low: "—", open: "—", day_high: "—", day_low: "—",
      pe: "—", pb: "—", forward_pe: "—", eps: "—",
      roe: "—", roa: "—", roce: "—", beta: "—",
      dividend_yield: "—", dividend_rate: "—",
      gross_margins: "—", operating_margins: "—", net_margins: "—",
      debt_to_equity: "—", current_ratio: "—", free_cashflow: "—",
      revenue: "—", profit: "—", revenue_fy: "—", enterprise_value: "—",
      recommendation: "hold", target_mean: "—", target_high: "—", target_low: "—",
      analyst_count: 0, buy_count: 0, hold_count: 0, sell_count: 0,
      held_institutions: "—", held_insiders: "—",
      quarterly_revenue: [], quarterly_net_income: [], annual_financials: [],
      events: [], peers: [], loading: false,
    };
  }

  function addCompany(c: { symbol: string; name: string; sector: string }) {
    if (selected.includes(c.symbol) || selected.length >= 4) return;
    setDirectory(prev => ({ ...prev, [c.symbol]: { name: c.name, sector: c.sector } }));
    setSelected(prev => [...prev, c.symbol]);
    setSearch(""); setShowSearch(false); setSearchResults([]);
  }
  function removeCompany(sym: string) {
    setSelected(prev => prev.filter(s => s !== sym));
    setStocks(prev => { const n = { ...prev }; delete n[sym]; return n; });
    setMrScores(prev => { const n = { ...prev }; delete n[sym]; return n; });
  }

  const companies = selected.map(sym => stocks[sym] ?? fallback(sym));

  // Merge chart data → % change from first point
  const mergedChart = useMemo(() => {
    const allLabels = new Set<string>();
    selected.forEach(sym => (chartMap[sym] || []).forEach(d => allLabels.add(d.label)));
    const labels = [...allLabels].sort();
    const bases: Record<string, number> = {};
    selected.forEach(sym => { const arr = chartMap[sym] || []; if (arr.length) bases[sym] = arr[0].value || 1; });
    return labels.map(label => {
      const pt: Record<string, any> = { label };
      selected.forEach(sym => {
        const d = (chartMap[sym] || []).find(x => x.label === label);
        if (d && bases[sym]) pt[sym] = parseFloat(((d.value - bases[sym]) / bases[sym] * 100).toFixed(2));
      });
      return pt;
    });
  }, [selected, chartMap]);

  const recBadge = (r: string) => {
    const map: Record<string, string> = {
      "strong buy": "border-emerald-500/40 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
      "buy":        "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
      "hold":       "border-amber-500/30  bg-amber-500/10  text-amber-600 dark:text-amber-300",
      "sell":       "border-rose-500/30   bg-rose-500/10   text-rose-600 dark:text-rose-300",
      "strong sell":"border-rose-500/40   bg-rose-500/15   text-rose-600 dark:text-rose-300",
    };
    return map[r] ?? map["hold"];
  };

  const gridCols = companies.length === 1 ? "grid-cols-1" :
    companies.length === 2 ? "grid-cols-2" :
    companies.length === 3 ? "grid-cols-3" : "grid-cols-4";

  // ── Tab content helpers ────────────────────────────────────────────────────

  function OverviewTab() {
    return (
      <div className="space-y-5">
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_300px] gap-5 items-start">
          {/* LEFT */}
          <div className="space-y-5">
            {/* Performance Chart */}
            <Card>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-text-primary">Performance Chart</h3>
                <div className="flex gap-0.5">
                  {PERIODS.map(p => (
                    <button key={p} onClick={() => setPeriod(p)}
                      className={`rounded-md px-2 py-1 text-[10px] font-medium transition ${period === p ? "bg-sky-500/20 text-sky-600 dark:text-sky-300" : "text-text-muted hover:text-text-secondary"}`}>
                      {p}
                    </button>
                  ))}
                </div>
              </div>
              {loadingChart ? (
                <div className="flex h-64 items-center justify-center"><Spinner /></div>
              ) : mergedChart.length > 0 ? (
                <div className="h-64">
                  <CompareLineChart mergedChart={mergedChart} selected={selected} color={color} />
                </div>
              ) : (
                <div className="flex h-64 items-center justify-center rounded-xl border border-surface-border/5 bg-text-primary/[0.02]">
                  <p className="text-sm text-text-muted">No chart data available</p>
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-4 border-t border-surface-border/5 pt-3">
                {selected.map((sym, i) => {
                  const pct = stocks[sym]?.pct_change || 0;
                  const isPos = pct >= 0;
                  return (
                    <div key={sym} className="flex items-center gap-2">
                      <div className="h-0.5 w-5 rounded-full" style={{ background: color(i) }} />
                      <span className="text-[11px] font-semibold text-text-secondary">{sym}</span>
                      <span className={`text-[11px] font-bold ${isPos ? "text-emerald-400" : "text-rose-400"}`}>
                        {isPos ? "+" : ""}{pct.toFixed(2)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Key Comparison Table */}
            <Card>
              <CardTitle>Key Comparison</CardTitle>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-surface-border/6">
                      <th className="pb-2 text-left text-[10px] font-medium text-text-muted w-36">Metric</th>
                      {companies.map((c, i) => (
                        <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <CmpRow label="Market Cap"       values={companies.map(c => c.market_cap)} />
                    <CmpRow label="P/E Ratio (TTM, x)" values={companies.map(c => c.pe)}           lowerBetter />
                    <CmpRow label="P/B Ratio (x)"    values={companies.map(c => c.pb)}           lowerBetter />
                    <CmpRow label="ROE (%, TTM)"      values={companies.map(c => c.roe)} />
                    <CmpRow label="ROCE (%, TTM)"     values={companies.map(c => c.roce)} />
                    <CmpRow label="Debt to Equity (x)" values={companies.map(c => c.debt_to_equity)} lowerBetter />
                    <CmpRow label="Dividend Yield (%)" values={companies.map(c => c.dividend_yield)} />
                    <CmpRow label="52W High (₹)"     values={companies.map(c => c.week52_high)}
                      fmt={v => v === "—" ? "—" : `₹${v}`} />
                    <CmpRow label="52W Low (₹)"      values={companies.map(c => c.week52_low)}
                      fmt={v => v === "—" ? "—" : `₹${v}`} lowerBetter />
                  </tbody>
                </table>
              </div>
              <TtmNote />
            </Card>
          </div>

          {/* RIGHT — sticky */}
          <div className="space-y-5 xl:sticky xl:top-[84px]">
            {/* Comparison Summary (renamed from "AI Comparison Summary",
                2026-09-26 one-score migration) — no longer declares an
                overall winner. Each item below is a transparent,
                single-real-metric superlative (highest ROE, lowest beta)
                with its own attribution, not a composite AI verdict.
                "Best Future Potential" (based on the removed fabricated
                score) is gone — there is no validated predictive metric
                to replace it with. */}
            <Card>
              <div className="mb-4 flex items-center gap-2">
                <BarChart2 className="h-3.5 w-3.5 shrink-0 text-sky-400" />
                <h3 className="text-sm font-semibold text-text-primary">Comparison Summary</h3>
              </div>
              <p className="mb-4 text-[12px] leading-5 text-text-secondary">
                Real, sourced metrics for the selected {companies.length === 1 ? "company" : "companies"} — the
                bolded value in each table below is the strongest among them for that metric.
              </p>
              <div className="space-y-2">
                {([
                  { icon: <Trophy className="h-4 w-4" />, label: "Highest ROE",  col: "text-amber-600 dark:text-amber-300", val: companies.reduce((b, c) => parseN(c.roe) > parseN(b.roe) ? c : b, companies[0])?.name || "—" },
                  { icon: <Shield className="h-4 w-4" />, label: "Lowest Beta",  col: "text-sky-600 dark:text-sky-300",     val: companies.reduce((b, c) => { const bn = parseN(b.beta); const cn = parseN(c.beta); return (cn > 0 && cn < bn) || bn <= 0 ? c : b; }, companies[0])?.name || "—" },
                ] as { icon: ReactNode; label: string; col: string; val: string }[]).map(item => (
                  <div key={item.label}
                    className="flex items-center justify-between rounded-xl border border-surface-border/5 bg-text-primary/[0.02] px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="text-text-secondary">{item.icon}</span>
                      <span className={`text-[11px] font-medium ${item.col}`}>{item.label}</span>
                    </div>
                    <span className="max-w-[110px] truncate text-right text-[11px] font-semibold text-text-primary">{item.val}</span>
                  </div>
                ))}
              </div>
              <button
                onClick={() => setActiveTab("AI Analysis")}
                className="mt-4 w-full rounded-xl border border-sky-500/20 bg-gradient-to-r from-sky-500/15 to-sky-500/10 py-2.5 text-[12px] font-medium text-sky-600 dark:text-sky-300 transition hover:from-sky-500/25 hover:to-sky-500/15">
                View Detailed Analysis →
              </button>
            </Card>

            {/* Valuation Metrics */}
            <Card>
              <CardTitle>Valuation Metrics</CardTitle>
              <table className="w-full">
                <thead>
                  <tr className="border-b border-surface-border/6">
                    <th className="pb-2 text-left text-[10px] font-medium text-text-muted">Metric</th>
                    {companies.map((c, i) => (
                      <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <CmpRow label="P/E Ratio (TTM, x)" values={companies.map(c => c.pe)}         lowerBetter />
                  <CmpRow label="P/B Ratio (x)"       values={companies.map(c => c.pb)}         lowerBetter />
                  <CmpRow label="Forward P/E (x)"     values={companies.map(c => c.forward_pe)} lowerBetter />
                  <CmpRow label="EPS (₹, TTM)"         values={companies.map(c => c.eps)} />
                  <CmpRow label="Beta"                values={companies.map(c => c.beta)}       lowerBetter />
                </tbody>
              </table>
              <TtmNote />
            </Card>

            {/* Recent Events */}
            <Card>
              <CardTitle>Recent Events</CardTitle>
              <div className="space-y-2">
                {companies.flatMap((c, i) =>
                  (c.events || []).slice(0, 2).map((e, j) => (
                    <div key={`${c.symbol}-${j}`}
                      className="flex items-start gap-2.5 rounded-xl border border-surface-border/5 bg-text-primary/[0.02] p-2.5">
                      <Avatar sym={c.symbol} idx={i} size={28} />
                      <div className="min-w-0 flex-1">
                        <p className="text-[11px] font-medium text-text-primary leading-snug line-clamp-2">{e.title}</p>
                        <div className="mt-1 flex items-center gap-2">
                          <span className="text-[9px] font-semibold" style={{ color: color(i) }}>{c.symbol}</span>
                          <span className="text-[9px] text-text-muted">{e.date}</span>
                        </div>
                      </div>
                    </div>
                  ))
                ).slice(0, 5)}
                {companies.every(c => !c.events?.length) && (
                  <p className="py-4 text-center text-[11px] text-text-muted">No events for selected companies</p>
                )}
              </div>
              <Link href="/events" className="mt-3 block text-center text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">
                View All Events →
              </Link>
            </Card>
          </div>
        </div>

        {/* Financial Highlights (full width below). Was labeled "(TTM)" for
            every row, but Revenue/Net Profit are real annual figures (the
            latest fiscal year in annual_financials — fixed 2026-09-26, see
            the revenue/profit mapping comment above; these were reading
            dead top-level API fields before) while EPS/margins genuinely
            are trailing figures — each row now states its own real
            period rather than one blanket, partly-inaccurate label. */}
        <Card>
          <CardTitle sub="Real, sourced figures — period shown per metric">Financial Highlights</CardTitle>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border/6">
                  <th className="pb-2 text-left text-[10px] font-medium text-text-muted w-40">Metric</th>
                  {companies.map((c, i) => (
                    <th key={c.symbol} className="pb-2">
                      <div className="flex items-center justify-end gap-1.5">
                        <div className="h-2 w-2 rounded-full" style={{ background: color(i) }} />
                        <span className="text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {([
                  // Real fiscal-year-end fix (2026-09-26, owner instruction):
                  // "Latest FY" was a generic placeholder — two compared
                  // companies can genuinely have different real latest
                  // fiscal years (verified against the source contract:
                  // market_data.py derives it per-symbol from yfinance's
                  // own statement columns, with no cross-company
                  // alignment). `fyKey` renders each company's own real
                  // year as a per-cell caption instead of a shared label.
                  { label: "Revenue (₹ Cr)",       key: "revenue",           fyKey: "revenue_fy" as const, lowerBetter: false },
                  { label: "Net Profit (₹ Cr)",    key: "profit",            fyKey: "revenue_fy" as const, lowerBetter: false },
                  { label: "EPS (₹, TTM)",                    key: "eps",               lowerBetter: false },
                  { label: "Operating Margin (%, TTM)",       key: "operating_margins", lowerBetter: false },
                  { label: "Net Margin (%, TTM)",             key: "net_margins",       lowerBetter: false },
                ] as { label: string; key: keyof StockData; fyKey?: keyof StockData; lowerBetter: boolean }[]).map(row => {
                  const vals = companies.map(c => parseN(String((c as any)[row.key])));
                  const max = Math.max(...vals.filter(v => v > 0), 1);
                  const cls = highlight(vals, row.lowerBetter);
                  return (
                    <tr key={row.label} className="border-b border-surface-border/4 last:border-0">
                      <td className="py-2.5 text-[11px] text-text-muted">{row.label}</td>
                      {companies.map((c, i) => {
                        const v = vals[i];
                        const w = max > 0 ? (v / max) * 100 : 0;
                        const display = String((c as any)[row.key]);
                        const fy = row.fyKey ? String((c as any)[row.fyKey]) : null;
                        return (
                          <td key={c.symbol} className="py-2.5 text-right">
                            {c.loading
                              ? <span className="text-[11px] text-text-muted">…</span>
                              : <div className="inline-flex flex-col items-end gap-1">
                                  <span className={`text-[12px] font-semibold ${cls[i]}`}>{display || "—"}</span>
                                  {fy && fy !== "—" && <span className="text-[9px] text-text-muted">{fy}</span>}
                                  {w > 0 && (
                                    <div className="h-1 w-16 overflow-hidden rounded-full bg-text-primary/[0.05]">
                                      <div className="h-full rounded-full" style={{ width: `${w}%`, background: color(i) }} />
                                    </div>
                                  )}
                                </div>
                            }
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <TtmNote />
        </Card>
      </div>
    );
  }

  function FinancialsTab() {
    return (
      <div className="space-y-5">
        <div className={`grid gap-5 ${gridCols}`}>
          {companies.map((c, i) => (
            <Card key={c.symbol}>
              <div className="mb-3 flex items-center gap-2">
                <Avatar sym={c.symbol} idx={i} size={32} />
                <div>
                  <p className="text-[13px] font-semibold text-text-primary">{c.symbol}</p>
                  <p className="text-[10px] text-text-muted">{c.sector}</p>
                </div>
              </div>
              {c.quarterly_revenue.length > 0 ? (
                <div className="h-28">
                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-secondary">Quarterly Revenue</p>
                  <div className="flex h-20 items-end gap-1">
                    {c.quarterly_revenue.map((d, j) => {
                      const maxV = Math.max(...c.quarterly_revenue.map(x => x.value), 1);
                      const pct = (d.value / maxV) * 100;
                      return (
                        <div key={j} className="group flex flex-1 flex-col items-center gap-0.5">
                          <span className="text-[8px] text-text-muted group-hover:text-text-secondary transition">
                            {d.value > 999 ? `${(d.value / 1000).toFixed(0)}K` : d.value}
                          </span>
                          <div className="flex w-full flex-1 items-end">
                            <div className="w-full rounded-t" style={{ height: `${Math.max(pct, 4)}%`, background: `${color(i)}99` }} />
                          </div>
                          <span className="text-[8px] text-text-muted">{d.label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="flex h-24 items-center justify-center text-[11px] text-text-muted">No data</div>
              )}
              <div className="mt-3 space-y-0 border-t border-surface-border/5 pt-3">
                <KVRow label={`Revenue (₹ Cr${c.revenue_fy !== "—" ? `, ${c.revenue_fy}` : ""})`}    value={c.revenue} />
                <KVRow label={`Net Profit (₹ Cr${c.revenue_fy !== "—" ? `, ${c.revenue_fy}` : ""})`} value={c.profit} />
                <KVRow label="Gross Margin (%, TTM)"        value={c.gross_margins} />
                <KVRow label="Op. Margin (%, TTM)"          value={c.operating_margins} />
                <KVRow label="Net Margin (%, TTM)"          value={c.net_margins} />
                <KVRow label="Free Cash Flow (TTM)"         value={c.free_cashflow} />
              </div>
            </Card>
          ))}
        </div>
        <TtmNote />
        {/* Annual table */}
        {companies.some(c => c.annual_financials?.length > 0) && (
          <Card>
            <CardTitle>Annual Financial Summary (₹ Cr)</CardTitle>
            <div className="overflow-x-auto">
              {companies.map((c, i) => c.annual_financials?.length > 0 && (
                <div key={c.symbol} className="mb-5 last:mb-0">
                  <div className="mb-2 flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full" style={{ background: color(i) }} />
                    <span className="text-[12px] font-semibold" style={{ color: color(i) }}>{c.name}</span>
                  </div>
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="border-b border-surface-border/6">
                        <th className="pb-2 text-left text-[10px] text-text-muted font-medium">₹ Cr</th>
                        {c.annual_financials.map(f => (
                          <th key={f.year} className="pb-2 text-right text-[10px] text-text-muted font-medium">{f.year}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-surface-border/4">
                        <td className="py-2 text-text-secondary">Revenue</td>
                        {c.annual_financials.map(f => (
                          <td key={f.year} className="py-2 text-right font-semibold text-text-primary">{f.revenue.toLocaleString()}</td>
                        ))}
                      </tr>
                      <tr>
                        <td className="py-2 text-text-secondary">Net Profit</td>
                        {c.annual_financials.map(f => (
                          <td key={f.year} className={`py-2 text-right font-semibold ${f.net_income >= 0 ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300"}`}>
                            {f.net_income.toLocaleString()}
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    );
  }

  function ValuationTab() {
    const rows = [
      { label: "P/E Ratio (TTM, x)", vals: companies.map(c => c.pe),          lowerBetter: true  },
      { label: "P/B Ratio (x)",      vals: companies.map(c => c.pb),          lowerBetter: true  },
      { label: "Forward P/E (x)",    vals: companies.map(c => c.forward_pe),  lowerBetter: true  },
      { label: "EPS (₹, TTM)",       vals: companies.map(c => c.eps),         lowerBetter: false },
      { label: "Beta",               vals: companies.map(c => c.beta),        lowerBetter: true  },
      { label: "Market Cap",         vals: companies.map(c => c.market_cap),  lowerBetter: false },
      { label: "Ent. Value",         vals: companies.map(c => c.enterprise_value), lowerBetter: false },
    ];
    return (
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
        <Card>
          <CardTitle>Valuation Multiples</CardTitle>
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border/6">
                <th className="pb-2 text-left text-[10px] font-medium text-text-muted w-36">Metric</th>
                {companies.map((c, i) => (
                  <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(r => <CmpRow key={r.label} label={r.label} values={r.vals} lowerBetter={r.lowerBetter} />)}
            </tbody>
          </table>
          <TtmNote />
        </Card>
        <Card>
          <CardTitle>MarketRipple Score</CardTitle>
          <div className="flex flex-wrap justify-around gap-4 pt-2">
            {companies.map((c, i) => (
              <MrScoreTile key={c.symbol} data={mrScores[c.symbol]} label={c.symbol} col={color(i)} />
            ))}
          </div>
          <p className="mt-4 text-[10px] text-text-muted text-center">
            The real, approved four-pillar methodology (Financial Strength, Valuation, Market Behaviour,
            Current Intelligence) — shown only where a company's sector has a published methodology and
            full evidence coverage. Not a prediction or a declared winner.
          </p>
        </Card>
      </div>
    );
  }

  function ProfitabilityTab() {
    const rows = [
      { label: "Gross Margin (%, TTM)",     key: "gross_margins"     as keyof StockData },
      { label: "Operating Margin (%, TTM)", key: "operating_margins" as keyof StockData },
      { label: "Net Margin (%, TTM)",       key: "net_margins"       as keyof StockData },
      { label: "ROE (%, TTM)",              key: "roe"               as keyof StockData },
      { label: "ROA (%, TTM)",              key: "roa"               as keyof StockData },
      { label: "ROCE (%, TTM)",             key: "roce"              as keyof StockData },
    ];
    return (
      <div className="space-y-5">
        <div className={`grid gap-5 ${gridCols}`}>
          {companies.map((c, i) => (
            <Card key={c.symbol}>
              <div className="mb-3 flex items-center gap-2">
                <Avatar sym={c.symbol} idx={i} size={32} />
                <span className="text-[13px] font-semibold text-text-primary">{c.symbol}</span>
              </div>
              <div className="space-y-3">
                {rows.map(r => {
                  const val = String((c as any)[r.key]);
                  const pct = parseN(val);
                  return (
                    <div key={r.key}>
                      <div className="mb-1 flex justify-between text-[11px]">
                        <span className="text-text-secondary">{r.label}</span>
                        <span className="font-semibold text-text-primary">{val || "—"}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-text-primary/[0.05]">
                        <div className="h-full rounded-full transition-all duration-700"
                          style={{ width: `${Math.min(100, Math.max(0, pct))}%`, background: color(i) }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          ))}
        </div>
        <Card>
          <CardTitle>Margin Comparison</CardTitle>
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border/6">
                <th className="pb-2 text-left text-[10px] font-medium text-text-muted w-36">Margin</th>
                {companies.map((c, i) => (
                  <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(r => <CmpRow key={r.key} label={r.label} values={companies.map(c => String((c as any)[r.key]))} />)}
            </tbody>
          </table>
          <TtmNote />
        </Card>
      </div>
    );
  }

  function BalanceSheetTab() {
    return (
      <Card>
        <CardTitle>Balance Sheet Ratios</CardTitle>
        <table className="w-full">
          <thead>
            <tr className="border-b border-surface-border/6">
              <th className="pb-2 text-left text-[10px] font-medium text-text-muted w-40">Metric</th>
              {companies.map((c, i) => (
                <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <CmpRow label="Debt to Equity (x)"   values={companies.map(c => c.debt_to_equity)} lowerBetter />
            <CmpRow label="Current Ratio (x)"    values={companies.map(c => c.current_ratio)} />
            <CmpRow label="Free Cash Flow (TTM)" values={companies.map(c => c.free_cashflow)} />
            <CmpRow label="Enterprise Value"     values={companies.map(c => c.enterprise_value)} />
            <CmpRow label="Market Cap"           values={companies.map(c => c.market_cap)} />
          </tbody>
        </table>
        <TtmNote />
      </Card>
    );
  }

  function DividendsTab() {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <Card>
          <CardTitle>Dividend Summary</CardTitle>
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border/6">
                <th className="pb-2 text-left text-[10px] font-medium text-text-muted w-36">Metric</th>
                {companies.map((c, i) => (
                  <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <CmpRow label="Dividend Yield (%)" values={companies.map(c => c.dividend_yield)} />
              <CmpRow label="Dividend Rate (₹)"  values={companies.map(c => c.dividend_rate)} />
              <CmpRow label="Payout Ratio"       values={companies.map(() => "—")} />
            </tbody>
          </table>
        </Card>
        <Card>
          <CardTitle>Yield Comparison</CardTitle>
          <div className="space-y-4 pt-2">
            {companies.map((c, i) => {
              const yld = parseN(c.dividend_yield);
              const maxYld = Math.max(...companies.map(x => parseN(x.dividend_yield)), 1);
              return (
                <div key={c.symbol}>
                  <div className="mb-1.5 flex items-center justify-between text-[12px]">
                    <div className="flex items-center gap-2">
                      <Avatar sym={c.symbol} idx={i} size={24} />
                      <span className="font-semibold text-text-primary">{c.symbol}</span>
                    </div>
                    <span className="font-bold text-emerald-400">{c.dividend_yield}</span>
                  </div>
                  <MiniBar pct={(yld / maxYld) * 100} col={color(i)} />
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    );
  }

  function PeersTab() {
    return (
      <div className={`grid gap-5 ${gridCols}`}>
        {companies.map((c, i) => (
          <Card key={c.symbol}>
            <div className="mb-3 flex items-center gap-2">
              <Avatar sym={c.symbol} idx={i} size={32} />
              <div>
                <p className="text-[13px] font-semibold text-text-primary">{c.symbol}</p>
                <p className="text-[10px] text-text-muted">{c.sector}</p>
              </div>
            </div>
            {c.peers.length > 0 ? (
              <div className="space-y-1.5">
                {c.peers.map(p => (
                  <Link key={p} href={`/companies/${p}`}
                    className="flex items-center gap-2.5 rounded-xl border border-surface-border/5 bg-text-primary/[0.02] px-3 py-2 hover:border-surface-border/10 hover:bg-text-primary/[0.04] transition">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-text-primary/[0.06] text-[9px] font-bold text-text-secondary">
                      {p.slice(0, 2)}
                    </div>
                    <span className="text-[12px] font-medium text-text-primary">{p}</span>
                    <span className="ml-auto text-[10px] text-sky-400">→</span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="py-6 text-center text-[11px] text-text-muted">No peer data</p>
            )}
          </Card>
        ))}
      </div>
    );
  }

  function EventsTab() {
    const allEvents = companies.flatMap((c, i) =>
      (c.events || []).map(e => ({ ...e, sym: c.symbol, idx: i }))
    );
    return (
      <Card>
        <CardTitle>All Events for Selected Companies</CardTitle>
        {allEvents.length > 0 ? (
          <div className="space-y-2">
            {allEvents.map((e, j) => (
              <div key={j} className="flex items-start gap-3 rounded-xl border border-surface-border/5 bg-text-primary/[0.02] p-3.5">
                <Avatar sym={e.sym} idx={e.idx} size={32} />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-text-primary leading-snug">{e.title}</p>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-[10px] font-semibold" style={{ color: color(e.idx) }}>{e.sym}</span>
                    <span className="text-[10px] text-text-muted">{e.date}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <ClipboardList className="h-8 w-8 text-text-muted" />
            <p className="text-sm text-text-secondary">No events found for the selected companies.</p>
            <Link href="/events" className="text-sm text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">Browse all events →</Link>
          </div>
        )}
      </Card>
    );
  }

  function AIAnalysisTab() {
    return (
      <div className="space-y-5">
        <div className={`grid gap-5 ${gridCols}`}>
          {companies.map((c, i) => {
            const strengths = [
              parseN(c.roe) > 15 && `Strong ROE of ${c.roe}`,
              parseN(c.dividend_yield) > 1 && `Dividend yield ${c.dividend_yield}`,
              parseN(c.gross_margins) > 20 && `Gross margins ${c.gross_margins}`,
              parseN(c.current_ratio) > 1.5 && "Healthy current ratio",
              parseN(c.free_cashflow) > 0 && "Positive free cash flow",
            ].filter(Boolean).slice(0, 4) as string[];
            const risks = [
              parseN(c.debt_to_equity) > 1.5 && `High D/E of ${c.debt_to_equity}`,
              parseN(c.pe) > 40 && `Premium valuation PE ${c.pe}`,
              parseN(c.beta) > 1.5 && `High volatility beta ${c.beta}`,
              parseN(c.net_margins) > 0 && parseN(c.net_margins) < 5 && `Thin net margins ${c.net_margins}`,
            ].filter(Boolean).slice(0, 4) as string[];
            return (
              <Card key={c.symbol}>
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <Avatar sym={c.symbol} idx={i} size={36} />
                    <div>
                      <p className="text-[13px] font-semibold text-text-primary">{c.name}</p>
                      <p className="text-[10px] text-text-muted">{c.symbol} · {c.sector}</p>
                    </div>
                  </div>
                  <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${recBadge(c.recommendation)}`}>
                    {(c.recommendation || "hold").replace(/_/g, " ").toUpperCase()}
                  </span>
                </div>
                <MrScoreTile data={mrScores[c.symbol]} label="MarketRipple Score" col={color(i)} />
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div>
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">Strengths</p>
                    {strengths.length > 0 ? (
                      <ul className="space-y-1">
                        {strengths.map((s, j) => (
                          <li key={j} className="flex items-start gap-1 text-[11px] text-text-secondary">
                            <span className="mt-0.5 text-emerald-400 shrink-0">•</span>{s}
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-[11px] text-text-muted">Loading…</p>}
                  </div>
                  <div>
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-rose-400">Risks</p>
                    {risks.length > 0 ? (
                      <ul className="space-y-1">
                        {risks.map((r, j) => (
                          <li key={j} className="flex items-start gap-1 text-[11px] text-text-secondary">
                            <span className="mt-0.5 text-rose-400 shrink-0">•</span>{r}
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-[11px] text-text-muted">No major risks identified</p>}
                  </div>
                </div>
                <div className="mt-3 space-y-0 border-t border-surface-border/5 pt-3">
                  <KVRow label="Target Mean (₹)" value={c.target_mean} />
                  <KVRow label="Target High (₹)" value={c.target_high} />
                  <KVRow label="Target Low (₹)"  value={c.target_low} />
                  <KVRow label="Analysts"        value={String(c.analyst_count || "—")} />
                  <KVRow label="Inst. Holding (%)" value={c.held_institutions} />
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    );
  }

  function GenericTab({ tab }: { tab: string }) {
    return (
      <Card>
        <div className="flex flex-col items-center gap-3 py-20 text-center">
          <BarChart2 className="h-8 w-8 text-text-muted" />
          <p className="text-sm font-semibold text-text-primary">{tab}</p>
          <p className="text-sm text-text-muted">Detailed {tab.toLowerCase()} data coming soon.</p>
        </div>
      </Card>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <main className="min-w-0 space-y-6 pb-10">

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-sky-600 dark:text-sky-300">Research</p>
          <Heading className="mt-2 text-4xl font-semibold tracking-tight text-text-primary">Compare Companies</Heading>
          <p className="mt-1 text-sm text-text-secondary">
            Compare financials, valuation, market performance, events and AI insights side by side.
          </p>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <button className="flex items-center gap-2 rounded-xl border border-surface-border/10 bg-text-primary/[0.03] px-4 py-2 text-xs font-medium text-text-secondary transition hover:border-surface-border/20 hover:text-text-primary">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Export PDF
          </button>
          <button className="flex items-center gap-2 rounded-xl border border-surface-border/10 bg-text-primary/[0.03] px-4 py-2 text-xs font-medium text-text-secondary transition hover:border-surface-border/20 hover:text-text-primary">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
            </svg>
            Share
          </button>
        </div>
      </div>

      {/* Company selector chips */}
      {/* relative + z-20: the Add Company dropdown inside (z-50) only wins
          its OWN local stacking context — without this, the sibling
          "Company summary cards" grid below (later in DOM order, its own
          z-index:auto) painted over it regardless, since z-50 doesn't
          escape to compete against elements outside this subtree. */}
      <div className="relative z-20 rounded-2xl border border-surface-border/8 bg-text-primary/[0.025] p-4 backdrop-blur-sm">
        <div className="flex flex-wrap items-center gap-3">
          {selected.map((sym, i) => {
            const m = meta(sym);
            return (
              <div key={sym} className="flex items-center gap-2">
                {i > 0 && <span className="text-xs font-bold text-text-muted">VS</span>}
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-2 rounded-xl border bg-text-primary/[0.04] px-3 py-2 transition"
                  style={{ borderColor: `${color(i)}33` }}>
                  <Avatar sym={sym} idx={i} size={28} />
                  <div>
                    <p className="max-w-[120px] truncate text-[11px] font-semibold text-text-primary leading-tight">{m.name}</p>
                    <p className="text-[9px] text-text-muted">{sym}</p>
                  </div>
                  <button
                    onClick={() => removeCompany(sym)}
                    className="ml-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-text-muted transition hover:bg-text-primary/10 hover:text-text-primary">
                    <X className="h-3 w-3" />
                  </button>
                </motion.div>
              </div>
            );
          })}

          {selected.length < 4 && (
            <div ref={searchRef} className="relative">
              <button
                onClick={() => setShowSearch(v => !v)}
                className="flex items-center gap-1.5 rounded-xl border border-dashed border-surface-border/20 px-3 py-2 text-xs text-text-secondary transition hover:border-surface-border/40 hover:text-text-primary">
                <span className="text-base leading-none font-light">+</span> Add Company
              </button>
              <AnimatePresence>
                {showSearch && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 4 }}
                    className="absolute left-0 top-full z-50 mt-2 w-72 rounded-xl border border-surface-border/10 bg-surface-card p-2 shadow-2xl">
                    <input
                      autoFocus
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      placeholder="Search company or symbol…"
                      className="w-full rounded-lg border border-surface-border/5 bg-text-primary/[0.04] px-3 py-2 text-xs text-text-primary outline-none placeholder:text-text-muted focus:border-sky-500/30"
                    />
                    <div className="mt-2 max-h-48 overflow-y-auto space-y-0.5">
                      {searchResults.map(c => (
                        <button key={c.symbol} onClick={() => addCompany(c)}
                          className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition hover:bg-text-primary/[0.04]">
                          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-text-primary/[0.06] text-[9px] font-bold text-text-secondary">
                            {c.symbol.slice(0, 2)}
                          </div>
                          <div>
                            <p className="text-[11px] font-medium text-text-primary">{c.name}</p>
                            <p className="text-[10px] text-text-muted">{c.symbol} · {c.sector}</p>
                          </div>
                        </button>
                      ))}
                      {searching && (
                        <p className="py-3 text-center text-[11px] text-text-muted">Searching…</p>
                      )}
                      {!searching && search.trim() && searchResults.length === 0 && (
                        <p className="py-3 text-center text-[11px] text-text-muted">No results found</p>
                      )}
                      {!search.trim() && (
                        <p className="py-3 text-center text-[11px] text-text-muted">Type a company name or symbol…</p>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>

      {/* Company summary cards */}
      {companies.length > 0 && (
        <div className={`grid gap-4 ${gridCols}`}>
          {companies.map((c, i) => {
            const isPos = (c.pct_change || 0) >= 0;
            return (
              <motion.div key={c.symbol}
                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07 }}
                className="rounded-2xl border bg-text-primary/[0.025] p-4 backdrop-blur-sm transition hover:-translate-y-0.5"
                style={{ borderColor: `${color(i)}22` }}>
                {c.loading ? (
                  <div className="flex h-32 items-center justify-center"><Spinner /></div>
                ) : (
                  <>
                    <div className="flex items-start gap-2.5">
                      <Avatar sym={c.symbol} idx={i} size={40} />
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-semibold text-text-primary">{c.name}</p>
                        <div className="mt-0.5 flex items-center gap-1.5">
                          <span className="text-[10px] text-text-secondary">{c.symbol}</span>
                          <span className="flex items-center gap-0.5 rounded border border-emerald-500/20 bg-emerald-500/10 px-1 py-px text-[8px] font-semibold text-emerald-400">
                            <span className="h-1 w-1 rounded-full bg-emerald-400 inline-block" /> NSE
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="mt-3">
                      <div className="flex flex-wrap items-baseline gap-2">
                        <span className="text-[22px] font-black text-text-primary">₹{c.price}</span>
                        <span className={`text-xs font-semibold ${isPos ? "text-emerald-400" : "text-rose-400"}`}>
                          {isPos ? "+" : ""}{c.change_abs} ({isPos ? "+" : ""}{(c.pct_change || 0).toFixed(2)}%) {isPos ? "▲" : "▼"}
                        </span>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-1 border-t border-surface-border/5 pt-3">
                      <div>
                        <p className="text-[9px] text-text-muted">Market Cap</p>
                        <p className="truncate text-[11px] font-semibold text-text-primary">{c.market_cap}</p>
                      </div>
                      <div>
                        <p className="text-[9px] text-text-muted">Sector</p>
                        <p className="truncate text-[11px] font-semibold text-text-primary">{c.sector}</p>
                      </div>
                      <div>
                        <p className="text-[9px] text-text-muted">52W H/L</p>
                        <p className="truncate text-[11px] font-semibold text-text-primary">{c.week52_high}/{c.week52_low}</p>
                      </div>
                    </div>
                  </>
                )}
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Tab bar */}
      <div className="flex gap-0.5 overflow-x-auto border-b border-surface-border/5 scrollbar-hide">
        {TABS.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`shrink-0 whitespace-nowrap border-b-2 px-3 py-2.5 text-[12px] font-medium transition ${
              activeTab === tab
                ? "border-sky-400 text-text-primary"
                : "border-transparent text-text-muted hover:text-text-secondary"
            }`}>
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        <motion.div key={activeTab} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.2 }}>
          {activeTab === "Overview"      && <OverviewTab />}
          {activeTab === "Financials"    && <FinancialsTab />}
          {activeTab === "Valuation"     && <ValuationTab />}
          {activeTab === "Profitability" && <ProfitabilityTab />}
          {activeTab === "Balance Sheet" && <BalanceSheetTab />}
          {activeTab === "Dividends"     && <DividendsTab />}
          {activeTab === "Peers"         && <PeersTab />}
          {activeTab === "Events"        && <EventsTab />}
          {activeTab === "AI Analysis"   && <AIAnalysisTab />}
          {["Performance","Cash Flow","Growth"].includes(activeTab) && <GenericTab tab={activeTab} />}
        </motion.div>
      </AnimatePresence>

      {companies.every(c => c.price === "—" && !c.loading) && companies.length > 0 && (
        <div className="rounded-[20px] border border-amber-500/20 bg-amber-500/[0.04] p-4">
          <p className="text-xs text-amber-600 dark:text-amber-300">Fetching live data from market — values will appear shortly.</p>
        </div>
      )}
    </main>
  );
}

// Named export (not default) so it can carry a `headingLevel` prop — see
// best-stocks/page.tsx's BestStocksContent for why the route's default
// export can't take custom props under Next's route typegen.
export function CompareContent({ headingLevel = "h1" }: { headingLevel?: "h1" | "h2" }) {
  return (
    <Suspense fallback={<div className="flex h-64 items-center justify-center"><div className="h-5 w-5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent"/></div>}>
      <ComparePageInner headingLevel={headingLevel} />
    </Suspense>
  );
}
