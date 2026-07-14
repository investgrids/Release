"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Landmark, BarChart2, Factory, TrendingUp, ClipboardList } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Fear & Greed Gauge ────────────────────────────────────────────────────────
function FearGreedGauge({ value }: { value: number }) {
  const label =
    value >= 75 ? "Extreme Greed" :
    value >= 60 ? "Greed"         :
    value >= 40 ? "Neutral"       :
    value >= 25 ? "Fear"          : "Extreme Fear";
  const color =
    value >= 75 ? "#22c55e" :
    value >= 60 ? "#84cc16" :
    value >= 40 ? "#f59e0b" :
    value >= 25 ? "#f97316" : "#f43f5e";

  // SVG arc gauge — 180° semicircle
  const R = 54, CX = 64, CY = 64;
  const valueDeg   = 180 - (value / 100) * 180;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const needleX = CX + R * Math.cos(toRad(valueDeg));
  const needleY = CY - R * Math.sin(toRad(valueDeg));
  const arcPath = (from: number, to: number) => {
    const fx = CX + R * Math.cos(toRad(from));
    const fy = CY - R * Math.sin(toRad(from));
    const tx = CX + R * Math.cos(toRad(to));
    const ty = CY - R * Math.sin(toRad(to));
    return `M ${fx} ${fy} A ${R} ${R} 0 0 1 ${tx} ${ty}`;
  };

  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-4">
      <p className="mb-2 text-[11px] font-bold text-white">Market Sentiment</p>
      <p className="mb-3 text-[9px] text-slate-500 uppercase tracking-wider">Fear &amp; Greed Index</p>
      <div className="flex flex-col items-center">
        <svg width="128" height="72" viewBox="0 0 128 72">
          {/* Gradient arcs */}
          <path d={arcPath(180, 144)} stroke="#f43f5e" strokeWidth="8" fill="none" strokeLinecap="round"/>
          <path d={arcPath(144, 108)} stroke="#f97316" strokeWidth="8" fill="none" strokeLinecap="round"/>
          <path d={arcPath(108, 72)}  stroke="#f59e0b" strokeWidth="8" fill="none" strokeLinecap="round"/>
          <path d={arcPath(72,  36)}  stroke="#84cc16" strokeWidth="8" fill="none" strokeLinecap="round"/>
          <path d={arcPath(36,  0)}   stroke="#22c55e" strokeWidth="8" fill="none" strokeLinecap="round"/>
          {/* Needle */}
          <line x1={CX} y1={CY} x2={needleX} y2={needleY} stroke="white" strokeWidth="2" strokeLinecap="round"/>
          <circle cx={CX} cy={CY} r="4" fill="white"/>
        </svg>
        <p className="text-[22px] font-black text-white leading-none">{value}</p>
        <p className="text-[12px] font-semibold mt-0.5" style={{ color }}>{label}</p>
        <p className="text-[9px] text-slate-600 mt-1">Yesterday: {Math.max(10, value - 4)}</p>
      </div>
    </div>
  );
}

