"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useAlerts } from "@/components/AlertProvider";
import { LiveIntelligenceFeed } from "@/components/market/LiveIntelligenceFeed";
import { API_BASE_URL as API } from "@/lib/api";
import {
  TrendingUp, TrendingDown, Minus, ChevronDown, ChevronRight,
  Banknote, Monitor, Zap, Shield, Car, Pill, HardHat,
  ShoppingCart, Layers, Building2, LineChart, FlaskConical, BarChart2,
} from "lucide-react";


// ── Types ──────────────────────────────────────────────────────────────────────
type MarketStory = {
  text: string; mood: string; pulse: string; direction: string;
  opportunity: string; risk: string; trader_watch: string;
  investor_watch: string; sector_rotation: string;
  confidence: number | null; generated_at: string;
};
type ThemeData = {
  theme: string; score: number | null; momentum: string;
  top_stocks: string[]; news_count_24h: number; updated_at: string;
};
type FeedItem = {
  id: string; headline: string; urgency: number;
  sentiment: string; direction: string; one_liner: string;
  themes: string[]; sectors: string[]; tickers: string[];
  source: string; triaged_at: string;
};
type ReplayEntry = {
  generated_at: string; mood: string; pulse: string;
  direction: string; story: string; nifty_at: number; vix_at: number; confidence: number;
};

