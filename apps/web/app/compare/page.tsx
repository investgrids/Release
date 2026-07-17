"use client";

import { useState, useEffect, useMemo, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Trophy, Shield, Leaf, ClipboardList, BarChart2, X, Award } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine,
} from "recharts";


// ── Company registry ──────────────────────────────────────────────────────────

const COMPANY_LIST = [
  { symbol: "TATAPOWER",  name: "Tata Power Co. Ltd.",         sector: "Power Generation" },
  { symbol: "NTPC",       name: "NTPC Ltd.",                   sector: "Power Generation" },
  { symbol: "ADANIPOWER", name: "Adani Power Ltd.",            sector: "Power Generation" },
  { symbol: "RELIANCE",   name: "Reliance Industries Ltd.",    sector: "Energy" },
  { symbol: "TCS",        name: "Tata Consultancy Services",   sector: "IT" },
  { symbol: "INFY",       name: "Infosys Ltd.",                sector: "IT" },
  { symbol: "HDFCBANK",   name: "HDFC Bank Ltd.",              sector: "Banking" },
  { symbol: "ICICIBANK",  name: "ICICI Bank Ltd.",             sector: "Banking" },
  { symbol: "KOTAKBANK",  name: "Kotak Mahindra Bank",         sector: "Banking" },
  { symbol: "SBIN",       name: "State Bank of India",         sector: "Banking" },
  { symbol: "WIPRO",      name: "Wipro Ltd.",                  sector: "IT" },
  { symbol: "BEL",        name: "Bharat Electronics Ltd.",     sector: "Defence" },
  { symbol: "HAL",        name: "Hindustan Aeronautics Ltd.",  sector: "Defence" },
  { symbol: "RVNL",       name: "Rail Vikas Nigam Ltd.",       sector: "Infrastructure" },
  { symbol: "IRFC",       name: "Indian Railway Finance Corp.",sector: "Finance" },
  { symbol: "ADANIENT",   name: "Adani Enterprises Ltd.",      sector: "Conglomerate" },
  { symbol: "TATASTEEL",  name: "Tata Steel Ltd.",             sector: "Metals" },
  { symbol: "JSWSTEEL",   name: "JSW Steel Ltd.",              sector: "Metals" },
  { symbol: "HINDUNILVR", name: "Hindustan Unilever Ltd.",     sector: "FMCG" },
  { symbol: "ITC",        name: "ITC Ltd.",                    sector: "FMCG" },
  { symbol: "SUNPHARMA",  name: "Sun Pharmaceutical",          sector: "Pharma" },
  { symbol: "DRREDDY",    name: "Dr Reddy's Laboratories",     sector: "Pharma" },
  { symbol: "MARUTI",     name: "Maruti Suzuki India Ltd.",    sector: "Auto" },
  { symbol: "TATAMOTORS", name: "Tata Motors Ltd.",            sector: "Auto" },
  { symbol: "LT",         name: "Larsen & Toubro Ltd.",        sector: "Infrastructure" },
  { symbol: "POWERGRID",  name: "Power Grid Corporation",      sector: "Power" },
  { symbol: "ONGC",       name: "Oil & Natural Gas Corp.",     sector: "Energy" },
  { symbol: "COALINDIA",  name: "Coal India Ltd.",             sector: "Energy" },
  { symbol: "AXISBANK",   name: "Axis Bank Ltd.",              sector: "Banking" },
  { symbol: "BAJFINANCE", name: "Bajaj Finance Ltd.",          sector: "Finance" },
];

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
  revenue: string; profit: string; enterprise_value: string;
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

function meta(sym: string) {
  return COMPANY_LIST.find(c => c.symbol === sym) ?? { symbol: sym, name: sym, sector: "General" };
}

function highlight(values: number[], lowerBetter = false): string[] {
  const valid = values.filter(v => v > 0);
  if (valid.length < 2) return values.map(() => "text-white");
  const best = lowerBetter ? Math.min(...valid) : Math.max(...valid);
  const worst = lowerBetter ? Math.max(...valid) : Math.min(...valid);
  return values.map(v =>
    v <= 0 ? "text-slate-500" :
    v === best  ? "text-emerald-400 font-bold" :
    v === worst ? "text-rose-400" : "text-white"
  );
}

// ── Micro-components ──────────────────────────────────────────────────────────

function Spinner() {
  return <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-sky-400" />;
}

