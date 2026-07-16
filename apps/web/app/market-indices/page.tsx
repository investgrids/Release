"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { MarketContextStrip } from "@/components/MarketContextStrip";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface IndexQuote {
  name: string; ticker: string; value: string; change: string;
  pct: number; positive: boolean; high: string; low: string;
  chart: { label: string; value: number }[];
}

// Plain-English context for each index
const INDEX_CONTEXT: Record<string, { desc: string; group: string }> = {
  "NIFTY 50":     { desc: "India's 50 largest companies",          group: "main" },
  "SENSEX":       { desc: "BSE's top 30 companies",                group: "main" },
  "INDIA VIX":    { desc: "Market nervousness — lower is calmer",  group: "vix"  },
  "BANK NIFTY":   { desc: "Banking sector (HDFC, ICICI, SBI...)",  group: "sector" },
  "NIFTY IT":     { desc: "Technology sector (TCS, Infosys...)",   group: "sector" },
  "NIFTY FMCG":   { desc: "Consumer brands (HUL, Nestle...)",      group: "sector" },
  "NIFTY PHARMA": { desc: "Pharmaceuticals sector",                group: "sector" },
  "NIFTY AUTO":   { desc: "Automobiles sector (M&M, Maruti...)",   group: "sector" },
  "NIFTY INFRA":  { desc: "Infrastructure and construction",       group: "sector" },
  "NIFTY METAL":  { desc: "Steel, aluminium, mining",              group: "sector" },
  "NIFTY REALTY": { desc: "Real estate developers",                group: "sector" },
  "NIFTY ENERGY": { desc: "Oil, gas, and power companies",         group: "sector" },
};

const FALLBACK: IndexQuote[] = [
  { name: "NIFTY 50",     ticker: "^NSEI",         value: "24,056", change: "+42.85 (+0.18%)", pct: 0.18,  positive: true,  high: "24,104", low: "24,008", chart: [] },
  { name: "SENSEX",       ticker: "^BSESN",        value: "77,100", change: "+109.47 (+0.14%)",pct: 0.14,  positive: true,  high: "77,254", low: "76,946", chart: [] },
  { name: "BANK NIFTY",   ticker: "^NSEBANK",      value: "58,177", change: "+4.35 (+0.01%)",  pct: 0.01,  positive: true,  high: "58,293", low: "58,061", chart: [] },
  { name: "NIFTY IT",     ticker: "^CNXIT",        value: "38,421", change: "-182.4 (-0.47%)", pct: -0.47, positive: false, high: "38,680", low: "38,210", chart: [] },
  { name: "INDIA VIX",    ticker: "^INDIAVIX",     value: "14.25",  change: "-0.32 (-2.19%)",  pct: -2.19, positive: false, high: "14.89",  low: "14.10",  chart: [] },
  { name: "NIFTY FMCG",   ticker: "NIFTYFMCG.NS",  value: "54,230", change: "+215.8 (+0.40%)", pct: 0.40,  positive: true,  high: "54,412", low: "53,980", chart: [] },
  { name: "NIFTY PHARMA", ticker: "NIFTYPHARMA.NS", value: "18,840", change: "+124.5 (+0.67%)", pct: 0.67,  positive: true,  high: "18,960", low: "18,710", chart: [] },
  { name: "NIFTY AUTO",   ticker: "NIFTYAUTO.NS",  value: "23,710", change: "+342.1 (+1.46%)", pct: 1.46,  positive: true,  high: "23,820", low: "23,340", chart: [] },
  { name: "NIFTY INFRA",  ticker: "NIFTYINFRA.NS", value: "8,940",  change: "+112.3 (+1.27%)", pct: 1.27,  positive: true,  high: "8,980",  low: "8,810",  chart: [] },
  { name: "NIFTY METAL",  ticker: "NIFTYMETAL.NS", value: "9,412",  change: "+78.6 (+0.84%)",  pct: 0.84,  positive: true,  high: "9,450",  low: "9,320",  chart: [] },
  { name: "NIFTY REALTY", ticker: "NIFTYREALTY.NS",value: "1,042",  change: "+8.4 (+0.81%)",   pct: 0.81,  positive: true,  high: "1,058",  low: "1,031",  chart: [] },
  { name: "NIFTY ENERGY", ticker: "NIFTYENERGY.NS",value: "40,128", change: "+521.4 (+1.31%)", pct: 1.31,  positive: true,  high: "40,320", low: "39,550", chart: [] },
];