// ── Helpers ────────────────────────────────────────────────────────────────────
function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m ago`;
}

function moodMeta(mood: string): { cls: string; bg: string; border: string } {
  const m = (mood ?? "").toLowerCase();
  if (m.includes("bull") || m.includes("optimis") || m.includes("positive") || m.includes("strong"))
    return { cls: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/25" };
  if (m.includes("bear") || m.includes("pessim") || m.includes("negative") || m.includes("weak"))
    return { cls: "text-rose-400",    bg: "bg-rose-500/10",    border: "border-rose-500/25" };
  if (m.includes("cautious") || m.includes("mixed") || m.includes("uncertain"))
    return { cls: "text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/25" };
  return   { cls: "text-slate-400",   bg: "bg-slate-500/10",   border: "border-slate-500/20" };
}

function signalColor(text: string) {
  const t = (text ?? "").toLowerCase();
  if (/\b(up|rise|gain|lead|strong|bull|recover|advance|buy)\b/.test(t)) return "text-emerald-400";
  if (/\b(down|fall|drop|lose|weak|bear|declin|sell|pressure)\b/.test(t)) return "text-rose-400";
  return "text-amber-400";
}

function computeHealthScore(data: any, story: MarketStory | null): number {
  let s = 50;
  const niftyChg = parseFloat(data?.indices?.[0]?.change?.replace(/[^0-9.-]/g, "") ?? "0");
  const positive  = data?.indices?.[0]?.positive !== false;
  s += Math.min(Math.max((positive ? niftyChg : -niftyChg) * 4, -18), 18);

  const b = data?.breadth;
  if (b?.advances && b?.declines) {
    const ratio = b.advances / (b.advances + b.declines + 1);
    s += (ratio - 0.5) * 28;
  }

  if (story) {
    const { cls } = moodMeta(story.mood);
    if (cls === "text-emerald-400") s += 7;
    if (cls === "text-rose-400")    s -= 7;
    s += ((story.confidence ?? 50) - 50) * 0.08;
  }

  return Math.round(Math.min(Math.max(s, 0), 100));
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 1 — AI Market Story
// ─────────────────────────────────────────────────────────────────────────────
function pulseDisplay(p: string): { icon: React.ReactNode; label: string; cls: string } {
  if (p === "+") return { icon: <TrendingUp  size={10} strokeWidth={2}/>, label: "Bullish", cls: "text-emerald-400" };
  if (p === "-") return { icon: <TrendingDown size={10} strokeWidth={2}/>, label: "Bearish", cls: "text-rose-400"   };
  return              { icon: <Minus        size={10} strokeWidth={2}/>, label: "Neutral", cls: "text-amber-400"  };
}

function dirDisplay(d: string): { icon: React.ReactNode; label: string; cls: string } {
  const dl = (d ?? "").toLowerCase();
  if (dl === "up"   || dl === "rising")    return { icon: <TrendingUp  size={10} strokeWidth={2}/>, label: "Uptrend",   cls: "text-emerald-400" };
  if (dl === "down" || dl === "falling")   return { icon: <TrendingDown size={10} strokeWidth={2}/>, label: "Downtrend", cls: "text-rose-400"    };
  return                                          { icon: <Minus        size={10} strokeWidth={2}/>, label: "Sideways",  cls: "text-amber-400"   };
}

function LiveStoryPanel({ story, loading }: { story: MarketStory | null; loading: boolean }) {
  const meta  = moodMeta(story?.mood ?? "");
  const pulse = story ? pulseDisplay(story.pulse) : null;
  const dir   = story ? dirDisplay(story.direction) : null;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-violet-500/20 bg-gradient-to-br from-[#0d0e1f] to-[#080c14] p-6">
      <div className="pointer-events-none absolute -right-10 -top-10 h-52 w-52 rounded-full bg-violet-600/8 blur-3xl" />

      <div className="relative">
        {/* Header row */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="flex h-1.5 w-1.5 rounded-full bg-violet-400 animate-pulse" />
            <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-violet-400">
              AI Market Narrative
            </span>
          </div>
          {story && (
            <div className="flex flex-wrap items-center gap-3">
              <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${meta.bg} ${meta.border} ${meta.cls}`}>
                {story.mood}
              </span>
              <span className="text-[10px] text-slate-600">
                Updated {timeAgo(story.generated_at)}
              </span>
              <span className="text-[10px] font-semibold text-violet-400">
                {story.confidence === null || story.confidence === undefined ? "Confidence unscored" : `${story.confidence}% confidence`}
              </span>
            </div>
          )}
        </div>

        {/* Body */}
        {loading ? (
          <div className="space-y-2.5">
            {[1, 0.9, 0.8].map((w, i) => (
              <div key={i} className="h-4 animate-pulse rounded bg-white/[0.04]" style={{ width: `${w * 100}%` }} />
            ))}
          </div>
        ) : story ? (
          <p className="text-[15px] leading-[1.8] text-slate-200">{story.text}</p>
        ) : (
          <p className="text-[14px] italic text-slate-500">
            Market narrative will appear here during trading hours.
            The AI generates a new story every 5 minutes when market conditions change.
          </p>
        )}

        {/* Pulse grid */}
        {story && pulse && dir && (
          <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {/* Pulse */}
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2.5">
              <p className="mb-1 text-[9px] font-semibold uppercase tracking-wider text-slate-600">Pulse</p>
              <p className={`text-[18px] font-black leading-none ${pulse.cls}`}>{pulse.icon}</p>
              <p className={`mt-0.5 text-[10px] font-semibold ${pulse.cls}`}>{pulse.label}</p>
            </div>
            {/* Direction */}
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2.5">
              <p className="mb-1 text-[9px] font-semibold uppercase tracking-wider text-slate-600">Direction</p>
              <p className={`text-[18px] font-black leading-none ${dir.cls}`}>{dir.icon}</p>
              <p className={`mt-0.5 text-[10px] font-semibold ${dir.cls}`}>{dir.label}</p>
            </div>
            {/* Trader Watch */}
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2.5">
              <p className="mb-1 text-[9px] font-semibold uppercase tracking-wider text-slate-600">Trader Watch</p>
              <p className={`text-[11px] font-semibold leading-snug ${signalColor(story.trader_watch)}`}>
                {story.trader_watch || "—"}
              </p>
            </div>
            {/* Investor Watch */}
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2.5">
              <p className="mb-1 text-[9px] font-semibold uppercase tracking-wider text-slate-600">Investor Watch</p>
              <p className={`text-[11px] font-semibold leading-snug ${signalColor(story.investor_watch)}`}>
                {story.investor_watch || "—"}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Market Health Score (gauge)
// ─────────────────────────────────────────────────────────────────────────────
function MarketHealthScore({ score, story, data }: { score: number; story: MarketStory | null; data: any }) {
  const scoreColor = score >= 70 ? "#34d399" : score >= 50 ? "#fbbf24" : "#f43f5e";
  const scoreText  = score >= 70 ? "text-emerald-400" : score >= 50 ? "text-amber-400" : "text-rose-400";
  const label      = score >= 70 ? "Healthy" : score >= 50 ? "Mixed" : score >= 30 ? "Weak" : "Stressed";

  // SVG half-arc gauge
  const r = 58, cx = 80, cy = 74;
  const angle = (score / 100) * 180;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const ex = cx + r * Math.cos(toRad(180 + angle));
  const ey = cy + r * Math.sin(toRad(180 + angle));
  const large = angle > 180 ? 1 : 0;

  const niftyChg = parseFloat(data?.indices?.[0]?.change?.replace(/[^0-9.-]/g, "") ?? "0");
  const niftyPos = data?.indices?.[0]?.positive !== false;
  const b = data?.breadth;
  const advRatio = b ? b.advances / (b.advances + b.declines + 1) : 0.5;

  const ok = (v: boolean) => v ? "text-emerald-400" : "text-rose-400";

  return (
    <div className="flex flex-col rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">Market Health</p>

      <div className="flex justify-center">
        <svg width="160" height="88" viewBox="0 0 160 88">
          <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
            fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="9" strokeLinecap="round" />
          {score > 0 && (
            <path d={`M ${cx - r} ${cy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}`}
              fill="none" stroke={scoreColor} strokeWidth="9" strokeLinecap="round" />
          )}
          <text x={cx} y={cy + 2}  textAnchor="middle" fill="white"   fontSize="22" fontWeight="900">{score}</text>
          <text x={cx} y={cy + 17} textAnchor="middle" fill="#475569" fontSize="9">{label}</text>
        </svg>
      </div>

      <div className="mt-2 space-y-1.5">
        {[
          { label: "Trend",    ok: niftyPos,       note: `${niftyPos ? "+" : ""}${niftyChg.toFixed(2)}%` },
          { label: "Breadth",  ok: advRatio > 0.5, note: b ? `${b.advances}↑ ${b.declines}↓` : "—" },
          { label: "Mood",     ok: story ? moodMeta(story.mood).cls !== "text-rose-400" : true,
            note: story?.mood ?? "—" },
        ].map(({ label, ok: isOk, note }) => (
          <div key={label} className="flex items-center justify-between rounded-lg border border-white/[0.04] bg-white/[0.02] px-2.5 py-1.5">
            <span className="text-[10px] text-slate-500">{label}</span>
            <span className={`text-[11px] font-bold ${ok(isOk)}`}>{note}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 2 — What Changed
// ─────────────────────────────────────────────────────────────────────────────
function WhatChanged({ story, feed }: { story: MarketStory | null; feed: FeedItem[] }) {
  type Bullet = { text: string; kind: "up" | "down" | "alert" | "neutral" };
  const bullets: Bullet[] = [];

  if (story?.sector_rotation) {
    story.sector_rotation
      .split(/(?<=[.!?])\s+/)
      .map(s => s.trim())
      .filter(Boolean)
      .forEach(t => {
        const kind: Bullet["kind"] =
          /gain|lead|strong|recov|rise|advance|bull/i.test(t) ? "up" :
          /lose|weak|fall|declin|sell|bear|pressure|drop/i.test(t) ? "down" : "neutral";
        bullets.push({ text: t, kind });
      });
  }

  feed.filter(f => f.urgency >= 6).slice(0, 4).forEach(f => {
    const kind: Bullet["kind"] =
      f.urgency >= 8 ? "alert" :
      f.direction === "up" ? "up" :
      f.direction === "down" ? "down" : "neutral";
    bullets.push({ text: f.one_liner || f.headline, kind });
  });

  if (!bullets.length) return null;

  const dot: Record<Bullet["kind"], string> = {
    up:      "bg-emerald-400",
    down:    "bg-rose-400",
    alert:   "bg-amber-400 animate-pulse",
    neutral: "bg-slate-500",
  };

  return (
    <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
        <h3 className="text-[11px] font-bold uppercase tracking-[0.15em] text-slate-400">What Changed</h3>
        <span className="ml-auto text-[10px] text-slate-600">Since last snapshot</span>
      </div>
      <div className="grid gap-y-2 gap-x-8 sm:grid-cols-2">
        {bullets.slice(0, 8).map((b, i) => (
          <div key={i} className="flex items-start gap-2.5">
            <span className={`mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full ${dot[b.kind]}`} />
            <p className="text-[12px] leading-5 text-slate-300">{b.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Section 3 — Market Drivers
// ─────────────────────────────────────────────────────────────────────────────
function MarketDrivers({ movers }: { movers: any }) {
  const [explains, setExplains] = useState<Record<string, string>>({});
  const [open, setOpen]         = useState<string | null>(null);

  const explain = async (ticker: string) => {
    if (open === ticker) { setOpen(null); return; }
    setOpen(ticker);
    if (explains[ticker]) return;
    try {
      const r = await fetch(`${API}/api/intelligence/market/explain?symbol=${ticker}`);
      const d = await r.json();
      setExplains(p => ({ ...p, [ticker]: d.explanation }));
    } catch {
      setExplains(p => ({ ...p, [ticker]: "Unable to generate explanation." }));
    }
  };

  const active: any[] = movers?.active ?? movers?.gainers ?? [];
  if (!active.length) return null;

  return (
    <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <div className="mb-4 flex items-center gap-3">
        <h3 className="text-[11px] font-bold uppercase tracking-[0.15em] text-slate-400">Market Drivers</h3>
        <span className="text-[10px] text-slate-600">Who is actually moving today's market</span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide">
        {active.slice(0, 8).map((m: any, i: number) => {
          const pos = m.positive !== false;
          const chg = m.value ?? "—";
          const price = m.subtitle ?? "—";
          const isOpen = open === m.ticker;
          return (
            <div key={m.ticker}
              className={`w-44 shrink-0 rounded-2xl border bg-white/[0.02] p-4 transition-all ${
                isOpen ? "border-violet-500/30 bg-violet-500/5" : "border-white/[0.06] hover:border-violet-500/20"
              }`}>
              <div className="mb-2 flex items-start justify-between">
                <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-white/[0.07] text-[9px] font-black text-slate-400">
                  #{i + 1}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                  pos ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
                }`}>{chg}</span>
              </div>
              <p className="text-[14px] font-black text-white">{m.ticker}</p>
              <p className="mt-0.5 truncate text-[10px] text-slate-500">
                {(m.company ?? m.ticker).split(" ").slice(0, 3).join(" ")}
              </p>
              <p className="mt-1.5 text-[12px] font-semibold text-slate-300 tabular-nums">{price}</p>
              <button onClick={() => explain(m.ticker)}
                className={`mt-3 w-full rounded-lg py-1.5 text-[9px] font-semibold transition text-left px-2 ${
                  isOpen ? "bg-violet-500/15 text-violet-300" : "bg-white/[0.04] text-slate-500 hover:text-violet-400 hover:bg-violet-500/8"
                }`}>
                <span className="flex items-center gap-1">{isOpen ? <ChevronDown size={9} strokeWidth={2}/> : <ChevronRight size={9} strokeWidth={2}/>} Why?</span>
              </button>
              {isOpen && (
                <p className="mt-2 border-t border-white/[0.05] pt-2 text-[10px] leading-4 text-slate-400">
                  {explains[m.ticker] ?? "Generating…"}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Company Card (shared by Winners + Weak)
// ─────────────────────────────────────────────────────────────────────────────
function CompanyCard({ company, positive }: { company: any; positive: boolean }) {
  const [open, setOpen]         = useState(false);
  const [explanation, setExpl]  = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);

  const toggle = async () => {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (explanation) return;
    setFetching(true);
    try {
      const r = await fetch(`${API}/api/intelligence/market/explain?symbol=${company.ticker}`);
      const d = await r.json();
      setExpl(d.explanation);
    } catch { setExpl("Unable to generate explanation."); }
    finally   { setFetching(false); }
  };

  const chg   = company.value ?? "—";
  const price = company.subtitle ?? "—";
  const accentBorder = positive ? "border-emerald-500/12 hover:border-emerald-500/30" : "border-rose-500/12 hover:border-rose-500/30";
  const accentBg     = positive ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400";
  const accentTxt    = positive ? "text-emerald-400" : "text-rose-400";

  return (
    <div className={`rounded-2xl border ${accentBorder} bg-white/[0.02] p-4 transition`}>
      <div className="flex items-start gap-3">
        <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[9px] font-black ${accentBg}`}>
          {company.ticker?.slice(0, 3)}
        </div>
        <div className="flex-1 min-w-0">
          <Link href={`/companies/${company.ticker}`}
            className="block truncate text-[13px] font-bold text-white hover:text-violet-300 transition">
            {company.ticker}
          </Link>
          <p className="truncate text-[10px] text-slate-600">
            {(company.company ?? company.ticker).split(" ").slice(0, 3).join(" ")}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className={`text-[14px] font-black tabular-nums ${accentTxt}`}>{chg}</p>
          <p className="text-[11px] tabular-nums text-slate-400">{price}</p>
        </div>
      </div>

      <button onClick={toggle}
        className={`mt-3 flex w-full items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[10px] font-semibold transition ${
          open ? "bg-violet-500/10 text-violet-300" : "bg-white/[0.03] text-slate-500 hover:text-violet-400 hover:bg-violet-500/5"
        }`}>
        {open ? <ChevronDown size={9} strokeWidth={2}/> : <ChevronRight size={9} strokeWidth={2}/>} Why?
      </button>

      {open && (
        <div className="mt-2 border-t border-white/[0.05] pt-2">
          {fetching
            ? <div className="h-3 w-4/5 animate-pulse rounded bg-white/[0.04]" />
            : <p className="text-[11px] leading-5 text-slate-400">{explanation}</p>}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sections 4 & 5 — Winners + Weak
// ─────────────────────────────────────────────────────────────────────────────
function WinnersWeak({ movers }: { movers: any }) {
  const gainers: any[] = movers?.gainers ?? [];
  const losers:  any[] = movers?.losers  ?? [];
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <div>
        <div className="mb-3 flex items-center gap-2">
          <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-emerald-400">Today's Winners</span>
          <span className="text-[9px] text-slate-600">Companies that matter</span>
        </div>
        <div className="space-y-2.5">
          {gainers.slice(0, 5).map((c: any) => <CompanyCard key={c.ticker} company={c} positive />)}
          {!gainers.length && <p className="py-4 text-center text-[12px] text-slate-600">No data yet.</p>}
        </div>
      </div>
      <div>
        <div className="mb-3 flex items-center gap-2">
          <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-rose-400">Today's Weak</span>
          <span className="text-[9px] text-slate-600">Underperforming today</span>
        </div>
        <div className="space-y-2.5">
          {losers.slice(0, 5).map((c: any) => <CompanyCard key={c.ticker} company={c} positive={false} />)}
          {!losers.length && <p className="py-4 text-center text-[12px] text-slate-600">No data yet.</p>}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sector Intelligence
// ─────────────────────────────────────────────────────────────────────────────
type SectorStatus = { label: string; cls: string; bg: string; border: string };
function getSectorStatus(val: number): SectorStatus {
  if (val >= 2.0)  return { label: "Leading",    cls: "text-emerald-300", bg: "bg-emerald-500/12", border: "border-emerald-500/25" };
  if (val >= 0.8)  return { label: "Strong",     cls: "text-emerald-400", bg: "bg-emerald-500/8",  border: "border-emerald-500/18" };
  if (val >= 0.1)  return { label: "Gaining",    cls: "text-sky-400",     bg: "bg-sky-500/8",      border: "border-sky-500/18" };
  if (val >= -0.1) return { label: "Flat",       cls: "text-slate-400",   bg: "bg-white/[0.03]",   border: "border-white/[0.06]" };
  if (val >= -0.8) return { label: "Weakening",  cls: "text-amber-400",   bg: "bg-amber-500/8",    border: "border-amber-500/18" };
  if (val >= -2.0) return { label: "Losing",     cls: "text-rose-400",    bg: "bg-rose-500/8",     border: "border-rose-500/18" };
  return              { label: "Declining",  cls: "text-rose-300",    bg: "bg-rose-500/12",    border: "border-rose-500/25" };
}

function SectorIntelligence({ sectors }: { sectors: any[] }) {
  if (!sectors.length) return null;
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <div className="mb-4 flex items-center gap-2">
        <h3 className="text-[11px] font-bold uppercase tracking-[0.15em] text-slate-400">Sector Intelligence</h3>
        <span className="ml-auto text-[10px] text-slate-600">Status not just %</span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
        {sectors.slice(0, 12).map((s) => {
          const raw = parseFloat(s.value?.replace(/[^0-9.-]/g, "") ?? "0");
          const val = s.positive === false ? -raw : raw;
          const st  = getSectorStatus(val);
          return (
            <div key={s.name} className={`rounded-xl border ${st.border} ${st.bg} px-3 py-3`}>
              <div className="mb-1.5 flex items-start justify-between gap-1">
                <p className="text-[11px] font-semibold text-white leading-tight">{s.name}</p>
                <span className={`shrink-0 rounded-full border ${st.border} ${st.bg} px-1.5 py-0.5 text-[8px] font-bold ${st.cls}`}>
                  {st.label}
                </span>
              </div>
              <p className={`text-[15px] font-black tabular-nums ${st.cls}`}>
                {val >= 0 ? "+" : ""}{val.toFixed(2)}%
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Theme Intelligence
// ─────────────────────────────────────────────────────────────────────────────
const THEME_ICON: Record<string, React.ReactNode> = {
  "Banking":           <Banknote     size={13} strokeWidth={1.7}/>,
  "IT & Technology":   <Monitor      size={13} strokeWidth={1.7}/>,
  "Power & Energy":    <Zap          size={13} strokeWidth={1.7}/>,
  "Defence":           <Shield       size={13} strokeWidth={1.7}/>,
  "Auto & EV":         <Car          size={13} strokeWidth={1.7}/>,
  "Pharma & Healthcare":<Pill        size={13} strokeWidth={1.7}/>,
  "Infrastructure":    <HardHat      size={13} strokeWidth={1.7}/>,
  "FMCG":              <ShoppingCart size={13} strokeWidth={1.7}/>,
  "Metals & Mining":   <Layers       size={13} strokeWidth={1.7}/>,
  "Real Estate":       <Building2    size={13} strokeWidth={1.7}/>,
  "Financial Services":<LineChart    size={13} strokeWidth={1.7}/>,
  "Chemicals":         <FlaskConical size={13} strokeWidth={1.7}/>,
};

function ThemeIntelligence({ themes }: { themes: ThemeData[] }) {
  if (!themes.length) return null;
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-[11px] font-bold uppercase tracking-[0.15em] text-slate-400">Theme Intelligence</h3>
        <span className="text-[10px] text-slate-600">Ranked by momentum</span>
      </div>
      <div className="space-y-1.5">
        {themes.slice(0, 10).map((t, i) => {
          const up   = /rising|up|strong|gaining/i.test(t.momentum ?? "");
          const down = /falling|down|weak|losing/i.test(t.momentum ?? "");
          const arrow  = up ? <TrendingUp size={10} strokeWidth={2}/> : down ? <TrendingDown size={10} strokeWidth={2}/> : <Minus size={10} strokeWidth={2}/>;
          const momCls = up ? "bg-emerald-500/10 text-emerald-400" : down ? "bg-rose-500/10 text-rose-400" : "bg-slate-500/10 text-slate-400";
          const barCls = up ? "bg-emerald-500" : down ? "bg-rose-500" : "bg-slate-500";
          return (
            <div key={t.theme}
              className="flex items-center gap-3 rounded-xl border border-white/[0.04] bg-white/[0.02] px-3 py-2.5 hover:border-violet-500/15 transition">
              <span className="w-4 shrink-0 text-[10px] font-black tabular-nums text-slate-600">#{i + 1}</span>
              <span className="w-5 shrink-0 flex items-center justify-center text-slate-400">{THEME_ICON[t.theme] ?? <BarChart2 size={13} strokeWidth={1.7}/>}</span>
              <span className="flex-1 truncate text-[12px] font-semibold text-white">{t.theme}</span>
              {t.news_count_24h > 0 && (
                <span className="shrink-0 rounded-full bg-sky-500/10 px-1.5 py-0.5 text-[8px] text-sky-400">
                  {t.news_count_24h} news
                </span>
              )}
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold ${momCls}`}>
                {arrow} {t.momentum || "Stable"}
              </span>
              <div className="w-14 shrink-0 overflow-hidden rounded-full bg-white/[0.04]" style={{ height: 5 }}>
                {t.score !== null && t.score !== undefined && (
                  <div className={`h-full rounded-full ${barCls}`} style={{ width: `${Math.min(Math.max(t.score, 0), 100)}%` }} />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Opportunity + Risk
// ─────────────────────────────────────────────────────────────────────────────
function OpportunityRisk({ story, opps, feed }: { story: MarketStory | null; opps: any[]; feed: FeedItem[] }) {
  const risks = feed.filter(f => f.urgency >= 7 && f.direction === "down").slice(0, 3);

  return (
    <div className="grid gap-5 md:grid-cols-2">
      {/* Opportunity */}
      <div className="rounded-2xl border border-emerald-500/15 bg-[#080c14] p-5">
        <div className="mb-3 flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          <h3 className="text-[11px] font-bold uppercase tracking-[0.15em] text-emerald-400">Opportunity Radar</h3>
        </div>
        {story?.opportunity && (
          <p className="mb-4 text-[13px] leading-6 text-slate-300">{story.opportunity}</p>
        )}
        {opps.slice(0, 3).map((o) => (
          <div key={o.id} className="mb-2 rounded-xl border border-emerald-500/12 bg-emerald-500/[0.04] p-3">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-[11px] font-bold text-white">{o.theme || o.title || "Opportunity"}</span>
              {o.score != null && <span className="text-[10px] font-black text-emerald-400">{o.score}/100</span>}
            </div>
            <p className="line-clamp-2 text-[10px] text-slate-500">{o.reason || o.summary || ""}</p>
          </div>
        ))}
        {!story?.opportunity && !opps.length && (
          <p className="text-[12px] text-slate-600">Opportunities appear as the AI identifies them during market hours.</p>
        )}
      </div>

      {/* Risk */}
      <div className="rounded-2xl border border-rose-500/15 bg-[#080c14] p-5">
        <div className="mb-3 flex items-center gap-2">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-rose-400" />
          <h3 className="text-[11px] font-bold uppercase tracking-[0.15em] text-rose-400">Risk Radar</h3>
        </div>
        {story?.risk && (
          <p className="mb-4 text-[13px] leading-6 text-slate-300">{story.risk}</p>
        )}
        {risks.map((r) => (
          <div key={r.id} className="mb-2 rounded-xl border border-rose-500/12 bg-rose-500/[0.04] p-3">
            <div className="mb-1 flex items-center gap-2">
              <span className="rounded-full bg-rose-500/10 px-1.5 py-0.5 text-[8px] font-black text-rose-400">
                URG {r.urgency}
              </span>
              <span className="truncate text-[11px] font-bold text-white">{r.headline}</span>
            </div>
            <p className="line-clamp-1 text-[10px] text-slate-500">{r.one_liner}</p>
          </div>
        ))}
        {!story?.risk && !risks.length && (
          <p className="text-[12px] text-slate-600">Risk signals appear when the AI detects elevated urgency events.</p>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Market Breadth — Explained
// ─────────────────────────────────────────────────────────────────────────────
function BreadthExplained({ breadth }: { breadth: any }) {
  if (!breadth) return null;
  const total = (breadth.advances || 0) + (breadth.declines || 0) + (breadth.unchanged || 0) || 1;
  const advPct = breadth.advances / total;

  const narrative =
    advPct > 0.70 ? `The rally is broad-based — ${breadth.advances} of ${total} stocks are advancing. Participation is widespread, not driven by a handful of large caps.` :
    advPct > 0.55 ? `The market is advancing with moderate participation. ${breadth.advances} stocks are up vs ${breadth.declines} declining — a healthy but not overwhelming majority.` :
    advPct > 0.45 ? `Mixed signals — roughly equal buyers and sellers. The index level may not reflect the full market mood. Watch for confirmation.` :
    advPct > 0.30 ? `The index may be holding up on the back of a few heavyweight stocks. Only ${breadth.advances} of ${total} stocks are advancing — the rally is narrow.` :
    `Broad-based selling. ${breadth.declines} stocks declining vs just ${breadth.advances} advancing. The market is under meaningful pressure across all segments.`;

  return (
    <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-[11px] font-bold uppercase tracking-[0.15em] text-slate-400">Market Breadth</h3>
      </div>
      <p className="mb-4 text-[14px] leading-6 text-slate-200">{narrative}</p>
      <div className="flex items-center gap-4">
        <div className="flex h-2.5 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
          <div className="h-full bg-emerald-500 transition-all" style={{ width: `${(breadth.advances / total * 100).toFixed(1)}%` }} />
          <div className="h-full bg-slate-600" style={{ width: `${(breadth.unchanged / total * 100).toFixed(1)}%` }} />
          <div className="h-full bg-rose-500 transition-all" style={{ width: `${(breadth.declines / total * 100).toFixed(1)}%` }} />
        </div>
        <div className="flex shrink-0 items-center gap-3 text-[11px] font-bold tabular-nums">
          <span className="flex items-center gap-0.5 text-emerald-400">{breadth.advances}<TrendingUp size={9} strokeWidth={2}/></span>
          <span className="flex items-center gap-0.5 text-slate-600">{breadth.unchanged}<Minus size={9} strokeWidth={2}/></span>
          <span className="flex items-center gap-0.5 text-rose-400">{breadth.declines}<TrendingDown size={9} strokeWidth={2}/></span>
        </div>
      </div>
      {(breadth.high52w || breadth.low52w) && (
        <div className="mt-3 grid grid-cols-2 gap-2">
          {breadth.high52w && (
            <div className="flex justify-between rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2">
              <span className="text-[10px] text-slate-600">52W High</span>
              <span className="text-[11px] font-black text-emerald-400">{breadth.high52w}</span>
            </div>
          )}
          {breadth.low52w && (
            <div className="flex justify-between rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2">
              <span className="text-[10px] text-slate-600">52W Low</span>
              <span className="text-[11px] font-black text-rose-400">{breadth.low52w}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Market Replay
// ─────────────────────────────────────────────────────────────────────────────
function MarketReplay() {
  const [entries, setEntries]   = useState<ReplayEntry[]>([]);
  const [loading, setLoading]   = useState(false);
  const [open, setOpen]         = useState(false);

  const load = useCallback(() => {
    if (entries.length) return;
    setLoading(true);
    fetch(`${API}/api/intelligence/market/replay`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.entries) setEntries(d.entries); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [entries.length]);

  const toggle = () => {
    if (!open) load();
    setOpen(o => !o);
  };

  return (
    <div className="rounded-2xl border border-white/[0.07] bg-[#080c14] p-5">
      <button onClick={toggle} className="flex w-full items-center gap-3 text-left">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-violet-500/10 text-violet-400">
          {open ? <ChevronDown size={14} strokeWidth={2}/> : <ChevronRight size={14} strokeWidth={2}/>}
        </span>
        <div>
          <h3 className="text-[14px] font-bold text-white">Market Replay</h3>
          <p className="text-[10px] text-slate-600">Relive today's market — how it evolved from open to now</p>
        </div>
        <span className="ml-auto shrink-0 text-[10px] text-slate-600">{open ? "Collapse" : "Expand"}</span>
      </button>

      {open && (
        <div className="relative mt-6">
          {/* Vertical timeline spine */}
          <div className="absolute left-[18px] top-0 bottom-0 w-px bg-white/[0.06]" />

          {loading ? (
            <div className="space-y-4 pl-12">
              {[1, 2, 3].map(i => <div key={i} className="h-16 animate-pulse rounded-xl bg-white/[0.02]" />)}
            </div>
          ) : entries.length ? (
            <div className="space-y-4">
              {entries.map((e, i) => {
                const d = new Date(e.generated_at);
                const t = d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" });
                const { cls: mCls, bg: mBg, border: mBdr } = moodMeta(e.mood);
                const arrow = e.pulse === "+" ? <TrendingUp size={11} strokeWidth={2}/> : e.pulse === "-" ? <TrendingDown size={11} strokeWidth={2}/> : <Minus size={11} strokeWidth={2}/>;
                return (
                  <div key={i} className="flex items-start gap-4">
                    <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border ${mBdr} ${mBg} z-10 ${mCls}`}>
                      {arrow}
                    </div>
                    <div className="flex-1 min-w-0 rounded-xl border border-white/[0.04] bg-white/[0.02] p-3">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <span className="text-[12px] font-black tabular-nums text-white">{t}</span>
                        <span className={`rounded-full border ${mBdr} ${mBg} px-1.5 py-0.5 text-[8px] font-bold ${mCls}`}>
                          {e.mood}
                        </span>
                        {e.nifty_at ? (
                          <span className="ml-auto text-[10px] tabular-nums text-slate-600">
                            Nifty {e.nifty_at.toFixed(0)}
                          </span>
                        ) : null}
                        {e.vix_at ? (
                          <span className="text-[10px] tabular-nums text-slate-600">VIX {e.vix_at.toFixed(1)}</span>
                        ) : null}
                      </div>
                      <p className="line-clamp-3 text-[11px] leading-5 text-slate-400">{e.story}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-8 pl-12 text-center">
              <p className="text-[13px] text-slate-500">No replay data yet.</p>
              <p className="mt-1 text-[11px] text-slate-700">
                The AI snapshots the market every 5 minutes during trading hours.
                Check back after 9:15 AM IST on a trading day.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────
export function LiveMarketTab({ initialData }: { initialData?: any }) {
  const [data,         setData]         = useState<any>(initialData ?? null);
  const [story,        setStory]        = useState<MarketStory | null>(null);
  const [themes,       setThemes]       = useState<ThemeData[]>([]);
  const [feed,         setFeed]         = useState<FeedItem[]>([]);
  const [opps,         setOpps]         = useState<any[]>([]);
  const [dataLoading,  setDataLoading]  = useState(!initialData);
  const [storyLoading, setStoryLoading] = useState(true);

  const safe = <T,>(p: Promise<T>) => p.catch(() => null);

  useEffect(() => {
    const base: Promise<any>[] = [
      safe(fetch(`${API}/api/intelligence/market/story`).then(r => r.ok ? r.json() : null)),
      safe(fetch(`${API}/api/intelligence/market/themes`).then(r => r.ok ? r.json() : null)),
      safe(fetch(`${API}/api/intelligence/market/feed?limit=20`).then(r => r.ok ? r.json() : null)),
      safe(fetch(`${API}/api/market/opportunities?limit=4`).then(r => r.ok ? r.json() : null)),
    ];
    if (!initialData) {
      base.push(safe(fetch(`${API}/api/market/live`).then(r => r.ok ? r.json() : null)));
    }

    Promise.all(base).then(([storyRes, themesRes, feedRes, oppsRes, liveRes]) => {
      if (storyRes?.story) setStory(storyRes.story);
      if (themesRes?.themes) setThemes(themesRes.themes);
      if (feedRes?.feed) setFeed(feedRes.feed);
      if (oppsRes?.opportunities) setOpps(oppsRes.opportunities);
      if (liveRes) setData(liveRes);
    }).finally(() => { setDataLoading(false); setStoryLoading(false); });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Refresh story every 5 min
  useEffect(() => {
    const id = setInterval(() => {
      fetch(`${API}/api/intelligence/market/story`)
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.story) setStory(d.story); })
        .catch(() => {});
    }, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  const movers  = data?.movers  ?? null;
  const sectors = data?.sectors ?? [];
  const breadth = data?.breadth ?? null;
  const health  = computeHealthScore(data, story);

  if (dataLoading && !initialData) {
    return (
      <div className="space-y-5">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="h-36 animate-pulse rounded-2xl border border-white/[0.05] bg-white/[0.02]" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* 1 — Story + Health */}
      <div className="grid gap-5 lg:grid-cols-[1fr_220px]">
        <LiveStoryPanel story={story} loading={storyLoading} />
        <MarketHealthScore score={health} story={story} data={data} />
      </div>

      {/* 2 — What Changed */}
      {(story || feed.length > 0) && <WhatChanged story={story} feed={feed} />}

      {/* 3 — Market Drivers */}
      {movers && <MarketDrivers movers={movers} />}

      {/* 4 & 5 — Winners + Weak */}
      {movers && <WinnersWeak movers={movers} />}

      {/* 6 — Sector Intelligence */}
      {sectors.length > 0 && <SectorIntelligence sectors={sectors} />}

      {/* 7 — Theme Intelligence */}
      {themes.length > 0 && <ThemeIntelligence themes={themes} />}

      {/* 8 — Opportunity + Risk */}
      <OpportunityRisk story={story} opps={opps} feed={feed} />

      {/* 9 — Breadth Explained */}
      {breadth && <BreadthExplained breadth={breadth} />}

      {/* 10 — Live Intelligence Feed (real SSE stream: every event, score update, and alert as it happens) */}
      <LiveIntelligenceFeed />

      {/* 11 — Market Replay */}
      <MarketReplay />
    </div>
  );
}