function Avatar({ sym, idx, size = 40 }: { sym: string; idx: number; size?: number }) {
  return (
    <div className="flex shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white"
      style={{ width: size, height: size, background: `${color(idx)}28`, border: `1px solid ${color(idx)}44` }}>
      {sym.slice(0, 2)}
    </div>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-white/[0.08] bg-white/[0.025] p-5 backdrop-blur-sm ${className}`}>
      {children}
    </div>
  );
}

function CardTitle({ children, sub }: { children: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <span className="text-sm font-semibold text-white">{children}</span>
      {sub && <span className="text-[11px] text-slate-500">{sub}</span>}
    </div>
  );
}

function KVRow({ label, value, cls = "text-white" }: { label: string; value: string; cls?: string }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-white/[0.04] py-1.5 last:border-0">
      <span className="text-[11px] text-slate-500 shrink-0">{label}</span>
      <span className={`text-[12px] font-semibold text-right ${cls}`}>{value || "—"}</span>
    </div>
  );
}

function MiniBar({ pct, col }: { pct: number; col: string }) {
  return (
    <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-white/[0.05]">
      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${Math.min(100, Math.max(0, pct))}%`, background: col }} />
    </div>
  );
}

// ── Custom tooltip for performance chart ─────────────────────────────────────

function PerfTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0f1e] px-3 py-2 text-[11px] shadow-xl">
      <p className="mb-1 text-slate-400">{label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <div className="h-1.5 w-3 rounded-full" style={{ background: p.color }} />
          <span className="text-slate-300">{p.dataKey}</span>
          <span className="font-semibold text-white">{p.value > 0 ? "+" : ""}{p.value?.toFixed(2)}%</span>
        </div>
      ))}
    </div>
  );
}

// ── Comparison table row ──────────────────────────────────────────────────────