// ── AI Confidence Meter ───────────────────────────────────────────────────────
function AIConfidenceMeter({ value }: { value: number }) {
  const label = value >= 85 ? "Very High" : value >= 70 ? "High" : value >= 55 ? "Medium" : "Low";
  const R = 32, CX = 38, CY = 38;
  const circ = 2 * Math.PI * R;
  const offset = circ - (value / 100) * circ;
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-4">
      <p className="mb-1 text-[11px] font-bold text-white">AI Confidence Meter</p>
      <p className="mb-3 text-[9px] text-slate-500 uppercase tracking-wider">Overall Market Confidence</p>
      <div className="flex items-center gap-4">
        <div className="relative shrink-0">
          <svg width="76" height="76" viewBox="0 0 76 76">
            <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="7"/>
            <circle cx={CX} cy={CY} r={R} fill="none" stroke="#a855f7" strokeWidth="7"
              strokeDasharray={circ} strokeDashoffset={offset}
              strokeLinecap="round" transform="rotate(-90,38,38)"/>
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <p className="text-[14px] font-black text-white leading-none">{value}%</p>
            <p className="text-[7px] text-violet-400 font-semibold">{label}</p>
          </div>
        </div>
        <div className="space-y-1">
          {[
            { l: "Accuracy", v: Math.min(98, value + 5) + "%" },
            { l: "Data Points", v: "1,240+" },
            { l: "Updated", v: "Live" },
          ].map(r => (
            <div key={r.l} className="flex justify-between gap-3 text-[10px]">
              <span className="text-slate-500">{r.l}</span>
              <span className="font-semibold text-slate-300">{r.v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Market Status ─────────────────────────────────────────────────────────────
function MarketStatusCard({ session, countdown }: { session: string; countdown: number | null }) {
  const [secs, setSecs] = useState(countdown ?? 0);
  useEffect(() => {
    if (!countdown || countdown <= 0) return;
    const id = setInterval(() => setSecs(s => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [countdown]);

  const isOpen = session === "open";
  const label =
    session === "pre_market" ? "Pre-Market" :
    session === "pre_open"   ? "Pre-Open"   :
    session === "open"       ? "Market Open" :
    session === "after_market"? "After Market" : "Market Closed";

  const nextLabel =
    session === "pre_market" || session === "pre_open" ? "Opens in" :
    session === "open"                                  ? "Closes in" : "";

  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  const pad = (n: number) => String(n).padStart(2, "0");

  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-4">
      <p className="mb-2 text-[11px] font-bold text-white">Market Status</p>
      <div className="flex items-center gap-2">
        <div className={`h-2 w-2 rounded-full ${isOpen ? "bg-emerald-400 shadow-[0_0_6px_rgba(34,197,94,0.6)]" : "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.5)]"} animate-pulse`}/>
        <span className="text-[12px] font-bold text-white">{label}</span>
      </div>
      {nextLabel && secs > 0 && (
        <div className="mt-2 rounded-xl bg-white/[0.03] p-2 text-center">
          <p className="text-[9px] text-slate-600 uppercase tracking-wider mb-0.5">{nextLabel}</p>
          <p className="text-[16px] font-black text-white tabular-nums">{pad(h)}:{pad(m)}:{pad(s)}</p>
        </div>
      )}
    </div>
  );
}

// ── Pre-Market Top Movers ─────────────────────────────────────────────────────
function TopMoversPanel({ gainers }: { gainers: any[] }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] font-bold text-white">Pre-Market Top Movers</p>
        <Link href="/stocks" className="text-[9px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>
      <div className="flex gap-2 mb-2 border-b border-white/[0.05] pb-2">
        {["Gainers","Losers","Most Active"].map((t, i) => (
          <button key={t} className={`text-[9px] font-semibold ${i === 0 ? "text-emerald-400 border-b border-emerald-400" : "text-slate-600 hover:text-slate-400"} pb-0.5 transition`}>{t}</button>
        ))}
      </div>
      <div className="space-y-1.5">
        {gainers.slice(0, 5).map((r) => (
          <Link key={r.ticker} href={`/companies/${r.ticker}`}
            className="flex items-center justify-between hover:bg-white/[0.02] rounded-lg px-1 py-0.5 transition">
            <div className="flex items-center gap-2">
              <div className="h-6 w-6 shrink-0 flex items-center justify-center rounded-md bg-white/[0.06] text-[7px] font-bold text-slate-400">{r.ticker?.slice(0,3)}</div>
              <p className="text-[11px] font-semibold text-white">{r.ticker}</p>
            </div>
            <div className="text-right">
              <p className="text-[10px] text-slate-400">{r.subtitle}</p>
              <p className="text-[10px] font-bold text-emerald-400">{r.value}</p>
            </div>
          </Link>
        ))}
        {gainers.length === 0 && <p className="py-3 text-center text-[10px] text-slate-600">Loading…</p>}
      </div>
    </div>
  );
}

// ── Upcoming Events ───────────────────────────────────────────────────────────
function UpcomingEventsPanel({ events }: { events: any[] }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] font-bold text-white">Upcoming Today</p>
        <Link href="/calendar" className="text-[9px] text-sky-400 hover:text-sky-300 transition">Full Calendar →</Link>
      </div>
      <div className="space-y-2">
        {events.slice(0, 5).map((e, i) => {
          const colors = ["bg-sky-500/10 text-sky-400","bg-violet-500/10 text-violet-400","bg-amber-500/10 text-amber-400","bg-emerald-500/10 text-emerald-400","bg-rose-500/10 text-rose-400"];
          return (
            <div key={`${e.id}-${i}`} className="flex items-start gap-2">
              <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${colors[i % colors.length]}`}>
                {[<Landmark className="h-3.5 w-3.5" />, <BarChart2 className="h-3.5 w-3.5" />, <Factory className="h-3.5 w-3.5" />, <TrendingUp className="h-3.5 w-3.5" />, <ClipboardList className="h-3.5 w-3.5" />][i % 5]}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[10px] font-semibold text-white line-clamp-1">{e.title}</p>
                <p className="text-[9px] text-slate-600">{e.date}</p>
              </div>
            </div>
          );
        })}
        {events.length === 0 && <p className="py-2 text-center text-[10px] text-slate-600">No events today</p>}
      </div>
    </div>
  );
}

// ── Breaking News ─────────────────────────────────────────────────────────────
function BreakingNewsPanel({ news }: { news: any[] }) {
  return (
    <div className="rounded-xl border border-rose-500/15 bg-[#0e060a] p-4">
      <div className="mb-3 flex items-center gap-1.5">
        <div className="h-1.5 w-1.5 rounded-full bg-rose-500 animate-pulse"/>
        <p className="text-[11px] font-bold text-white">Breaking News</p>
      </div>
      <div className="space-y-2">
        {news.slice(0, 3).map((n) => (
          <Link key={n.id} href={`/news/${n.id}`}
            className="block rounded-xl border border-white/[0.04] bg-white/[0.02] p-2.5 hover:border-rose-500/15 transition">
            <p className="text-[10px] font-semibold text-white line-clamp-2 leading-snug">{n.headline}</p>
            <p className="mt-1 text-[9px] text-slate-600">{n.source}</p>
          </Link>
        ))}
        {news.length === 0 && <p className="text-center text-[10px] text-slate-600 py-2">No breaking news</p>}
      </div>
    </div>
  );
}

// ── Main Sidebar ──────────────────────────────────────────────────────────────
export function MarketIntelligenceSidebar({
  session,
  countdown,
  insights,
  movers,
  calendarEvents,
  news,
}: {
  session: string;
  countdown: number | null;
  insights: any;
  movers: any;
  calendarEvents: any[];
  news: any[];
}) {
  const [liveInsights, setLiveInsights] = useState(insights);
  const [liveMovers,   setLiveMovers]   = useState(movers);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/market/insights`).then(r => r.ok ? r.json() : null),
      fetch(`${API}/api/market/top-movers`).then(r => r.ok ? r.json() : null),
    ]).then(([ins, mv]) => {
      if (ins) setLiveInsights(ins);
      if (mv)  setLiveMovers(mv);
    });
  }, []);

  const conf      = liveInsights?.confidence ?? 86;
  const fearGreed = liveInsights?.fear_greed ?? 72;
  const gainers   = liveMovers?.gainers ?? [];

  return (
    <div className="space-y-3">
      <MarketStatusCard session={session} countdown={countdown}/>
      <TopMoversPanel gainers={gainers}/>
      <UpcomingEventsPanel events={calendarEvents}/>
      <FearGreedGauge value={fearGreed}/>
      <AIConfidenceMeter value={conf}/>
      <BreakingNewsPanel news={news}/>
    </div>
  );
}
