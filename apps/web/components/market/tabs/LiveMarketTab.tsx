"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AreaChart, Area, ResponsiveContainer } from "recharts";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ── Market Index Card ─────────────────────────────────────────────────────────
function IndexCard({ item }: { item: any }) {
  const pos = item.positive !== false;
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-4 hover:border-sky-500/15 hover:bg-white/[0.05] transition">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">{item.name}</p>
      <p className="text-[20px] font-black text-white leading-none tabular-nums">{item.value}</p>
      <p className={`mt-1 text-[11px] font-bold ${pos ? "text-emerald-400" : "text-rose-400"}`}>{item.change}</p>
      <div className="mt-2 flex items-center justify-between text-[9px] text-slate-600">
        <span>H: {item.high}</span>
        <span>L: {item.low}</span>
      </div>
    </div>
  );
}

// ── Market Breadth ────────────────────────────────────────────────────────────
function MarketBreadth({ breadth }: { breadth: any }) {
  if (!breadth) return null;
  const total = (breadth.advances || 0) + (breadth.declines || 0) + (breadth.unchanged || 0);
  const advPct = total ? ((breadth.advances / total) * 100).toFixed(0) : 0;
  const decPct = total ? ((breadth.declines / total) * 100).toFixed(0) : 0;
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <h3 className="mb-4 text-[14px] font-bold text-white">Market Breadth</h3>
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[
          { label: "Advances",   val: breadth.advances,  color: "text-emerald-400 bg-emerald-500/10" },
          { label: "Declines",   val: breadth.declines,  color: "text-rose-400 bg-rose-500/10" },
          { label: "Unchanged",  val: breadth.unchanged, color: "text-slate-400 bg-white/[0.04]" },
        ].map(s => (
          <div key={s.label} className={`flex flex-col items-center justify-center rounded-xl py-3 ${s.color.split(" ")[1]}`}>
            <p className={`text-[22px] font-black ${s.color.split(" ")[0]}`}>{s.val ?? "—"}</p>
            <p className="text-[10px] text-slate-500 mt-0.5">{s.label}</p>
          </div>
        ))}
      </div>
      {/* Breadth bar */}
      <div className="h-2 w-full rounded-full overflow-hidden bg-white/[0.05] flex">
        <div className="h-full bg-emerald-500 transition-all duration-700" style={{ width: `${advPct}%` }}/>
        <div className="h-full bg-rose-500 transition-all duration-700"    style={{ width: `${decPct}%` }}/>
        <div className="h-full bg-slate-600 flex-1"/>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {[
          { label: "52W High", val: breadth.high52w, color: "text-emerald-400" },
          { label: "52W Low",  val: breadth.low52w,  color: "text-rose-400"    },
        ].map(s => (
          <div key={s.label} className="rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2 flex justify-between">
            <span className="text-[11px] text-slate-500">{s.label}</span>
            <span className={`text-[13px] font-black ${s.color}`}>{s.val ?? "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Sector Heatmap ────────────────────────────────────────────────────────────
function SectorHeatmap({ sectors }: { sectors: any[] }) {
  const [hovered, setHovered] = useState<string | null>(null);
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <h3 className="mb-4 text-[14px] font-bold text-white">Sector Heatmap</h3>
      <div className="grid grid-cols-4 gap-2">
        {sectors.slice(0, 12).map((s) => {
          const val = parseFloat(s.value?.replace(/[^0-9.-]/g, "") ?? "0");
          const pos = s.positive !== false;
          const intensity = Math.min(Math.abs(val) / 3, 1);
          const bg = pos
            ? `rgba(34,197,94,${0.05 + intensity * 0.25})`
            : `rgba(244,63,94,${0.05 + intensity * 0.25})`;
          const border = pos
            ? `rgba(34,197,94,${0.1 + intensity * 0.2})`
            : `rgba(244,63,94,${0.1 + intensity * 0.2})`;
          return (
            <div
              key={s.id ?? s.name}
              className="relative flex flex-col items-center justify-center rounded-2xl py-4 px-2 cursor-pointer transition-all duration-200 hover:scale-[1.02]"
              style={{ background: bg, border: `1px solid ${border}` }}
              onMouseEnter={() => setHovered(s.name)}
              onMouseLeave={() => setHovered(null)}
            >
              <p className="text-[10px] font-medium text-slate-400 text-center leading-tight">{s.name}</p>
              <p className={`text-[14px] font-black mt-1 ${pos ? "text-emerald-400" : "text-rose-400"}`}>
                {s.value?.startsWith("+") || s.value?.startsWith("-") ? s.value : `${pos ? "+" : ""}${s.value}%`}
              </p>
              {hovered === s.name && (
                <div className="absolute -top-10 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-white/10 bg-[#0a0f1a] px-2.5 py-1.5 text-[10px] text-slate-300 shadow-xl z-10">
                  {s.name} · {pos ? "+" : ""}{val.toFixed(1)}%
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Top Movers ────────────────────────────────────────────────────────────────
const MOVER_TABS = ["Top Gainers", "Top Losers", "Most Active"] as const;
type MoverTab = typeof MOVER_TABS[number];

function TopMovers({ movers }: { movers: any }) {
  const [tab, setTab] = useState<MoverTab>("Top Gainers");
  const rows =
    tab === "Top Gainers" ? (movers?.gainers ?? []) :
    tab === "Top Losers"  ? (movers?.losers  ?? []) :
    (movers?.active ?? []);

  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="mb-3 flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-[14px] font-bold text-white">Top Movers</h3>
        <div className="flex gap-0.5 rounded-xl bg-white/[0.04] p-0.5">
          {MOVER_TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`rounded-lg px-2.5 py-1 text-[10px] font-medium transition ${tab === t ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"}`}>
              {t}
            </button>
          ))}
        </div>
      </div>
      {/* Table header */}
      <div className="mb-1 grid grid-cols-[1fr_80px_70px] gap-2 text-[9px] font-semibold uppercase tracking-wider text-slate-600 px-3">
        <span>Company</span><span className="text-right">Price</span><span className="text-right">Change</span>
      </div>
      <div className="space-y-1">
        {rows.map((r: any) => (
          <Link key={r.ticker} href={`/companies/${r.ticker}`}
            className="grid grid-cols-[1fr_80px_70px] items-center gap-2 rounded-xl border border-white/[0.04] bg-white/[0.02] px-3 py-2.5 hover:border-sky-500/10 transition">
            <div className="flex items-center gap-2 min-w-0">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/[0.07] text-[8px] font-bold text-slate-400">
                {r.ticker?.slice(0, 3)}
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-bold text-white truncate">{r.ticker}</p>
                <p className="text-[9px] text-slate-600 truncate">{r.company?.split(" ").slice(0, 2).join(" ")}</p>
              </div>
            </div>
            <p className="text-right text-[11px] font-semibold text-white">{r.subtitle}</p>
            <p className={`text-right text-[11px] font-bold ${r.positive !== false ? "text-emerald-400" : "text-rose-400"}`}>{r.value}</p>
          </Link>
        ))}
        {rows.length === 0 && (
          <p className="py-6 text-center text-[12px] text-slate-600">Loading market data…</p>
        )}
      </div>
    </div>
  );
}

// ── Live Event Timeline ───────────────────────────────────────────────────────
function LiveEvents({ events }: { events: any[] }) {
  if (!events.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-[14px] font-bold text-white">Live Event Timeline</h3>
        <Link href="/events" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>
      <div className="space-y-2">
        {events.slice(0, 5).map((e) => {
          const score = e.impact_score ?? 0;
          const col = score >= 80 ? "bg-rose-500/15 text-rose-400" : score >= 60 ? "bg-amber-500/15 text-amber-400" : "bg-sky-500/15 text-sky-400";
          return (
            <Link key={e.id} href={`/events/${e.id}`}
              className="flex items-start gap-3 rounded-2xl border border-white/[0.04] bg-white/[0.02] p-3 hover:border-sky-500/10 transition">
              <div className={`flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-xl ${col} text-[11px] font-black`}>
                {score}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-semibold text-white line-clamp-1">{e.title}</p>
                <div className="mt-1 flex items-center gap-2">
                  <span className="rounded-full bg-white/[0.04] px-1.5 py-0.5 text-[9px] text-slate-500">{e.category}</span>
                  {(e.sectors || []).slice(0, 1).map((s: string) => (
                    <span key={s} className="rounded-full bg-violet-500/10 px-1.5 py-0.5 text-[9px] text-violet-400">{s}</span>
                  ))}
                </div>
              </div>
              <span className="text-[10px] font-semibold text-slate-600 shrink-0">Conf: {e.confidence}%</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

// ── Opportunity Radar ─────────────────────────────────────────────────────────
function OpportunityCards({ items }: { items: any[] }) {
  if (!items.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-[14px] font-bold text-white">Opportunity Radar</h3>
        <Link href="/opportunity-radar" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {items.slice(0, 4).map((o) => (
          <Link key={o.id} href={`/opportunity-radar/${o.id}`}
            className="rounded-2xl border border-white/[0.05] bg-white/[0.02] p-3 hover:border-violet-500/15 transition">
            <div className="flex items-center justify-between mb-2">
              <span className="rounded-full bg-violet-500/10 px-2 py-0.5 text-[9px] font-semibold text-violet-400">
                {(o.beneficiaries || [])[0] ?? "Market"}
              </span>
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/15 text-[11px] font-black text-emerald-400">
                {o.score}
              </div>
            </div>
            <p className="text-[12px] font-bold text-white line-clamp-1">{o.theme}</p>
            <p className="mt-0.5 text-[10px] text-slate-500 line-clamp-2">{o.reason}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

// ── Latest News ───────────────────────────────────────────────────────────────
function LatestMarketNews({ news }: { news: any[] }) {
  if (!news.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-[14px] font-bold text-white">Latest Market News</h3>
        <Link href="/news" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>
      <div className="space-y-2">
        {news.slice(0, 5).map((n) => {
          const score = n.impact_score ?? 0;
          return (
            <Link key={n.id} href={`/news/${n.id}`}
              className="flex items-start gap-3 rounded-2xl border border-white/[0.04] bg-white/[0.02] p-3 hover:border-sky-500/10 transition">
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[10px] font-black ${
                score >= 80 ? "bg-emerald-500/15 text-emerald-400" : score >= 60 ? "bg-sky-500/15 text-sky-400" : "bg-slate-700 text-slate-400"
              }`}>{score}</div>
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-semibold text-white line-clamp-2 leading-snug">{n.headline}</p>
                <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-600">
                  <span>{n.source}</span>
                  <span>•</span>
                  <span>{n.published_at ? ((n.published_at.match(/T(\d{2}:\d{2})/) ?? [])[1] ?? "") : ""}</span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

// ── Main Tab ──────────────────────────────────────────────────────────────────
export function LiveMarketTab({ initialData }: { initialData?: any }) {
  const [data, setData]     = useState<any>(initialData ?? null);
  const [events, setEvents] = useState<any[]>([]);
  const [opps, setOpps]     = useState<any[]>([]);
  const [news, setNews]     = useState<any[]>([]);
  const [loading, setLoading] = useState(!initialData);

  useEffect(() => {
    // Fetch events/opps/news (fast DB queries) — always fresh
    // Only fetch /live if we don't have initialData from overview
    const fetches: Promise<any>[] = [
      fetch(`${API}/api/market/events?limit=5`).then(r => r.ok ? r.json() : null),
      fetch(`${API}/api/market/opportunities?limit=4`).then(r => r.ok ? r.json() : null),
      fetch(`${API}/api/market/news?limit=5`).then(r => r.ok ? r.json() : null),
    ];
    if (!initialData) {
      fetches.unshift(fetch(`${API}/api/market/live`).then(r => r.ok ? r.json() : null));
    }
    Promise.all(fetches).then((results) => {
      if (!initialData) {
        const [live, evts, ops, nws] = results;
        if (live) setData(live);
        if (evts) setEvents(evts.events ?? []);
        if (ops)  setOpps(ops.opportunities ?? []);
        if (nws)  setNews(nws.news ?? []);
      } else {
        const [evts, ops, nws] = results;
        if (evts) setEvents(evts.events ?? []);
        if (ops)  setOpps(ops.opportunities ?? []);
        if (nws)  setNews(nws.news ?? []);
      }
    }).finally(() => setLoading(false));
  }, []);

  const indices = data?.indices?.slice(0, 6) ?? [];
  const sectors = data?.sectors ?? [];
  const movers  = data?.movers;
  const breadth = data?.breadth;

  if (loading) return (
    <div className="space-y-4">
      {[1,2,3,4].map(i => (
        <div key={i} className="h-40 rounded-xl border border-white/[0.05] bg-white/[0.02] animate-pulse"/>
      ))}
    </div>
  );

  return (
    <div className="space-y-5">
      {/* Index cards */}
      <div className="grid grid-cols-3 gap-3 lg:grid-cols-6">
        {indices.map((idx: any) => <IndexCard key={idx.name} item={idx}/>)}
      </div>

      {/* Breadth + Heatmap */}
      <div className="grid grid-cols-[260px_1fr] gap-5">
        <MarketBreadth breadth={breadth}/>
        <SectorHeatmap sectors={sectors}/>
      </div>

      {/* Movers + Events */}
      <div className="grid grid-cols-[1fr_380px] gap-5">
        <TopMovers movers={movers}/>
        <LiveEvents events={events}/>
      </div>

      {/* Opportunities + News */}
      <div className="grid grid-cols-[1fr_380px] gap-5">
        <OpportunityCards items={opps}/>
        <LatestMarketNews news={news}/>
      </div>
    </div>
  );
}
