"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Droplets, BarChart2, Banknote, ArrowRightLeft,
  TrendingUp, TrendingDown, Minus, Sunrise, Target,
  Compass, History, Newspaper, Sparkles,
  ChevronRight, ChevronDown, Activity, Building2, Moon, Circle, Globe2,
} from "lucide-react";
import { API_BASE_URL as API } from "@/lib/api";


// ── Real mini-chart from backend data ─────────────────────────────────────────
function MiniChart({ chart, positive }: { chart?: { value: number }[]; positive: boolean }) {
  if (!chart || chart.length < 3) {
    return <div className={`h-0.5 w-12 rounded-full ${positive ? "bg-emerald-500/40" : "bg-rose-500/40"}`} />;
  }
  const vals = chart.map(p => p.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const pts = vals
    .map((v, i) => `${(i / (vals.length - 1)) * 60},${24 - ((v - min) / range) * 20}`)
    .join(" ");
  const color = positive ? "#22c55e" : "#f43f5e";
  return (
    <svg viewBox="0 0 60 24" className="h-6 w-14 shrink-0" fill="none">
      <polyline points={pts} stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Countdown timer to 9:15 AM IST ────────────────────────────────────────────
function useCountdown() {
  const [label, setLabel] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [greeting, setGreeting] = useState("Good Morning");

  useEffect(() => {
    function compute() {
      const now = new Date();
      const ist = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
      const dow = ist.getDay();
      const hour = ist.getHours();
      const totalMin = hour * 60 + ist.getMinutes();
      const openMin = 9 * 60 + 15;
      const closeMin = 15 * 60 + 30;

      setGreeting(hour < 12 ? "Good Morning" : hour < 17 ? "Good Afternoon" : "Good Evening");

      if (dow === 0 || dow === 6) {
        setIsOpen(false);
        setLabel("Market closed for the weekend. Opens Monday 9:15 AM IST");
        return;
      }

      if (totalMin >= openMin && totalMin <= closeMin) {
        setIsOpen(true);
        setLabel("Market Open");
        return;
      }
      setIsOpen(false);
      if (totalMin > closeMin) {
        const nextOpen = openMin + 24 * 60 - totalMin;
        const h = Math.floor(nextOpen / 60);
        const m = nextOpen % 60;
        const nextDay = dow === 5 ? "Monday" : "tomorrow";
        setLabel(`Opens in ${h}h ${m}m (${nextDay})`);
        return;
      }
      const diff = (openMin - totalMin) * 60 - ist.getSeconds();
      if (diff <= 0) { setLabel("Opening soon…"); return; }
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = diff % 60;
      setLabel(h > 0 ? `Opens in ${h}h ${m}m ${s}s` : `Opens in ${m}m ${s}s`);
    }
    compute();
    const id = setInterval(compute, 1000);
    return () => clearInterval(id);
  }, []);

  return { label, isOpen, greeting };
}

// ── GIFT Nifty hero card ───────────────────────────────────────────────────────
function GiftNiftyHero({ data }: { data: any }) {
  if (!data) return (
    <div className="rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-5 animate-pulse h-48" />
  );
  const status = data.status ?? (data.value !== "—" ? "live" : "unavailable");
  if (status === "unavailable") {
    return (
      <div className="rounded-xl border border-surface-border/10 bg-surface-card p-4">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-muted">GIFT Nifty</span>
          <span className="rounded-full border border-surface-border/20 bg-text-primary/[0.05] px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-text-muted">
            Unavailable
          </span>
        </div>
        <p className="text-[12px] text-text-muted">GIFT Nifty's overnight signal isn't available right now.</p>
        {data.spot_value && (
          <p className="mt-2 text-[11px] text-text-muted">Nifty Spot (reference only): <span className="font-bold text-text-primary">{data.spot_value}</span></p>
        )}
      </div>
    );
  }
  const pos = data.positive !== false;
  const tc = pos ? "text-emerald-400" : "text-rose-400";
  const bc = pos ? "border-emerald-500/20" : "border-rose-500/20";
  const isStale = status === "stale";
  return (
    <div className={`rounded-xl border ${bc} bg-surface-card p-4`}>
      <div className="mb-2.5 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-muted">GIFT Nifty</span>
            <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
              isStale ? "border-amber-500/30 bg-amber-500/10 text-amber-400" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
            }`}>
              {isStale ? "Stale" : "Live"}
            </span>
          </div>
          <p className="mt-0.5 text-[10px] text-text-muted">{data.note ?? "NSE IX, GIFT City"}</p>
        </div>
        <MiniChart chart={data.chart} positive={pos} />
      </div>
      <div className="flex items-baseline gap-2.5 mb-1">
        <p className="text-[26px] font-black tracking-tight text-text-primary leading-none tabular-nums">{data.value}</p>
        <p className={`text-[14px] font-bold tabular-nums ${tc}`}>{data.pct}</p>
      </div>
      <p className={`text-[11px] font-semibold ${tc}`}>{data.change}</p>
      {data.spot_value && (
        <div className="mt-3 flex items-center gap-3 rounded-[12px] border border-surface-border/7 bg-text-primary/[0.04] px-3 py-2">
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-text-muted">Nifty Spot</span>
            <span className="text-[11px] font-bold text-text-primary">{data.spot_value}</span>
          </div>
          {data.premium_pct && (
            <div className="ml-auto flex items-center gap-1.5">
              <span className="text-[9px] text-text-muted">Premium</span>
              <span className={`text-[11px] font-bold ${data.is_premium ? "text-emerald-400" : "text-rose-400"}`}>
                {data.premium_pct}
              </span>
            </div>
          )}
        </div>
      )}
      {data.opening_range && (
        <div className="mt-2 flex items-center gap-2 rounded-[10px] border border-sky-500/15 bg-sky-500/[0.06] px-3 py-1.5">
          <span className="text-[9px] text-text-muted">Expected open</span>
          <span className="text-[11px] font-bold text-sky-600 dark:text-sky-300">
            {data.opening_range.low} – {data.opening_range.high}
          </span>
          <span className="ml-auto text-[8px] text-text-muted">± {data.opening_range.band_pct}% band</span>
        </div>
      )}
    </div>
  );
}

// ── Bank Nifty Futures card ───────────────────────────────────────────────────
function BankNiftyCard({ data }: { data: any }) {
  if (!data) return (
    <div className="rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-5 animate-pulse h-48" />
  );
  const pos = data.positive !== false;
  const tc = pos ? "text-emerald-400" : "text-rose-400";
  const bc = pos ? "border-emerald-500/15" : "border-rose-500/15";
  return (
    <div className={`relative overflow-hidden rounded-xl border ${bc} bg-surface-card p-4`}>
      <div className="mb-2.5 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-muted">Bank Nifty Futures</span>
          </div>
          <p className="mt-0.5 text-[10px] text-text-muted">{data.note ?? "NSE near-month contract"}</p>
        </div>
        <MiniChart chart={data.chart} positive={pos} />
      </div>
      <div className="flex items-baseline gap-2.5 mb-1">
        <p className="text-[22px] font-black tracking-tight text-text-primary leading-none">{data.value}</p>
        <p className={`text-[13px] font-bold ${tc}`}>{data.pct}</p>
      </div>
      <p className={`text-[11px] font-semibold ${tc}`}>{data.change}</p>
      {data.spot_value && (
        <div className="mt-3 flex items-center gap-3 rounded-[10px] border border-surface-border/7 bg-text-primary/[0.04] px-3 py-2">
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-text-muted">BNF Spot</span>
            <span className="text-[11px] font-bold text-text-primary">{data.spot_value}</span>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="text-[9px] text-text-muted">Basis</span>
            <span className={`text-[11px] font-bold ${data.is_premium ? "text-emerald-400" : "text-rose-400"}`}>
              {data.premium_pct}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── India VIX card ────────────────────────────────────────────────────────────
function IndiaVIXCard({ data }: { data: any }) {
  if (!data) return (
    <div className="rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-5 animate-pulse" />
  );
  const pos = data.positive !== false;
  const c = data.color ?? "slate";
  const BADGE: Record<string, string> = {
    emerald: "bg-emerald-500/10 border-emerald-500/25 text-emerald-400",
    amber:   "bg-amber-500/10  border-amber-500/25  text-amber-400",
    orange:  "bg-orange-500/10 border-orange-500/25 text-orange-400",
    rose:    "bg-rose-500/10   border-rose-500/25   text-rose-400",
    slate:   "bg-slate-500/10  border-surface-border/6  text-text-secondary",
  };
  const TEXT: Record<string, string> = {
    emerald: "text-emerald-400", amber: "text-amber-400",
    orange: "text-orange-400",   rose: "text-rose-400", slate: "text-text-secondary",
  };
  return (
    <div className="relative overflow-hidden rounded-2xl border border-surface-border/7 bg-surface-card p-4">
      <div className="mb-2.5 flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-muted">India VIX</span>
        <MiniChart chart={data.chart} positive={!pos} />
      </div>
      <div className="mb-2 flex items-baseline gap-2">
        <p className="text-[22px] font-black tracking-tight text-text-primary leading-none">{data.value}</p>
        <p className={`text-[11px] font-bold ${pos ? "text-rose-400" : "text-emerald-400"}`}>{data.pct}</p>
      </div>
      <span className={`mb-2 inline-block rounded-full border px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${BADGE[c]}`}>
        {data.level_label ?? "—"}
      </span>
      <p className={`text-[11px] leading-4 ${TEXT[c]}`}>{data.interpretation ?? "Fear gauge for Indian markets"}</p>
    </div>
  );
}

// ── FII / DII card ────────────────────────────────────────────────────────────
function FIIDIICard({ data }: { data: any }) {
  if (!data) return null;
  if (!data.available) {
    return (
      <div className="rounded-[20px] border border-surface-border/6 bg-text-primary/[0.02] px-5 py-3 flex items-center gap-3">
        <span className="text-[11px] text-text-muted">FII / DII data · {data.note ?? "NSE data unavailable"}</span>
      </div>
    );
  }
  const fii = data.fii_net ?? 0;
  const dii = data.dii_net ?? 0;
  const fiiPos = fii >= 0;
  const diiPos = dii >= 0;
  function fmt(v: number) {
    const abs = Math.abs(v);
    const sign = v >= 0 ? "+" : "−";
    if (abs >= 10000) return `${sign}₹${(abs / 100).toFixed(0)}Cr`;
    return `${sign}₹${abs.toLocaleString("en-IN", { maximumFractionDigits: 0 })}Cr`;
  }
  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-surface-card px-5 py-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-muted">FII / DII Flows</span>
          <span className="rounded-full border border-surface-border/6 bg-slate-500/10 px-2 py-0.5 text-[8px] font-bold uppercase text-text-muted">
            {data.note ?? "Previous Session"}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1">
          <p className="text-[9px] font-semibold uppercase tracking-wider text-text-muted">FII / FPI</p>
          <p className={`text-[17px] font-black leading-none ${fiiPos ? "text-emerald-400" : "text-rose-400"}`}>{fmt(fii)}</p>
          <p className="text-[10px] text-text-muted">{fiiPos ? "Net Buying" : "Net Selling"}</p>
        </div>
        <div className="flex flex-col gap-1 border-l border-surface-border/6 pl-4">
          <p className="text-[9px] font-semibold uppercase tracking-wider text-text-muted">DII</p>
          <p className={`text-[17px] font-black leading-none ${diiPos ? "text-emerald-400" : "text-rose-400"}`}>{fmt(dii)}</p>
          <p className="text-[10px] text-text-muted">{diiPos ? "Net Buying" : "Net Selling"}</p>
        </div>
      </div>
    </div>
  );
}

// ── US Futures card ───────────────────────────────────────────────────────────
function USFutureCard({ item }: { item: any }) {
  const pos = item.positive !== false;
  return (
    <div className="flex flex-col rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-4 hover:border-sky-500/15 hover:bg-text-primary/[0.05] transition">
      <div className="mb-2 flex items-start justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted leading-tight max-w-[80px]">{item.name}</p>
        <MiniChart chart={item.chart} positive={pos} />
      </div>
      <p className="text-[16px] font-black text-text-primary leading-none mb-1">{item.value}</p>
      <p className={`text-[11px] font-bold ${pos ? "text-emerald-400" : "text-rose-400"}`}>{item.pct}</p>
      <p className="text-[10px] text-text-muted mt-0.5">{item.change}</p>
    </div>
  );
}

// ── Market row (Asian / European) ─────────────────────────────────────────────
const MARKET_FLAGS: Record<string, string> = {
  "Nikkei 225": "JP", "Hang Seng": "HK", "Shanghai": "CN", "KOSPI": "KR",
  "FTSE 100":   "GB", "DAX": "DE",       "CAC 40":   "FR",
};
function MarketRow({ item }: { item: any }) {
  const pos = item.positive !== false;
  const flag = item.flag ?? MARKET_FLAGS[item.name] ?? "GLB";
  return (
    <div className="flex items-center gap-3 rounded-xl border border-surface-border/4 bg-text-primary/[0.02] px-3 py-2.5 hover:bg-text-primary/[0.04] transition">
      <span className="inline-flex items-center justify-center rounded px-1 py-0.5 text-[9px] font-bold bg-text-primary/10 text-text-secondary font-mono shrink-0">{flag}</span>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-semibold text-text-primary truncate">{item.name}</p>
      </div>
      <div className="text-right shrink-0">
        <p className="text-[12px] font-bold text-text-primary">{item.value}</p>
        <p className={`text-[10px] font-semibold ${pos ? "text-emerald-400" : "text-rose-400"}`}>
          {item.change_str ?? item.pct}
        </p>
      </div>
    </div>
  );
}

// ── Indian ADR section ────────────────────────────────────────────────────────
function ADRCard({ item }: { item: any }) {
  const pos = item.positive !== false;
  const premPos = item.premium_positive !== false;
  return (
    <div className="flex flex-col rounded-[16px] border border-surface-border/6 bg-text-primary/[0.02] p-3 hover:bg-text-primary/[0.04] transition">
      <div className="mb-1.5 flex items-center justify-between">
        <p className="text-[10px] font-bold text-text-primary">{item.ticker}</p>
        <span className="text-[8px] text-text-muted">{item.name}</span>
      </div>
      <p className="text-[16px] font-black text-text-primary leading-none">{item.adr_price}</p>
      <p className={`mt-0.5 text-[10px] font-bold ${pos ? "text-emerald-400" : "text-rose-400"}`}>{item.pct}</p>
      {item.premium_pct && item.premium_pct !== "—" && (
        <div className="mt-2 pt-2 border-t border-surface-border/5">
          <p className="text-[8px] text-text-muted mb-0.5">vs NSE ({item.nse_price})</p>
          <p className={`text-[10px] font-bold ${premPos ? "text-emerald-400" : "text-rose-400"}`}>
            {premPos ? "▲" : "▼"} {item.premium_pct}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Currency card ─────────────────────────────────────────────────────────────
function CurrencyCard({ item }: { item: any }) {
  const pos = item.positive !== false;
  const ICONS = {
    "USD/INR": <Banknote className="h-4 w-4" />,
    "EUR/INR": <Banknote className="h-4 w-4" />,
    "GBP/INR": <Banknote className="h-4 w-4" />,
  } as Record<string, React.ReactNode>;
  return (
    <div className="flex flex-col rounded-[16px] border border-surface-border/6 bg-text-primary/[0.02] p-3 hover:bg-text-primary/[0.04] transition">
      <div className="mb-1 flex items-center gap-1.5">
        <span className="flex items-center">{item.icon ?? ICONS[item.name] ?? <ArrowRightLeft className="h-4 w-4" />}</span>
        <p className="text-[9px] font-semibold text-text-muted">{item.name}</p>
      </div>
      <p className="text-[15px] font-black text-text-primary">{item.value}</p>
      <p className={`mt-0.5 text-[10px] font-bold ${pos ? "text-rose-400" : "text-emerald-400"}`}>
        {item.change_str ?? item.pct}
      </p>
    </div>
  );
}

// ── Commodity card ────────────────────────────────────────────────────────────
function CommodityCard({ item }: { item: any }) {
  const pos = item.positive !== false;
  const ICONS: Record<string, React.ReactNode> = {
    "Brent Crude": <Droplets className="h-4 w-4 text-text-secondary" />,
    "Gold":        <div className="h-4 w-4 rounded-full bg-amber-400" />,
    "Silver":      <div className="h-4 w-4 rounded-full bg-slate-300" />,
    "DXY":         <BarChart2 className="h-4 w-4" />,
    "USD/INR":     <Banknote className="h-4 w-4" />,
  };
  return (
    <div className="flex flex-col rounded-[16px] border border-surface-border/6 bg-text-primary/[0.02] p-3 hover:bg-text-primary/[0.04] transition">
      <div className="mb-1 flex items-center gap-1.5">
        <span className="flex items-center">{ICONS[item.name] ?? <TrendingUp className="h-4 w-4" />}</span>
        <p className="text-[9px] font-semibold text-text-muted truncate">{item.name}</p>
      </div>
      <p className="text-[15px] font-black text-text-primary">{item.value}</p>
      <p className={`mt-0.5 text-[10px] font-bold ${pos ? "text-emerald-400" : "text-rose-400"}`}>
        {item.change_str ?? item.pct}
      </p>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Section wrapper + shared style maps
   ═══════════════════════════════════════════════════════════════════════════ */

function Section({ icon: Icon, title, sub, children }: { icon: typeof Target; title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section>
      <div className="mb-3 flex items-center gap-2">
        <Icon className="h-4 w-4 text-violet-400" />
        <h2 className="text-[13px] font-bold uppercase tracking-widest text-text-secondary">{title}</h2>
      </div>
      {sub && <p className="mb-3 text-[12px] text-text-muted">{sub}</p>}
      {children}
    </section>
  );
}

const DIR_STYLE: Record<string, { label: string; color: string; icon: typeof TrendingUp }> = {
  Positive: { label: "Likely Positive Opening", color: "text-emerald-400", icon: TrendingUp },
  Negative: { label: "Likely Negative Opening", color: "text-rose-400",    icon: TrendingDown },
  Neutral:  { label: "Flat / Neutral Opening",  color: "text-amber-400",  icon: Minus },
};

const SESSION_LABEL: Record<string, string> = {
  pre_market:   "Pre-Market",
  pre_open:     "Pre-Open",
  open:         "Market Open",
  after_market: "After Market",
  weekend:      "Weekend",
};

const SIGNAL_DIR_STYLE: Record<string, { color: string; icon: typeof TrendingUp }> = {
  positive:   { color: "text-emerald-400", icon: TrendingUp },
  negative:   { color: "text-rose-400",    icon: TrendingDown },
  neutral:    { color: "text-amber-400",   icon: Minus },
  contextual: { color: "text-text-secondary", icon: Circle },
};

const MOMENTUM_META: Record<string, { color: string; icon: typeof TrendingUp }> = {
  rising:  { color: "text-emerald-400", icon: TrendingUp },
  falling: { color: "text-rose-400",    icon: TrendingDown },
  stable:  { color: "text-amber-400",   icon: Minus },
};

const FOCUS_DIR_STYLE: Record<string, { label: string; color: string }> = {
  positive: { label: "Positive", color: "text-emerald-400" },
  negative: { label: "Negative", color: "text-rose-400" },
  neutral:  { label: "Mixed",    color: "text-amber-400" },
};

/* ═══════════════════════════════════════════════════════════════════════════
   HERO — the one dominant briefing surface (reasoning folded in directly,
   no separate "Morning Intelligence Brief" section below it)
   ═══════════════════════════════════════════════════════════════════════════ */
function Hero({ pred, generatedAt, greeting, dateLabel, dataCoverage }: {
  pred: any; generatedAt: string | null; greeting: string; dateLabel: string;
  dataCoverage: { available: number; total: number } | null;
}) {
  const dir = DIR_STYLE[pred?.direction ?? "Neutral"];
  const DirIcon = dir.icon;
  const timeLabel = generatedAt ? new Date(generatedAt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : null;

  return (
    <div className="rounded-2xl border border-surface-border/10 bg-surface-card p-6 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sunrise className="h-4 w-4 text-amber-400" />
          <span className="text-[11px] font-bold uppercase tracking-widest text-text-secondary">{greeting}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-text-muted">{dateLabel}</span>
          {timeLabel && <span className="text-[11px] text-text-muted">· Updated {timeLabel}</span>}
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <DirIcon className={`h-8 w-8 shrink-0 ${dir.color}`} />
        <h1 className={`text-[24px] font-black leading-tight sm:text-[28px] ${dir.color}`}>{dir.label}</h1>
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-x-8 gap-y-3">
        {pred?.range_low != null && (
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-text-muted">NIFTY Expected Range</p>
            <p className="text-[22px] font-black text-text-primary tabular-nums">
              {pred.range_low >= 0 ? "+" : ""}{pred.range_low} to {pred.range_high >= 0 ? "+" : ""}{pred.range_high} pts
            </p>
          </div>
        )}
        {pred?.confidence != null && (
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-text-muted">Confidence</p>
            <p className="text-[22px] font-black text-text-primary tabular-nums">{pred.confidence}%</p>
          </div>
        )}
        {dataCoverage && (
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-text-muted">Data Coverage</p>
            <p className="text-[14px] font-bold text-text-secondary tabular-nums">{dataCoverage.available}/{dataCoverage.total} signals</p>
          </div>
        )}
      </div>

      {pred?.reasoning && (
        <p className="mt-4 max-w-2xl text-[13px] leading-6 text-text-secondary">{pred.reasoning}</p>
      )}
      {pred?.ai_generated === false && pred?.uncertainty_note && (
        <p className="mt-2 text-[11px] italic text-text-muted">{pred.uncertainty_note}</p>
      )}
      {pred?.strategy_note && (
        <p className="mt-3 text-[11px] leading-5 text-text-muted">
          <span className="font-semibold text-text-secondary">Approach: </span>{pred.strategy_note}
        </p>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   RIGHT RAIL (desktop) — "Driving The View" + "Global Markets", compact rows
   ═══════════════════════════════════════════════════════════════════════════ */
function SignalRail({ rows }: { rows: any[] }) {
  if (!rows?.length) return null;
  return (
    <div className="rounded-xl border border-surface-border/8 bg-surface-card p-4">
      <p className="mb-2.5 text-[10px] font-bold uppercase tracking-widest text-text-muted">Driving The View</p>
      <div className="divide-y divide-surface-border/6">
        {rows.map((r, i) => {
          const st = SIGNAL_DIR_STYLE[r.direction] ?? SIGNAL_DIR_STYLE.neutral;
          const RIcon = st.icon;
          return (
            <div key={i} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
              <span className="text-[11px] font-semibold text-text-secondary truncate">{r.label}</span>
              <span className={`flex shrink-0 items-center gap-1 text-[12px] font-bold tabular-nums ${st.color}`}>
                {r.value}
                <RIcon className="h-3 w-3" />
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GlobalMarketsRail({ signals }: { signals: any }) {
  const rows = [
    ...((signals?.us_futures ?? []).slice(0, 3)),
    ...((signals?.asian_markets ?? []).slice(0, 2)),
  ].filter((m: any) => m?.value && m.value !== "—");
  if (!rows.length) return null;
  return (
    <div className="rounded-xl border border-surface-border/8 bg-surface-card p-4">
      <p className="mb-2.5 text-[10px] font-bold uppercase tracking-widest text-text-muted">Global Markets</p>
      <div className="divide-y divide-surface-border/6">
        {rows.map((m: any, i: number) => {
          const pos = m.positive !== false;
          return (
            <div key={i} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
              <span className="text-[11px] font-semibold text-text-secondary truncate">{m.name}</span>
              <span className={`shrink-0 text-[12px] font-bold tabular-nums ${pos ? "text-emerald-400" : "text-rose-400"}`}>{m.pct ?? m.value}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   DEVELOPMENTS THAT MATTER
   ═══════════════════════════════════════════════════════════════════════════ */
function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.round(ms / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.round(hr / 24)}d ago`;
}
const DEV_DIR_STYLE: Record<string, string> = {
  positive: "text-emerald-400",
  negative: "text-rose-400",
  neutral:  "text-amber-400",
  mixed:    "text-amber-400",
};
function DevelopmentsThatMatter({ developments, breaking, scheduled }: {
  developments: any[]; breaking: any[]; scheduled: any[];
}) {
  const has = developments.length + breaking.length + scheduled.length > 0;
  if (!has) return null;
  return (
    <Section icon={Activity} title="Developments That Matter">
      <div className="space-y-4">
        {breaking.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {breaking.map((e: any) => (
              <span key={e.title} className="rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1.5 text-[12px] font-semibold text-amber-600 dark:text-amber-300">{e.title}</span>
            ))}
          </div>
        )}

        {developments.length > 0 && (
          <div className="divide-y divide-surface-border/6">
            {developments.map((d: any) => (
              <div key={d.id} className="py-3 first:pt-0 last:pb-0">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-[13px] font-semibold text-text-primary leading-snug">{d.title}</p>
                  <span className={`shrink-0 text-[10px] font-bold uppercase tracking-wide ${DEV_DIR_STYLE[d.direction] ?? DEV_DIR_STYLE.neutral}`}>
                    {d.direction ?? "neutral"}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-text-muted">
                  <span>Updated {timeAgo(d.last_observed_at)}</span>
                  <span>· {d.evidence_count} {d.evidence_count === 1 ? "source" : "sources"}</span>
                  {d.sectors?.length > 0 && <span>· {d.sectors.slice(0, 2).join(", ")}</span>}
                </div>
              </div>
            ))}
          </div>
        )}

        {scheduled.length > 0 && (
          <div className="divide-y divide-surface-border/6 border-t border-surface-border/6 pt-1">
            {scheduled.map((e: any) => (
              <div key={e.title} className="py-2.5 first:pt-2 last:pb-0">
                <p className="text-[12px] font-semibold text-text-primary">{e.title}</p>
                {e.description && <p className="mt-0.5 text-[10px] text-text-muted">{e.description}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </Section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   WHERE THE IMPACT MAY LAND — compact consequence chip row, full width
   ═══════════════════════════════════════════════════════════════════════════ */
function ImpactMayLand({ sectorSetup }: { sectorSetup: any[] }) {
  if (!sectorSetup?.length) return null;
  const tagged = sectorSetup.filter(s => s.impact_tag);
  const rows = tagged.length > 0 ? tagged : sectorSetup.slice(0, 5);
  return (
    <Section icon={Compass} title="Where The Impact May Land">
      <div className="flex flex-wrap items-center gap-x-7 gap-y-3">
        {rows.map(s => {
          const m = MOMENTUM_META[s.momentum] ?? MOMENTUM_META.stable;
          const MIcon = m.icon;
          return (
            <div key={s.sector} className="flex items-center gap-1.5">
              <span className="text-[13px] font-bold text-text-primary">{s.sector}</span>
              <MIcon className={`h-3.5 w-3.5 ${m.color}`} />
              {s.impact_tag && <span className="text-[10px] text-text-muted">({s.impact_tag})</span>}
            </div>
          );
        })}
      </div>
    </Section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   SECTOR SETUP + COMPANIES IN FOCUS — compact row lists, paired 50/50
   ═══════════════════════════════════════════════════════════════════════════ */
function SectorSetupRows({ sectorSetup }: { sectorSetup: any[] }) {
  if (!sectorSetup?.length) return null;
  return (
    <Section icon={Compass} title="Sector Setup">
      {/* Fixed height shared with CompaniesInFocusRows so the paired 50/50
          columns line up regardless of natural content length (sector
          rows are single-line, company rows carry a 2-line reason) —
          the shorter list just has empty room, the longer one scrolls
          internally rather than stretching the row taller than its pair. */}
      <div className="sidebar-scroll max-h-[420px] divide-y divide-surface-border/6 overflow-y-auto pr-1">
        {sectorSetup.map(s => {
          const m = MOMENTUM_META[s.momentum] ?? MOMENTUM_META.stable;
          const MIcon = m.icon;
          return (
            <div key={s.sector} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
              <span className="text-[12px] font-semibold text-text-primary">{s.sector}</span>
              <span className={`flex shrink-0 items-center gap-1.5 text-[11px] font-bold ${m.color}`}>
                {s.label}
                <MIcon className="h-3.5 w-3.5" />
              </span>
            </div>
          );
        })}
      </div>
    </Section>
  );
}

function CompaniesInFocusRows({ companies }: { companies: any[] }) {
  if (!companies?.length) return null;
  const rows = companies.slice(0, 5);
  return (
    <Section icon={Building2} title="Companies In Focus">
      <div className="sidebar-scroll max-h-[420px] divide-y divide-surface-border/6 overflow-y-auto pr-1">
        {rows.map((c: any) => {
          const st = FOCUS_DIR_STYLE[c.direction] ?? FOCUS_DIR_STYLE.neutral;
          return (
            <Link key={c.symbol} href={`/companies/${c.symbol}`}
              className="-mx-1 flex items-center justify-between gap-3 rounded px-1 py-2.5 transition first:pt-0 last:pb-0 hover:bg-text-primary/[0.03]">
              <div className="min-w-0">
                <span className="text-[12px] font-bold text-text-primary">{c.symbol}</span>
                <p className="truncate text-[10px] text-text-muted">{c.reason}</p>
              </div>
              <span className={`shrink-0 text-[10px] font-bold ${st.color}`}>{st.label}</span>
            </Link>
          );
        })}
      </div>
    </Section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   HISTORICAL SIMILAR DAYS
   ═══════════════════════════════════════════════════════════════════════════ */
function HistoricalSimilarDays({ historical }: { historical: any }) {
  const events = (historical?.similar_events ?? []).filter((e: any) => e.nifty_1d != null || e.key_lesson);
  if (events.length === 0) return null;
  return (
    <Section icon={History} title="Historical Similar Days" sub={historical.historical_accuracy_hint ?? undefined}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {events.slice(0, 4).map((e: any) => (
          <div key={e.id} className="rounded-2xl border border-surface-border/8 bg-text-primary/[0.03] p-5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-text-muted">{e.event_date}</p>
            <p className="mt-1 text-[13px] font-bold text-text-primary leading-snug">{e.event_title}</p>
            <div className="mt-3 flex items-center gap-4">
              {e.nifty_1d != null && (
                <div>
                  <p className="text-[9px] uppercase tracking-wide text-text-muted">Result (1D)</p>
                  <p className={`text-[16px] font-black ${e.nifty_1d >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {e.nifty_1d >= 0 ? "+" : ""}{e.nifty_1d}%
                  </p>
                </div>
              )}
              {e.confidence != null && (
                <div>
                  <p className="text-[9px] uppercase tracking-wide text-text-muted">Confidence</p>
                  <p className="text-[16px] font-black text-text-primary">{e.confidence}%</p>
                </div>
              )}
            </div>
            {e.key_lesson && (
              <p className="mt-3 text-[11px] leading-5 text-text-secondary">
                <span className="font-bold text-text-muted">Key lesson: </span>{e.key_lesson}
              </p>
            )}
          </div>
        ))}
      </div>
    </Section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   WEEKEND → MONDAY SETUP (conditional)
   ═══════════════════════════════════════════════════════════════════════════ */
function WeekendSetup({ adjustment, watchlist }: { adjustment: any; watchlist: any }) {
  if (!adjustment?.applied) return null;
  return (
    <Section icon={Moon} title="Weekend → Monday Setup" sub="Weekend developments folded into today's opening read.">
      <div className="rounded-2xl border border-surface-border/8 bg-text-primary/[0.03] p-6">
        <div className="flex flex-wrap items-center gap-6">
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-text-muted">Friday-Close Score</p>
            <p className="text-[16px] font-bold text-text-primary">{adjustment.base_score >= 0 ? "+" : ""}{adjustment.base_score}</p>
          </div>
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-text-muted">Weekend Adjustment</p>
            <p className={`text-[16px] font-bold ${adjustment.adjustment >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {adjustment.adjustment >= 0 ? "+" : ""}{adjustment.adjustment}
            </p>
          </div>
          <div>
            <p className="text-[9px] font-bold uppercase tracking-widest text-text-muted">Monday Setup</p>
            <p className="text-[16px] font-bold text-text-primary">{adjustment.final_direction} ({adjustment.final_score >= 0 ? "+" : ""}{adjustment.final_score})</p>
          </div>
        </div>
        <p className="mt-4 text-[12px] leading-5 text-text-secondary">{adjustment.reason}</p>
        {(watchlist?.sectors?.length > 0 || watchlist?.companies?.length > 0) && (
          <div className="mt-4 border-t border-surface-border/6 pt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {watchlist.sectors?.length > 0 && (
              <div>
                <p className="mb-1.5 text-[9px] font-bold uppercase tracking-widest text-text-muted">Weekend Sector Signals</p>
                <div className="flex flex-wrap gap-1.5">
                  {watchlist.sectors.map((s: any) => (
                    <span key={s.sector} className="rounded-full border border-surface-border/15 bg-text-primary/[0.04] px-2.5 py-1 text-[11px] text-text-secondary">{s.sector} ({s.direction})</span>
                  ))}
                </div>
              </div>
            )}
            {watchlist.companies?.length > 0 && (
              <div>
                <p className="mb-1.5 text-[9px] font-bold uppercase tracking-widest text-text-muted">Weekend Company Signals</p>
                <div className="flex flex-wrap gap-1.5">
                  {watchlist.companies.map((c: any) => (
                    <span key={c.symbol} className="rounded-full border border-surface-border/15 bg-text-primary/[0.04] px-2.5 py-1 text-[11px] text-text-secondary">{c.symbol} ({c.state})</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {watchlist?.note && <p className="mt-3 text-[10px] text-text-muted">{watchlist.note}</p>}
      </div>
    </Section>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN TAB
   ═══════════════════════════════════════════════════════════════════════════ */

export function PreMarketTab({ initialData }: { initialData?: any }) {
  const [data, setData] = useState<any>(initialData ?? null);
  const [prediction, setPrediction] = useState<any>(null);
  const [insights, setInsights] = useState<any[]>([]);
  const [developments, setDevelopments] = useState<any[]>([]);
  const [session, setSession] = useState<any>(null);
  const [loading, setLoading] = useState(!initialData);
  const [showRawData, setShowRawData] = useState(false);
  const { label: countdownLabel, isOpen, greeting } = useCountdown();

  useEffect(() => {
    const load = async () => {
      try {
        const safe = (p: Promise<any>) => p.catch(() => null);
        const [pmRes, opRes, inRes, devRes, sessRes] = await Promise.all([
          safe(fetch(`${API}/api/market/premarket`).then(r => r.ok ? r.json() : null)),
          safe(fetch(`${API}/api/market/opening-prediction`).then(r => r.ok ? r.json() : null)),
          safe(fetch(`${API}/api/insights/?limit=6`).then(r => r.ok ? r.json() : null)),
          safe(fetch(`${API}/api/market/developments?limit=6`).then(r => r.ok ? r.json() : null)),
          safe(fetch(`${API}/api/market/session`).then(r => r.ok ? r.json() : null)),
        ]);
        if (pmRes) setData(pmRes);
        if (opRes) setPrediction(opRes);
        if (inRes?.items) setInsights(inRes.items);
        if (devRes?.items) setDevelopments(devRes.items);
        if (sessRes) setSession(sessRes);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) return (
    <div className="space-y-4">
      {[1, 2, 3, 4].map(i => (
        <div key={i} className="h-28 rounded-xl border border-surface-border/5 bg-text-primary/[0.02] animate-pulse" />
      ))}
    </div>
  );

  const adrs: any[] = data?.adrs ?? [];
  const pred = prediction?.prediction ?? null;
  const events = prediction?.events ?? { today: [], tomorrow: [], mie_signals: [] };

  const sessionLabel = session ? (SESSION_LABEL[session.session] ?? session.session) : null;
  const dateLabel = session?.date ?? new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
  const MAX_SIGNALS = 5;
  const dataCoverage = prediction?.signal_breakdown
    ? { available: prediction.signal_breakdown.length, total: MAX_SIGNALS }
    : null;

  return (
    <div className="space-y-8">

      {/* ── Status strip ──────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        {sessionLabel && (
          <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-400">
            {sessionLabel}
          </span>
        )}
        {countdownLabel && (
          <div className={`flex items-center gap-1.5 rounded-full border px-3 py-0.5 text-[9px] font-bold ${
            isOpen
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
              : "border-sky-500/20 bg-sky-500/[0.07] text-sky-400"
          }`}>
            {!isOpen && <span className="inline-block h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />}
            {countdownLabel}
          </div>
        )}
      </div>

      {/* ── TOP ZONE: 68/32 editorial split at xl+, single column below ─────
          Explicit grid placement (col-start/row-start, not `order` alone)
          keeps Hero + Developments in the left column and the evidence
          rail spanning both its rows on the right at xl+; below xl the
          items fall back to `order` for the tablet/mobile read sequence:
          Hero → Driving The View → Developments (per explicit layout
          direction — the rail is NOT a permanent sidebar down the page,
          only this top zone). ── */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_320px]">
        <div className="order-1 min-w-0 xl:order-none xl:col-start-1 xl:row-start-1">
          <Hero pred={pred} generatedAt={prediction?.generated_at ?? null} greeting={greeting}
                dateLabel={dateLabel} dataCoverage={dataCoverage} />
        </div>

        <div className="order-3 min-w-0 xl:order-none xl:col-start-1 xl:row-start-2">
          <DevelopmentsThatMatter developments={developments} breaking={events.mie_signals} scheduled={events.today} />
        </div>

        <div className="order-2 space-y-5 xl:order-none xl:col-start-2 xl:row-start-1 xl:row-span-2">
          <SignalRail rows={prediction?.signal_breakdown ?? []} />
          <GlobalMarketsRail signals={prediction?.signals} />
        </div>
      </div>

      {/* ── Full width: Where The Impact May Land ────────────────────────── */}
      <ImpactMayLand sectorSetup={prediction?.sector_setup ?? []} />

      {/* ── 50/50: Sector Setup | Companies In Focus ─────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectorSetupRows sectorSetup={prediction?.sector_setup ?? []} />
        <CompaniesInFocusRows companies={prediction?.companies_in_focus ?? []} />
      </div>

      {/* ── Full width: Historical Setup ─────────────────────────────────── */}
      <HistoricalSimilarDays historical={prediction?.historical} />

      {/* ── Full width: Weekend → Monday Setup (conditional) ─────────────── */}
      <WeekendSetup adjustment={prediction?.weekend_adjustment} watchlist={prediction?.weekend_watchlist} />

      {/* ── Full width: Latest Intelligence (AI-authored longer-form —
             distinct from the deduplicated Developments feed above) ─────── */}
      {insights.length > 0 && (
        <Section icon={Newspaper} title="Latest Intelligence">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {insights.map((a: any) => (
              <Link key={a.slug} href={`/newsroom/article/${a.slug}`}
                className="group rounded-xl border border-surface-border/7 bg-text-primary/[0.03] p-4 transition hover:border-violet-500/25 hover:bg-text-primary/[0.05]">
                <h3 className="text-[13px] font-bold leading-snug text-text-primary line-clamp-2 group-hover:text-violet-700 dark:text-violet-200 transition">{a.headline}</h3>
                {(a.key_takeaway || a.executive_summary) && (
                  <p className="mt-1.5 line-clamp-2 text-[11px] leading-5 text-text-muted">{a.key_takeaway ?? a.executive_summary}</p>
                )}
                <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-bold text-violet-400 group-hover:text-violet-600 dark:text-violet-300">
                  Read Intelligence <ChevronRight className="h-3 w-3" />
                </div>
              </Link>
            ))}
          </div>
        </Section>
      )}

      {/* ── Full width, collapsed by default: Raw Market Data ────────────── */}
      <section>
        <button
          type="button"
          onClick={() => setShowRawData(v => !v)}
          className="mb-3 flex w-full items-center gap-2 text-left"
        >
          <BarChart2 className="h-4 w-4 text-violet-400" />
          <h2 className="text-[13px] font-bold uppercase tracking-widest text-text-secondary">Raw Market Data</h2>
          <ChevronDown className={`ml-auto h-4 w-4 text-text-muted transition-transform ${showRawData ? "rotate-180" : ""}`} />
        </button>
        {showRawData && (
          <div className="space-y-4 opacity-90">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <GiftNiftyHero  data={data?.gift_nifty} />
              <BankNiftyCard  data={data?.banknifty_futures} />
              <IndiaVIXCard   data={data?.india_vix} />
            </div>

            {data?.fii_dii && <FIIDIICard data={data.fii_dii} />}

            {data?.us_futures?.length > 0 && (
              <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
                <div className="mb-3 flex items-center gap-2">
                  <span className="text-base">🇺🇸</span>
                  <h3 className="text-[13px] font-bold text-text-primary">US Futures</h3>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {data.us_futures.map((f: any) => <USFutureCard key={f.name} item={f} />)}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {data?.asian?.length > 0 && (
                <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <span className="text-base">🌏</span>
                    <h3 className="text-[13px] font-bold text-text-primary">Asian Markets</h3>
                  </div>
                  <div className="space-y-2">
                    {data.asian.map((m: any) => <MarketRow key={m.name} item={m} />)}
                  </div>
                </div>
              )}
              {data?.european?.length > 0 && (
                <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <Globe2 size={14} strokeWidth={1.8} className="text-text-secondary"/>
                    <h3 className="text-[13px] font-bold text-text-primary">European Markets</h3>
                  </div>
                  <div className="space-y-2">
                    {data.european.map((m: any) => <MarketRow key={m.name} item={m} />)}
                  </div>
                </div>
              )}
            </div>

            {adrs.length > 0 && (
              <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
                <div className="mb-3 flex items-center gap-2">
                  <span className="text-base">🗽</span>
                  <h3 className="text-[13px] font-bold text-text-primary">Indian ADRs</h3>
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {adrs.map((a: any) => <ADRCard key={a.ticker} item={a} />)}
                </div>
              </div>
            )}

            <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
              <h3 className="mb-4 text-[13px] font-bold text-text-primary">Currencies & Commodities</h3>
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <div>
                  <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.16em] text-text-muted">Currency Pairs</p>
                  <div className="grid grid-cols-3 gap-2">
                    {(data?.currencies ?? []).map((c: any) => <CurrencyCard key={c.name} item={c} />)}
                  </div>
                </div>
                <div>
                  <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.16em] text-text-muted">Commodities</p>
                  <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                    {(data?.commodities ?? []).map((c: any) => <CommodityCard key={c.name} item={c} />)}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </section>

    </div>
  );
}
