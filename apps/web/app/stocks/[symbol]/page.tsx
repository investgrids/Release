"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { StockDetailChart } from "@/components/StockDetailChart";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const TABS = ["Overview", "Financials", "Analysis", "Events", "News", "Peers", "Chart"];

const PERIODS = ["1D", "1W", "1M", "6M", "1Y", "3Y", "5Y", "Max"];

const COMPANY_ABBR: Record<string, string> = {
  RELIANCE: "RIL", HDFCBANK: "HDFC", INFY: "INFY", TCS: "TCS",
  WIPRO: "WIP", TATASTEEL: "TATA", RVNL: "RVNL", L_T: "L&T", BEL: "BEL",
};

interface PageProps {
  params: Promise<{ symbol: string }>;
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.03] p-3 text-center">
      <p className="text-[10px] uppercase tracking-widest text-slate-500">{label}</p>
      <p className="mt-1 text-[13px] font-bold text-white">{value || "—"}</p>
    </div>
  );
}

export default function StockPage({ params }: PageProps) {
  const { symbol } = use(params);
  const [stock, setStock]   = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("Overview");
  const [period, setPeriod] = useState("6M");
  const [following, setFollowing] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/stocks/${symbol}`, { cache: "no-store" })
      .then(r => r.ok ? r.json() : null)
      .then(setStock)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) {
    return (
      <main className="min-w-0 pb-10">
        <div className="h-32 animate-pulse rounded-[24px] border border-white/8 bg-white/[0.02] mb-4"/>
        <div className="h-72 animate-pulse rounded-[24px] border border-white/8 bg-white/[0.02]"/>
      </main>
    );
  }

  if (!stock) {
    return (
      <main className="min-w-0 flex flex-col items-center justify-center gap-4 py-24 text-center">
        <span className="text-5xl">📉</span>
        <h1 className="text-2xl font-semibold text-white">{symbol.toUpperCase()} not found</h1>
        <p className="text-slate-400">This symbol may not be listed on NSE, or the backend is offline.</p>
        <Link href="/stocks" className="mt-2 rounded-full bg-sky-500/15 px-5 py-2 text-sm text-sky-300 hover:bg-sky-500/25">
          ← Back to Explorer
        </Link>
      </main>
    );
  }

  const isPos = !String(stock.change ?? "").startsWith("-");

  return (
    <main className="min-w-0 space-y-5 pb-10">
      {/* Back */}
      <Link href="/stocks" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 transition">
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/>
        </svg>
        Stocks
      </Link>

      {/* Header card */}
      <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
        <div className="flex items-start justify-between gap-4">
          {/* Company info */}
          <div className="flex items-center gap-4">
            {/* Logo placeholder */}
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500/20 to-blue-500/10 border border-sky-500/20 text-sm font-bold text-sky-300">
              {symbol.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">{stock.name ?? `${symbol.toUpperCase()} Ltd.`}</h1>
              <div className="mt-1 flex items-center gap-2">
                <span className="rounded-md border border-white/10 bg-white/[0.05] px-2 py-0.5 text-[11px] font-medium text-slate-300">
                  {symbol.toUpperCase()}
                </span>
                <span className="rounded-md border border-sky-500/20 bg-sky-500/10 px-2 py-0.5 text-[11px] font-medium text-sky-300">
                  NSE
                </span>
                {stock.industry && (
                  <span className="text-[11px] text-slate-500">{stock.industry}</span>
                )}
              </div>
            </div>
          </div>
          {/* Price + follow */}
          <div className="flex items-start gap-4">
            <div className="text-right">
              <p className="text-2xl font-black text-white">₹{stock.price ?? "—"}</p>
              <p className={`mt-0.5 text-[13px] font-semibold ${isPos ? "text-emerald-400" : "text-rose-400"}`}>
                {isPos ? "▲" : "▼"} {stock.change}
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
        <div className="mt-5 flex gap-1 border-t border-white/5 pt-4">
          {TABS.map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`rounded-lg px-3.5 py-1.5 text-[13px] font-medium transition ${
                activeTab === t
                  ? "bg-white/10 text-white"
                  : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.03]"
              }`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      {activeTab === "Overview" && (
        <div className="grid grid-cols-[1fr_240px] gap-5 items-start">
          {/* Chart area */}
          <div className="space-y-4">
            {/* Chart card */}
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
              {/* Period selector */}
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <span className="text-[13px] font-semibold text-white">Price Chart</span>
                  <span className="ml-2 text-[11px] text-slate-500">via yfinance · 15-min delayed</span>
                </div>
                <div className="flex gap-1">
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

              {stock.chart_data?.length > 0 ? (
                <StockDetailChart data={stock.chart_data}/>
              ) : (
                <div className="flex h-48 items-center justify-center rounded-xl bg-white/[0.03] border border-white/5">
                  <p className="text-sm text-slate-500">No chart data available</p>
                </div>
              )}
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-3 gap-3">
              <StatBox label="Open"       value={`₹${stock.open ?? stock.price ?? "—"}`}/>
              <StatBox label="52W High"   value={`₹${stock.high_52w ?? "—"}`}/>
              <StatBox label="52W Low"    value={`₹${stock.low_52w ?? "—"}`}/>
              <StatBox label="Prev Close" value={`₹${stock.prev_close ?? "—"}`}/>
              <StatBox label="P/E Ratio"  value={String(stock.pe ?? "—")}/>
              <StatBox label="Market Cap" value={stock.market_cap ?? "—"}/>
            </div>

            {/* AI Analysis */}
            <div className="rounded-[20px] border border-violet-500/20 bg-violet-500/[0.04] p-4 backdrop-blur-xl">
              <div className="mb-2 flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-500/20 text-xs">✦</span>
                <h3 className="text-sm font-semibold text-white">AI Analysis</h3>
              </div>
              <p className="text-[13px] leading-5 text-slate-300">
                {stock.ai_analysis ?? `Strong fundamentals with robust sectoral positioning. ${symbol.toUpperCase()} continues to show resilient earnings with consistent quarterly growth. Long-term outlook remains positive given the macro tailwinds in the ${stock.industry ?? "sector"}.`}
              </p>
              <button className="mt-3 text-[12px] font-medium text-violet-400 hover:text-violet-300 transition">
                View Full Analysis →
              </button>
            </div>
          </div>

          {/* Key Info sidebar */}
          <aside className="sticky top-[84px] space-y-4">
            <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
              <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Key Info</h3>
              <div className="space-y-2.5">
                {[
                  { label: "Market Cap",  value: stock.market_cap ?? "—"         },
                  { label: "P/E Ratio",   value: stock.pe         ?? "—"         },
                  { label: "P/B Ratio",   value: stock.pb         ?? "—"         },
                  { label: "ROE",         value: stock.roe        ?? "—"         },
                  { label: "Industry",    value: stock.industry   ?? "—"         },
                  { label: "52W High",    value: `₹${stock.high_52w ?? "—"}`    },
                  { label: "52W Low",     value: `₹${stock.low_52w  ?? "—"}`    },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between gap-2 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
                    <span className="text-[12px] text-slate-500">{label}</span>
                    <span className="text-[12px] font-semibold text-white text-right truncate">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Events */}
            {stock.events?.length > 0 && (
              <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
                <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Related Events</h3>
                <div className="space-y-2">
                  {stock.events.slice(0, 3).map((e: any, i: number) => (
                    <div key={i} className="rounded-xl border border-white/5 bg-white/[0.02] p-2.5">
                      <p className="text-[12px] font-medium text-white leading-snug">{e.title}</p>
                      <p className="mt-0.5 text-[10px] text-slate-500">{e.date}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Peers */}
            {stock.peers?.length > 0 && (
              <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
                <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Peers</h3>
                <div className="flex flex-wrap gap-1.5">
                  {stock.peers.map((p: string) => (
                    <Link key={p} href={`/stocks/${p}`}
                      className="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] text-slate-300 hover:border-sky-500/30 hover:text-sky-300 transition">
                      {p}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </aside>
        </div>
      )}

      {activeTab === "Chart" && (
        <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur-xl">
          <div className="mb-4 flex items-center gap-2">
            {PERIODS.map(p => (
              <button key={p} onClick={() => setPeriod(p)}
                className={`rounded-lg px-3 py-1.5 text-[12px] font-medium transition ${
                  period === p ? "bg-sky-500/20 text-sky-300" : "text-slate-500 hover:text-slate-300"
                }`}>
                {p}
              </button>
            ))}
          </div>
          {stock.chart_data?.length > 0
            ? <StockDetailChart data={stock.chart_data}/>
            : <div className="flex h-64 items-center justify-center text-sm text-slate-500">No chart data available</div>
          }
        </div>
      )}

      {(activeTab === "Financials" || activeTab === "Analysis" || activeTab === "Events" || activeTab === "News" || activeTab === "Peers") && (
        <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-8 text-center backdrop-blur-xl">
          <p className="text-4xl mb-3">📊</p>
          <p className="text-base font-semibold text-white">{activeTab}</p>
          <p className="mt-1 text-sm text-slate-400">Connect a financial data API (Upstox, Kite Connect) for live {activeTab.toLowerCase()} data.</p>
        </div>
      )}
    </main>
  );
}
