"use client";

import { useState } from "react";
import Link from "next/link";

const ALL_COMPANIES = [
  { symbol: "INFY",      name: "Infosys",                   revenue: "18.5B", profit: "3.2B", roe: 28, debtEquity: 0.15, pe: 24.8, pb: 7.1,  sector: "IT"        },
  { symbol: "TCS",       name: "Tata Consultancy Services", revenue: "27.1B", profit: "5.0B", roe: 35, debtEquity: 0.02, pe: 29.4, pb: 10.5, sector: "IT"        },
  { symbol: "HDFCBANK",  name: "HDFC Bank",                 revenue: "24.6B", profit: "6.1B", roe: 16, debtEquity: 7.20, pe: 18.2, pb: 2.8,  sector: "Banking"   },
  { symbol: "RELIANCE",  name: "Reliance Industries",       revenue: "88.3B", profit: "8.9B", roe: 11, debtEquity: 0.38, pe: 28.1, pb: 2.4,  sector: "Energy"    },
  { symbol: "BEL",       name: "Bharat Electronics",        revenue: "2.9B",  profit: "0.6B", roe: 22, debtEquity: 0.05, pe: 44.1, pb: 9.2,  sector: "Defence"   },
  { symbol: "WIPRO",     name: "Wipro",                     revenue: "10.8B", profit: "1.3B", roe: 15, debtEquity: 0.08, pe: 21.5, pb: 3.2,  sector: "IT"        },
];

const METRICS = ["Revenue", "Profit", "ROE %", "D/E Ratio", "P/E", "P/B"];

function metricValue(c: typeof ALL_COMPANIES[0], m: string) {
  switch (m) {
    case "Revenue":  return c.revenue;
    case "Profit":   return c.profit;
    case "ROE %":    return `${c.roe}%`;
    case "D/E Ratio":return c.debtEquity.toFixed(2);
    case "P/E":      return c.pe.toFixed(1);
    case "P/B":      return c.pb.toFixed(1);
    default:         return "—";
  }
}

function barWidth(c: typeof ALL_COMPANIES[0], m: string, all: typeof ALL_COMPANIES) {
  const val = (company: typeof c) => {
    switch (m) {
      case "Revenue":  return parseFloat(company.revenue);
      case "Profit":   return parseFloat(company.profit);
      case "ROE %":    return company.roe;
      case "D/E Ratio":return company.debtEquity;
      case "P/E":      return company.pe;
      case "P/B":      return company.pb;
      default:         return 0;
    }
  };
  const vals = all.map(val);
  const max = Math.max(...vals);
  return max > 0 ? (val(c) / max) * 100 : 0;
}

const SECTOR_COLORS: Record<string, string> = {
  IT:      "border-sky-500/20 bg-sky-500/10 text-sky-300",
  Banking: "border-indigo-500/20 bg-indigo-500/10 text-indigo-300",
  Energy:  "border-amber-500/20 bg-amber-500/10 text-amber-300",
  Defence: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
};

export default function ComparePage() {
  const [selected, setSelected] = useState<string[]>(["INFY", "TCS"]);
  const [hoveredMetric, setHoveredMetric] = useState<string | null>(null);

  const companies = ALL_COMPANIES.filter((c) => selected.includes(c.symbol));

  function toggle(sym: string) {
    setSelected((prev) =>
      prev.includes(sym)
        ? prev.filter((s) => s !== sym)
        : prev.length < 4 ? [...prev, sym] : prev
    );
  }

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Research</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Compare Companies</h1>
        <p className="mt-1 text-sm text-slate-400">Side-by-side financial scorecard for up to 4 companies.</p>
      </div>

      {/* Company selector */}
      <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl">
        <p className="mb-3 text-[10px] uppercase tracking-widest text-slate-500">Select companies (max 4)</p>
        <div className="flex flex-wrap gap-2">
          {ALL_COMPANIES.map((c) => {
            const active = selected.includes(c.symbol);
            return (
              <button key={c.symbol} onClick={() => toggle(c.symbol)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                  active
                    ? "border-sky-500/40 bg-sky-500/15 text-sky-300"
                    : "border-white/10 bg-white/5 text-slate-400 hover:border-white/20 hover:text-white"
                }`}>
                {c.symbol}
                {active && <span className="ml-1.5">✓</span>}
              </button>
            );
          })}
        </div>
      </div>

      {/* Comparison table */}
      {companies.length > 0 ? (
        <div className="rounded-[24px] border border-white/10 bg-white/[0.03] shadow-glow backdrop-blur-xl overflow-hidden">
          {/* Header row */}
          <div className={`grid border-b border-white/10 bg-white/[0.02]`}
            style={{ gridTemplateColumns: `180px repeat(${companies.length}, 1fr)` }}>
            <div className="p-4" />
            {companies.map((c) => (
              <div key={c.symbol} className="p-4">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-xs font-bold text-slate-300">
                    {c.symbol.slice(0, 2)}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{c.symbol}</p>
                    <p className="text-[10px] text-slate-500 truncate max-w-[100px]">{c.name}</p>
                  </div>
                </div>
                <div className="mt-2">
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${SECTOR_COLORS[c.sector] ?? "border-white/10 bg-white/5 text-slate-300"}`}>
                    {c.sector}
                  </span>
                </div>
                <Link href={`/stocks/${c.symbol}`}
                  className="mt-2 block text-[10px] text-sky-400 hover:text-sky-300">
                  View stock →
                </Link>
              </div>
            ))}
          </div>

          {/* Metric rows */}
          {METRICS.map((metric) => (
            <div key={metric}
              onMouseEnter={() => setHoveredMetric(metric)}
              onMouseLeave={() => setHoveredMetric(null)}
              className={`grid border-b border-white/5 transition ${hoveredMetric === metric ? "bg-white/[0.02]" : ""}`}
              style={{ gridTemplateColumns: `180px repeat(${companies.length}, 1fr)` }}>
              <div className="flex items-center px-4 py-3">
                <span className="text-xs text-slate-500">{metric}</span>
              </div>
              {companies.map((c) => {
                const w = barWidth(c, metric, companies);
                return (
                  <div key={c.symbol} className="flex flex-col justify-center px-4 py-3">
                    <span className="text-sm font-semibold text-white">{metricValue(c, metric)}</span>
                    <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/5">
                      <div className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500 transition-all duration-500"
                        style={{ width: `${w}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20">
          <p className="text-slate-500">Select at least one company to compare.</p>
        </div>
      )}

      <div className="rounded-[20px] border border-amber-500/20 bg-amber-500/[0.04] p-4">
        <p className="text-xs text-amber-300">
          📊 <strong>Live financial data</strong> requires <strong>Screener.in API</strong>,{" "}
          <strong>NSE Financial Results API</strong>, or <strong>Alpha Vantage Fundamentals API</strong>.
          Values shown are illustrative.
        </p>
      </div>
    </main>
  );
}
