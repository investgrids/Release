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
    degraded?: boolean;
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

function InsightsPanel({ insights, label, degraded }: { insights: InsightGroup; label: string; degraded?: boolean }) {
  return (
    <div className="rounded-[20px] border border-violet-500/20 bg-violet-500/[0.04] p-4">
      <div className="flex items-start justify-between gap-2 mb-4">
        <p className="text-[10px] font-bold tracking-[0.18em] text-violet-300 uppercase leading-tight">
          AI Insights — {label}
        </p>
        {!degraded && (
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${IMPACT_BADGE[insights.impact] ?? "bg-rose-500/10 text-rose-300"}`}>
            {insights.impact}
          </span>
        )}
      </div>
      {degraded ? (
        <p className="text-xs text-slate-500 leading-relaxed">
          AI commentary isn&apos;t available right now — the prices above are still live. Try again shortly.
        </p>
      ) : (
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
      )}
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
  commodities, insights, drivers, degraded,
}: {
  title: string; icon: ReactNode; subtitle: string; viewHref: string; viewLabel: string;
  commodities: Commodity[]; insights: InsightGroup; drivers: KeyDriver[]; degraded?: boolean;
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
        <InsightsPanel insights={insights} label={title} degraded={degraded} />
      </div>

      {!degraded && <KeyDrivers drivers={drivers} />}
    </div>
  );
}

export default function MarketsPage() {
  const [data, setData]       = useState<CommodityData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/commodities/`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setData(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <main className="min-w-0 space-y-5 pb-10">
        <div className="h-16 animate-pulse rounded-2xl border border-white/[0.06] bg-white/[0.02]" />
        {[1, 2].map(i => <div key={i} className="h-64 animate-pulse rounded-[24px] border border-white/[0.06] bg-white/[0.02]" />)}
      </main>
    );
  }

  if (!data) {
    return (
      <main className="flex min-w-0 flex-col items-center justify-center gap-3 py-24 text-center">
        <p className="text-sm text-slate-500">Commodity data isn&apos;t available right now.</p>
      </main>
    );
  }

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
                {insights.degraded ? "Not available right now." : insights.daily_summary}
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
        degraded={insights.degraded}
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
        degraded={insights.degraded}
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
              {insights.degraded ? "AI summary isn't available right now — prices above are still live." : insights.daily_summary}
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
