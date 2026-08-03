"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { Flame, Zap, Droplets, Activity, Cpu, Layers } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────
interface MoverRow {
  company: string;
  ticker: string;
  value: string;
  subtitle: string;
  positive?: boolean;
}

interface GlobalMarketRow {
  name: string;
  value: string;
  change: string;
  positive: boolean;
  flag?: string;
}

interface DashboardRightSidebarProps {
  gainers: MoverRow[];
  losers: MoverRow[];
  active: MoverRow[];
  globalIndices: GlobalMarketRow[];
  globalCommodities: GlobalMarketRow[];
  globalCurrencies: GlobalMarketRow[];
  aiInsight: string;
}

// ── Pre-Market Movers ─────────────────────────────────────────────────────────
function PreMarketMovers({ gainers, losers, active }: { gainers: MoverRow[]; losers: MoverRow[]; active: MoverRow[] }) {
  const [tab, setTab] = useState<"Gainers"|"Losers"|"Active">("Gainers");
  const rows = tab === "Gainers" ? gainers : tab === "Losers" ? losers : active;

  return (
    <div className="rounded-[24px] border border-surface-border/10 bg-text-primary/[0.03] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[13px] font-bold text-text-primary">Pre-Market Movers</h3>
        <Link href="/stocks" className="text-[10px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View All →</Link>
      </div>
      {/* Tabs */}
      <div className="mb-3 flex gap-0.5 rounded-xl bg-text-primary/[0.04] p-0.5">
        {(["Gainers", "Losers", "Active"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 rounded-lg py-1 text-[10px] font-medium transition ${
              tab === t ? "bg-text-primary/10 text-text-primary" : "text-text-muted hover:text-text-secondary"}`}>
            {t}
          </button>
        ))}
      </div>
      {/* Header */}
      <div className="mb-1.5 grid grid-cols-[1fr_55px_50px_42px] gap-1 text-[9px] font-semibold uppercase tracking-wider text-text-muted px-1">
        <span>Company</span>
        <span className="text-right">Price</span>
        <span className="text-right">Chg %</span>
        <span className="text-right">Vol</span>
      </div>
      {/* Rows */}
      <div className="space-y-1">
        {rows.slice(0, 5).map((r) => {
          const isPos = r.positive !== false;
          const vol = r.subtitle?.includes("Cr") ? r.subtitle.replace("₹","").replace(" Cr","") + "Cr" : "—";
          return (
            <Link key={r.ticker} href={`/companies/${r.ticker}`}
              className="grid grid-cols-[1fr_55px_50px_42px] items-center gap-1 rounded-xl border border-surface-border/4 bg-text-primary/[0.02] px-2 py-1.5 hover:border-sky-500/15 transition">
              <div className="flex items-center gap-1.5 min-w-0">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-text-primary/[0.07] text-[8px] font-bold text-text-secondary">
                  {r.ticker.slice(0, 3)}
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold text-text-primary truncate leading-none">{r.ticker}</p>
                  <p className="text-[8px] text-text-muted truncate leading-none mt-0.5">{r.company.split(" ")[0]}</p>
                </div>
              </div>
              <p className="text-right text-[10px] font-semibold text-text-primary">{r.subtitle || "—"}</p>
              <p className={`text-right text-[10px] font-bold ${isPos ? "text-emerald-400" : "text-rose-400"}`}>{r.value}</p>
              <p className="text-right text-[9px] text-text-muted">{vol}</p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

// ── Global Market Overview ────────────────────────────────────────────────────
type GlobalTab = "Indices" | "Commodities" | "Currencies";

const COMMODITY_ICONS: Record<string, ReactNode> = {
  "Crude Oil":   <Flame className="h-3.5 w-3.5 text-amber-400" />,
  "Gold":        <Activity className="h-3.5 w-3.5 text-yellow-400" />,
  "Silver":      <Layers className="h-3.5 w-3.5 text-text-secondary" />,
  "Natural Gas": <Zap className="h-3.5 w-3.5 text-sky-400" />,
  "Copper":      <Cpu className="h-3.5 w-3.5 text-orange-400" />,
  "Aluminium":   <Droplets className="h-3.5 w-3.5 text-text-secondary" />,
};

const CURRENCY_FLAGS: Record<string, ReactNode> = {
  "USD/INR": <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">US</span>,
  "EUR/INR": <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">EU</span>,
  "GBP/INR": <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">GB</span>,
  "JPY/INR": <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">JP</span>,
  "CNY/INR": <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">CN</span>,
  "AUD/INR": <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">AU</span>,
};

const INDEX_FLAGS: Record<string, ReactNode> = {
  "Dow Jones":  <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">US</span>,
  "S&P 500":    <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">US</span>,
  "Nasdaq":     <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">US</span>,
  "FTSE 100":   <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">GB</span>,
  "Nikkei 225": <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">JP</span>,
  "Hang Seng":  <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">HK</span>,
  "Shanghai":   <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">CN</span>,
  "DAX":        <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">DE</span>,
  "CAC 40":     <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">FR</span>,
  "SGX Nifty":  <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">SG</span>,
};

function GlobalMarketOverview({
  indices, commodities, currencies,
}: { indices: GlobalMarketRow[]; commodities: GlobalMarketRow[]; currencies: GlobalMarketRow[] }) {
  const [tab, setTab] = useState<GlobalTab>("Indices");

  const rows =
    tab === "Indices" ? indices :
    tab === "Commodities" ? commodities : currencies;

  return (
    <div className="rounded-[24px] border border-surface-border/10 bg-text-primary/[0.03] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[13px] font-bold text-text-primary">Global Market Overview</h3>
        <Link href="/market-intelligence?tab=global-markets" className="text-[10px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View All →</Link>
      </div>
      {/* Tabs */}
      <div className="mb-3 flex gap-0.5 rounded-xl bg-text-primary/[0.04] p-0.5">
        {(["Indices", "Commodities", "Currencies"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 rounded-lg py-1 text-[10px] font-medium transition ${
              tab === t ? "bg-text-primary/10 text-text-primary" : "text-text-muted hover:text-text-secondary"}`}>
            {t}
          </button>
        ))}
      </div>
      {/* Rows */}
      <div className="space-y-1">
        {rows.slice(0, 6).map((r, i) => {
          const icon: ReactNode =
            tab === "Indices" ? (INDEX_FLAGS[r.name] ?? <Activity className="h-3.5 w-3.5 text-text-secondary" />) :
            tab === "Commodities" ? (COMMODITY_ICONS[r.name] ?? <Layers className="h-3.5 w-3.5 text-text-secondary" />) :
            (CURRENCY_FLAGS[r.name] ?? <span className="rounded px-1 py-0.5 text-[8px] font-bold bg-text-primary/10 text-text-secondary">FX</span>);
          return (
            <div key={r.name + i}
              className="flex items-center justify-between rounded-xl border border-surface-border/4 bg-text-primary/[0.02] px-2.5 py-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="shrink-0">{icon}</span>
                <p className="text-[11px] font-medium text-text-secondary truncate">{r.name}</p>
              </div>
              <div className="text-right shrink-0 ml-2">
                <p className="text-[11px] font-bold text-text-primary">{r.value}</p>
                <p className={`text-[10px] font-semibold ${r.positive ? "text-emerald-400" : "text-rose-400"}`}>{r.change}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── AI Market Insight ─────────────────────────────────────────────────────────
function AIMarketInsight({ insight }: { insight: string }) {
  return (
    <div className="relative overflow-hidden rounded-[24px] border border-violet-500/20 bg-gradient-to-br from-violet-500/[0.07] via-transparent to-sky-500/[0.05] p-4">
      <div className="pointer-events-none absolute -right-6 -top-6 h-20 w-20 rounded-full bg-violet-500/15 blur-2xl"/>
      <div className="flex items-center gap-2 mb-2.5">
        <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-500/20">
          <svg viewBox="0 0 24 24" fill="currentColor" className="h-3 w-3 text-violet-400"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg>
        </div>
        <p className="text-[12px] font-bold text-text-primary">AI Market Insight</p>
        <span className="ml-auto rounded-full border border-violet-500/30 bg-violet-500/10 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wider text-violet-400">Live</span>
      </div>
      <p className="text-[11px] leading-[1.6] text-text-secondary">{insight}</p>
      <button className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-violet-600/80 to-sky-600/60 py-2 text-[11px] font-semibold text-text-primary hover:from-violet-600 hover:to-sky-600 transition">
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-3 w-3"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg> Ask AI About Market
      </button>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export function DashboardRightSidebar({
  gainers, losers, active,
  globalIndices, globalCommodities, globalCurrencies,
  aiInsight,
}: DashboardRightSidebarProps) {
  return (
    <div className="space-y-4">
      <PreMarketMovers gainers={gainers} losers={losers} active={active}/>
      <GlobalMarketOverview indices={globalIndices} commodities={globalCommodities} currencies={globalCurrencies}/>
      <AIMarketInsight insight={aiInsight}/>
    </div>
  );
}
