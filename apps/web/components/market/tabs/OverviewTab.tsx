"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { BarChart2, Bot, Zap, Target, Newspaper, CalendarDays, Sparkles } from "lucide-react";
import { AIOpportunitySection } from "@/components/AIOpportunitySection";
import { TopEventsSection }     from "@/components/TopEventsSection";

// ── AI Executive Summary ──────────────────────────────────────────────────────
function AIExecutiveSummary({ data }: { data: any }) {
  const score = data?.sentiment_score ?? 72;
  const label = score >= 65 ? "Bullish" : score >= 45 ? "Neutral" : "Bearish";
  const color = score >= 65 ? "text-emerald-400" : score >= 45 ? "text-amber-400" : "text-rose-400";
  return (
    <div className="rounded-xl border border-sky-500/10 bg-[#080c14] p-6">
      <div className="relative flex items-start gap-8">
        <div className="flex-1 min-w-0">
          <div className="mb-3 flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-sky-500/20 text-sky-400"><Sparkles className="h-3.5 w-3.5" /></span>
            <span className="rounded-full border border-sky-500/25 bg-sky-500/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-sky-400">AI Executive Summary</span>
          </div>
          <h2 className="text-[18px] font-black text-white mb-2 leading-snug">
            Market Sentiment: <span className={color}>{label}</span>
          </h2>
          <p className="text-[13px] leading-6 text-slate-400">
            Indian markets are showing {label.toLowerCase()} momentum with {score >= 65 ? "strong" : "mixed"} institutional participation.
            Infrastructure, banking, and defence sectors are in focus with multiple high-impact events scheduled.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 shrink-0">
          {([
            { label: "Sentiment Score", value: `${score}%`,  color: color,            icon: <BarChart2 className="h-4 w-4" /> },
            { label: "AI Confidence",   value: "92%",        color: "text-violet-400", icon: <Bot className="h-4 w-4" /> },
            { label: "Events Today",    value: (data?.events?.length ?? 0) + "",        color: "text-amber-400",  icon: <Zap className="h-4 w-4" /> },
            { label: "Opportunities",   value: (data?.opportunities?.length ?? 0) + "", color: "text-emerald-400",icon: <Target className="h-4 w-4" /> },
          ] as { label: string; value: string; color: string; icon: ReactNode }[]).map(s => (
            <div key={s.label} className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 min-w-[120px]">
              <span className="text-slate-400 mb-0.5 block">{s.icon}</span>
              <p className={`text-[18px] font-black ${s.color}`}>{s.value}</p>
              <p className="text-[10px] text-slate-500">{s.label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Sector Overview ───────────────────────────────────────────────────────────
function SectorOverview({ sectors }: { sectors: any[] }) {
  const sorted = [...sectors].sort((a, b) =>
    Math.abs(parseFloat(b.value?.replace(/[^0-9.-]/g, "") ?? "0")) -
    Math.abs(parseFloat(a.value?.replace(/[^0-9.-]/g, "") ?? "0"))
  );
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-[14px] font-bold text-white">Sector Performance</h3>
        <Link href="/sectors" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>
      <div className="space-y-2.5">
        {sorted.slice(0, 8).map((s) => {
          const val = parseFloat(s.value?.replace(/[^0-9.-]/g, "") ?? "0");
          const pos = s.positive !== false;
          const maxAbs = Math.max(...sorted.map(x => Math.abs(parseFloat(x.value?.replace(/[^0-9.-]/g, "") ?? "0"))), 2);
          const pct = Math.min(Math.abs(val) / maxAbs, 1) * 100;
          const display = s.value?.startsWith("+") || s.value?.startsWith("-") ? s.value : `${pos ? "+" : ""}${s.value}%`;
          return (
            <div key={s.id ?? s.name} className="flex items-center gap-3">
              <div className={`h-2 w-2 rounded-full shrink-0 ${pos ? "bg-emerald-400" : "bg-rose-400"}`}/>
              <p className="w-28 shrink-0 text-[11px] text-slate-300 truncate">{s.name}</p>
              <div className="flex-1 h-1.5 rounded-full bg-white/[0.05] overflow-hidden">
                <div className={`h-full rounded-full transition-all duration-700 ${pos ? "bg-emerald-500" : "bg-rose-500"}`} style={{ width: `${pct}%` }}/>
              </div>
              <span className={`w-12 text-right text-[11px] font-semibold shrink-0 ${pos ? "text-emerald-400" : "text-rose-400"}`}>{display}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Top Movers ────────────────────────────────────────────────────────────────
function TopMoversOverview({ movers }: { movers: any }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-[14px] font-bold text-white">Top Movers</h3>
        <Link href="/stocks" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {[
          { key: "gainers", label: "Top Gainers", color: "emerald" },
          { key: "losers",  label: "Top Losers",  color: "rose"    },
        ].map(({ key, label, color }) => (
          <div key={key}>
            <p className={`mb-2 text-[10px] font-bold uppercase tracking-wider text-${color}-400`}>{label}</p>
            <div className="space-y-1.5">
              {(movers?.[key] ?? []).slice(0, 4).map((r: any) => (
                <Link key={r.ticker} href={`/companies/${r.ticker}`}
                  className="flex items-center justify-between rounded-xl border border-white/[0.04] bg-white/[0.02] px-2.5 py-1.5 hover:border-sky-500/10 transition">
                  <p className="text-[11px] font-semibold text-white">{r.ticker}</p>
                  <p className={`text-[11px] font-bold text-${color}-400`}>{r.value}</p>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Latest News Preview ───────────────────────────────────────────────────────
function NewsPreview({ news }: { news: any[] }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-[14px] font-bold text-white">Latest News</h3>
        <Link href="/news" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>
      {news.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <Newspaper className="h-7 w-7 text-slate-500 mb-2" />
          <p className="text-[12px] text-slate-500">No news at the moment. Check back soon.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {news.slice(0, 4).map((n) => (
            <Link key={n.id} href={`/news/${n.id}`}
              className="flex items-start gap-3 rounded-xl border border-white/[0.04] bg-white/[0.02] p-3 hover:border-sky-500/10 transition">
              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[10px] font-black ${
                n.impact_score >= 80 ? "bg-emerald-500/15 text-emerald-400" : "bg-sky-500/15 text-sky-400"
              }`}>{n.impact_score ?? 0}</div>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold text-white line-clamp-2 leading-snug">{n.headline}</p>
                <p className="mt-0.5 text-[10px] text-slate-600">{n.source}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Upcoming Economic Events ──────────────────────────────────────────────────
function UpcomingEvents({ events }: { events: any[] }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-[14px] font-bold text-white">Upcoming Economic Events</h3>
        <Link href="/calendar" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
      </div>
      {events.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <CalendarDays className="h-7 w-7 text-slate-500 mb-2" />
          <p className="text-[12px] text-slate-500">No events scheduled.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {events.slice(0, 4).map((e) => {
            const imp = e.impact?.toLowerCase() ?? "medium";
            const col = imp === "high" ? "text-rose-400 bg-rose-500/10" : imp === "medium" ? "text-amber-400 bg-amber-500/10" : "text-sky-400 bg-sky-500/10";
            return (
              <div key={e.id} className="flex items-center gap-3 rounded-xl border border-white/[0.04] bg-white/[0.02] px-3 py-2.5">
                <div className={`shrink-0 rounded-full px-2 py-0.5 text-[8px] font-bold uppercase ${col}`}>{imp}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] font-semibold text-white truncate">{e.title}</p>
                  <p className="text-[9px] text-slate-600">{e.category}</p>
                </div>
                <p className="text-[10px] text-slate-500 shrink-0">{e.date}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Skeleton pulse block ─────────────────────────────────────────────────────
function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-white/[0.05] ${className ?? ""}`}/>;
}

function OverviewSkeleton() {
  return (
    <div className="rounded-xl border border-white/10 bg-[#0a0d16] p-5 space-y-3">
      <Skeleton className="h-4 w-40"/>
      <Skeleton className="h-3 w-full"/>
      <Skeleton className="h-3 w-5/6"/>
      <Skeleton className="h-3 w-4/6"/>
      <div className="grid grid-cols-2 gap-2 pt-1">
        {[1,2,3,4].map(i => <Skeleton key={i} className="h-16"/>)}
      </div>
    </div>
  );
}

// ── Main Tab ──────────────────────────────────────────────────────────────────
export function OverviewTab({ data, loading = false, events: rawEvents, news: rawNews, opportunities: rawOpps, calendarEvents }: {
  data: any;
  loading?: boolean;
  events?: any[];
  news?: any[];
  opportunities?: any[];
  calendarEvents?: any[];
}) {
  const events  = rawEvents       ?? data?.events        ?? [];
  const news    = rawNews         ?? data?.news          ?? [];
  const opps    = rawOpps         ?? data?.opportunities ?? [];
  const calEvts = calendarEvents  ?? [];
  const sectors = data?.sectors   ?? [];
  const movers  = data?.movers;

  const topEvents = events.map((e: any, i: number) => ({
    id:        String(e.id),
    score:     Math.round(e.impact_score ?? 0),
    title:     e.title,
    tags:      [e.category ?? "Macro", ...(e.sectors ?? []).slice(0, 1)],
    companies: (e.companies ?? []).map((c: any) => {
      const s = typeof c === "string" ? c : (c?.symbol ?? c?.name ?? c?.ticker ?? "");
      return s.slice(0, 4).toUpperCase();
    }).filter(Boolean),
    sector:    (e.sectors ?? ["Market"])[0] ?? "Market",
    time:      e.published_at ? (e.published_at.match(/T(\d{2}:\d{2})/) ?? [])[1] ?? e.published_at.slice(0, 5) : `${9 + i}:30`,
    trend:     ((e.impact_score ?? 0) >= 70 ? "up" : "stable") as "up" | "stable",
  }));

  const radarItems = opps.slice(0, 6).map((r: any) => ({
    id:       String(r.id ?? r.slug),
    score:    Math.round(r.score ?? r.opportunity_score ?? 0),
    theme:    r.theme ?? r.title,
    reason:   r.reason ?? r.summary ?? "",
    category: (r.beneficiaries ?? [])[0] ?? "General",
    trend:    ((r.score ?? 0) >= 70 ? "up" : "stable") as "up" | "stable",
  }));

  return (
    <div className="space-y-5">
      {loading ? <OverviewSkeleton /> : <AIExecutiveSummary data={{ ...data, events, opportunities: opps }}/>}

      <div className="grid grid-cols-[1fr_300px] gap-5">
        <TopEventsSection events={topEvents}/>
        <AIOpportunitySection items={radarItems}/>
      </div>

      <div className="grid grid-cols-[1fr_280px] gap-5">
        {loading ? <OverviewSkeleton /> : <TopMoversOverview movers={movers}/>}
        {loading ? <OverviewSkeleton /> : <SectorOverview sectors={sectors}/>}
      </div>

      <div className="grid grid-cols-[1fr_280px] gap-5">
        <NewsPreview news={news}/>
        <UpcomingEvents events={calEvts}/>
      </div>
    </div>
  );
}
