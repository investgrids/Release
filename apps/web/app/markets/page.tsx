"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import Link from "next/link";
import { Coins, Layers, Zap, Gem, Droplets, Flame, Gauge, Globe, Shield, TrendingUp, Package, Bot, BarChart2 } from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";


interface ChartPoint { label: string; value: number }
interface Commodity {
  id: string; name: string; unit: string;
  price: string; change: string; pct: number; positive: boolean;
  high: string; low: string; chart: ChartPoint[];
}
interface InsightItem { text: string; impact: string }
interface InsightGroup { impact: string; items: InsightItem[] }
interface KeyDriver { label: string; level: string }
interface CommodityData {
  metals: Commodity[]; energy: Commodity[];
  insights: {
    metals: InsightGroup; energy: InsightGroup;
    key_drivers_metals: KeyDriver[]; key_drivers_energy: KeyDriver[];
    daily_summary: string;
  };
  updated: string;
}

const COLORS: Record<string, string> = {
  gold: "#fbbf24", silver: "#94a3b8", copper: "#f97316", platinum: "#38bdf8",
  brent: "#60a5fa", wti: "#93c5fd", natgas: "#818cf8", petrol: "#34d399",
};
const ICONS: Record<string, ReactNode> = {
  gold:     <Coins className="h-5 w-5 text-amber-400" />,
  silver:   <Layers className="h-5 w-5 text-slate-300" />,
  copper:   <Zap className="h-5 w-5 text-orange-400" />,
  platinum: <Gem className="h-5 w-5 text-sky-300" />,
  brent:    <Droplets className="h-5 w-5 text-blue-400" />,
  wti:      <Droplets className="h-5 w-5 text-blue-300" />,
  natgas:   <Flame className="h-5 w-5 text-violet-400" />,
  petrol:   <Gauge className="h-5 w-5 text-emerald-400" />,
};

const mkChart = (base: number, pts = 7, vol = 0.006): ChartPoint[] =>
  Array.from({ length: pts }, (_, i) => ({
    label: `D${i}`,
    value: parseFloat((base * (1 + (Math.random() - 0.48) * vol * (i + 1))).toFixed(2)),
  }));

const FB_METALS: Commodity[] = [
  { id:"gold",     name:"Gold",     unit:"USD / oz",  price:"2,427.50", change:"+28.40", pct: 1.18, positive:true,  high:"2,438.70", low:"2,392.10", chart:mkChart(2395) },
  { id:"silver",   name:"Silver",   unit:"USD / oz",  price:"28.65",    change:"+0.42",  pct: 1.49, positive:true,  high:"28.74",    low:"28.10",    chart:mkChart(28.2) },
  { id:"copper",   name:"Copper",   unit:"USD / lb",  price:"4.68",     change:"+0.07",  pct: 1.52, positive:true,  high:"4.71",     low:"4.59",     chart:mkChart(4.6) },
  { id:"platinum", name:"Platinum", unit:"USD / oz",  price:"1,045.30", change:"+9.10",  pct: 0.88, positive:true,  high:"1,051.80", low:"1,028.40", chart:mkChart(1030) },
];
const FB_ENERGY: Commodity[] = [
  { id:"brent",  name:"Crude Oil (Brent)",     unit:"USD / bbl",   price:"83.47",  change:"+2.34", pct: 2.89, positive:true,  high:"83.92",  low:"80.95",  chart:mkChart(80.8) },
  { id:"wti",    name:"Crude Oil (WTI)",        unit:"USD / bbl",   price:"79.68",  change:"+2.11", pct: 2.72, positive:true,  high:"80.12",  low:"77.32",  chart:mkChart(77.4) },
  { id:"natgas", name:"Natural Gas",            unit:"USD / MMBtu", price:"2.56",   change:"+0.05", pct: 2.00, positive:true,  high:"2.58",   low:"2.47",   chart:mkChart(2.5) },
  { id:"petrol", name:"India Petrol (Retail)", unit:"INR / Litre", price:"103.19", change:"-0.28", pct:-0.27, positive:false, high:"103.45", low:"102.85", chart:mkChart(103.3) },
];
const FB_INSIGHTS: CommodityData["insights"] = {
  metals: {
    impact: "High Impact",
    items: [
      { text: "Gold is up due to safe-haven demand amid escalating geopolitical tensions.", impact: "Bullish" },
      { text: "Silver and Platinum are gaining as industrial demand remains strong despite global uncertainties.", impact: "Moderately Bullish" },
      { text: "Copper prices rising due to supply concerns and strong demand from China.", impact: "Bullish" },
    ],
  },
  energy: {
    impact: "Very High Impact",
    items: [
      { text: "Crude oil prices are up sharply due to supply risks from geopolitical tensions in the Middle East.", impact: "Very Bullish" },
      { text: "Petrol and diesel prices likely to remain elevated in the short term. Monitor OPEC+ decisions.", impact: "Bullish" },
      { text: "Natural gas prices inch higher as US inventory falls and summer demand expectations rise.", impact: "Moderately Bullish" },
    ],
  },
  key_drivers_metals: [
    { label:"Middle East Tensions", level:"High" }, { label:"US Dollar Index", level:"Moderate" },
    { label:"China Manufacturing Data", level:"Moderate" }, { label:"Interest Rate Outlook", level:"Low" },
  ],
  key_drivers_energy: [
    { label:"OPEC+ Decisions", level:"High" }, { label:"Geopolitical Risk", level:"High" },
    { label:"US Crude Inventory", level:"Moderate" }, { label:"Summer Demand", level:"Moderate" },
  ],
  daily_summary: "War-related tensions continue to support safe-haven assets like gold. Crude oil remains volatile with upside risk. Monitor geopolitical news, OPEC+ updates, and USD movement for short-term price direction.",
};

