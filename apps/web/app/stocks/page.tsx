"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const POPULAR = [
  { symbol: "RELIANCE",  name: "Reliance Industries",       sector: "Energy",       change: "+2.4%",  positive: true  },
  { symbol: "TCS",       name: "Tata Consultancy Services", sector: "IT",           change: "-0.9%",  positive: false },
  { symbol: "HDFCBANK",  name: "HDFC Bank",                 sector: "Banking",      change: "+1.2%",  positive: true  },
  { symbol: "INFY",      name: "Infosys",                   sector: "IT",           change: "-1.1%",  positive: false },
  { symbol: "LT",        name: "Larsen & Toubro",           sector: "Infra",        change: "+3.1%",  positive: true  },
  { symbol: "ICICIBANK", name: "ICICI Bank",                sector: "Banking",      change: "+1.5%",  positive: true  },
  { symbol: "BEL",       name: "Bharat Electronics",        sector: "Defence",      change: "+6.3%",  positive: true  },
  { symbol: "HAL",       name: "Hindustan Aeronautics",     sector: "Defence",      change: "+4.8%",  positive: true  },
  { symbol: "ADANIGREEN",name: "Adani Green Energy",        sector: "Energy",       change: "+2.1%",  positive: true  },
  { symbol: "TATAMOTORS",name: "Tata Motors",               sector: "Auto",         change: "+1.4%",  positive: true  },
  { symbol: "SUNPHARMA", name: "Sun Pharmaceutical",        sector: "Pharma",       change: "+0.6%",  positive: true  },
  { symbol: "WIPRO",     name: "Wipro",                     sector: "IT",           change: "-2.0%",  positive: false },
];

const TRENDING = ["BEL", "HAL", "ADANIGREEN", "RELIANCE", "HDFCBANK", "LT", "NTPC", "BHARATFORG"];

export default function StocksPage() {
  const [query, setQuery] = useState("");
  const router = useRouter();

  const filtered = query.trim()
    ? POPULAR.filter(
        (s) =>
          s.symbol.toLowerCase().includes(query.toLowerCase()) ||
          s.name.toLowerCase().includes(query.toLowerCase()) ||
          s.sector.toLowerCase().includes(query.toLowerCase())
      )
    : POPULAR;

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim().toUpperCase();
    if (q) router.push(`/stocks/${q}`);
  }

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Research</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Event Explorer</h1>
        <p className="mt-1 text-sm text-slate-400">Search any NSE stock to explore its events, news, and financial context.</p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="relative">
        <div className="flex items-center overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] shadow-glow backdrop-blur-xl transition focus-within:border-sky-500/40 focus-within:bg-sky-500/[0.02]">
          <span className="pl-5 text-slate-500">🔍</span>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by symbol, company name, or sector…"
            className="flex-1 bg-transparent px-4 py-4 text-sm text-white outline-none placeholder:text-slate-500"
          />
          {query && (
            <button type="submit"
              className="mr-2 rounded-xl bg-sky-500/20 px-4 py-2 text-xs font-semibold text-sky-300 transition hover:bg-sky-500/30">
              Go →
            </button>
          )}
        </div>
      </form>

      {/* Trending chips */}
      <div>
        <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Trending searches</p>
        <div className="flex flex-wrap gap-2">
          {TRENDING.map((s) => (
            <Link key={s} href={`/stocks/${s}`}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300 transition hover:border-sky-500/30 hover:bg-sky-500/10 hover:text-sky-300">
              {s}
            </Link>
          ))}
        </div>
      </div>

      {/* Stock grid */}
      <div>
        <p className="mb-3 text-[10px] uppercase tracking-widest text-slate-500">
          {query ? `${filtered.length} result${filtered.length !== 1 ? "s" : ""}` : "Popular stocks"}
        </p>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((s) => (
            <Link key={s.symbol} href={`/stocks/${s.symbol}`}
              className="group rounded-[18px] border border-white/10 bg-white/[0.03] p-4 shadow-glow backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-white/20">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-xs font-bold text-slate-300">
                    {s.symbol.slice(0, 2)}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white group-hover:text-sky-300">{s.symbol}</p>
                    <p className="truncate text-[11px] text-slate-500">{s.name}</p>
                  </div>
                </div>
                <span className={`shrink-0 text-sm font-medium ${s.positive ? "text-emerald-400" : "text-rose-400"}`}>
                  {s.change}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <span className="rounded-full border border-white/8 bg-white/5 px-2 py-0.5 text-[10px] text-slate-500">{s.sector}</span>
                <span className="text-[11px] text-slate-600 group-hover:text-slate-400">View →</span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {filtered.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-[20px] border border-white/10 bg-white/[0.03] py-16 text-center">
          <span className="text-3xl">🔍</span>
          <p className="text-sm text-slate-400">No stocks found for &quot;{query}&quot;</p>
          <p className="text-xs text-slate-600">Try searching by NSE ticker symbol, e.g. INFY, TCS, RELIANCE</p>
        </div>
      )}

      <p className="text-center text-[11px] text-slate-600">
        Stock prices are illustrative · Real-time data requires{" "}
        <span className="text-slate-500">NSE Live API / Upstox / Zerodha Kite Connect</span>
      </p>
    </main>
  );
}
