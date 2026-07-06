"use client";

import React, { useEffect, useState, useRef } from "react";
import Link from "next/link";
import {
  Droplets, BarChart2, Banknote, ArrowRightLeft,
  TrendingUp, Sparkles,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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

// ── Global sentiment pill ─────────────────────────────────────────────────────
function GlobalMoodPill({ score }: { score?: number }) {
  if (score == null) return null;
  const label = score >= 65 ? "Bullish" : score >= 40 ? "Mixed" : "Cautious";
  const cls   = score >= 65
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
    : score >= 40
    ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
    : "border-rose-500/30 bg-rose-500/10 text-rose-400";
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${cls}`}>
      Global Mood: {score} · {label}
    </span>
  );
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
    <div className={`rounded-xl border ${bc} bg-[#0a0d16] p-5`}>

      <div className="mb-3 flex items-start justify-between">
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

      <div className="flex items-baseline gap-3 mb-1">
        <p className="text-[34px] font-black tracking-tight text-white leading-none tabular-nums">{data.value}</p>
        <p className={`text-[17px] font-bold tabular-nums ${tc}`}>{data.pct}</p>
      </div>
      <p className={`text-[12px] font-semibold ${tc}`}>{data.change}</p>

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
    <div className={`relative overflow-hidden rounded-xl border ${bc} bg-[#0a0d16] p-5`}>
      <div className="mb-3 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Bank Nifty Futures</span>
          </div>
          <p className="mt-0.5 text-[10px] text-slate-600">{data.note ?? "NSE near-month contract"}</p>
        </div>
        <MiniChart chart={data.chart} positive={pos} />
      </div>

      <div className="flex items-baseline gap-3 mb-1">
        <p className="text-[28px] font-black tracking-tight text-white leading-none">{data.value}</p>
        <p className={`text-[15px] font-bold ${tc}`}>{data.pct}</p>
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
    <div className="relative overflow-hidden rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">India VIX</span>
        <MiniChart chart={data.chart} positive={!pos} />
      </div>

      <div className="mb-2 flex items-baseline gap-2">
        <p className="text-[30px] font-black tracking-tight text-white leading-none">{data.value}</p>
        <p className={`text-[13px] font-bold ${pos ? "text-rose-400" : "text-emerald-400"}`}>{data.pct}</p>
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
    <div className="rounded-[20px] border border-white/[0.07] bg-[#0a0d16] px-5 py-4">
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
          <p className={`text-[22px] font-black leading-none ${fiiPos ? "text-emerald-400" : "text-rose-400"}`}>
            {fmt(fii)}
          </p>
          <p className="text-[10px] text-slate-500">{fiiPos ? "Net Buying" : "Net Selling"}</p>
          {(data.fii_buy || data.fii_sell) && (
            <div className="mt-1 flex gap-3 text-[9px] text-slate-600">
              <span>Buy: ₹{(data.fii_buy ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}Cr</span>
              <span>Sell: ₹{(data.fii_sell ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}Cr</span>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1 border-l border-white/[0.06] pl-4">
          <p className="text-[9px] font-semibold uppercase tracking-wider text-slate-600">DII</p>
          <p className={`text-[22px] font-black leading-none ${diiPos ? "text-emerald-400" : "text-rose-400"}`}>
            {fmt(dii)}
          </p>
          <p className="text-[10px] text-slate-500">{diiPos ? "Net Buying" : "Net Selling"}</p>
          {(data.dii_buy || data.dii_sell) && (
            <div className="mt-1 flex gap-3 text-[9px] text-slate-600">
              <span>Buy: ₹{(data.dii_buy ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}Cr</span>
              <span>Sell: ₹{(data.dii_sell ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}Cr</span>
            </div>
          )}
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
      <p className="text-[20px] font-black text-white leading-none mb-1">{item.value}</p>
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

// ── AI Opening Prediction with PCR ────────────────────────────────────────────
function AIPrediction({ data, pcr }: { data: any; pcr?: any }) {
  if (!data) return null;
  const { sentiment, bull_pct, neutral_pct, bear_pct, confidence, reasons, opening_strategy } = data;
  const sentColor = sentiment === "Bullish" ? "text-emerald-400" : sentiment === "Bearish" ? "text-rose-400" : "text-amber-400";
  const sentBg    = sentiment === "Bullish" ? "bg-emerald-500/10 border-emerald-500/20" : sentiment === "Bearish" ? "bg-rose-500/10 border-rose-500/20" : "bg-amber-500/10 border-amber-500/20";

  const R = 42, CX = 52, CY = 52, circ = 2 * Math.PI * R;
  const bullDash = (bull_pct / 100) * circ;
  const neutDash = (neutral_pct / 100) * circ;
  const bearDash = (bear_pct / 100) * circ;

  const PCR_COLOR: Record<string, string> = {
    emerald: "text-emerald-400 border-emerald-500/25 bg-emerald-500/10",
    amber:   "text-amber-400   border-amber-500/25   bg-amber-500/10",
    orange:  "text-orange-400  border-orange-500/25  bg-orange-500/10",
    rose:    "text-rose-400    border-rose-500/25    bg-rose-500/10",
    slate:   "text-slate-400   border-slate-500/25   bg-slate-500/10",
  };

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-500/20 text-violet-400"><svg viewBox="0 0 24 24" fill="currentColor" className="h-3 w-3"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg></span>
          <h3 className="text-[13px] font-bold text-white">AI Opening Prediction</h3>
        </div>
        <span className="rounded-full border border-violet-500/25 bg-violet-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-violet-400">
          Live AI
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative shrink-0">
          <svg width="104" height="104" viewBox="0 0 104 104">
            <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="14"/>
            <circle cx={CX} cy={CY} r={R} fill="none" stroke="#f43f5e" strokeWidth="14"
              strokeDasharray={`${bearDash} ${circ - bearDash}`}
              strokeDashoffset={-(bullDash + neutDash)} strokeLinecap="butt" transform="rotate(-90,52,52)"/>
            <circle cx={CX} cy={CY} r={R} fill="none" stroke="#f59e0b" strokeWidth="14"
              strokeDasharray={`${neutDash} ${circ - neutDash}`}
              strokeDashoffset={-bullDash} strokeLinecap="butt" transform="rotate(-90,52,52)"/>
            <circle cx={CX} cy={CY} r={R} fill="none" stroke="#22c55e" strokeWidth="14"
              strokeDasharray={`${bullDash} ${circ - bullDash}`}
              strokeDashoffset="0" strokeLinecap="butt" transform="rotate(-90,52,52)"/>
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <p className="text-[13px] font-black text-white">{confidence}%</p>
            <p className="text-[8px] text-slate-500">Confidence</p>
          </div>
        </div>

        <div className="flex-1 space-y-1.5">
          <p className={`text-[22px] font-black ${sentColor}`}>{sentiment}</p>
          <div className="space-y-1">
            {([["Bullish", bull_pct, "#22c55e"], ["Neutral", neutral_pct, "#f59e0b"], ["Bearish", bear_pct, "#f43f5e"]] as const).map(([l, p, c]) => (
              <div key={l} className="flex items-center gap-2">
                <div className="h-1.5 w-1.5 rounded-full shrink-0" style={{ background: c }}/>
                <span className="text-[10px] text-slate-500 w-12">{l}</span>
                <div className="flex-1 h-1 rounded-full bg-white/[0.05]">
                  <div className="h-full rounded-full transition-all duration-700" style={{ width: `${p}%`, background: c }}/>
                </div>
                <span className="text-[10px] font-bold text-slate-400 w-7 text-right">{p}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* PCR row */}
      {pcr?.available && pcr.pcr != null && (
        <div className={`flex items-center justify-between rounded-xl border px-3 py-2 ${PCR_COLOR[pcr.color ?? "slate"]}`}>
          <div className="flex items-center gap-2">
            <span className="text-[9px] font-bold uppercase tracking-wider opacity-70">Put-Call Ratio</span>
            <span className="text-[14px] font-black">{pcr.pcr}</span>
            <span className={`rounded-full border px-2 py-0.5 text-[8px] font-bold uppercase ${PCR_COLOR[pcr.color ?? "slate"]}`}>
              {pcr.label}
            </span>
          </div>
          {pcr.max_pain && (
            <div className="text-right">
              <p className="text-[8px] opacity-60">Max Pain</p>
              <p className="text-[11px] font-bold">{pcr.max_pain.toLocaleString("en-IN")}</p>
            </div>
          )}
        </div>
      )}

      <div>
        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600">Key Signals</p>
        <ul className="space-y-1">
          {(reasons ?? []).slice(0, 6).map((r: string, i: number) => (
            <li key={i} className="flex items-start gap-1.5 text-[11px] text-slate-400">
              <span className="text-emerald-500 mt-0.5 shrink-0">•</span>{r}
            </li>
          ))}
        </ul>
      </div>

      {opening_strategy && (
        <div className={`rounded-xl border px-3 py-2 text-[11px] leading-5 text-slate-300 ${sentBg}`}>
          <span className={`font-bold mr-1 ${sentColor}`}>Strategy:</span>
          {opening_strategy}
        </div>
      )}
    </div>
  );
}

// ── Stocks to Watch ───────────────────────────────────────────────────────────
function StocksToWatch({ stocks }: { stocks: any[] }) {
  if (!stocks?.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-[13px] font-bold text-white">Stocks to Watch Today</h3>
        <Link href="/stocks" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>
      <div className="space-y-2">
        {stocks.map((s: any) => (
          <Link key={s.ticker} href={`/companies/${s.ticker}`}
            className="flex items-center gap-3 rounded-2xl border border-white/[0.05] bg-white/[0.02] px-4 py-3 hover:border-sky-500/15 hover:bg-white/[0.04] transition">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/[0.07] text-[10px] font-bold text-slate-300">
              {s.ticker.slice(0, 3)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[12px] font-bold text-white">{s.ticker}</p>
              <p className="text-[10px] text-slate-500 truncate">{s.reason}</p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className="text-[9px] rounded-full bg-white/[0.04] px-2 py-0.5 text-slate-500">{s.sector}</span>
              <div className={`flex h-8 w-8 items-center justify-center rounded-xl text-[11px] font-black ${
                s.score >= 85 ? "bg-emerald-500/15 text-emerald-400" :
                s.score >= 75 ? "bg-sky-500/15 text-sky-400" :
                "bg-amber-500/15 text-amber-400"
              }`}>{s.score}</div>
              <svg viewBox="0 0 24 24" fill="none" stroke={s.direction === "up" ? "#22c55e" : s.direction === "down" ? "#f43f5e" : "#64748b"} strokeWidth="2" className="h-4 w-4">
                {s.direction === "up"   ? <polyline points="18 15 12 9 6 15"/> :
                 s.direction === "down" ? <polyline points="6 9 12 15 18 9"/> :
                                          <line x1="5" y1="12" x2="19" y2="12"/>}
              </svg>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

// ── Pre-Market Movers ─────────────────────────────────────────────────────────
function PreMarketMovers({ movers }: { movers: any }) {
  const [tab, setTab] = useState<"gainers" | "losers" | "active">("gainers");
  const rows = movers?.[tab] ?? [];
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[13px] font-bold text-white">Pre-Market Movers</h3>
        <Link href="/stocks" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>
      <div className="mb-3 flex gap-0.5 rounded-xl bg-white/[0.04] p-0.5">
        {(["gainers", "losers", "active"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 rounded-lg py-1.5 text-[11px] font-medium capitalize transition ${
              tab === t ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"
            }`}>
            {t === "active" ? "Most Active" : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      <div className="space-y-1.5">
        {rows.map((r: any) => (
          <Link key={r.ticker} href={`/companies/${r.ticker}`}
            className="flex items-center justify-between rounded-xl border border-white/[0.04] bg-white/[0.02] px-3 py-2 hover:border-sky-500/10 transition">
            <div className="flex items-center gap-2">
              <div className="h-7 w-7 shrink-0 flex items-center justify-center rounded-lg bg-white/[0.06] text-[8px] font-bold text-slate-400">
                {r.ticker?.slice(0, 3)}
              </div>
              <p className="text-[11px] font-semibold text-white">{r.ticker}</p>
            </div>
            <div className="text-right">
              <p className="text-[11px] font-semibold text-white">{r.subtitle}</p>
              <p className={`text-[10px] font-bold ${r.positive !== false ? "text-emerald-400" : "text-rose-400"}`}>{r.value}</p>
            </div>
          </Link>
        ))}
        {rows.length === 0 && (
          <p className="py-4 text-center text-[11px] text-slate-600">Loading market data…</p>
        )}
      </div>
    </div>
  );
}

// ── Main Pre-Market Tab ────────────────────────────────────────────────────────
export function PreMarketTab({ initialData }: { initialData?: any }) {
  const [data, setData] = useState<any>(initialData ?? null);
  const [movers, setMovers] = useState<any>(null);
  const [loading, setLoading] = useState(!initialData);
  const { label: countdownLabel, isOpen } = useCountdown();

  useEffect(() => {
    const load = async () => {
      try {
        const [pmRes, mvRes] = await Promise.all([
          fetch(`${API}/api/market/premarket`).then(r => r.ok ? r.json() : null),
          fetch(`${API}/api/market/top-movers`).then(r => r.ok ? r.json() : null),
        ]);
        if (pmRes) setData(pmRes);
        if (mvRes) setMovers(mvRes);
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

  return (
    <div className="space-y-5">

      {/* ── Tab Header with countdown + global mood ───────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-400">
          Pre-Open
        </span>
        <GlobalMoodPill score={data?.global_sentiment_score} />
        {countdownLabel && (
          <div className={`flex items-center gap-1.5 rounded-full border px-3 py-0.5 text-[9px] font-bold ${
            isOpen
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
              : "border-sky-500/20 bg-sky-500/[0.07] text-sky-400"
          }`}>
            {!isOpen && (
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />
            )}
            {countdownLabel}
          </div>
        )}
      </div>

      {/* ── Section 1: Nifty Futures | Bank Nifty | India VIX ────────────── */}
      <div className="grid grid-cols-3 gap-4">
        <GiftNiftyHero  data={data?.gift_nifty} />
        <BankNiftyCard  data={data?.banknifty_futures} />
        <IndiaVIXCard   data={data?.india_vix} />
      </div>

      {/* ── FII / DII Flows ───────────────────────────────────────────────── */}
      {data?.fii_dii && <FIIDIICard data={data.fii_dii} />}

      {/* ── Section 2: US Futures ─────────────────────────────────────────── */}
      {data?.us_futures?.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-base">🇺🇸</span>
              <h3 className="text-[13px] font-bold text-white">US Futures</h3>
              <span className="text-[10px] text-slate-500">· Overnight session</span>
            </div>
            <span className="rounded-full border border-sky-500/20 bg-sky-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-sky-400">
              Live
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {data.us_futures.map((f: any) => <USFutureCard key={f.name} item={f} />)}
          </div>
        </div>
      )}

      {/* ── Section 3: Global Markets (Asian + European) ──────────────────── */}
      <div className="grid grid-cols-2 gap-4">
        {data?.asian?.length > 0 && (
          <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
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
          <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-base">🌍</span>
              <h3 className="text-[13px] font-bold text-white">European Markets</h3>
            </div>
            <div className="space-y-2">
              {data.european.map((m: any) => <MarketRow key={m.name} item={m} />)}
            </div>
          </div>
        )}
      </div>

      {/* ── Indian ADRs ───────────────────────────────────────────────────── */}
      {adrs.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
          <div className="mb-3 flex items-center gap-2">
            <span className="text-base">🗽</span>
            <h3 className="text-[13px] font-bold text-white">Indian ADRs</h3>
            <span className="text-[10px] text-slate-500">· NYSE / NASDAQ overnight</span>
            <span className="ml-auto text-[9px] text-slate-600">↑ Premium = gap-up expected on NSE</span>
          </div>
          <div className="grid grid-cols-4 gap-3">
            {adrs.map((a: any) => <ADRCard key={a.ticker} item={a} />)}
          </div>
        </div>
      )}

      {/* ── Section 4: Currencies + Commodities ──────────────────────────── */}
      <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
        <h3 className="mb-4 text-[13px] font-bold text-white">Currencies & Commodities</h3>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-600">
              Currency Pairs · Higher = Rupee weakens
            </p>
            <div className="grid grid-cols-3 gap-2">
              {(data?.currencies ?? []).map((c: any) => <CurrencyCard key={c.name} item={c} />)}
            </div>
          </div>
          <div>
            <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-600">Commodities</p>
            <div className="grid grid-cols-5 gap-2">
              {(data?.commodities ?? []).map((c: any) => <CommodityCard key={c.name} item={c} />)}
            </div>
          </div>
        </div>
      </div>

      {/* ── Section 5: Stocks + AI + Movers ──────────────────────────────── */}
      <div className="grid grid-cols-[1fr_320px] gap-5">
        <StocksToWatch stocks={data?.stocks_to_watch ?? []} />
        <div className="space-y-5">
          <AIPrediction data={data?.ai_prediction} pcr={data?.pcr} />
          <PreMarketMovers movers={movers} />
        </div>
      </div>

    </div>
  );
}