function MiniArea({ data, positive }: { data: { label: string; value: number }[]; positive: boolean }) {
  if (!data.length) return <div className="mt-3 h-12 rounded-lg bg-white/[0.02]" />;
  const color = positive ? "#10b981" : "#f43f5e";
  return (
    <div className="mt-3 h-12">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`g-${positive}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0}   />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={1.5}
            fill={`url(#g-${positive})`} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function IndexCard({ idx }: { idx: IndexQuote }) {
  const ctx = INDEX_CONTEXT[idx.name];
  return (
    <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 transition hover:-translate-y-0.5 hover:border-white/20">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="mt-0.5 truncate text-sm font-semibold text-white">{idx.name}</p>
          {ctx && <p className="text-[11px] text-slate-500 mt-0.5">{ctx.desc}</p>}
        </div>
        <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${idx.positive ? "bg-emerald-500/10 text-emerald-300" : "bg-rose-500/10 text-rose-300"}`}>
          {idx.pct > 0 ? "+" : ""}{idx.pct.toFixed(2)}%
        </span>
      </div>
      <p className="mt-3 text-2xl font-bold text-white">{idx.value}</p>
      <p className={`mt-0.5 text-xs ${idx.positive ? "text-emerald-400" : "text-rose-400"}`}>{idx.change}</p>
      <MiniArea data={idx.chart} positive={idx.positive} />
      <div className="mt-3 flex justify-between border-t border-white/5 pt-3 text-[11px] text-slate-500">
        <span>H: <span className="text-slate-400">{idx.high}</span></span>
        <span>L: <span className="text-slate-400">{idx.low}</span></span>
      </div>
    </div>
  );
}

// ── WhatThisMeans ─────────────────────────────────────────────────────────────
function WhatThisMeans({ indices }: { indices: IndexQuote[] }) {
  const nifty     = indices.find(i => i.name === "NIFTY 50");
  const vix       = indices.find(i => i.name === "INDIA VIX");
  const bankNifty = indices.find(i => i.name === "BANK NIFTY");

  const insights: { arrow: React.ReactNode; color: string; title: string; detail: string }[] = [];

  if (nifty) {
    const up = nifty.positive;
    insights.push({
      arrow: up ? "↗" : "↘",
      color: up ? "text-emerald-400" : "text-rose-400",
      title: up ? "Large caps are rising today" : "Large caps are falling today",
      detail: up
        ? "Most large company stocks are likely up. If you hold index funds, your portfolio is probably rising."
        : "Most large company stocks are likely down. Normal market day — don't react without checking your own holdings.",
    });
  }

  if (vix) {
    const vixVal = parseFloat(vix.value) || 18;
    const calm   = vixVal < 20;
    insights.push({
      arrow: calm ? <CheckCircle2 size={16} strokeWidth={1.8}/> : <AlertTriangle size={16} strokeWidth={1.8}/>,
      color: calm ? "text-sky-400" : "text-amber-400",
      title: calm
        ? `Market is calm (VIX ${vix.value})`
        : `Market is nervous (VIX ${vix.value})`,
      detail: calm
        ? "Low volatility means smaller daily swings. Good environment to hold positions and avoid overtrading."
        : "Elevated volatility means larger daily swings. Consider reviewing your risk before adding new positions.",
    });
  }

  if (bankNifty) {
    const up = bankNifty.positive;
    insights.push({
      arrow: up ? "↗" : "↘",
      color: up ? "text-emerald-400" : "text-rose-400",
      title: `Banking sector is ${up ? "outperforming" : "under pressure"}`,
      detail: up
        ? "HDFC Bank, ICICI Bank, SBI are moving higher. Banking stocks drive ~35% of the Nifty — this lifts the broader index."
        : "Banking stocks are falling. This drags the Nifty down. Watch for RBI policy signals or NPA concerns.",
    });
  }

  if (!insights.length) return null;

  return (
    <div className="rounded-[20px] border border-sky-500/15 bg-sky-500/[0.04] p-5">
      <h3 className="mb-4 text-[11px] font-bold uppercase tracking-[0.15em] text-sky-400">
        What This Means For You
      </h3>
      <div className="space-y-4">
        {insights.map((ins, i) => (
          <div key={i} className="flex items-start gap-3">
            <span className={`shrink-0 flex items-center ${ins.color}`}>{ins.arrow}</span>
            <div className="min-w-0">
              <p className={`text-[13px] font-semibold ${ins.color}`}>{ins.title}</p>
              <p className="mt-0.5 text-[12px] leading-5 text-slate-400">{ins.detail}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-white/[0.05] pt-4">
        <Link
          href="/ai-search?q=What+do+today%27s+market+index+moves+mean+for+my+portfolio"
          className="inline-flex items-center gap-1.5 rounded-xl bg-violet-600/80 px-4 py-2 text-[12px] font-bold text-white transition hover:bg-violet-500"
        >
          Ask AI what this means for me →
        </Link>
        <Link href="/events" className="text-[12px] font-medium text-sky-400 transition hover:text-sky-300">
          See what's driving this →
        </Link>
        <Link href="/market-intelligence" className="text-[12px] font-medium text-slate-400 transition hover:text-slate-300">
          Live Market →
        </Link>
      </div>
    </div>
  );
}

export default function MarketIndicesPage() {
  const [indices, setIndices] = useState<IndexQuote[]>(FALLBACK);

  useEffect(() => {
    fetch(`${API}/api/indices`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d?.length) setIndices(d); })
      .catch(() => {});
  }, []);

  const hero = indices[0];

  const mainIndices   = indices.filter(i => INDEX_CONTEXT[i.name]?.group === "main");
  const vixIndex      = indices.filter(i => INDEX_CONTEXT[i.name]?.group === "vix");
  const sectorIndices = indices.filter(i => INDEX_CONTEXT[i.name]?.group === "sector" || !INDEX_CONTEXT[i.name]);

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <MarketContextStrip />
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Market Overview</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Market Indices</h1>
        <p className="mt-1 text-sm text-slate-400">An index tracks a group of stocks together. If Nifty 50 is up, most large companies are rising.</p>
      </div>

      {/* Interpretation first — numbers second */}
      <WhatThisMeans indices={indices} />

      {/* Hero spotlight */}
      {hero && (
        <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-6 shadow-glow">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs uppercase tracking-widest text-slate-500">Benchmark</p>
              <p className="mt-1 text-xl font-bold text-white">{hero.name}</p>
              <p className="mt-3 text-5xl font-semibold tracking-tight text-white">{hero.value}</p>
              <p className={`mt-2 text-lg font-medium ${hero.positive ? "text-emerald-400" : "text-rose-400"}`}>{hero.change}</p>
            </div>
            <div className="flex gap-8 text-sm">
              {[["Day High", hero.high], ["Day Low", hero.low]].map(([label, val]) => (
                <div key={label} className="text-center">
                  <p className="text-xs uppercase tracking-widest text-slate-500">{label}</p>
                  <p className="mt-1 text-xl font-semibold text-white">{val}</p>
                </div>
              ))}
              <div className="text-center">
                <p className="text-xs uppercase tracking-widest text-slate-500">Status</p>
                <span className="mt-1 inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                  Live
                </span>
              </div>
            </div>
          </div>
          {hero.chart.length > 0 && (
            <div className="mt-6 h-20">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={hero.chart}>
                  <defs>
                    <linearGradient id="hero-g" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#38bdf8" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#38bdf8" stopOpacity={0}   />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="label" hide />
                  <YAxis domain={["auto", "auto"]} hide />
                  <Tooltip contentStyle={{ background: "#020617", border: "1px solid rgba(255,255,255,0.08)", color: "#fff", borderRadius: 12 }} />
                  <Area type="monotone" dataKey="value" stroke="#38bdf8" strokeWidth={2} fill="url(#hero-g)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* The Big Two */}
      {mainIndices.length > 0 && (
        <div>
          <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.15em] text-slate-500">The Big Two — Watch these first</p>
          <div className="grid gap-4 sm:grid-cols-2">
            {mainIndices.map((idx) => (
              <IndexCard key={idx.name} idx={idx} />
            ))}
          </div>
        </div>
      )}

      {/* Market Nervousness */}
      {vixIndex.length > 0 && (
        <div>
          <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.15em] text-slate-500">Market Nervousness</p>
          <div className="grid gap-4 sm:grid-cols-2">
            {vixIndex.map((idx) => (
              <IndexCard key={idx.name} idx={idx} />
            ))}
          </div>
        </div>
      )}

      {/* Sector Indices */}
      {sectorIndices.length > 0 && (
        <div>
          <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.15em] text-slate-500">Sector Indices — Drill into specific industries</p>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {sectorIndices.map((idx) => (
              <IndexCard key={idx.name} idx={idx} />
            ))}
          </div>
        </div>
      )}

      <p className="text-center text-[11px] text-slate-600">
        Prices via yfinance · NSE/BSE · Delayed data · Real-time tick requires{" "}
        <span className="text-slate-500">NSE Live API / Upstox / Zerodha Kite</span>
      </p>
    </main>
  );
}