const IMPACT_BADGE: Record<string, string> = {
  "High Impact":      "bg-rose-500/10 text-rose-300 border border-rose-500/20",
  "Very High Impact": "bg-rose-500/15 text-rose-300 border border-rose-500/25",
  "Moderate Impact":  "bg-amber-500/10 text-amber-300",
};
const SENTIMENT_BADGE: Record<string, string> = {
  "Bullish":            "bg-emerald-500/10 text-emerald-300",
  "Very Bullish":       "bg-emerald-500/15 text-emerald-300",
  "Moderately Bullish": "bg-teal-500/10 text-teal-300",
  "Neutral":            "bg-slate-500/10 text-slate-400",
};
const DRIVER_LEVEL: Record<string, string> = {
  High:     "bg-rose-500/10 text-rose-300",
  Moderate: "bg-amber-500/10 text-amber-300",
  Low:      "bg-slate-500/10 text-slate-400",
};
const INSIGHT_ICONS: ReactNode[] = [
  <Shield className="h-4 w-4 text-slate-400" />,
  <TrendingUp className="h-4 w-4 text-slate-400" />,
  <Package className="h-4 w-4 text-slate-400" />,
];

function SparkLine({ data, id }: { data: ChartPoint[]; id: string }) {
  const color = COLORS[id] ?? "#818cf8";
  if (!data.length) return <div className="mt-3 min-h-[48px] flex-1 rounded-lg bg-white/[0.02]" />;
  return (
    <div className="mt-3 min-h-[48px] flex-1">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`g-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0}   />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="value" stroke={color} strokeWidth={1.5}
            fill={`url(#g-${id})`} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function CommodityCard({ c }: { c: Commodity }) {
  return (
    <div className="flex flex-col rounded-[20px] border border-white/10 bg-white/[0.03] p-4 transition hover:-translate-y-0.5 hover:border-white/20">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-white/[0.06] shrink-0">
          {ICONS[c.id] ?? <BarChart2 className="h-5 w-5 text-slate-400" />}
        </div>
        <div className="min-w-0">
          <p className="text-xs font-bold tracking-widest text-white truncate">{c.name.toUpperCase()}</p>
          <p className="text-[10px] text-slate-500">{c.unit}</p>
        </div>
      </div>
      <p className="mt-3 text-2xl font-bold text-white">{c.price}</p>
      <p className={`mt-0.5 text-sm font-medium ${c.positive ? "text-emerald-400" : "text-rose-400"}`}>
        {c.positive ? "▲" : "▼"} {c.change} ({c.pct > 0 ? "+" : ""}{c.pct.toFixed(2)}%)
      </p>
      <SparkLine data={c.chart} id={c.id} />
      <div className="mt-3 flex justify-between border-t border-white/5 pt-3 text-[11px] text-slate-500">
        <span>High: <span className="text-slate-400">{c.high}</span></span>
        <span>Low: <span className="text-slate-400">{c.low}</span></span>
      </div>
    </div>
  );
}

function InsightsPanel({ insights, label }: { insights: InsightGroup; label: string }) {
  return (
    <div className="rounded-[20px] border border-violet-500/20 bg-violet-500/[0.04] p-4">
      <div className="flex items-start justify-between gap-2 mb-4">
        <p className="text-[10px] font-bold tracking-[0.18em] text-violet-300 uppercase leading-tight">
          AI Insights — {label}
        </p>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${IMPACT_BADGE[insights.impact] ?? "bg-rose-500/10 text-rose-300"}`}>
          {insights.impact}
        </span>
      </div>
      <div className="space-y-3.5">
        {insights.items.map((item, i) => (
          <div key={i} className="flex gap-2.5">
            <span className="mt-0.5 shrink-0 text-slate-400">{INSIGHT_ICONS[i] ?? <span>•</span>}</span>
            <div>
              <p className="text-xs text-slate-300 leading-relaxed">{item.text}</p>
              <span className={`mt-1.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${SENTIMENT_BADGE[item.impact] ?? "bg-slate-500/10 text-slate-400"}`}>
                Impact: {item.impact}
              </span>
            </div>
          </div>
        ))}
      </div>
      <Link href="/ai-search"
        className="mt-4 flex items-center gap-1 text-[11px] text-violet-400 hover:text-violet-300 transition">
        View Detailed Analysis <span aria-hidden>→</span>
      </Link>
    </div>
  );
}

function KeyDrivers({ drivers }: { drivers: KeyDriver[] }) {
  return (
    <div className="flex flex-wrap items-center gap-2 pt-4 mt-4 border-t border-white/5">
      <p className="text-[11px] font-semibold text-slate-500 mr-1">Key Drivers Today</p>
      {drivers.map((d, i) => (
        <span key={i} className={`flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${DRIVER_LEVEL[d.level] ?? "bg-slate-500/10 text-slate-400"}`}>
          • {d.label}
          <span className="opacity-60 text-[10px]">{d.level}</span>
        </span>
      ))}
    </div>
  );
}

function CommoditySection({
  title, icon, subtitle, viewHref, viewLabel,
  commodities, insights, drivers,
}: {
  title: string; icon: ReactNode; subtitle: string; viewHref: string; viewLabel: string;
  commodities: Commodity[]; insights: InsightGroup; drivers: KeyDriver[];
}) {
  return (
    <div className="rounded-[24px] border border-violet-500/15 bg-[#0A0B0F]/80 p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <span className="text-slate-400">{icon}</span>
          <div>
            <p className="text-sm font-bold tracking-[0.22em] text-sky-300 uppercase">{title}</p>
            <p className="text-[11px] text-slate-500">{subtitle}</p>
          </div>
        </div>
        <Link href={viewHref} className="text-[11px] text-violet-400 hover:text-violet-300 transition">
          {viewLabel} →
        </Link>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {commodities.map(c => <CommodityCard key={c.id} c={c} />)}
        </div>
        <InsightsPanel insights={insights} label={title} />
      </div>

      <KeyDrivers drivers={drivers} />
    </div>
  );
}

export default function MarketsPage() {
  const [data, setData] = useState<CommodityData>({
    metals: FB_METALS, energy: FB_ENERGY, insights: FB_INSIGHTS, updated: "—",
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/commodities/`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setData(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const { metals, energy, insights } = data;

  return (
    <main className="min-w-0 space-y-5 pb-10">
      {/* Page header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Market Data</p>
          <h1 className="mt-1.5 text-4xl font-semibold tracking-tight text-white">Commodities & Energy</h1>
          <p className="mt-1 text-sm text-slate-400">
            Real-time prices · AI-powered insights ·{" "}
            <span className="text-slate-500">
              Updated: {loading ? "Loading…" : new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} IST
            </span>
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3 rounded-[16px] border border-violet-500/20 bg-violet-500/[0.06] px-4 py-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-violet-500/20 text-violet-300 shrink-0">
              <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg>
            </div>
            <div className="hidden sm:block">
              <p className="text-[10px] font-semibold text-violet-300 uppercase tracking-widest">AI Daily Insight</p>
              <p className="mt-0.5 max-w-xs text-xs text-slate-400 leading-relaxed line-clamp-2">
                {insights.daily_summary}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Commodities section */}
      <CommoditySection
        title="Commodities"
        icon={<Globe className="h-5 w-5" />}
        subtitle="Global Commodity Prices"
        viewHref="/markets"
        viewLabel="View All Commodities"
        commodities={metals}
        insights={insights.metals}
        drivers={insights.key_drivers_metals}
      />

      {/* Energy section */}
      <CommoditySection
        title="Petrol & Crude Oil"
        icon={<Flame className="h-5 w-5" />}
        subtitle="Energy Prices"
        viewHref="/markets"
        viewLabel="View Energy Markets"
        commodities={energy}
        insights={insights.energy}
        drivers={insights.key_drivers_energy}
      />

      {/* AI Daily Market Summary footer */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[20px] border border-white/8 bg-white/[0.02] px-5 py-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-violet-500/15 text-violet-300">
            <Bot className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-white">AI Daily Market Summary</p>
            <p className="mt-0.5 text-xs text-slate-400 leading-relaxed line-clamp-2">
              {insights.daily_summary}
            </p>
          </div>
        </div>
        <Link href="/ai-search"
          className="shrink-0 rounded-[14px] bg-gradient-to-r from-violet-600 to-sky-500 px-4 py-2 text-xs font-semibold text-white shadow-lg transition hover:opacity-90">
          Ask AI Anything
        </Link>
      </div>

      <p className="text-center text-[11px] text-slate-600">
        Prices via yfinance · COMEX / NYMEX / ICE futures · Delayed ~15 min
      </p>
    </main>
  );
}
