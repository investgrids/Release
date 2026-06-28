"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { StockDetailChart } from "@/components/StockDetailChart";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const TABS    = ["Overview", "Financials", "Analysis", "Events", "News", "Peers", "Chart"];
const PERIODS = ["1D", "1W", "1M", "6M", "1Y", "3Y", "5Y", "Max"];

const REC_STYLE: Record<string, { label: string; cls: string; dot: string; ring: string }> = {
  "strong buy":   { label: "Strong Buy",   cls: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30", dot: "bg-emerald-400", ring: "border-emerald-500/40" },
  "buy":          { label: "Buy",          cls: "text-emerald-300 bg-emerald-500/10 border-emerald-500/25", dot: "bg-emerald-400", ring: "border-emerald-500/30" },
  "hold":         { label: "Hold",         cls: "text-amber-300  bg-amber-500/10  border-amber-500/25",    dot: "bg-amber-400",  ring: "border-amber-500/30"  },
  "underperform": { label: "Underperform", cls: "text-rose-300   bg-rose-500/10   border-rose-500/25",     dot: "bg-rose-400",   ring: "border-rose-500/30"   },
  "sell":         { label: "Sell",         cls: "text-rose-300   bg-rose-500/10   border-rose-500/25",     dot: "bg-rose-400",   ring: "border-rose-500/30"   },
  "strong sell":  { label: "Strong Sell",  cls: "text-rose-400   bg-rose-500/15   border-rose-500/30",     dot: "bg-rose-500",   ring: "border-rose-500/40"   },
};

interface StockEvent { title: string; date: string; }
interface StockDetail {
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
  events: StockEvent[]; news: any[]; peers: string[]; chart_data: any[];
}
interface PageProps { params: Promise<{ symbol: string }>; }

// ── Helper components ─────────────────────────────────────────────────────────

function StatBox({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02] p-3">
      <p className="text-[10px] uppercase tracking-widest text-slate-500">{label}</p>
      <p className="mt-1 text-[13px] font-bold text-white">{value || "—"}</p>
      {sub && <p className="mt-0.5 text-[10px] text-slate-600">{sub}</p>}
    </div>
  );
}

function KvRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
      <span className="text-[12px] text-slate-500">{label}</span>
      <span className="text-[12px] font-semibold text-white text-right truncate">{value || "—"}</span>
    </div>
  );
}

