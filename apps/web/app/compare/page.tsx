"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const ALL_SYMBOLS = [
  { symbol: "INFY",      name: "Infosys",                   sector: "IT"       },
  { symbol: "TCS",       name: "Tata Consultancy Services", sector: "IT"       },
  { symbol: "HDFCBANK",  name: "HDFC Bank",                 sector: "Banking"  },
  { symbol: "RELIANCE",  name: "Reliance Industries",       sector: "Energy"   },
  { symbol: "BEL",       name: "Bharat Electronics",        sector: "Defence"  },
  { symbol: "WIPRO",     name: "Wipro",                     sector: "IT"       },
];

interface CompanyData {
  symbol: string;
  name: string;
  sector: string;
  price: string;
  revenue: string;
  profit: string;
  roe: number;
  debtEquity: number;
  pe: number;
  pb: number;
  loading?: boolean;
}

const METRICS = ["Price", "Revenue", "Profit", "ROE %", "D/E Ratio", "P/E", "P/B"];

const SECTOR_COLORS: Record<string, string> = {
  IT:      "border-sky-500/20 bg-sky-500/10 text-sky-300",
  Banking: "border-indigo-500/20 bg-indigo-500/10 text-indigo-300",
  Energy:  "border-amber-500/20 bg-amber-500/10 text-amber-300",
  Defence: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
};

function parseNumStr(s: string): number {
  if (!s || s === "—") return 0;
  const clean = s.replace(/[₹,%×x\s]/g, "");
  const m = clean.match(/^([\d.]+)([BMKbmk]?)$/);
  if (!m) return parseFloat(clean) || 0;
  const n = parseFloat(m[1]);
  const sfx = m[2]?.toUpperCase();
  if (sfx === "B") return n;
  if (sfx === "M") return n / 1000;
  if (sfx === "K") return n / 1_000_000;
  return n;
}

function metricValue(c: CompanyData, m: string): string {
  switch (m) {
    case "Price":    return c.price || "—";
    case "Revenue":  return c.revenue;
    case "Profit":   return c.profit;
    case "ROE %":    return c.roe ? `${c.roe.toFixed(1)}%` : "—";
    case "D/E Ratio":return c.debtEquity ? c.debtEquity.toFixed(2) : "—";
    case "P/E":      return c.pe ? c.pe.toFixed(1) : "—";
    case "P/B":      return c.pb ? c.pb.toFixed(1) : "—";
    default:         return "—";
  }
}

function barWidth(c: CompanyData, m: string, all: CompanyData[]): number {
  const val = (x: CompanyData) => {
    switch (m) {
      case "Price":    return parseNumStr(x.price);
      case "Revenue":  return parseNumStr(x.revenue);
      case "Profit":   return parseNumStr(x.profit);
      case "ROE %":    return x.roe;
      case "D/E Ratio":return x.debtEquity;
      case "P/E":      return x.pe;
      case "P/B":      return x.pb;
      default:         return 0;
    }
  };
  const vals = all.map(val);
  const max = Math.max(...vals);
  return max > 0 ? (val(c) / max) * 100 : 0;
}

export default function ComparePage() {
  const [selected, setSelected] = useState<string[]>(["INFY", "TCS"]);
  const [hoveredMetric, setHoveredMetric] = useState<string | null>(null);
  const [liveData, setLiveData] = useState<Record<string, CompanyData>>({});

  useEffect(() => {
    selected.forEach(sym => {
      if (liveData[sym]?.price) return; // already fetched
      setLiveData(prev => ({ ...prev, [sym]: { ...buildFallback(sym), loading: true } }));
      fetch(`${API}/api/stocks/${sym}`)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (!data) return;
          const base = ALL_SYMBOLS.find(s => s.symbol === sym)!;
          setLiveData(prev => ({
            ...prev,
            [sym]: {
              symbol: sym,
              name: data.name || base.name,
              sector: data.sector || base.sector,
              price: data.price || "—",
              revenue: data.revenue || "—",
              profit: data.profit || "—",
              roe: parseNumStr(data.roe),
              debtEquity: parseNumStr(data.debt_to_equity),
              pe: parseNumStr(data.pe_ratio),
              pb: parseNumStr(data.pb_ratio),
              loading: false,
            }
          }));
        })
        .catch(() => {
          setLiveData(prev => ({ ...prev, [sym]: { ...buildFallback(sym), loading: false } }));
        });
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  function buildFallback(sym: string): CompanyData {
    const meta = ALL_SYMBOLS.find(s => s.symbol === sym) ?? { symbol: sym, name: sym, sector: "General" };
    return { symbol: sym, name: meta.name, sector: meta.sector, price: "—", revenue: "—", profit: "—", roe: 0, debtEquity: 0, pe: 0, pb: 0 };
  }

  function toggle(sym: string) {
    setSelected(prev =>
      prev.includes(sym)
        ? prev.filter(s => s !== sym)
        : prev.length < 4 ? [...prev, sym] : prev
    );
  }

  const companies = selected.map(sym => liveData[sym] ?? buildFallback(sym));
  const hasLive = companies.some(c => c.price !== "—");

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
          {ALL_SYMBOLS.map((c) => {
            const active = selected.includes(c.symbol);
            const isLoading = liveData[c.symbol]?.loading;
            return (
              <button key={c.symbol} onClick={() => toggle(c.symbol)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                  active
                    ? "border-sky-500/40 bg-sky-500/15 text-sky-300"
                    : "border-white/10 bg-white/5 text-slate-400 hover:border-white/20 hover:text-white"
                }`}>
                {c.symbol}
                {active && (isLoading ? <span className="ml-1.5 opacity-60">...</span> : <span className="ml-1.5">✓</span>)}
              </button>
            );
          })}
        </div>
      </div>

      {/* Comparison table */}
      {companies.length > 0 ? (
        <div className="rounded-[24px] border border-white/10 bg-white/[0.03] shadow-glow backdrop-blur-xl overflow-hidden">
          {/* Header row */}
          <div className="grid border-b border-white/10 bg-white/[0.02]"
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
                    <span className="text-sm font-semibold text-white">
                      {c.loading ? <span className="opacity-40">…</span> : metricValue(c, metric)}
                    </span>
                    {w > 0 && (
                      <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/5">
                        <div className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500 transition-all duration-500"
                          style={{ width: `${w}%` }} />
                      </div>
                    )}
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

      {!hasLive && (
        <div className="rounded-[20px] border border-amber-500/20 bg-amber-500/[0.04] p-4">
          <p className="text-xs text-amber-300">
            Fetching live data from market… Values will update shortly.
          </p>
        </div>
      )}
    </main>
  );
}
