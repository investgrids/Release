"use client";

import { useState, useTransition } from "react";
import Link from "next/link";

const SAMPLE_EVENTS = [
  { id: "s1", title: "RBI holds repo rate at 6.5%, signals easing bias", category: "RBI",        impact: 8.8, sectors: ["Banking", "NBFC"] },
  { id: "s2", title: "Govt approves ₹75,000 Cr railway expansion plan",  category: "Government", impact: 9.2, sectors: ["Infra", "Capital Goods"] },
  { id: "s3", title: "India-US semiconductor partnership expanded",        category: "Policy",     impact: 7.5, sectors: ["Technology", "Defence"] },
  { id: "s4", title: "Defence budget increased by 12%",                   category: "Government", impact: 9.0, sectors: ["Defence", "Aerospace"] },
  { id: "s5", title: "India Q4 GDP growth beats estimates at 7.8%",       category: "Macro",      impact: 8.5, sectors: ["All Sectors"] },
  { id: "s6", title: "FII net buyers for 5th consecutive session",        category: "Global",     impact: 7.0, sectors: ["Equity"] },
  { id: "s7", title: "SEBI tightens F&O margin norms",                    category: "Policy",     impact: 6.5, sectors: ["Derivatives", "Broking"] },
  { id: "s8", title: "Semiconductor PLI scheme incentives approved",      category: "Government", impact: 8.0, sectors: ["Electronics", "Tech"] },
];

const STOCKS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "LT", "ICICIBANK", "BEL", "HAL", "WIPRO", "SUNPHARMA"];

const CAT_COLORS: Record<string, string> = {
  Government: "border-violet-500/20 bg-violet-500/10 text-violet-300",
  Policy:     "border-sky-500/20 bg-sky-500/10 text-sky-300",
  Macro:      "border-amber-500/20 bg-amber-500/10 text-amber-300",
  Global:     "border-slate-500/20 bg-slate-500/10 text-slate-300",
  RBI:        "border-indigo-500/20 bg-indigo-500/10 text-indigo-300",
};

function impactColor(score: number) {
  if (score >= 9) return "text-emerald-400";
  if (score >= 7) return "text-sky-400";
  return "text-amber-400";
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [, startTransition] = useTransition();
  const [active, setActive] = useState("Events");

  const q = query.trim().toLowerCase();

  const filteredEvents = q
    ? SAMPLE_EVENTS.filter((e) =>
        e.title.toLowerCase().includes(q) ||
        e.category.toLowerCase().includes(q) ||
        e.sectors.some((s) => s.toLowerCase().includes(q))
      )
    : SAMPLE_EVENTS;

  const filteredStocks = q
    ? STOCKS.filter((s) => s.toLowerCase().includes(q))
    : STOCKS;

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Search</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Event Explorer</h1>
        <p className="mt-1 text-sm text-slate-400">Search across events, stocks, themes, and policy signals.</p>
      </div>

      {/* Search bar */}
      <div className="relative">
        <div className="flex items-center overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] shadow-glow backdrop-blur-xl transition focus-within:border-sky-500/40 focus-within:bg-sky-500/[0.02]">
          <span className="pl-5 text-slate-500">🔍</span>
          <input
            type="text"
            value={query}
            onChange={(e) => startTransition(() => setQuery(e.target.value))}
            placeholder="Search events, stocks, sectors, themes…"
            className="flex-1 bg-transparent px-4 py-4 text-sm text-white outline-none placeholder:text-slate-500"
          />
          {query && (
            <button onClick={() => setQuery("")}
              className="mr-2 rounded-xl bg-white/5 px-3 py-1.5 text-xs text-slate-400 hover:text-white transition">
              ✕ Clear
            </button>
          )}
        </div>
      </div>

      {/* Category tabs */}
      <div className="flex gap-2">
        {["Events", "Stocks"].map((tab) => (
          <button key={tab} onClick={() => setActive(tab)}
            className={`rounded-full border px-4 py-1.5 text-xs font-medium transition ${
              active === tab
                ? "border-sky-500/30 bg-sky-500/10 text-sky-300"
                : "border-white/10 bg-white/5 text-slate-400 hover:text-white"
            }`}>
            {tab}
          </button>
        ))}
      </div>

      {/* Events results */}
      {active === "Events" && (
        <div>
          <p className="mb-3 text-[10px] uppercase tracking-widest text-slate-500">
            {q ? `${filteredEvents.length} result${filteredEvents.length !== 1 ? "s" : ""} for "${query}"` : "All events"}
          </p>
          <div className="space-y-3">
            {filteredEvents.map((e) => (
              <article key={e.id}
                className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4 shadow-glow backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-white/20">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${CAT_COLORS[e.category] ?? "border-white/10 bg-white/5 text-slate-300"}`}>
                    {e.category}
                  </span>
                  <span className={`text-[11px] font-semibold ${impactColor(e.impact)}`}>
                    Impact {e.impact.toFixed(1)}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium text-white">{e.title}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {e.sectors.map((s) => (
                    <span key={s} className="rounded-full border border-white/8 bg-white/5 px-2 py-0.5 text-[10px] text-slate-500">{s}</span>
                  ))}
                </div>
              </article>
            ))}
          </div>
          {filteredEvents.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-16 text-center">
              <span className="text-3xl">🔍</span>
              <p className="text-sm text-slate-400">No events found for &quot;{query}&quot;</p>
              <p className="text-xs text-slate-600">Try: RBI, defence, PMI, semiconductor</p>
            </div>
          )}
        </div>
      )}

      {/* Stocks results */}
      {active === "Stocks" && (
        <div>
          <p className="mb-3 text-[10px] uppercase tracking-widest text-slate-500">
            {q ? `${filteredStocks.length} stock${filteredStocks.length !== 1 ? "s" : ""} for "${query}"` : "Popular stocks"}
          </p>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {filteredStocks.map((symbol) => (
              <Link key={symbol} href={`/stocks/${symbol}`}
                className="group flex items-center gap-3 rounded-[18px] border border-white/10 bg-white/[0.03] p-4 shadow-glow backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-white/20">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-xs font-bold text-slate-300">
                  {symbol.slice(0, 2)}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-white group-hover:text-sky-300">{symbol}</p>
                  <p className="text-[11px] text-slate-500">NSE · View stock detail</p>
                </div>
                <span className="text-[11px] text-slate-600 group-hover:text-slate-400">→</span>
              </Link>
            ))}
          </div>
          {filteredStocks.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-16 text-center">
              <span className="text-3xl">📉</span>
              <p className="text-sm text-slate-400">No stocks matched &quot;{query}&quot;</p>
              <p className="text-xs text-slate-600">Try: RELIANCE, TCS, INFY, BEL</p>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