function BarChart({ data, colorFrom, colorTo, label }: {
  data: { label: string; value: number }[];
  colorFrom: string; colorTo: string; label: string;
}) {
  const maxAbs = Math.max(...data.map(d => Math.abs(d.value)), 1);
  return (
    <div>
      <p className="mb-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{label}</p>
      <div className="flex h-36 items-end gap-2">
        {data.map((d, i) => {
          const pct    = Math.round((Math.abs(d.value) / maxAbs) * 100);
          const isNeg  = d.value < 0;
          const valLbl = d.value === 0 ? "—" : `${isNeg ? "−" : ""}₹${Math.abs(d.value).toLocaleString()}Cr`;
          return (
            <div key={i} className="group flex flex-1 flex-col items-center gap-1">
              <span className="text-[8px] text-slate-500 group-hover:text-slate-300 transition leading-tight">{valLbl}</span>
              <div className="flex w-full flex-1 items-end">
                <div
                  style={{ height: `${Math.max(pct, 3)}%` }}
                  className={`w-full rounded-t-md transition-all duration-500 ${isNeg ? "bg-rose-500/50" : `bg-gradient-to-t ${colorFrom} ${colorTo}`}`}
                />
              </div>
              <span className="text-[9px] text-slate-600">{d.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TargetBand({ current, low, mean, high }: { current: string; low: string; mean: string; high: string }) {
  const parse = (s: string) => parseFloat((s || "").replace(/[₹,\s]/g, "")) || 0;
  const c = parse(current), l = parse(low), m = parse(mean), h = parse(high);
  if (!l || !h || l >= h) return null;
  const pos = (v: number) => `${Math.max(0, Math.min(100, ((v - l) / (h - l)) * 100)).toFixed(1)}%`;
  return (
    <div className="mt-4">
      <div className="relative mx-2 h-2 rounded-full bg-white/[0.06]">
        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-amber-500/20 via-sky-500/20 to-emerald-500/20"/>
        <div className="absolute top-1/2 h-3.5 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-sky-400" style={{ left: pos(m) }}/>
        <div className="absolute top-1/2 h-5 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white" style={{ left: pos(c) }}/>
      </div>
      <div className="mt-3 flex justify-between text-[10px]">
        <div className="text-center"><span className="block text-slate-500">Low</span><span className="font-semibold text-amber-300">{low}</span></div>
        <div className="text-center"><span className="block text-slate-500">Mean</span><span className="font-semibold text-sky-300">{mean}</span></div>
        <div className="text-center"><span className="block text-slate-500">High</span><span className="font-semibold text-emerald-300">{high}</span></div>
      </div>
    </div>
  );
}

function MarginBar({ label, value, color }: { label: string; value: string; color: string }) {
  const pct = parseFloat((value || "0").replace("%", "")) || 0;
  return (
    <div>
      <div className="mb-1 flex justify-between">
        <span className="text-[12px] text-slate-400">{label}</span>
        <span className="text-[12px] font-bold text-white">{value || "—"}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }}/>
      </div>
    </div>
  );
}

function OwnershipBar({ label, value, color }: { label: string; value: string; color: string }) {
  const pct = parseFloat((value || "0").replace("%", "")) || 0;
  return (
    <div>
      <div className="mb-1.5 flex justify-between">
        <span className="text-[13px] text-slate-300">{label}</span>
        <span className="text-[13px] font-bold text-white">{value || "—"}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
        <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${Math.min(pct, 100)}%` }}/>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function StockPage({ params }: PageProps) {
  const { symbol } = use(params);
  const [stock,       setStock]       = useState<StockDetail | null>(null);
  const [chartData,   setChartData]   = useState<any[]>([]);
  const [loadingInfo, setLoadingInfo] = useState(true);
  const [loadingChart,setLoadingChart]= useState(true);
  const [activeTab,   setActiveTab]   = useState("Overview");
  const [period,      setPeriod]      = useState("6M");
  const [following,   setFollowing]   = useState(false);
  const [relatedNews, setRelatedNews] = useState<any[]>([]);

  useEffect(() => {
    setLoadingInfo(true);
    fetch(`${API}/api/stocks/${symbol}`)
      .then(r => r.ok ? r.json() : null)
      .then(setStock)
      .catch(() => {})
      .finally(() => setLoadingInfo(false));
  }, [symbol]);

  useEffect(() => {
    setLoadingChart(true);
    fetch(`${API}/api/stocks/${symbol}/chart?period=${period}`)
      .then(r => r.ok ? r.json() : [])
      .then(d => setChartData(Array.isArray(d) ? d : []))
      .catch(() => setChartData([]))
      .finally(() => setLoadingChart(false));
  }, [symbol, period]);

  useEffect(() => {
    if (activeTab !== "News") return;
    fetch(`${API}/api/news`)
      .then(r => r.ok ? r.json() : [])
      .then(d => {
        const sym = symbol.toLowerCase();
        const all = Array.isArray(d) ? d : [];
        const filtered = all.filter((a: any) =>
          (a.companies || []).some((c: string) =>
            c.toLowerCase().includes(sym) || sym.includes(c.toLowerCase().split(" ")[0])
          )
        );
        setRelatedNews(filtered.length > 0 ? filtered : all.slice(0, 6));
      })
      .catch(() => {});
  }, [activeTab, symbol]);

  if (loadingInfo) {
    return (
      <main className="min-w-0 space-y-4 pb-10">
        <div className="h-7 w-32 animate-pulse rounded-lg bg-white/[0.04]"/>
        <div className="h-36 animate-pulse rounded-[24px] border border-white/8 bg-white/[0.02]"/>
        <div className="h-96 animate-pulse rounded-[24px] border border-white/8 bg-white/[0.02]"/>
      </main>
    );
  }

  if (!stock) {
    return (
      <main className="min-w-0 flex flex-col items-center justify-center gap-4 py-24 text-center">
        <span className="text-5xl">📉</span>
        <h1 className="text-2xl font-semibold text-white">{symbol.toUpperCase()} not found</h1>
        <p className="text-slate-400">This symbol may not be listed on NSE, or the backend is offline.</p>
        <Link href="/stocks" className="mt-2 rounded-full bg-sky-500/15 px-5 py-2 text-sm text-sky-300 hover:bg-sky-500/25 transition">
          ← Back to Explorer
        </Link>
      </main>
    );
  }

  const isPos = !stock.change.startsWith("-");
  const rec   = REC_STYLE[stock.recommendation] ?? REC_STYLE["hold"];

  return (
    <main className="min-w-0 space-y-5 pb-10">

      {/* Back */}
      <Link href="/stocks" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 transition">
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
        </svg>
        Stocks
      </Link>

      {/* ── Header card ─────────────────────────────────────────────────── */}
      <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-sky-500/20 bg-gradient-to-br from-sky-500/25 to-violet-500/15 text-base font-black text-sky-300">
              {symbol.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">{stock.name}</h1>
              <div className="mt-1.5 flex flex-wrap items-center gap-2">
                <span className="rounded-md border border-white/10 bg-white/[0.05] px-2 py-0.5 text-[11px] font-medium text-slate-300">
                  {symbol.toUpperCase()}
                </span>
                <span className="rounded-md border border-sky-500/20 bg-sky-500/10 px-2 py-0.5 text-[11px] font-medium text-sky-300">NSE</span>
                {stock.industry && stock.industry !== "N/A" && (
                  <span className="text-[11px] text-slate-500">{stock.industry}</span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="text-right">
              <p className="text-3xl font-black text-white">₹{stock.price}</p>
              <p className={`mt-0.5 text-sm font-semibold ${isPos ? "text-emerald-400" : "text-rose-400"}`}>
                {isPos ? "▲" : "▼"} {stock.change}
                {stock.change_abs && stock.change_abs !== "—" && (
                  <span className="ml-1 font-normal opacity-70">({stock.change_abs})</span>
                )}
              </p>
            </div>
            <button
              onClick={() => setFollowing(f => !f)}
              className={`mt-1 rounded-xl border px-4 py-2 text-sm font-medium transition ${
                following
                  ? "border-sky-500/40 bg-sky-500/15 text-sky-300"
                  : "border-white/15 bg-white/[0.03] text-slate-300 hover:border-white/25 hover:text-white"
              }`}>
              {following ? "Following ✓" : "+ Follow"}
            </button>
          </div>
        </div>

        {/* Tab nav */}
        <div className="mt-5 flex flex-wrap gap-1 border-t border-white/5 pt-4">
          {TABS.map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`rounded-lg px-3.5 py-1.5 text-[13px] font-medium transition ${
                activeTab === t ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.03]"
              }`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* ── OVERVIEW ────────────────────────────────────────────────────── */}
      {activeTab === "Overview" && (
        <div className="grid grid-cols-[1fr_260px] gap-5 items-start">
          <div className="space-y-4">
            {/* Chart */}
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
              <div className="mb-4 flex items-center justify-between">
                <span className="text-[13px] font-semibold text-white">Price Chart</span>
                <div className="flex flex-wrap gap-1">
                  {PERIODS.map(p => (
                    <button key={p} onClick={() => setPeriod(p)}
                      className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition ${
                        period === p ? "bg-sky-500/20 text-sky-300" : "text-slate-500 hover:text-slate-300"
                      }`}>
                      {p}
                    </button>
                  ))}
                </div>
              </div>
              {loadingChart
                ? <div className="flex h-48 items-center justify-center rounded-xl bg-white/[0.02]">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-sky-400"/>
                  </div>
                : chartData.length > 0
                ? <StockDetailChart data={chartData}/>
                : <div className="flex h-48 items-center justify-center rounded-xl border border-white/5 bg-white/[0.02]">
                    <p className="text-sm text-slate-500">No chart data — market may be closed or backend offline</p>
                  </div>
              }
            </div>

            {/* Intraday stats */}
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Open"       value={`₹${stock.open}`}/>
              <StatBox label="Day High"   value={`₹${stock.day_high}`}/>
              <StatBox label="Day Low"    value={`₹${stock.day_low}`}/>
              <StatBox label="Prev Close" value={`₹${stock.prev_close}`}/>
              <StatBox label="Volume"     value={stock.volume}     sub="today"/>
              <StatBox label="Avg Volume" value={stock.avg_volume} sub="3-month"/>
            </div>

            {/* Description */}
            {stock.description && (
              <div className="rounded-[20px] border border-white/8 bg-white/[0.02] p-4">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-500">About {stock.name}</p>
                <p className="text-[13px] leading-5 text-slate-300">{stock.description}</p>
              </div>
            )}
          </div>

          {/* Right sidebar */}
          <aside className="sticky top-[84px] space-y-4">
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
              <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Key Metrics</h3>
              <div className="space-y-1.5">
                <KvRow label="Market Cap"  value={stock.market_cap}/>
                <KvRow label="P/E Ratio"   value={stock.pe}/>
                <KvRow label="Forward P/E" value={stock.forward_pe}/>
                <KvRow label="P/B Ratio"   value={stock.pb}/>
                <KvRow label="EPS (TTM)"   value={stock.eps ? `₹${stock.eps}` : "—"}/>
                <KvRow label="Beta"        value={stock.beta}/>
                <KvRow label="Div Yield"   value={stock.dividend_yield}/>
                <KvRow label="52W High"    value={`₹${stock.week52_high}`}/>
                <KvRow label="52W Low"     value={`₹${stock.week52_low}`}/>
                <KvRow label="ROE"         value={stock.roe}/>
              </div>
            </div>

            {stock.analyst_count > 0 && (
              <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
                <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Analyst View</h3>
                <div className="mb-3 flex items-center gap-2">
                  <span className={`rounded-full border px-3 py-1 text-[12px] font-bold ${rec.cls}`}>{rec.label}</span>
                  <span className="text-[11px] text-slate-500">{stock.analyst_count} analysts</span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-[11px]"><span className="text-slate-500">Target Low</span><span className="font-semibold text-amber-300">{stock.target_low}</span></div>
                  <div className="flex justify-between text-[11px]"><span className="text-slate-500">Target Mean</span><span className="font-semibold text-sky-300">{stock.target_mean}</span></div>
                  <div className="flex justify-between text-[11px]"><span className="text-slate-500">Target High</span><span className="font-semibold text-emerald-300">{stock.target_high}</span></div>
                </div>
              </div>
            )}
          </aside>
        </div>
      )}

      {/* ── FINANCIALS ──────────────────────────────────────────────────── */}
      {activeTab === "Financials" && (
        <div className="grid grid-cols-2 gap-5 items-start">
          <div className="space-y-5">
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
              {stock.quarterly_revenue.length > 0
                ? <BarChart data={stock.quarterly_revenue}     label="Quarterly Revenue (₹Cr)"    colorFrom="from-sky-500/60"     colorTo="to-sky-400/30"/>
                : <p className="py-10 text-center text-sm text-slate-500">Revenue data unavailable for {symbol.toUpperCase()}</p>
              }
            </div>
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
              {stock.quarterly_net_income.length > 0
                ? <BarChart data={stock.quarterly_net_income} label="Quarterly Net Income (₹Cr)" colorFrom="from-emerald-500/60" colorTo="to-emerald-400/30"/>
                : <p className="py-10 text-center text-sm text-slate-500">Net income data unavailable</p>
              }
            </div>
          </div>

          <div className="space-y-5">
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
              <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Profit Margins</h3>
              <div className="space-y-3.5">
                <MarginBar label="Gross Margin"     value={stock.gross_margins}     color="bg-sky-500"/>
                <MarginBar label="Operating Margin" value={stock.operating_margins} color="bg-violet-500"/>
                <MarginBar label="Net Margin"       value={stock.net_margins}       color="bg-emerald-500"/>
              </div>
            </div>
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
              <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Key Ratios</h3>
              <div className="space-y-1.5">
                <KvRow label="Return on Equity" value={stock.roe}/>
                <KvRow label="Return on Assets" value={stock.roa}/>
                <KvRow label="Debt / Equity"    value={stock.debt_to_equity}/>
                <KvRow label="Current Ratio"    value={stock.current_ratio}/>
                <KvRow label="Free Cash Flow"   value={stock.free_cashflow}/>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── ANALYSIS ────────────────────────────────────────────────────── */}
      {activeTab === "Analysis" && (
        <div className="grid grid-cols-2 gap-5 items-start">
          {/* Analyst consensus */}
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
            <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Analyst Consensus</h3>
            <div className="mb-5 flex items-center gap-4">
              <div className={`flex h-16 w-16 items-center justify-center rounded-full border-2 ${rec.ring}`}>
                <span className={`h-3 w-3 rounded-full ${rec.dot}`}/>
              </div>
              <div>
                <p className={`text-2xl font-black ${rec.cls.split(" ")[0]}`}>{rec.label}</p>
                <p className="text-[12px] text-slate-500">
                  {stock.analyst_count > 0
                    ? `${stock.analyst_count} analysts covering ${symbol.toUpperCase()}`
                    : "Analyst data unavailable"}
                </p>
              </div>
            </div>
            {stock.target_mean && stock.target_mean !== "—" && (
              <>
                <p className="mb-1 text-[11px] text-slate-500">12-month price target range</p>
                <TargetBand
                  current={stock.price}
                  low={stock.target_low}
                  mean={stock.target_mean}
                  high={stock.target_high}
                />
              </>
            )}
          </div>

          {/* Shareholding */}
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
            <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Shareholding Pattern</h3>
            <div className="space-y-4 mb-5">
              <OwnershipBar label="Institutional Investors" value={stock.held_institutions} color="bg-sky-500"/>
              <OwnershipBar label="Insider Holdings"        value={stock.held_insiders}     color="bg-violet-500"/>
            </div>
            <div className="space-y-1.5 border-t border-white/5 pt-4">
              <KvRow label="P/E Ratio"   value={stock.pe}/>
              <KvRow label="Forward P/E" value={stock.forward_pe}/>
              <KvRow label="P/B Ratio"   value={stock.pb}/>
              <KvRow label="Beta"        value={stock.beta}/>
              <KvRow label="EPS (TTM)"   value={stock.eps ? `₹${stock.eps}` : "—"}/>
            </div>
          </div>
        </div>
      )}

      {/* ── EVENTS ──────────────────────────────────────────────────────── */}
      {activeTab === "Events" && (
        <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
          <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Related Events</h3>
          {stock.events.length > 0
            ? <div className="space-y-3">
                {stock.events.map((e, i) => (
                  <div key={i} className="rounded-xl border border-white/5 bg-white/[0.02] p-3.5">
                    <p className="text-[13px] font-medium text-white leading-snug">{e.title}</p>
                    <p className="mt-1 text-[11px] text-slate-500">{e.date}</p>
                  </div>
                ))}
              </div>
            : <div className="flex flex-col items-center gap-3 py-16 text-center">
                <span className="text-4xl">📋</span>
                <p className="text-sm text-slate-400">No events linked to {symbol.toUpperCase()} yet.</p>
                <Link href="/events" className="text-sm text-sky-400 hover:text-sky-300 transition">Browse all events →</Link>
              </div>
          }
        </div>
      )}

      {/* ── NEWS ────────────────────────────────────────────────────────── */}
      {activeTab === "News" && (
        <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
          <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Latest News</h3>
          {relatedNews.length > 0
            ? <div className="space-y-3">
                {relatedNews.map((a: any) => (
                  <div key={a.id} className="flex gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-3 hover:border-white/10 transition">
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium text-white line-clamp-2 leading-snug">{a.headline}</p>
                      <div className="mt-1.5 flex items-center gap-2">
                        <span className="text-[10px] text-slate-500">{a.source}</span>
                        <span className="text-[10px] text-slate-600">{a.published_at}</span>
                      </div>
                    </div>
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[11px] font-bold text-white">
                      {Math.round((a.impact_score ?? 7) * 10)}
                    </div>
                  </div>
                ))}
              </div>
            : <div className="flex flex-col items-center gap-3 py-16 text-center">
                <span className="text-4xl">📰</span>
                <p className="text-sm text-slate-400">No recent news for {symbol.toUpperCase()}.</p>
                <Link href="/news" className="text-sm text-sky-400 hover:text-sky-300 transition">Browse market news →</Link>
              </div>
          }
        </div>
      )}

      {/* ── PEERS ───────────────────────────────────────────────────────── */}
      {activeTab === "Peers" && (
        <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
          <h3 className="mb-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Peer Companies — {stock.industry}</h3>
          {stock.peers.length > 0
            ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {stock.peers.map(p => (
                  <Link key={p} href={`/stocks/${p}`}
                    className="group flex items-center gap-3 rounded-[18px] border border-white/10 bg-white/[0.03] p-4 hover:border-sky-500/30 hover:bg-sky-500/[0.04] transition">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/8 bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-xs font-bold text-slate-300">
                      {p.slice(0, 2)}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white group-hover:text-sky-300 transition truncate">{p}</p>
                      <p className="text-[11px] text-slate-500">View →</p>
                    </div>
                  </Link>
                ))}
              </div>
            : <p className="py-8 text-center text-sm text-slate-500">No peer data available.</p>
          }
        </div>
      )}

      {/* ── CHART ───────────────────────────────────────────────────────── */}
      {activeTab === "Chart" && (
        <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            {PERIODS.map(p => (
              <button key={p} onClick={() => setPeriod(p)}
                className={`rounded-lg px-3 py-1.5 text-[12px] font-medium transition ${
                  period === p ? "bg-sky-500/20 text-sky-300" : "text-slate-500 hover:text-slate-300"
                }`}>
                {p}
              </button>
            ))}
          </div>
          {loadingChart
            ? <div className="flex h-72 items-center justify-center">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-sky-400"/>
              </div>
            : chartData.length > 0
            ? <StockDetailChart data={chartData}/>
            : <div className="flex h-72 items-center justify-center text-sm text-slate-500">No chart data available</div>
          }
        </div>
      )}
    </main>
  );
}