function CmpRow({ label, values, fmt, lowerBetter = false }: {
  label: string; values: (string | number)[]; fmt?: (v: string | number) => string; lowerBetter?: boolean;
}) {
  const nums = values.map(v => parseN(String(v)));
  const cls = highlight(nums, lowerBetter);
  const display = fmt ? values.map(fmt) : values.map(v => String(v));
  return (
    <tr className="border-b border-white/[0.04] last:border-0">
      <td className="py-2 pr-4 text-[11px] text-slate-500 whitespace-nowrap">{label}</td>
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
        <circle cx="38" cy="38" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
        <circle cx="38" cy="38" r={r} fill="none" stroke={col} strokeWidth="6"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" transform="rotate(-90 38 38)"
          style={{ transition: "stroke-dasharray 1s ease" }} />
        <text x="38" y="42" textAnchor="middle" fill="white" fontSize="14" fontWeight="700" fontFamily="sans-serif">{score}</text>
      </svg>
      <span className="text-[10px] text-slate-400 text-center leading-tight">{label}</span>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function ComparePageInner() {
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
  const searchRef = useRef<HTMLDivElement>(null);

  // Close search on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setShowSearch(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  // Fetch stock info
  useEffect(() => {
    selected.forEach(sym => {
      if (stocks[sym] && !stocks[sym].loading) return;
      setStocks(prev => ({ ...prev, [sym]: { ...fallback(sym), loading: true } }));
      fetch(`${API}/api/stocks/${sym}`)
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (!d) { setStocks(prev => ({ ...prev, [sym]: { ...fallback(sym), loading: false } })); return; }
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
              revenue:           d.revenue       || "—",
              profit:            d.profit        || "—",
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
      revenue: "—", profit: "—", enterprise_value: "—",
      recommendation: "hold", target_mean: "—", target_high: "—", target_low: "—",
      analyst_count: 0, buy_count: 0, hold_count: 0, sell_count: 0,
      held_institutions: "—", held_insiders: "—",
      quarterly_revenue: [], quarterly_net_income: [], annual_financials: [],
      events: [], peers: [], loading: false,
    };
  }

  function addCompany(sym: string) {
    if (selected.includes(sym) || selected.length >= 4) return;
    setSelected(prev => [...prev, sym]);
    setSearch(""); setShowSearch(false);
  }
  function removeCompany(sym: string) {
    setSelected(prev => prev.filter(s => s !== sym));
    setStocks(prev => { const n = { ...prev }; delete n[sym]; return n; });
  }

  const companies = selected.map(sym => stocks[sym] ?? fallback(sym));

  const filteredSearch = COMPANY_LIST.filter(c =>
    !selected.includes(c.symbol) &&
    (c.symbol.toLowerCase().includes(search.toLowerCase()) ||
     c.name.toLowerCase().includes(search.toLowerCase()))
  ).slice(0, 8);

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

  // AI winner
  const aiScores = useMemo(() => companies.map(c => {
    let s = 50;
    const roe = parseN(c.roe);      if (roe  > 0) s += Math.min(roe * 0.8, 20);
    const pe  = parseN(c.pe);       if (pe   > 0 && pe < 60) s += Math.max(0, (30 - pe) * 0.5);
    const de  = parseN(c.debt_to_equity); s -= Math.min(de * 5, 20);
    const gm  = parseN(c.gross_margins); s += Math.min(gm * 0.3, 15);
    const div = parseN(c.dividend_yield); s += Math.min(div * 2, 8);
    return Math.min(99, Math.max(10, Math.round(s)));
  }), [companies]);

  const winnerIdx = aiScores.indexOf(Math.max(...aiScores));

  const recBadge = (r: string) => {
    const map: Record<string, string> = {
      "strong buy": "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
      "buy":        "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
      "hold":       "border-amber-500/30  bg-amber-500/10  text-amber-300",
      "sell":       "border-rose-500/30   bg-rose-500/10   text-rose-300",
      "strong sell":"border-rose-500/40   bg-rose-500/15   text-rose-300",
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
                <h3 className="text-sm font-semibold text-white">Performance Chart</h3>
                <div className="flex gap-0.5">
                  {PERIODS.map(p => (
                    <button key={p} onClick={() => setPeriod(p)}
                      className={`rounded-md px-2 py-1 text-[10px] font-medium transition ${period === p ? "bg-sky-500/20 text-sky-300" : "text-slate-500 hover:text-slate-300"}`}>
                      {p}
                    </button>
                  ))}
                </div>
              </div>
              {loadingChart ? (
                <div className="flex h-64 items-center justify-center"><Spinner /></div>
              ) : mergedChart.length > 0 ? (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={mergedChart}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                      <XAxis dataKey="label" stroke="#475569" axisLine={false} tickLine={false}
                        tick={{ fontSize: 9, fill: "#64748b" }} interval="preserveStartEnd" />
                      <YAxis stroke="#475569" axisLine={false} tickLine={false} width={50}
                        tick={{ fontSize: 9, fill: "#64748b" }}
                        tickFormatter={v => `${v > 0 ? "+" : ""}${v.toFixed(0)}%`} />
                      <ReferenceLine y={0} stroke="rgba(255,255,255,0.08)" />
                      <Tooltip content={<PerfTooltip />} />
                      {selected.map((sym, i) => (
                        <Line key={sym} type="monotone" dataKey={sym} stroke={color(i)}
                          strokeWidth={2} dot={false} connectNulls name={sym} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="flex h-64 items-center justify-center rounded-xl border border-white/5 bg-white/[0.02]">
                  <p className="text-sm text-slate-500">No chart data available</p>
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-4 border-t border-white/5 pt-3">
                {selected.map((sym, i) => {
                  const pct = stocks[sym]?.pct_change || 0;
                  const isPos = pct >= 0;
                  return (
                    <div key={sym} className="flex items-center gap-2">
                      <div className="h-0.5 w-5 rounded-full" style={{ background: color(i) }} />
                      <span className="text-[11px] font-semibold text-slate-300">{sym}</span>
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
                    <tr className="border-b border-white/[0.06]">
                      <th className="pb-2 text-left text-[10px] font-medium text-slate-500 w-36">Metric</th>
                      {companies.map((c, i) => (
                        <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <CmpRow label="Market Cap"       values={companies.map(c => c.market_cap)} />
                    <CmpRow label="P/E Ratio (TTM)"  values={companies.map(c => c.pe)}           lowerBetter />
                    <CmpRow label="P/B Ratio"        values={companies.map(c => c.pb)}           lowerBetter />
                    <CmpRow label="ROE (%)"          values={companies.map(c => c.roe)} />
                    <CmpRow label="ROCE (%)"         values={companies.map(c => c.roce)} />
                    <CmpRow label="Debt to Equity"   values={companies.map(c => c.debt_to_equity)} lowerBetter />
                    <CmpRow label="Dividend Yield"   values={companies.map(c => c.dividend_yield)} />
                    <CmpRow label="52W High"         values={companies.map(c => c.week52_high)}
                      fmt={v => v === "—" ? "—" : `₹${v}`} />
                    <CmpRow label="52W Low"          values={companies.map(c => c.week52_low)}
                      fmt={v => v === "—" ? "—" : `₹${v}`} lowerBetter />
                  </tbody>
                </table>
              </div>
            </Card>
          </div>

          {/* RIGHT — sticky */}
          <div className="space-y-5 xl:sticky xl:top-[84px]">
            {/* AI Comparison Summary */}
            <Card className="border-violet-500/10">
              <div className="mb-4 flex items-center gap-2">
                <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5 shrink-0 text-violet-400"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg>
                <h3 className="text-sm font-semibold text-white">AI Comparison Summary</h3>
              </div>
              <p className="mb-4 text-[12px] leading-5 text-slate-300">
                {companies[winnerIdx]?.name || companies[0]?.name || "—"} leads on risk-adjusted return metrics.
                {companies.length > 1 ? ` ${companies.find((_, i) => i !== winnerIdx)?.name ?? ""} offers stability with lower volatility.` : ""}
                {companies.length > 2 ? " Consider sector exposure and time horizon before comparing." : ""}
              </p>
              <div className="space-y-2">
                {([
                  { icon: <Trophy className="h-4 w-4" />, label: "Best Performer",      col: "text-amber-300",   val: companies.reduce((b, c) => parseN(c.roe) > parseN(b.roe) ? c : b, companies[0])?.name || "—" },
                  { icon: <Shield className="h-4 w-4" />, label: "Most Stable",         col: "text-sky-300",     val: companies.reduce((b, c) => { const bn = parseN(b.beta); const cn = parseN(c.beta); return (cn > 0 && cn < bn) || bn <= 0 ? c : b; }, companies[0])?.name || "—" },
                  { icon: <Leaf className="h-4 w-4" />,   label: "Best Future Potential",col: "text-emerald-300", val: companies.reduce((b, c) => aiScores[companies.indexOf(c)] > aiScores[companies.indexOf(b)] ? c : b, companies[0])?.name || "—" },
                ] as { icon: ReactNode; label: string; col: string; val: string }[]).map(item => (
                  <div key={item.label}
                    className="flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400">{item.icon}</span>
                      <span className={`text-[11px] font-medium ${item.col}`}>{item.label}</span>
                    </div>
                    <span className="max-w-[110px] truncate text-right text-[11px] font-semibold text-white">{item.val}</span>
                  </div>
                ))}
              </div>
              <button
                onClick={() => setActiveTab("AI Analysis")}
                className="mt-4 w-full rounded-xl border border-violet-500/20 bg-gradient-to-r from-violet-500/15 to-sky-500/10 py-2.5 text-[12px] font-medium text-violet-300 transition hover:from-violet-500/25 hover:to-sky-500/15">
                View Detailed AI Analysis →
              </button>
            </Card>

            {/* Valuation Metrics */}
            <Card>
              <CardTitle>Valuation Metrics</CardTitle>
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="pb-2 text-left text-[10px] font-medium text-slate-500">Metric</th>
                    {companies.map((c, i) => (
                      <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <CmpRow label="P/E Ratio (TTM)" values={companies.map(c => c.pe)}         lowerBetter />
                  <CmpRow label="P/B Ratio"       values={companies.map(c => c.pb)}         lowerBetter />
                  <CmpRow label="Forward P/E"     values={companies.map(c => c.forward_pe)} lowerBetter />
                  <CmpRow label="EPS (₹)"         values={companies.map(c => c.eps)} />
                  <CmpRow label="Beta"            values={companies.map(c => c.beta)}       lowerBetter />
                </tbody>
              </table>
            </Card>

            {/* Recent Events */}
            <Card>
              <CardTitle>Recent Events</CardTitle>
              <div className="space-y-2">
                {companies.flatMap((c, i) =>
                  (c.events || []).slice(0, 2).map((e, j) => (
                    <div key={`${c.symbol}-${j}`}
                      className="flex items-start gap-2.5 rounded-xl border border-white/5 bg-white/[0.02] p-2.5">
                      <Avatar sym={c.symbol} idx={i} size={28} />
                      <div className="min-w-0 flex-1">
                        <p className="text-[11px] font-medium text-white leading-snug line-clamp-2">{e.title}</p>
                        <div className="mt-1 flex items-center gap-2">
                          <span className="text-[9px] font-semibold" style={{ color: color(i) }}>{c.symbol}</span>
                          <span className="text-[9px] text-slate-500">{e.date}</span>
                        </div>
                      </div>
                    </div>
                  ))
                ).slice(0, 5)}
                {companies.every(c => !c.events?.length) && (
                  <p className="py-4 text-center text-[11px] text-slate-500">No events for selected companies</p>
                )}
              </div>
              <Link href="/events" className="mt-3 block text-center text-[11px] text-sky-400 hover:text-sky-300 transition">
                View All Events →
              </Link>
            </Card>
          </div>
        </div>

        {/* Financial Highlights (full width below) */}
        <Card>
          <CardTitle sub="Trailing Twelve Months">Financial Highlights (TTM)</CardTitle>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="pb-2 text-left text-[10px] font-medium text-slate-500 w-40">Metric</th>
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
                  { label: "Revenue (₹ Cr)",      key: "revenue",           lowerBetter: false },
                  { label: "Net Profit (₹ Cr)",   key: "profit",            lowerBetter: false },
                  { label: "EPS (₹)",             key: "eps",               lowerBetter: false },
                  { label: "Operating Margin (%)",key: "operating_margins", lowerBetter: false },
                  { label: "Net Margin (%)",      key: "net_margins",       lowerBetter: false },
                ] as { label: string; key: keyof StockData; lowerBetter: boolean }[]).map(row => {
                  const vals = companies.map(c => parseN(String((c as any)[row.key])));
                  const max = Math.max(...vals.filter(v => v > 0), 1);
                  const cls = highlight(vals, row.lowerBetter);
                  return (
                    <tr key={row.label} className="border-b border-white/[0.04] last:border-0">
                      <td className="py-2.5 text-[11px] text-slate-500">{row.label}</td>
                      {companies.map((c, i) => {
                        const v = vals[i];
                        const w = max > 0 ? (v / max) * 100 : 0;
                        const display = String((c as any)[row.key]);
                        return (
                          <td key={c.symbol} className="py-2.5 text-right">
                            {c.loading
                              ? <span className="text-[11px] text-slate-600">…</span>
                              : <div className="inline-flex flex-col items-end gap-1">
                                  <span className={`text-[12px] font-semibold ${cls[i]}`}>{display || "—"}</span>
                                  {w > 0 && (
                                    <div className="h-1 w-16 overflow-hidden rounded-full bg-white/[0.05]">
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
                  <p className="text-[13px] font-semibold text-white">{c.symbol}</p>
                  <p className="text-[10px] text-slate-500">{c.sector}</p>
                </div>
              </div>
              {c.quarterly_revenue.length > 0 ? (
                <div className="h-28">
                  <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Quarterly Revenue</p>
                  <div className="flex h-20 items-end gap-1">
                    {c.quarterly_revenue.map((d, j) => {
                      const maxV = Math.max(...c.quarterly_revenue.map(x => x.value), 1);
                      const pct = (d.value / maxV) * 100;
                      return (
                        <div key={j} className="group flex flex-1 flex-col items-center gap-0.5">
                          <span className="text-[8px] text-slate-600 group-hover:text-slate-400 transition">
                            {d.value > 999 ? `${(d.value / 1000).toFixed(0)}K` : d.value}
                          </span>
                          <div className="flex w-full flex-1 items-end">
                            <div className="w-full rounded-t" style={{ height: `${Math.max(pct, 4)}%`, background: `${color(i)}99` }} />
                          </div>
                          <span className="text-[8px] text-slate-600">{d.label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="flex h-24 items-center justify-center text-[11px] text-slate-600">No data</div>
              )}
              <div className="mt-3 space-y-0 border-t border-white/5 pt-3">
                <KVRow label="Revenue"        value={c.revenue} />
                <KVRow label="Net Profit"     value={c.profit} />
                <KVRow label="Gross Margin"   value={c.gross_margins} />
                <KVRow label="Op. Margin"     value={c.operating_margins} />
                <KVRow label="Net Margin"     value={c.net_margins} />
                <KVRow label="Free Cash Flow" value={c.free_cashflow} />
              </div>
            </Card>
          ))}
        </div>
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
                      <tr className="border-b border-white/[0.06]">
                        <th className="pb-2 text-left text-[10px] text-slate-500 font-medium">₹ Cr</th>
                        {c.annual_financials.map(f => (
                          <th key={f.year} className="pb-2 text-right text-[10px] text-slate-500 font-medium">{f.year}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-white/[0.04]">
                        <td className="py-2 text-slate-400">Revenue</td>
                        {c.annual_financials.map(f => (
                          <td key={f.year} className="py-2 text-right font-semibold text-white">{f.revenue.toLocaleString()}</td>
                        ))}
                      </tr>
                      <tr>
                        <td className="py-2 text-slate-400">Net Profit</td>
                        {c.annual_financials.map(f => (
                          <td key={f.year} className={`py-2 text-right font-semibold ${f.net_income >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
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
      { label: "P/E Ratio (TTM)", vals: companies.map(c => c.pe),          lowerBetter: true  },
      { label: "P/B Ratio",       vals: companies.map(c => c.pb),          lowerBetter: true  },
      { label: "Forward P/E",     vals: companies.map(c => c.forward_pe),  lowerBetter: true  },
      { label: "EPS (₹)",         vals: companies.map(c => c.eps),         lowerBetter: false },
      { label: "Beta",            vals: companies.map(c => c.beta),        lowerBetter: true  },
      { label: "Market Cap",      vals: companies.map(c => c.market_cap),  lowerBetter: false },
      { label: "Ent. Value",      vals: companies.map(c => c.enterprise_value), lowerBetter: false },
    ];
    return (
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
        <Card>
          <CardTitle>Valuation Multiples</CardTitle>
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/[0.06]">
                <th className="pb-2 text-left text-[10px] font-medium text-slate-500 w-36">Metric</th>
                {companies.map((c, i) => (
                  <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(r => <CmpRow key={r.label} label={r.label} values={r.vals} lowerBetter={r.lowerBetter} />)}
            </tbody>
          </table>
        </Card>
        <Card>
          <CardTitle>Score Comparison</CardTitle>
          <div className="flex flex-wrap justify-around gap-4 pt-2">
            {companies.map((c, i) => (
              <div key={c.symbol} className="flex flex-col items-center gap-3">
                <ScoreRing score={aiScores[i]} label={c.symbol} col={color(i)} />
                <div className="text-center">
                  <p className="text-[10px] text-slate-500">Valuation Score</p>
                  <p className="text-[12px] font-bold text-white">{aiScores[i]}/100</p>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-4 text-[10px] text-slate-600 text-center">
            Score derived from ROE, PE, D/E, gross margins, and dividend yield.
          </p>
        </Card>
      </div>
    );
  }

  function ProfitabilityTab() {
    const rows = [
      { label: "Gross Margin",     key: "gross_margins"     as keyof StockData },
      { label: "Operating Margin", key: "operating_margins" as keyof StockData },
      { label: "Net Margin",       key: "net_margins"       as keyof StockData },
      { label: "ROE",              key: "roe"               as keyof StockData },
      { label: "ROA",              key: "roa"               as keyof StockData },
      { label: "ROCE",             key: "roce"              as keyof StockData },
    ];
    return (
      <div className="space-y-5">
        <div className={`grid gap-5 ${gridCols}`}>
          {companies.map((c, i) => (
            <Card key={c.symbol}>
              <div className="mb-3 flex items-center gap-2">
                <Avatar sym={c.symbol} idx={i} size={32} />
                <span className="text-[13px] font-semibold text-white">{c.symbol}</span>
              </div>
              <div className="space-y-3">
                {rows.map(r => {
                  const val = String((c as any)[r.key]);
                  const pct = parseN(val);
                  return (
                    <div key={r.key}>
                      <div className="mb-1 flex justify-between text-[11px]">
                        <span className="text-slate-400">{r.label}</span>
                        <span className="font-semibold text-white">{val || "—"}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.05]">
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
              <tr className="border-b border-white/[0.06]">
                <th className="pb-2 text-left text-[10px] font-medium text-slate-500 w-36">Margin</th>
                {companies.map((c, i) => (
                  <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(r => <CmpRow key={r.key} label={r.label} values={companies.map(c => String((c as any)[r.key]))} />)}
            </tbody>
          </table>
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
            <tr className="border-b border-white/[0.06]">
              <th className="pb-2 text-left text-[10px] font-medium text-slate-500 w-40">Metric</th>
              {companies.map((c, i) => (
                <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <CmpRow label="Debt to Equity"   values={companies.map(c => c.debt_to_equity)} lowerBetter />
            <CmpRow label="Current Ratio"    values={companies.map(c => c.current_ratio)} />
            <CmpRow label="Free Cash Flow"   values={companies.map(c => c.free_cashflow)} />
            <CmpRow label="Enterprise Value" values={companies.map(c => c.enterprise_value)} />
            <CmpRow label="Market Cap"       values={companies.map(c => c.market_cap)} />
          </tbody>
        </table>
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
              <tr className="border-b border-white/[0.06]">
                <th className="pb-2 text-left text-[10px] font-medium text-slate-500 w-36">Metric</th>
                {companies.map((c, i) => (
                  <th key={c.symbol} className="pb-2 text-right text-[10px] font-semibold" style={{ color: color(i) }}>{c.symbol}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <CmpRow label="Dividend Yield"  values={companies.map(c => c.dividend_yield)} />
              <CmpRow label="Dividend Rate"   values={companies.map(c => c.dividend_rate)} />
              <CmpRow label="Payout Ratio"    values={companies.map(() => "—")} />
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
                      <span className="font-semibold text-white">{c.symbol}</span>
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
                <p className="text-[13px] font-semibold text-white">{c.symbol}</p>
                <p className="text-[10px] text-slate-500">{c.sector}</p>
              </div>
            </div>
            {c.peers.length > 0 ? (
              <div className="space-y-1.5">
                {c.peers.map(p => (
                  <Link key={p} href={`/companies/${p}`}
                    className="flex items-center gap-2.5 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2 hover:border-white/10 hover:bg-white/[0.04] transition">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/[0.06] text-[9px] font-bold text-slate-300">
                      {p.slice(0, 2)}
                    </div>
                    <span className="text-[12px] font-medium text-white">{p}</span>
                    <span className="ml-auto text-[10px] text-sky-400">→</span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="py-6 text-center text-[11px] text-slate-500">No peer data</p>
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
              <div key={j} className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-3.5">
                <Avatar sym={e.sym} idx={e.idx} size={32} />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-white leading-snug">{e.title}</p>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-[10px] font-semibold" style={{ color: color(e.idx) }}>{e.sym}</span>
                    <span className="text-[10px] text-slate-500">{e.date}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <ClipboardList className="h-8 w-8 text-slate-500" />
            <p className="text-sm text-slate-400">No events found for the selected companies.</p>
            <Link href="/events" className="text-sm text-sky-400 hover:text-sky-300 transition">Browse all events →</Link>
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
                      <p className="text-[13px] font-semibold text-white">{c.name}</p>
                      <p className="text-[10px] text-slate-500">{c.symbol} · {c.sector}</p>
                    </div>
                  </div>
                  <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold ${recBadge(c.recommendation)}`}>
                    {(c.recommendation || "hold").replace(/_/g, " ").toUpperCase()}
                  </span>
                </div>
                <ScoreRing score={aiScores[i]} label="AI Score" col={color(i)} />
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div>
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">Strengths</p>
                    {strengths.length > 0 ? (
                      <ul className="space-y-1">
                        {strengths.map((s, j) => (
                          <li key={j} className="flex items-start gap-1 text-[11px] text-slate-300">
                            <span className="mt-0.5 text-emerald-400 shrink-0">•</span>{s}
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-[11px] text-slate-500">Loading…</p>}
                  </div>
                  <div>
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-rose-400">Risks</p>
                    {risks.length > 0 ? (
                      <ul className="space-y-1">
                        {risks.map((r, j) => (
                          <li key={j} className="flex items-start gap-1 text-[11px] text-slate-300">
                            <span className="mt-0.5 text-rose-400 shrink-0">•</span>{r}
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-[11px] text-slate-500">No major risks identified</p>}
                  </div>
                </div>
                <div className="mt-3 space-y-0 border-t border-white/5 pt-3">
                  <KVRow label="Target Mean"     value={c.target_mean} />
                  <KVRow label="Target High"     value={c.target_high} />
                  <KVRow label="Target Low"      value={c.target_low} />
                  <KVRow label="Analysts"        value={String(c.analyst_count || "—")} />
                  <KVRow label="Inst. Holding"   value={c.held_institutions} />
                </div>
              </Card>
            );
          })}
        </div>

        {/* Winner summary */}
        <Card className="border-violet-500/20 bg-violet-500/[0.04]">
          <div className="flex flex-wrap items-center gap-4">
            <Award className="h-7 w-7 text-violet-400" />
            <div className="flex-1">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-violet-400">AI Recommended Pick</p>
              <p className="mt-0.5 text-xl font-bold text-white">{companies[winnerIdx]?.name || "—"}</p>
              <p className="mt-1 text-[12px] text-slate-300">
                Scores highest ({aiScores[winnerIdx]}/100) on risk-adjusted return metrics among the compared companies.
                Based on ROE, valuation multiples, debt levels, and dividend returns.
              </p>
            </div>
            <div className="flex gap-4">
              {companies.map((c, i) => (
                <div key={c.symbol} className="text-center">
                  <p className="text-[10px] text-slate-500">{c.symbol}</p>
                  <p className="text-[20px] font-black" style={{ color: color(i) }}>{aiScores[i]}</p>
                  <p className="text-[9px] text-slate-600">/100</p>
                </div>
              ))}
            </div>
          </div>
          <button className="mt-4 rounded-xl border border-violet-500/20 bg-gradient-to-r from-violet-500/15 to-sky-500/10 px-5 py-2.5 text-[12px] font-medium text-violet-300 transition hover:from-violet-500/25 hover:to-sky-500/20">
            View Detailed AI Analysis →
          </button>
        </Card>
      </div>
    );
  }

  function GenericTab({ tab }: { tab: string }) {
    return (
      <Card>
        <div className="flex flex-col items-center gap-3 py-20 text-center">
          <BarChart2 className="h-8 w-8 text-slate-500" />
          <p className="text-sm font-semibold text-white">{tab}</p>
          <p className="text-sm text-slate-500">Detailed {tab.toLowerCase()} data coming soon.</p>
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
          <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Research</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Compare Companies</h1>
          <p className="mt-1 text-sm text-slate-400">
            Compare financials, valuation, market performance, events and AI insights side by side.
          </p>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <button className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-xs font-medium text-slate-300 transition hover:border-white/20 hover:text-white">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Export PDF
          </button>
          <button className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-xs font-medium text-slate-300 transition hover:border-white/20 hover:text-white">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
            </svg>
            Share
          </button>
        </div>
      </div>

      {/* Company selector chips */}
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-4 backdrop-blur-sm">
        <div className="flex flex-wrap items-center gap-3">
          {selected.map((sym, i) => {
            const m = meta(sym);
            return (
              <div key={sym} className="flex items-center gap-2">
                {i > 0 && <span className="text-xs font-bold text-slate-600">VS</span>}
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-2 rounded-xl border bg-white/[0.04] px-3 py-2 transition"
                  style={{ borderColor: `${color(i)}33` }}>
                  <Avatar sym={sym} idx={i} size={28} />
                  <div>
                    <p className="max-w-[120px] truncate text-[11px] font-semibold text-white leading-tight">{m.name}</p>
                    <p className="text-[9px] text-slate-500">{sym}</p>
                  </div>
                  <button
                    onClick={() => removeCompany(sym)}
                    className="ml-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-slate-500 transition hover:bg-white/10 hover:text-white">
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
                className="flex items-center gap-1.5 rounded-xl border border-dashed border-white/20 px-3 py-2 text-xs text-slate-400 transition hover:border-white/40 hover:text-white">
                <span className="text-base leading-none font-light">+</span> Add Company
              </button>
              <AnimatePresence>
                {showSearch && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 4 }}
                    className="absolute left-0 top-full z-50 mt-2 w-72 rounded-xl border border-white/10 bg-[#080d1c] p-2 shadow-2xl">
                    <input
                      autoFocus
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      placeholder="Search company or symbol…"
                      className="w-full rounded-lg border border-white/5 bg-white/[0.04] px-3 py-2 text-xs text-white outline-none placeholder:text-slate-500 focus:border-sky-500/30"
                    />
                    <div className="mt-2 max-h-48 overflow-y-auto space-y-0.5">
                      {filteredSearch.map(c => (
                        <button key={c.symbol} onClick={() => addCompany(c.symbol)}
                          className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition hover:bg-white/[0.04]">
                          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-white/[0.06] text-[9px] font-bold text-slate-300">
                            {c.symbol.slice(0, 2)}
                          </div>
                          <div>
                            <p className="text-[11px] font-medium text-white">{c.name}</p>
                            <p className="text-[10px] text-slate-500">{c.symbol} · {c.sector}</p>
                          </div>
                        </button>
                      ))}
                      {filteredSearch.length === 0 && (
                        <p className="py-3 text-center text-[11px] text-slate-500">No results found</p>
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
                className="rounded-2xl border bg-white/[0.025] p-4 backdrop-blur-sm transition hover:-translate-y-0.5"
                style={{ borderColor: `${color(i)}22` }}>
                {c.loading ? (
                  <div className="flex h-32 items-center justify-center"><Spinner /></div>
                ) : (
                  <>
                    <div className="flex items-start gap-2.5">
                      <Avatar sym={c.symbol} idx={i} size={40} />
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-semibold text-white">{c.name}</p>
                        <div className="mt-0.5 flex items-center gap-1.5">
                          <span className="text-[10px] text-slate-400">{c.symbol}</span>
                          <span className="flex items-center gap-0.5 rounded border border-emerald-500/20 bg-emerald-500/10 px-1 py-px text-[8px] font-semibold text-emerald-400">
                            <span className="h-1 w-1 rounded-full bg-emerald-400 inline-block" /> NSE
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="mt-3">
                      <div className="flex flex-wrap items-baseline gap-2">
                        <span className="text-[22px] font-black text-white">₹{c.price}</span>
                        <span className={`text-xs font-semibold ${isPos ? "text-emerald-400" : "text-rose-400"}`}>
                          {isPos ? "+" : ""}{c.change_abs} ({isPos ? "+" : ""}{(c.pct_change || 0).toFixed(2)}%) {isPos ? "▲" : "▼"}
                        </span>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-1 border-t border-white/5 pt-3">
                      <div>
                        <p className="text-[9px] text-slate-500">Market Cap</p>
                        <p className="truncate text-[11px] font-semibold text-white">{c.market_cap}</p>
                      </div>
                      <div>
                        <p className="text-[9px] text-slate-500">Sector</p>
                        <p className="truncate text-[11px] font-semibold text-white">{c.sector}</p>
                      </div>
                      <div>
                        <p className="text-[9px] text-slate-500">52W H/L</p>
                        <p className="truncate text-[11px] font-semibold text-white">{c.week52_high}/{c.week52_low}</p>
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
      <div className="flex gap-0.5 overflow-x-auto border-b border-white/5 scrollbar-hide">
        {TABS.map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`shrink-0 whitespace-nowrap border-b-2 px-3 py-2.5 text-[12px] font-medium transition ${
              activeTab === tab
                ? "border-sky-400 text-white"
                : "border-transparent text-slate-500 hover:text-slate-300"
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
          <p className="text-xs text-amber-300">Fetching live data from market — values will appear shortly.</p>
        </div>
      )}
    </main>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<div className="flex h-64 items-center justify-center"><div className="h-5 w-5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent"/></div>}>
      <ComparePageInner />
    </Suspense>
  );
}
