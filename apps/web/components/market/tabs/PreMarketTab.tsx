"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Droplets, BarChart2, Banknote, ArrowRightLeft,
  TrendingUp, TrendingDown, Minus, Globe, Sunrise, Target,
  Compass, ListChecks, History, Newspaper, Sparkles,
  ChevronRight, Gauge,
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

  useEffect(() => {
    function compute() {
      const now = new Date();
      const ist = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
      const totalMin = ist.getHours() * 60 + ist.getMinutes();
      const openMin = 9 * 60 + 15;
      const closeMin = 15 * 60 + 30;

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
        setLabel(`Opens in ${h}h ${m}m (tomorrow)`);
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

  return { label, isOpen };
}

// ── Gift Nifty / Nifty Futures hero card ──────────────────────────────────────
function GiftNiftyHero({ data }: { data: any }) {
  if (!data) return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5 animate-pulse h-48" />
  );
  const pos = data.positive !== false;
  const tc = pos ? "text-emerald-400" : "text-rose-400";
  const bc = pos ? "border-emerald-500/20" : "border-rose-500/20";
  return (
    <div className={`rounded-xl border ${bc} bg-[#080c14] p-4`}>

      <div className="mb-2.5 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Nifty Futures</span>
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-400">
              Gift City Proxy
            </span>
          </div>
          <p className="mt-0.5 text-[10px] text-slate-600">{data.note ?? "NSE near-month contract"}</p>
        </div>
        <MiniChart chart={data.chart} positive={pos} />
      </div>

      <div className="flex items-baseline gap-2.5 mb-1">
        <p className="text-[26px] font-black tracking-tight text-white leading-none tabular-nums">{data.value}</p>
        <p className={`text-[14px] font-bold tabular-nums ${tc}`}>{data.pct}</p>
      </div>
      <p className={`text-[11px] font-semibold ${tc}`}>{data.change}</p>

      {data.spot_value && (
        <div className="mt-3 flex items-center gap-3 rounded-[12px] border border-white/[0.07] bg-white/[0.04] px-3 py-2">
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-slate-500">Nifty Spot</span>
            <span className="text-[11px] font-bold text-white">{data.spot_value}</span>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="text-[9px] text-slate-500">Premium</span>
            <span className={`text-[11px] font-bold ${data.is_premium ? "text-emerald-400" : "text-rose-400"}`}>
              {data.premium_pct}
            </span>
          </div>
        </div>
      )}

      {data.opening_range && (
        <div className="mt-2 flex items-center gap-2 rounded-[10px] border border-sky-500/15 bg-sky-500/[0.06] px-3 py-1.5">
          <span className="text-[9px] text-slate-500">Expected open</span>
          <span className="text-[11px] font-bold text-sky-300">
            {data.opening_range.low} – {data.opening_range.high}
          </span>
          <span className="ml-auto text-[8px] text-slate-600">± {data.opening_range.band_pct}% band</span>
        </div>
      )}
    </div>
  );
}

// ── Bank Nifty Futures card ───────────────────────────────────────────────────
function BankNiftyCard({ data }: { data: any }) {
  if (!data) return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5 animate-pulse h-48" />
  );
  const pos = data.positive !== false;
  const tc = pos ? "text-emerald-400" : "text-rose-400";
  const bc = pos ? "border-emerald-500/15" : "border-rose-500/15";

  return (
    <div className={`relative overflow-hidden rounded-xl border ${bc} bg-[#080c14] p-4`}>
      <div className="mb-2.5 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Bank Nifty Futures</span>
          </div>
          <p className="mt-0.5 text-[10px] text-slate-600">{data.note ?? "NSE near-month contract"}</p>
        </div>
        <MiniChart chart={data.chart} positive={pos} />
      </div>

      <div className="flex items-baseline gap-2.5 mb-1">
        <p className="text-[22px] font-black tracking-tight text-white leading-none">{data.value}</p>
        <p className={`text-[13px] font-bold ${tc}`}>{data.pct}</p>
      </div>
      <p className={`text-[11px] font-semibold ${tc}`}>{data.change}</p>

      {data.spot_value && (
        <div className="mt-3 flex items-center gap-3 rounded-[10px] border border-white/[0.07] bg-white/[0.04] px-3 py-2">
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-slate-500">BNF Spot</span>
            <span className="text-[11px] font-bold text-white">{data.spot_value}</span>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="text-[9px] text-slate-500">Basis</span>
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
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] p-5 animate-pulse" />
  );
  const pos = data.positive !== false;
  const c = data.color ?? "slate";

  const BADGE: Record<string, string> = {
    emerald: "bg-emerald-500/10 border-emerald-500/25 text-emerald-400",
    amber:   "bg-amber-500/10  border-amber-500/25  text-amber-400",
    orange:  "bg-orange-500/10 border-orange-500/25 text-orange-400",
    rose:    "bg-rose-500/10   border-rose-500/25   text-rose-400",
    slate:   "bg-slate-500/10  border-slate-500/25  text-slate-400",
  };
  const TEXT: Record<string, string> = {
    emerald: "text-emerald-400", amber: "text-amber-400",
    orange: "text-orange-400",   rose: "text-rose-400", slate: "text-slate-400",
  };

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/[0.07] bg-[#080c14] p-4">
      <div className="mb-2.5 flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">India VIX</span>
        <MiniChart chart={data.chart} positive={!pos} />
      </div>

      <div className="mb-2 flex items-baseline gap-2">
        <p className="text-[22px] font-black tracking-tight text-white leading-none">{data.value}</p>
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
      <div className="rounded-[20px] border border-white/[0.06] bg-white/[0.02] px-5 py-3 flex items-center gap-3">
        <span className="text-[11px] text-slate-600">FII / DII data · {data.note ?? "NSE data unavailable"}</span>
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
    <div className="rounded-[20px] border border-white/[0.07] bg-[#080c14] px-5 py-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">FII / DII Flows</span>
          <span className="rounded-full border border-slate-500/25 bg-slate-500/10 px-2 py-0.5 text-[8px] font-bold uppercase text-slate-500">
            {data.note ?? "Previous Session"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1">
          <p className="text-[9px] font-semibold uppercase tracking-wider text-slate-600">FII / FPI</p>
          <p className={`text-[17px] font-black leading-none ${fiiPos ? "text-emerald-400" : "text-rose-400"}`}>
            {fmt(fii)}
          </p>
          <p className="text-[10px] text-slate-500">{fiiPos ? "Net Buying" : "Net Selling"}</p>
        </div>

        <div className="flex flex-col gap-1 border-l border-white/[0.06] pl-4">
          <p className="text-[9px] font-semibold uppercase tracking-wider text-slate-600">DII</p>
          <p className={`text-[17px] font-black leading-none ${diiPos ? "text-emerald-400" : "text-rose-400"}`}>
            {fmt(dii)}
          </p>
          <p className="text-[10px] text-slate-500">{diiPos ? "Net Buying" : "Net Selling"}</p>
        </div>
      </div>
    </div>
  );
}

// ── US Futures card ───────────────────────────────────────────────────────────
function USFutureCard({ item }: { item: any }) {
  const pos = item.positive !== false;
  return (
    <div className="flex flex-col rounded-[20px] border border-white/[0.07] bg-white/[0.03] p-4 hover:border-sky-500/15 hover:bg-white/[0.05] transition">
      <div className="mb-2 flex items-start justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 leading-tight max-w-[80px]">{item.name}</p>
        <MiniChart chart={item.chart} positive={pos} />
      </div>
      <p className="text-[16px] font-black text-white leading-none mb-1">{item.value}</p>
      <p className={`text-[11px] font-bold ${pos ? "text-emerald-400" : "text-rose-400"}`}>{item.pct}</p>
      <p className="text-[10px] text-slate-600 mt-0.5">{item.change}</p>
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
    <div className="flex items-center gap-3 rounded-xl border border-white/[0.04] bg-white/[0.02] px-3 py-2.5 hover:bg-white/[0.04] transition">
      <span className="inline-flex items-center justify-center rounded px-1 py-0.5 text-[9px] font-bold bg-white/10 text-slate-300 font-mono shrink-0">{flag}</span>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-semibold text-white truncate">{item.name}</p>
      </div>
      <div className="text-right shrink-0">
        <p className="text-[12px] font-bold text-white">{item.value}</p>
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
    <div className="flex flex-col rounded-[16px] border border-white/[0.06] bg-white/[0.02] p-3 hover:bg-white/[0.04] transition">
      <div className="mb-1.5 flex items-center justify-between">
        <p className="text-[10px] font-bold text-white">{item.ticker}</p>
        <span className="text-[8px] text-slate-600">{item.name}</span>
      </div>
      <p className="text-[16px] font-black text-white leading-none">{item.adr_price}</p>
      <p className={`mt-0.5 text-[10px] font-bold ${pos ? "text-emerald-400" : "text-rose-400"}`}>{item.pct}</p>
      {item.premium_pct && item.premium_pct !== "—" && (
        <div className="mt-2 pt-2 border-t border-white/[0.05]">
          <p className="text-[8px] text-slate-600 mb-0.5">vs NSE ({item.nse_price})</p>
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
    <div className="flex flex-col rounded-[16px] border border-white/[0.06] bg-white/[0.02] p-3 hover:bg-white/[0.04] transition">
      <div className="mb-1 flex items-center gap-1.5">
        <span className="flex items-center">{item.icon ?? ICONS[item.name] ?? <ArrowRightLeft className="h-4 w-4" />}</span>
        <p className="text-[9px] font-semibold text-slate-500">{item.name}</p>
      </div>
      <p className="text-[15px] font-black text-white">{item.value}</p>
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
    "Brent Crude": <Droplets className="h-4 w-4 text-slate-400" />,
    "Gold":        <div className="h-4 w-4 rounded-full bg-amber-400" />,
    "Silver":      <div className="h-4 w-4 rounded-full bg-slate-300" />,
    "DXY":         <BarChart2 className="h-4 w-4" />,
    "USD/INR":     <Banknote className="h-4 w-4" />,
  };
  return (
    <div className="flex flex-col rounded-[16px] border border-white/[0.06] bg-white/[0.02] p-3 hover:bg-white/[0.04] transition">
      <div className="mb-1 flex items-center gap-1.5">
        <span className="flex items-center">{ICONS[item.name] ?? <TrendingUp className="h-4 w-4" />}</span>
        <p className="text-[9px] font-semibold text-slate-500 truncate">{item.name}</p>
      </div>
      <p className="text-[15px] font-black text-white">{item.value}</p>
      <p className={`mt-0.5 text-[10px] font-bold ${pos ? "text-emerald-400" : "text-rose-400"}`}>
        {item.change_str ?? item.pct}
      </p>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   NEW — investor-briefing sections
   ═══════════════════════════════════════════════════════════════════════════ */

function Section({ icon: Icon, title, sub, children }: { icon: typeof Target; title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section>
      <div className="mb-3 flex items-center gap-2">
        <Icon className="h-4 w-4 text-violet-400" />
        <h2 className="text-[13px] font-bold uppercase tracking-widest text-slate-400">{title}</h2>
      </div>
      {sub && <p className="mb-3 text-[12px] text-slate-500">{sub}</p>}
      {children}
    </section>
  );
}

const DIR_STYLE: Record<string, { label: string; color: string; bg: string; icon: typeof TrendingUp }> = {
  Positive: { label: "Likely Positive Opening", color: "text-emerald-400", bg: "from-emerald-500/15 border-emerald-500/25", icon: TrendingUp },
  Negative: { label: "Likely Negative Opening", color: "text-rose-400",    bg: "from-rose-500/15 border-rose-500/25",       icon: TrendingDown },
  Neutral:  { label: "Flat / Neutral Opening",  color: "text-amber-400",  bg: "from-amber-500/15 border-amber-500/25",     icon: Minus },
};

// ── HERO ────────────────────────────────────────────────────────────────────
function Hero({ pred, topTheme, bottomTheme, topEvent, generatedAt }: {
  pred: any; topTheme: any; bottomTheme: any; topEvent: { title: string; category: string } | null; generatedAt: string | null;
}) {
  const dir = DIR_STYLE[pred?.direction ?? "Neutral"];
  const DirIcon = dir.icon;
  const now = new Date();
  const dateLabel = now.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
  const timeLabel = generatedAt ? new Date(generatedAt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : null;

  return (
    <div className={`rounded-2xl border bg-gradient-to-br ${dir.bg} to-transparent p-6 sm:p-8`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sunrise className="h-4 w-4 text-amber-400" />
          <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">Good Morning</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">{dateLabel}</span>
          {timeLabel && <span className="text-[11px] text-slate-600">· Updated {timeLabel}</span>}
        </div>
      </div>

      <h1 className="mt-3 text-[24px] font-black text-white sm:text-[30px]">Market Opening Intelligence</h1>

      <div className="mt-6 flex flex-wrap items-center gap-6">
        <div className="flex items-center gap-3">
          <DirIcon className={`h-9 w-9 ${dir.color}`} />
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">AI Opening Verdict</p>
            <p className={`text-[22px] font-black ${dir.color}`}>{dir.label}</p>
          </div>
        </div>
        {pred?.confidence != null && (
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Confidence</p>
            <p className="text-[22px] font-black text-white">{pred.confidence}%</p>
          </div>
        )}
        {pred?.range_low != null && (
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Expected Range</p>
            <p className="text-[16px] font-bold text-white">
              {pred.range_low >= 0 ? "+" : ""}{pred.range_low} to {pred.range_high >= 0 ? "+" : ""}{pred.range_high} pts
            </p>
          </div>
        )}
        <div className="ml-auto flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] font-semibold text-slate-400">
          <Gauge className="h-3.5 w-3.5" /> Read Time: 30 Seconds
        </div>
      </div>

      {pred?.ai_generated === false && pred?.uncertainty_note && (
        <p className="mt-4 text-[11px] italic text-slate-500">{pred.uncertainty_note}</p>
      )}

      <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {topTheme && (
          <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/[0.05] p-3.5">
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Today's Biggest Opportunity</p>
            <p className="mt-1 text-[15px] font-bold text-emerald-400">{topTheme.theme}</p>
          </div>
        )}
        {bottomTheme && (
          <div className="rounded-xl border border-rose-500/15 bg-rose-500/[0.05] p-3.5">
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Today's Biggest Risk</p>
            <p className="mt-1 text-[15px] font-bold text-rose-400">{bottomTheme.theme}</p>
          </div>
        )}
        {topEvent && (
          <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3.5">
            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Most Important Event</p>
            <p className="mt-1 text-[15px] font-bold text-white">{topEvent.title}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── MORNING INTELLIGENCE BRIEF ───────────────────────────────────────────────
function outlookLabel(direction: string, confidence: number): string {
  if (direction === "Positive") return confidence >= 70 ? "Bullish" : "Moderately Bullish";
  if (direction === "Negative") return confidence >= 70 ? "Bearish" : "Moderately Bearish";
  return "Neutral";
}
function MorningBrief({ pred }: { pred: any }) {
  if (!pred?.reasoning) return null;
  const outlook = outlookLabel(pred.direction, pred.confidence ?? 50);
  const paragraphs = pred.reasoning.split(/(?<=[.!?])\s+(?=[A-Z])/).filter(Boolean);
  return (
    <Section icon={Newspaper} title="Morning Intelligence Brief">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-6">
        <div className="space-y-3">
          {paragraphs.map((p: string, i: number) => (
            <p key={i} className="text-[14px] leading-7 text-slate-300">{p}</p>
          ))}
        </div>
        <div className="mt-5 flex items-center gap-2 border-t border-white/[0.06] pt-4">
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Overall Outlook</span>
          <span className={`rounded-full border px-3 py-1 text-[12px] font-bold ${
            outlook.includes("Bullish") ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400"
            : outlook.includes("Bearish") ? "border-rose-500/25 bg-rose-500/10 text-rose-400"
            : "border-amber-500/25 bg-amber-500/10 text-amber-400"
          }`}>{outlook}</span>
        </div>
      </div>
    </Section>
  );
}

// ── WHY AI THINKS THIS ───────────────────────────────────────────────────────
const PLACEHOLDER_RISKS = new Set(["AI reasoning unavailable — signal-only estimate", "Monitor pre-open session carefully"]);
function WhyAIThinks({ pred }: { pred: any }) {
  if (!pred) return null;
  const drivers = (pred.primary_drivers ?? []).map((d: string) => ({ text: d, impact: "Bullish" as const }));
  const realRisks = pred.ai_generated === false ? [] : (pred.risks ?? []).filter((r: string) => !PLACEHOLDER_RISKS.has(r));
  const risks = realRisks.map((r: string) => ({ text: r, impact: "Bearish" as const }));
  const mixed = (pred.conflicting_signals ?? []).map((s: string) => ({ text: s, impact: "Mixed" as const }));
  const reasons = [...drivers, ...risks, ...mixed];
  if (reasons.length === 0) return null;

  const IMPACT_STYLE: Record<string, { color: string; icon: typeof TrendingUp; bg: string }> = {
    Bullish: { color: "text-emerald-400", icon: TrendingUp, bg: "border-emerald-500/15 bg-emerald-500/[0.04]" },
    Bearish: { color: "text-rose-400", icon: TrendingDown, bg: "border-rose-500/15 bg-rose-500/[0.04]" },
    Mixed:   { color: "text-amber-400", icon: Minus, bg: "border-amber-500/15 bg-amber-500/[0.04]" },
  };

  return (
    <Section icon={Sparkles} title="Why AI Thinks This">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {reasons.map((r, i) => {
          const st = IMPACT_STYLE[r.impact];
          const RIcon = st.icon;
          return (
            <div key={i} className={`flex items-start gap-3 rounded-xl border p-4 ${st.bg}`}>
              <RIcon className={`mt-0.5 h-4 w-4 shrink-0 ${st.color}`} />
              <div>
                <span className={`text-[10px] font-bold uppercase tracking-wide ${st.color}`}>{r.impact}</span>
                <p className="mt-0.5 text-[13px] leading-5 text-slate-300">{r.text}</p>
              </div>
            </div>
          );
        })}
      </div>
    </Section>
  );
}

// ── WHAT IS LIKELY TO HAPPEN TODAY (sector expectations) ─────────────────────
const MOMENTUM_META: Record<string, { label: string; color: string; icon: typeof TrendingUp }> = {
  rising:  { label: "Expected Outperform", color: "text-emerald-400", icon: TrendingUp },
  falling: { label: "Likely Weak",         color: "text-rose-400",    icon: TrendingDown },
  stable:  { label: "Neutral Bias",        color: "text-amber-400",   icon: Minus },
};
function SectorExpectations({ themes }: { themes: any[] }) {
  if (themes.length === 0) return null;
  return (
    <Section icon={Compass} title="What Is Likely To Happen Today" sub="AI momentum score per theme — not a heatmap, an expectation.">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {themes.map(t => {
          const m = MOMENTUM_META[t.momentum] ?? MOMENTUM_META.stable;
          const MIcon = m.icon;
          const why = t.top_stocks?.length
            ? `${t.top_stocks.slice(0, 2).map((s: any) => s.sym).join(", ")} leading`
            : null;
          return (
            <div key={t.theme} className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-4">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-bold text-white">{t.theme}</span>
                <MIcon className={`h-4 w-4 ${m.color}`} />
              </div>
              <p className={`mt-1.5 text-[12px] font-bold ${m.color}`}>{m.label}</p>
              <div className="mt-2 flex items-center gap-2">
                <div className="h-1.5 flex-1 rounded-full bg-white/[0.06] overflow-hidden">
                  <div className={`h-full rounded-full ${m.color.replace("text-", "bg-")}`} style={{ width: `${Math.min(100, t.score)}%` }} />
                </div>
                <span className="text-[11px] font-bold text-slate-400">{t.score.toFixed(0)}</span>
              </div>
              {why && <p className="mt-2 text-[11px] text-slate-500">{why}</p>}
            </div>
          );
        })}
      </div>
    </Section>
  );
}

// ── TODAY'S MARKET STRATEGY ───────────────────────────────────────────────────
function aggressiveness(confidence: number, vix: number): string {
  if (confidence >= 70 && vix < 15) return "Aggressive";
  if (confidence >= 55 && vix < 20) return "Moderately Aggressive";
  if (vix >= 22) return "Defensive";
  return "Cautious";
}
function MarketStrategy({ strategy, focus, avoid, confidence, vix }: {
  strategy: string | null; focus: any[]; avoid: any[]; confidence: number; vix: number;
}) {
  if (!strategy && focus.length === 0) return null;
  const stance = aggressiveness(confidence, vix);
  return (
    <Section icon={Target} title="Today's Market Strategy">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-6">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">AI Strategy</span>
          <span className="rounded-full border border-violet-500/25 bg-violet-500/10 px-3 py-1 text-[12px] font-bold text-violet-300">{stance}</span>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {focus.length > 0 && (
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-500 mb-1.5">Focus</p>
              <div className="flex flex-wrap gap-1.5">
                {focus.map(t => <span key={t.theme} className="rounded-full border border-emerald-500/20 bg-emerald-500/[0.06] px-2.5 py-1 text-[11px] text-emerald-300">{t.theme}</span>)}
              </div>
            </div>
          )}
          {avoid.length > 0 && (
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-rose-500 mb-1.5">Avoid</p>
              <div className="flex flex-wrap gap-1.5">
                {avoid.map(t => <span key={t.theme} className="rounded-full border border-rose-500/20 bg-rose-500/[0.06] px-2.5 py-1 text-[11px] text-rose-300">{t.theme}</span>)}
              </div>
            </div>
          )}
        </div>
        {strategy && (
          <div className="mt-4 border-t border-white/[0.06] pt-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1.5">Ideal Approach</p>
            <p className="text-[13px] leading-6 text-slate-300">{strategy}</p>
          </div>
        )}
      </div>
    </Section>
  );
}

// ── STOCKS TO WATCH (real score, derived action label) ────────────────────────
function stockAction(score: number, direction: string): { label: string; color: string } {
  if (score >= 80 && direction === "up") return { label: "Accumulate", color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/25" };
  if (score < 55 || direction === "down") return { label: "Avoid Today", color: "text-rose-400 bg-rose-500/10 border-rose-500/25" };
  return { label: "Watch", color: "text-sky-400 bg-sky-500/10 border-sky-500/25" };
}
function StocksToWatch({ stocks }: { stocks: any[] }) {
  if (!stocks?.length) return null;
  return (
    <Section icon={Target} title="Stocks To Watch">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {stocks.slice(0, 8).map((s: any) => {
          const action = stockAction(s.score, s.direction);
          return (
            <Link key={s.ticker} href={`/companies/${s.ticker}`}
              className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-3 hover:border-violet-500/25 hover:bg-white/[0.05] transition">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/[0.07] text-[10px] font-bold text-slate-300">
                {s.ticker.slice(0, 3)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-[13px] font-bold text-white">{s.ticker}</p>
                  <span className="text-[13px] font-black text-slate-400">{s.score}</span>
                </div>
                <p className="line-clamp-1 text-[11px] text-slate-500">{s.reason}</p>
              </div>
              <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-bold ${action.color}`}>{action.label}</span>
            </Link>
          );
        })}
      </div>
    </Section>
  );
}

// ── MARKET DRIVERS (ranked, real AI order) ────────────────────────────────────
function MarketDrivers({ drivers }: { drivers: string[] }) {
  if (!drivers?.length) return null;
  return (
    <Section icon={ListChecks} title="Market Drivers" sub="Ranked in the order the AI weighted them.">
      <div className="space-y-0">
        {drivers.map((d, i) => (
          <div key={i} className="relative flex items-start gap-3 pb-4 last:pb-0">
            <div className="flex flex-col items-center">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-500/15 text-[11px] font-black text-violet-300">{i + 1}</span>
              {i < drivers.length - 1 && <span className="mt-1 h-full w-px flex-1 bg-white/10" />}
            </div>
            <p className="pt-0.5 text-[13px] leading-5 text-slate-300">{d}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

// ── GLOBAL SNAPSHOT (compact) ─────────────────────────────────────────────────
function GlobalSnapshot({ signals }: { signals: any }) {
  if (!signals) return null;
  const usPositive = (signals.us_futures ?? []).filter((f: any) => f.positive).length;
  const usTotal = (signals.us_futures ?? []).length;
  const usLabel = usTotal === 0 ? null : usPositive >= usTotal * 0.66 ? "Bullish" : usPositive <= usTotal * 0.33 ? "Bearish" : "Mixed";
  const euPositive = (signals.european_markets ?? []).filter((f: any) => f.positive).length;
  const euTotal = (signals.european_markets ?? []).length;
  const euLabel = euTotal === 0 ? null : euPositive >= euTotal * 0.66 ? "Bullish" : euPositive <= euTotal * 0.33 ? "Bearish" : "Neutral";

  const chips: { label: string; value: string; dir?: "up" | "down" }[] = [];
  if (usLabel) chips.push({ label: "US", value: usLabel });
  if (euLabel) chips.push({ label: "Europe", value: euLabel });
  if (signals.global_sentiment) chips.push({ label: "Asia + Global", value: signals.global_sentiment.label });
  if (signals.brent_crude) chips.push({ label: "Oil", value: signals.brent_crude.value, dir: signals.brent_crude.direction === "falling" ? "down" : "up" });
  if (signals.usd_inr) chips.push({ label: "USD/INR", value: signals.usd_inr.value, dir: signals.usd_inr.positive ? "up" : "down" });

  if (chips.length === 0) return null;
  return (
    <Section icon={Globe} title="Global Snapshot">
      <div className="flex flex-wrap gap-3">
        {chips.map(c => (
          <div key={c.label} className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-4 py-2">
            <span className="text-[11px] font-semibold text-slate-500">{c.label}</span>
            <span className="text-[12px] font-bold text-white">{c.value}</span>
            {c.dir && (c.dir === "up" ? <TrendingUp className="h-3 w-3 text-emerald-400" /> : <TrendingDown className="h-3 w-3 text-rose-400" />)}
          </div>
        ))}
      </div>
    </Section>
  );
}

// ── TODAY'S EVENTS ─────────────────────────────────────────────────────────────
function EventsTimeline({ events }: { events: { today: any[]; tomorrow: any[]; mie_signals: any[] } }) {
  const has = events.today.length + events.tomorrow.length + events.mie_signals.length > 0;
  if (!has) return null;
  return (
    <Section icon={ListChecks} title="Today's Events">
      <div className="space-y-4">
        {events.mie_signals.length > 0 && (
          <div>
            <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-amber-500">Breaking</p>
            <div className="flex flex-wrap gap-2">
              {events.mie_signals.map((e: any) => (
                <span key={e.title} className="rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1.5 text-[12px] font-semibold text-amber-300">{e.title}</span>
              ))}
            </div>
          </div>
        )}
        {events.today.length > 0 && (
          <div>
            <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">Today</p>
            <div className="space-y-2">
              {events.today.map((e: any) => (
                <div key={e.title} className="rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-2.5">
                  <p className="text-[13px] font-semibold text-white">{e.title}</p>
                  {e.description && <p className="mt-0.5 text-[11px] text-slate-500">{e.description}</p>}
                </div>
              ))}
            </div>
          </div>
        )}
        {events.tomorrow.length > 0 && (
          <div>
            <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">Tomorrow</p>
            <div className="space-y-2">
              {events.tomorrow.map((e: any) => (
                <div key={e.title} className="rounded-xl border border-white/[0.05] bg-white/[0.02] px-4 py-2.5">
                  <p className="text-[13px] font-semibold text-slate-300">{e.title}</p>
                  {e.description && <p className="mt-0.5 text-[11px] text-slate-500">{e.description}</p>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Section>
  );
}

// ── HISTORICAL SIMILAR DAYS ─────────────────────────────────────────────────
function HistoricalSimilarDays({ historical }: { historical: any }) {
  const events = (historical?.similar_events ?? []).filter((e: any) => e.nifty_1d != null || e.key_lesson);
  if (events.length === 0) return null;
  return (
    <Section icon={History} title="Historical Similar Days" sub={historical.historical_accuracy_hint ?? undefined}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {events.slice(0, 4).map((e: any) => (
          <div key={e.id} className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{e.event_date}</p>
            <p className="mt-1 text-[13px] font-bold text-white leading-snug">{e.event_title}</p>
            <div className="mt-3 flex items-center gap-4">
              {e.nifty_1d != null && (
                <div>
                  <p className="text-[9px] uppercase tracking-wide text-slate-600">Result (1D)</p>
                  <p className={`text-[16px] font-black ${e.nifty_1d >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {e.nifty_1d >= 0 ? "+" : ""}{e.nifty_1d}%
                  </p>
                </div>
              )}
              {e.confidence != null && (
                <div>
                  <p className="text-[9px] uppercase tracking-wide text-slate-600">Confidence</p>
                  <p className="text-[16px] font-black text-white">{e.confidence}%</p>
                </div>
              )}
            </div>
            {e.key_lesson && (
              <p className="mt-3 text-[11px] leading-5 text-slate-400">
                <span className="font-bold text-slate-500">Key lesson: </span>{e.key_lesson}
              </p>
            )}
          </div>
        ))}
      </div>
    </Section>
  );
}

// ── LATEST INTELLIGENCE ───────────────────────────────────────────────────────
function LatestIntelligence({ items }: { items: any[] }) {
  if (items.length === 0) return null;
  return (
    <Section icon={Newspaper} title="Latest Intelligence">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((a: any) => (
          <Link key={a.slug} href={`/insights/${a.slug}`}
            className="group rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 transition hover:border-violet-500/25 hover:bg-white/[0.05]">
            <h3 className="text-[13px] font-bold leading-snug text-white line-clamp-2 group-hover:text-violet-200 transition">{a.headline}</h3>
            {(a.key_takeaway || a.executive_summary) && (
              <p className="mt-1.5 line-clamp-2 text-[11px] leading-5 text-slate-500">{a.key_takeaway ?? a.executive_summary}</p>
            )}
            <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-bold text-violet-400 group-hover:text-violet-300">
              Read Intelligence <ChevronRight className="h-3 w-3" />
            </div>
          </Link>
        ))}
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
  const [themes, setThemes] = useState<any[]>([]);
  const [insights, setInsights] = useState<any[]>([]);
  const [loading, setLoading] = useState(!initialData);
  const { label: countdownLabel, isOpen } = useCountdown();

  useEffect(() => {
    const load = async () => {
      try {
        const safe = (p: Promise<any>) => p.catch(() => null);
        const [pmRes, opRes, thRes, inRes] = await Promise.all([
          safe(fetch(`${API}/api/market/premarket`).then(r => r.ok ? r.json() : null)),
          safe(fetch(`${API}/api/market/opening-prediction`).then(r => r.ok ? r.json() : null)),
          safe(fetch(`${API}/api/intelligence/market/themes`).then(r => r.ok ? r.json() : null)),
          safe(fetch(`${API}/api/insights/?limit=6`).then(r => r.ok ? r.json() : null)),
        ]);
        if (pmRes) setData(pmRes);
        if (opRes) setPrediction(opRes);
        if (thRes?.themes) setThemes(thRes.themes);
        if (inRes?.items) setInsights(inRes.items);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) return (
    <div className="space-y-4">
      {[1, 2, 3, 4].map(i => (
        <div key={i} className="h-28 rounded-xl border border-white/[0.05] bg-white/[0.02] animate-pulse" />
      ))}
    </div>
  );

  const adrs: any[] = data?.adrs ?? [];
  const pred = prediction?.prediction ?? null;
  const sortedThemes = [...themes].sort((a, b) => b.score - a.score);
  const topTheme = sortedThemes[0] ?? null;
  const bottomTheme = sortedThemes.length > 1 ? sortedThemes[sortedThemes.length - 1] : null;
  const events = prediction?.events ?? { today: [], tomorrow: [], mie_signals: [] };
  const topEvent = events.mie_signals[0] ?? events.today[0] ?? events.tomorrow[0] ?? null;
  const vixLevel = data?.india_vix?.float ?? 15;

  return (
    <div className="space-y-8">

      {/* ── Status strip ──────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-400">
          Pre-Open
        </span>
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

      {/* 1. Hero */}
      <Hero pred={pred} topTheme={topTheme} bottomTheme={bottomTheme} topEvent={topEvent} generatedAt={prediction?.generated_at ?? null} />

      {/* 2. Morning Intelligence Brief */}
      {pred && <MorningBrief pred={pred} />}

      {/* 3. Why AI Thinks This */}
      {pred && <WhyAIThinks pred={pred} />}

      {/* 4. What Is Likely To Happen Today */}
      <SectorExpectations themes={sortedThemes} />

      {/* 5. Today's Market Strategy */}
      <MarketStrategy
        strategy={data?.ai_prediction?.opening_strategy ?? null}
        focus={sortedThemes.slice(0, 3)}
        avoid={sortedThemes.filter(t => t.momentum === "falling").slice(0, 2)}
        confidence={pred?.confidence ?? 50}
        vix={vixLevel}
      />

      {/* 6. Stocks To Watch */}
      <StocksToWatch stocks={data?.stocks_to_watch ?? []} />

      {/* 7. Market Drivers */}
      {pred && <MarketDrivers drivers={pred.primary_drivers ?? []} />}

      {/* 8. Global Snapshot */}
      <GlobalSnapshot signals={prediction?.signals} />

      {/* 9. Supporting Market Data — evidence, de-emphasized */}
      <Section icon={BarChart2} title="Supporting Market Data" sub="The raw evidence behind the AI's read above.">
        <div className="space-y-4 opacity-90">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <GiftNiftyHero  data={data?.gift_nifty} />
            <BankNiftyCard  data={data?.banknifty_futures} />
            <IndiaVIXCard   data={data?.india_vix} />
          </div>

          {data?.fii_dii && <FIIDIICard data={data.fii_dii} />}

          {data?.us_futures?.length > 0 && (
            <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
              <div className="mb-3 flex items-center gap-2">
                <span className="text-base">🇺🇸</span>
                <h3 className="text-[13px] font-bold text-white">US Futures</h3>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {data.us_futures.map((f: any) => <USFutureCard key={f.name} item={f} />)}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {data?.asian?.length > 0 && (
              <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
                <div className="mb-3 flex items-center gap-2">
                  <span className="text-base">🌏</span>
                  <h3 className="text-[13px] font-bold text-white">Asian Markets</h3>
                </div>
                <div className="space-y-2">
                  {data.asian.map((m: any) => <MarketRow key={m.name} item={m} />)}
                </div>
              </div>
            )}
            {data?.european?.length > 0 && (
              <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
                <div className="mb-3 flex items-center gap-2">
                  <Globe size={14} strokeWidth={1.8} className="text-slate-400"/>
                  <h3 className="text-[13px] font-bold text-white">European Markets</h3>
                </div>
                <div className="space-y-2">
                  {data.european.map((m: any) => <MarketRow key={m.name} item={m} />)}
                </div>
              </div>
            )}
          </div>

          {adrs.length > 0 && (
            <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
              <div className="mb-3 flex items-center gap-2">
                <span className="text-base">🗽</span>
                <h3 className="text-[13px] font-bold text-white">Indian ADRs</h3>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {adrs.map((a: any) => <ADRCard key={a.ticker} item={a} />)}
              </div>
            </div>
          )}

          <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
            <h3 className="mb-4 text-[13px] font-bold text-white">Currencies & Commodities</h3>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-600">Currency Pairs</p>
                <div className="grid grid-cols-3 gap-2">
                  {(data?.currencies ?? []).map((c: any) => <CurrencyCard key={c.name} item={c} />)}
                </div>
              </div>
              <div>
                <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-600">Commodities</p>
                <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                  {(data?.commodities ?? []).map((c: any) => <CommodityCard key={c.name} item={c} />)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* 10. Today's Events */}
      <EventsTimeline events={events} />

      {/* 11. Historical Similar Days */}
      <HistoricalSimilarDays historical={prediction?.historical} />

      {/* 12. Latest Intelligence */}
      <LatestIntelligence items={insights} />

    </div>
  );
}
