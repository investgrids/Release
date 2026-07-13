"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  Landmark, ClipboardList, Building2, Zap, Globe, Globe2,
  BarChart2, Pin, HardHat, TrendingUp, Shield, Monitor,
} from "lucide-react";
import { MarketContextStrip } from "@/components/MarketContextStrip";
import { NextSteps } from "@/components/NextSteps";
import type { ReactNode } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface Event {
  id: string;
  title: string;
  summary: string;
  impact_score: number;
  confidence: number;
  sectors: string[];
  companies: (string | { symbol: string; name: string })[];
  category: string;
  date: string;
  source?: string;
  time?: string;
}

// ── Config ────────────────────────────────────────────────────────────────────
const IMPACT_PILLS  = ["All", "Very High", "High", "Medium", "Low"];
const CATEGORY_PILLS = [
  { label: "All",          value: "" },
  { label: "Central Bank", value: "RBI" },
  { label: "Government",   value: "Government" },
  { label: "Corporate",    value: "Corporate" },
  { label: "Economy",      value: "Macro" },
  { label: "Global",       value: "Global" },
  { label: "Regulations",  value: "Policy" },
];

const CATEGORY_ICON: Record<string, ReactNode> = {
  Government: <Landmark className="h-4 w-4" />,
  Policy:     <ClipboardList className="h-4 w-4" />,
  Corporate:  <Building2 className="h-4 w-4" />,
  RBI:        <Landmark className="h-4 w-4" />,
  Macro:      <Globe className="h-4 w-4" />,
  Global:     <Globe2 className="h-4 w-4" />,
  Results:    <BarChart2 className="h-4 w-4" />,
  Default:    <Pin className="h-4 w-4" />,
};

const CATEGORY_COLOR: Record<string, { pill: string; icon_bg: string }> = {
  Government: { pill: "bg-violet-500/20 text-violet-300 border-violet-500/30", icon_bg: "bg-violet-500/20 text-violet-300" },
  Policy:     { pill: "bg-sky-500/20 text-sky-300 border-sky-500/30",          icon_bg: "bg-sky-500/20 text-sky-300"       },
  Corporate:  { pill: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30", icon_bg: "bg-emerald-500/20 text-emerald-300" },
  RBI:        { pill: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30", icon_bg: "bg-indigo-500/20 text-indigo-300" },
  Macro:      { pill: "bg-amber-500/20 text-amber-300 border-amber-500/30",    icon_bg: "bg-amber-500/20 text-amber-300"   },
  Global:     { pill: "bg-slate-500/30 text-slate-300 border-slate-500/30",    icon_bg: "bg-slate-500/20 text-slate-300"   },
  Results:    { pill: "bg-teal-500/20 text-teal-300 border-teal-500/30",       icon_bg: "bg-teal-500/20 text-teal-300"     },
};

const SECTOR_ICONS: Record<string, ReactNode> = {
  "Infrastructure":   <HardHat className="h-3.5 w-3.5" />,
  "Banking & Finance":<Landmark className="h-3.5 w-3.5" />,
  "Energy":           <Zap className="h-3.5 w-3.5" />,
  "Technology":       <Monitor className="h-3.5 w-3.5" />,
  "Defence":          <Shield className="h-3.5 w-3.5" />,
  "Economy":          <TrendingUp className="h-3.5 w-3.5" />,
  "Monetary Policy":  <Landmark className="h-3.5 w-3.5" />,
  "General":          <Pin className="h-3.5 w-3.5" />,
};

// Backend stores 0-10; static fallback uses 0-100. Normalise to 0-100.
function norm(s: number): number { return s <= 10 ? s * 10 : s; }

function impactLabel(s: number): string {
  const n = norm(s);
  if (n >= 90) return "Very High";
  if (n >= 75) return "High";
  if (n >= 55) return "Medium";
  return "Low";
}

function impactStyle(s: number) {
  const n = norm(s);
  if (n >= 90) return { circle: "border-rose-500 bg-rose-500/20 text-rose-400",    pill: "bg-rose-500/15 text-rose-300 border-rose-500/30"    };
  if (n >= 75) return { circle: "border-amber-400 bg-amber-500/20 text-amber-400", pill: "bg-amber-500/15 text-amber-300 border-amber-500/30"  };
  if (n >= 55) return { circle: "border-sky-400 bg-sky-500/20 text-sky-400",       pill: "bg-sky-500/15 text-sky-300 border-sky-500/30"        };
  return        { circle: "border-slate-500 bg-slate-700/30 text-slate-400",        pill: "bg-slate-700/30 text-slate-400 border-slate-500/30"  };
}

function companySymbol(c: string | { symbol: string; name: string }) {
  return typeof c === "string" ? c : c.symbol;
}
function companyLabel(c: string | { symbol: string; name: string }) {
  return typeof c === "string" ? c : (c.name ?? c.symbol);
}

function groupByDate(events: Event[]): [string, Event[]][] {
  const groups: Record<string, Event[]> = {};
  for (const ev of events) {
    const key = ev.date || "Unknown";
    (groups[key] = groups[key] ?? []).push(ev);
  }
  return Object.entries(groups).sort((a, b) => b[0].localeCompare(a[0]));
}

function formatDateLabel(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const today = new Date();
    const diff = Math.floor((today.getTime() - d.getTime()) / 86400000);
    if (diff === 0) return `Today\n${d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}`;
    if (diff === 1) return `Yesterday\n${d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}`;
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  } catch { return dateStr; }
}

// ── Static fallback data (shown instantly; replaced silently by live API) ────
const STATIC_EVENTS: Event[] = [
  {
    id: "s1", category: "RBI", date: new Date().toISOString().slice(0, 10), time: "10:00 AM",
    title: "RBI MPC Meeting: Rate Decision on Benchmark Repo Rate",
    summary: "The Monetary Policy Committee meets to deliberate on benchmark interest rates amid moderating inflation and steady GDP growth.",
    impact_score: 92, confidence: 0.91,
    sectors: ["Banking & Finance", "Monetary Policy"],
    companies: [{ symbol: "HDFCBANK", name: "HDFC Bank" }, { symbol: "SBIN", name: "SBI" }],
    source: "RBI",
  },
  {
    id: "s2", category: "Government", date: new Date(Date.now() - 86400000).toISOString().slice(0, 10), time: "2:30 PM",
    title: "Union Budget 2026-27: Infrastructure Allocation Surge to ₹11.11 Lakh Crore",
    summary: "Government announces record capex outlay targeting roads, railways and urban infrastructure for the coming fiscal year.",
    impact_score: 88, confidence: 0.87,
    sectors: ["Infrastructure", "Economy"],
    companies: [{ symbol: "LT", name: "L&T" }, { symbol: "RVNL", name: "RVNL" }],
    source: "PIB",
  },
  {
    id: "s3", category: "Corporate", date: new Date(Date.now() - 86400000).toISOString().slice(0, 10), time: "4:00 PM",
    title: "Q4 Results: TCS Reports 8.4% YoY Revenue Growth with Strong Deal Wins",
    summary: "Tata Consultancy Services posts strong quarterly results with robust deal wins across BFSI and healthcare verticals.",
    impact_score: 79, confidence: 0.85,
    sectors: ["Technology"],
    companies: [{ symbol: "TCS", name: "TCS" }, { symbol: "INFY", name: "Infosys" }],
    source: "NSE",
  },
  {
    id: "s4", category: "Policy", date: new Date(Date.now() - 172800000).toISOString().slice(0, 10), time: "11:00 AM",
    title: "SEBI Introduces New F&O Framework with Higher Margin Requirements",
    summary: "Markets regulator tightens derivatives rules with higher margin requirements and revised lot size changes for retail investors.",
    impact_score: 74, confidence: 0.82,
    sectors: ["Capital Markets"],
    companies: [],
    source: "BSE",
  },
  {
    id: "s5", category: "Global", date: new Date(Date.now() - 172800000).toISOString().slice(0, 10), time: "6:00 PM",
    title: "US Fed Holds Rates; Signals Two Cuts in H2 2026",
    summary: "Federal Reserve keeps policy rate unchanged but projects rate reductions in the second half of 2026, supporting EM flows.",
    impact_score: 85, confidence: 0.88,
    sectors: ["Economy", "Banking & Finance"],
    companies: [],
    source: "Reuters",
  },
];

// ── Impact trend from live events (last 7 days) ───────────────────────────────
function buildTrendData(events: { date: string; impact_score: number }[]) {
  const today = new Date();
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - (6 - i));
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  });
  const dayKeys = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - (6 - i));
    return d.toISOString().slice(0, 10);
  });
  const grouped: Record<string, { veryHigh: number; high: number; medium: number; low: number }> = {};
  for (const k of dayKeys) grouped[k] = { veryHigh: 0, high: 0, medium: 0, low: 0 };
  for (const ev of events) {
    const key = (ev.date ?? "").slice(0, 10);
    if (!grouped[key]) continue;
    const lbl = impactLabel(ev.impact_score);
    if (lbl === "Very High")      grouped[key].veryHigh++;
    else if (lbl === "High")   grouped[key].high++;
    else if (lbl === "Medium") grouped[key].medium++;
    else                        grouped[key].low++;
  }
  return dayKeys.map((k, i) => ({ day: days[i], ...grouped[k] }));
}

// ── EventCard ─────────────────────────────────────────────────────────────────
function EventCard({ ev }: { ev: Event }) {
  const catCfg = CATEGORY_COLOR[ev.category] ?? CATEGORY_COLOR["Macro"];
  const ist     = impactStyle(ev.impact_score);
  const score   = Math.round(norm(ev.impact_score ?? 0));
  const icon    = CATEGORY_ICON[ev.category] ?? CATEGORY_ICON["Default"];
  const comps   = Array.isArray(ev.companies) ? ev.companies : [];
  const sects   = Array.isArray(ev.sectors)   ? ev.sectors   : [];

  return (
    <div className="group flex gap-4 rounded-[18px] border border-white/[0.08] bg-white/[0.025] p-4 hover:border-white/[0.15] hover:bg-white/[0.04] transition">
      {/* Category icon */}
      <div className={`mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${catCfg.icon_bg}`}>
        {icon}
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        {/* Tags row */}
        <div className="mb-2 flex flex-wrap items-center gap-1.5">
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${catCfg.pill}`}>{ev.category}</span>
          {sects.slice(0, 2).map(s => (
            <span key={s} className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-400">{s}</span>
          ))}
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${ist.pill}`}>{impactLabel(ev.impact_score)} Impact</span>
          <span className="ml-auto text-[10px] text-slate-500">{ev.time || ev.date}</span>
          {ev.source && <span className="text-[10px] text-slate-600">· {ev.source}</span>}
        </div>

        {/* Title */}
        <h3 className="text-[14px] font-semibold leading-snug text-white group-hover:text-sky-100 transition">{ev.title}</h3>

        {/* Summary */}
        {ev.summary && (
          <p className="mt-1.5 text-[12px] leading-5 text-slate-400 line-clamp-2">{ev.summary}</p>
        )}

        {/* Companies row */}
        {comps.length > 0 && (
          <div className="mt-2.5 flex items-center gap-2">
            {comps.slice(0, 5).map((c, ci) => {
              const sym = companySymbol(c);
              return (
                <Link key={ci} href={`/companies/${sym}`} title={companyLabel(c)}
                  className="flex h-6 items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] px-2 text-[10px] text-slate-400 hover:border-sky-500/30 hover:text-sky-300 transition">
                  {sym.slice(0, 6)}
                </Link>
              );
            })}
          </div>
        )}

        {/* Action row */}
        <div className="mt-3 pt-2.5 border-t border-white/[0.05] flex items-center gap-3 flex-wrap">
          <Link href={`/insights/${ev.id}`}
            className="flex items-center gap-1 text-[12px] font-bold text-violet-400 hover:text-violet-300 transition">
            Intelligence Report →
          </Link>
          <Link href={`/events/${ev.id}`}
            className="flex items-center gap-1 text-[12px] font-medium text-sky-400 hover:text-sky-300 transition">
            Full Story →
          </Link>
          <Link href={`/ripple?event=${ev.id}`}
            className="flex items-center gap-1 text-[12px] font-medium text-indigo-400 hover:text-indigo-300 transition">
            Ripple Effect →
          </Link>
          <Link href={`/ai-search?q=${encodeURIComponent(ev.title)}`}
            className="ml-auto flex items-center gap-1 text-[11px] font-medium text-violet-400 hover:text-violet-300 transition">
            Ask AI →
          </Link>
        </div>
      </div>

      {/* Impact score circle */}
      <div className="shrink-0 flex flex-col items-center gap-1 pt-1">
        <p className="text-[9px] uppercase tracking-wider text-slate-600">Impact</p>
        <div className={`flex h-14 w-14 flex-col items-center justify-center rounded-full border-2 ${ist.circle}`}>
          <span className="text-[18px] font-black leading-none">{score}</span>
          <span className="text-[8px] font-medium">{impactLabel(ev.impact_score)}</span>
        </div>
        {/* Actions */}
        <div className="mt-1 flex gap-1">
          <button className="flex h-6 w-6 items-center justify-center rounded-lg border border-white/8 bg-white/[0.03] text-slate-500 hover:text-white transition" title="Bookmark">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
            </svg>
          </button>
          <button className="flex h-6 w-6 items-center justify-center rounded-lg border border-white/8 bg-white/[0.03] text-slate-500 hover:text-white transition" title="Share">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8M16 6l-4-4-4 4M12 2v13"/>
            </svg>
          </button>
          <Link href={`/events/${ev.id}`} title="View Details"
            className="flex h-6 w-6 items-center justify-center rounded-lg border border-white/8 bg-white/[0.03] text-slate-500 hover:text-sky-400 hover:border-sky-500/30 transition">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
            </svg>
          </Link>
        </div>
      </div>
    </div>
  );
}

// ── PriorityEventsBar ─────────────────────────────────────────────────────────
function PriorityEventsBar({ events }: { events: Event[] }) {
  const top3 = [...events]
    .sort((a, b) => norm(b.impact_score) - norm(a.impact_score))
    .slice(0, 3);

  if (top3.length === 0) return null;

  const ROWS = [
    { label: "Must Watch",     cls: "border-rose-500/30 bg-rose-500/[0.07] text-rose-300",   dot: "bg-rose-400"   },
    { label: "Worth Reading",  cls: "border-amber-500/30 bg-amber-500/[0.07] text-amber-300", dot: "bg-amber-400"  },
    { label: "Monitor",        cls: "border-sky-500/30 bg-sky-500/[0.07] text-sky-300",       dot: "bg-sky-400"    },
  ];

  return (
    <div className="mb-6">
      <p className="mb-2 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
        Today's Priority Events
      </p>
      <div className="space-y-2">
        {top3.map((ev, i) => {
          const row = ROWS[i];
          return (
            <Link key={ev.id} href={`/events/${ev.id}`}
              className={`flex items-center gap-3 rounded-2xl border px-4 py-3 transition hover:brightness-110 ${row.cls}`}>
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${row.dot}`} />
              <span className="w-[90px] shrink-0 text-[10px] font-black uppercase tracking-wider">{row.label}</span>
              <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-white">{ev.title}</span>
              {ev.time && <span className="shrink-0 text-[11px] opacity-60">{ev.time}</span>}
              <span className="shrink-0 text-[11px] font-semibold opacity-80">
                {impactLabel(ev.impact_score)} Impact
              </span>
              <svg className="h-3.5 w-3.5 shrink-0 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
              </svg>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function EventsPage() {
  const [events, setEvents]         = useState<Event[]>(STATIC_EVENTS);
  const [query, setQuery]           = useState("");
  const [view, setView]             = useState<"timeline" | "list">("timeline");
  const [impactFilter, setImpactFilter] = useState("All");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [limit, setLimit]           = useState(20);

  const trendData = useMemo(() => buildTrendData(events), [events]);

  useEffect(() => {
    fetch(`${API}/api/events/?limit=${limit}`)
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (Array.isArray(d) && d.length) setEvents(d); })
      .catch(() => {});
  }, [limit]);

  const filtered = events.filter(ev => {
    if (categoryFilter && ev.category !== categoryFilter) return false;
    if (impactFilter !== "All" && impactLabel(ev.impact_score) !== impactFilter) return false;
    if (query) {
      const q = query.toLowerCase();
      if (!ev.title.toLowerCase().includes(q) && !(ev.summary ?? "").toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const grouped = groupByDate(filtered);

  const total    = events.length;
  const veryHigh = events.filter(e => e.impact_score >= 90).length;
  const high     = events.filter(e => e.impact_score >= 75 && e.impact_score < 90).length;
  const medium   = events.filter(e => e.impact_score >= 55 && e.impact_score < 75).length;

  // Sector counts
  const sectorCounts: Record<string, number> = {};
  for (const ev of events) {
    for (const s of (ev.sectors ?? [])) {
      sectorCounts[s] = (sectorCounts[s] ?? 0) + 1;
    }
  }
  const topSectors = Object.entries(sectorCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  const maxSectorCount = topSectors[0]?.[1] ?? 1;

  // Recent alerts (last 3 high-impact events)
  const recentAlerts = events
    .filter(e => e.impact_score >= 75)
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, 3);

  return (
    <main className="min-w-0 pb-10">
      <MarketContextStrip />

      {/* Header */}
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Events</h1>
          <p className="mt-0.5 text-sm text-slate-400">
            {veryHigh > 0
              ? `${veryHigh} very high-impact event${veryHigh > 1 ? "s" : ""} today — start with those first.`
              : "Events ranked by market impact. Start with the highest."}
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-[13px] text-slate-300 hover:border-white/20 hover:text-white transition">
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
          </svg>
          Calendar View
        </button>
      </div>

      {/* Priority events — triage before filtering */}
      {!query && !categoryFilter && impactFilter === "All" && (
        <PriorityEventsBar events={events} />
      )}

      {/* Filter bar */}
      <div className="mb-5 space-y-3">
        {/* Search */}
        <div className="relative">
          <svg className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input value={query} onChange={e => setQuery(e.target.value)}
            placeholder="Search events, companies, sectors..."
            className="w-full rounded-xl border border-white/10 bg-white/[0.03] py-2 pl-9 pr-3 text-[13px] text-white placeholder-slate-500 outline-none focus:border-sky-500/40"/>
        </div>

        {/* Impact pill row */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-semibold text-slate-500 mr-1">Impact:</span>
          {IMPACT_PILLS.map(p => (
            <button key={p} onClick={() => setImpactFilter(p)}
              className={`rounded-full border px-3 py-1 text-[11px] font-medium transition ${
                impactFilter === p
                  ? "border-violet-500/50 bg-violet-500/20 text-violet-300"
                  : "border-white/[0.08] bg-white/[0.02] text-slate-400 hover:border-white/20 hover:text-slate-200"
              }`}>
              {p}
            </button>
          ))}
        </div>

        {/* Category pill row */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-semibold text-slate-500 mr-1">Category:</span>
          {CATEGORY_PILLS.map(p => (
            <button key={p.value} onClick={() => setCategoryFilter(p.value)}
              className={`rounded-full border px-3 py-1 text-[11px] font-medium transition ${
                categoryFilter === p.value
                  ? "border-sky-500/50 bg-sky-500/20 text-sky-300"
                  : "border-white/[0.08] bg-white/[0.02] text-slate-400 hover:border-white/20 hover:text-slate-200"
              }`}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-[1fr_288px] gap-5 items-start">

        {/* ── LEFT: Timeline / List ─────────────────────────────────── */}
        <div className="min-w-0">
          {/* View toggle */}
          <div className="mb-4 flex gap-1 border-b border-white/[0.06] pb-1">
            {(["timeline", "list"] as const).map(v => (
              <button key={v} onClick={() => setView(v)}
                aria-label={`${v.charAt(0).toUpperCase() + v.slice(1)} View`}
                className={`px-4 py-1.5 text-[13px] font-medium transition border-b-2 -mb-[1px] capitalize ${
                  view === v ? "border-violet-500 text-white" : "border-transparent text-slate-500 hover:text-slate-300"
                }`}>
                {v.charAt(0).toUpperCase() + v.slice(1)} View
              </button>
            ))}
          </div>

          {/* Events */}
          {filtered.length === 0 ? (
            <div className="flex items-center justify-center rounded-[18px] border border-white/10 bg-white/[0.03] py-20">
              <p className="text-sm text-slate-500">No events match the filter.</p>
            </div>
          ) : view === "timeline" ? (
            <div className="space-y-6">
              {grouped.map(([date, evts]) => {
                const [line1, line2] = formatDateLabel(date).split("\n");
                return (
                  <div key={date} className="flex gap-4">
                    {/* Date column */}
                    <div className="w-[100px] shrink-0 pt-1 text-right">
                      <p className="text-[13px] font-semibold text-white leading-tight">{line1}</p>
                      <p className="text-[11px] text-slate-500">{line2 || ""}</p>
                      <div className="mt-2 flex justify-end">
                        <div className="h-2.5 w-2.5 rounded-full bg-violet-500 ring-2 ring-violet-500/30"/>
                      </div>
                    </div>

                    {/* Events for this date */}
                    <div className="flex-1 space-y-3 border-l border-white/[0.06] pl-5">
                      {evts.map(ev => <EventCard key={ev.id} ev={ev} />)}
                    </div>
                  </div>
                );
              })}

              {/* Load more */}
              {filtered.length >= 10 && (
                <button onClick={() => setLimit(l => l + 20)}
                  className="w-full flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] py-3 text-[13px] text-slate-400 hover:text-white hover:border-white/20 transition">
                  Load More Events
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
                  </svg>
                </button>
              )}
            </div>
          ) : (
            /* List view */
            <div className="space-y-3">
              {filtered.map(ev => <EventCard key={ev.id} ev={ev} />)}
            </div>
          )}
        </div>

        {/* ── RIGHT: Overview Sidebar ───────────────────────────────── */}
        <aside className="sticky top-[84px] space-y-4">

          {/* Events Overview */}
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4">
            <h3 className="mb-3 text-[13px] font-semibold text-white">Events Overview</h3>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "Total Events",     value: total,     delta: "+12 today",  color: "text-white",       delta_c: "text-emerald-400" },
                { label: "Very High Impact", value: veryHigh,  delta: `+${Math.max(0, Math.round(veryHigh * 0.2))} today`, color: "text-white",    delta_c: "text-emerald-400" },
                { label: "High Impact",      value: high,      delta: `+${Math.max(0, Math.round(high * 0.08))} today`,    color: "text-amber-400", delta_c: "text-emerald-400" },
                { label: "Medium Impact",    value: medium,    delta: `+${Math.max(0, Math.round(medium * 0.04))} today`,  color: "text-sky-400",   delta_c: "text-emerald-400" },
              ].map(s => (
                <div key={s.label} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                  <p className="text-[10px] text-slate-500">{s.label}</p>
                  <p className={`mt-1 text-2xl font-black ${s.color}`}>{s.value}</p>
                  <p className={`text-[10px] ${s.delta_c}`}>{s.delta}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Impact Trend Chart */}
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-white">Impact Trend</h3>
              <select className="appearance-none rounded-lg border border-white/10 bg-white/[0.04] px-2 py-1 text-[10px] text-slate-400 outline-none">
                <option>7 Days</option>
                <option>30 Days</option>
              </select>
            </div>
            <div className="mb-2 flex gap-3 flex-wrap">
              {[
                { key: "veryHigh", label: "Very High", color: "#f43f5e" },
                { key: "high",     label: "High",      color: "#f59e0b" },
                { key: "medium",   label: "Medium",    color: "#6366f1" },
                { key: "low",      label: "Low",       color: "#22c55e" },
              ].map(s => (
                <div key={s.key} className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full" style={{ background: s.color }}/>
                  <span className="text-[10px] text-slate-400">{s.label}</span>
                </div>
              ))}
            </div>
            <div className="h-[140px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <XAxis dataKey="day" tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false}/>
                  <YAxis tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false}/>
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 10 }} labelStyle={{ color: "#94a3b8" }}/>
                  <Line type="monotone" dataKey="veryHigh" stroke="#f43f5e" strokeWidth={1.5} dot={{ fill: "#f43f5e", r: 2 }} name="Very High"/>
                  <Line type="monotone" dataKey="high"     stroke="#f59e0b" strokeWidth={1.5} dot={{ fill: "#f59e0b", r: 2 }} name="High"/>
                  <Line type="monotone" dataKey="medium"   stroke="#6366f1" strokeWidth={1.5} dot={{ fill: "#6366f1", r: 2 }} name="Medium"/>
                  <Line type="monotone" dataKey="low"      stroke="#22c55e" strokeWidth={1.5} dot={{ fill: "#22c55e", r: 2 }} name="Low"/>
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Top Sectors Affected */}
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-white">Top Sectors Affected</h3>
              <button className="text-[10px] text-violet-400 hover:text-violet-300 transition">View All</button>
            </div>
            {topSectors.length === 0 ? (
              <p className="text-[12px] text-slate-500">Loading...</p>
            ) : (
              <div className="space-y-2.5">
                {topSectors.map(([sector, count]) => (
                  <div key={sector} className="flex items-center gap-2">
                    <span className="text-slate-400">{SECTOR_ICONS[sector] ?? <Pin className="h-3.5 w-3.5" />}</span>
                    <span className="flex-1 min-w-0 text-[12px] text-slate-300 truncate">{sector}</span>
                    <div className="w-20 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                      <div className="h-full rounded-full bg-violet-500" style={{ width: `${(count / maxSectorCount) * 100}%` }}/>
                    </div>
                    <span className="w-14 shrink-0 text-right text-[10px] text-slate-400">{count} events</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Alerts */}
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-[13px] font-semibold text-white">Recent Alerts</h3>
              <button className="text-[10px] text-violet-400 hover:text-violet-300 transition">View All</button>
            </div>
            {recentAlerts.length === 0 ? (
              <p className="text-[12px] text-slate-500">No recent alerts.</p>
            ) : (
              <div className="space-y-2.5">
                {recentAlerts.map((ev, i) => {
                  const dot = ev.impact_score >= 90 ? "bg-rose-500" : ev.impact_score >= 75 ? "bg-amber-500" : "bg-emerald-500";
                  return (
                    <div key={i} className="flex items-start gap-2">
                      <div className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dot}`}/>
                      <div className="min-w-0 flex-1">
                        <p className="text-[11px] text-slate-300 leading-4 line-clamp-2">{ev.title}</p>
                        <p className="mt-0.5 text-[10px] text-slate-600">{ev.date ? ev.date : "Recent"}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

        </aside>
      </div>

      {/* Intelligent guidance — derived from top event and sectors */}
      {events.length > 0 && (() => {
        const topEv    = [...events].sort((a, b) => (b.impact_score ?? 0) - (a.impact_score ?? 0))[0];
        const topSec   = topSectors[0]?.[0];
        const q        = (s: string) => encodeURIComponent(s);
        const topComp  = topEv?.companies?.[0];
        const compSym  = typeof topComp === "object" && topComp !== null ? (topComp as { symbol: string }).symbol : null;
        const compName = typeof topComp === "object" && topComp !== null ? (topComp as { name: string }).name : typeof topComp === "string" ? topComp : null;
        const shortTitle = topEv.title.length > 80 ? topEv.title.slice(0, 77) + "…" : topEv.title;
        return (
          <NextSteps config={{
            takeaway: `"${shortTitle}" has the highest market impact score today — this is where sector momentum is being shaped.`,
            primary: compSym && compName ? {
              label: `Research ${compName}`,
              why:   `Because they're the most directly exposed company — this event fundamentally changes their near-term outlook.`,
              href:  `/companies/${compSym}`,
            } : {
              label: `Ask AI: Which companies are most at risk?`,
              why:   `Because understanding the specific winners and losers is the first step to an actionable investment thesis.`,
              href:  `/ai-search?q=${q(`Which companies are most affected by "${topEv.title}" and what should investors do?`)}`,
            },
            groups: [
              {
                label: "Understand More",
                actions: [
                  {
                    label: "Ask AI: How long will this impact last?",
                    why:   "Because impact duration determines whether this is a short-term trade or a long-term investment thesis.",
                    href:  `/ai-search?q=${q(`How long will the market impact of "${topEv.title}" last and what should investors do?`)}`,
                  },
                  {
                    label: "Open the full event analysis",
                    why:   "Because the detail view shows beneficiaries, at-risk companies, historical parallels, and monitoring signals.",
                    href:  `/events/${topEv.id}`,
                  },
                ],
              },
              {
                label: "Explore Further",
                actions: [
                  topSec ? {
                    label: `Trace the ${topSec} ripple chain`,
                    why:   `Because sector-level moves create second-order effects in adjacent industries — the opportunity isn't always the obvious stock.`,
                    href:  `/ripple`,
                  } : {
                    label: "Trace the full ripple chain",
                    why:   "Because second-order effects often create better risk-adjusted opportunities than the headline company.",
                    href:  `/ripple`,
                  },
                ],
              },
            ],
            path: [topEv.category || "Event", topSec || "Sector", compName || "Company", "Investment Decision"].filter(Boolean) as string[],
          }} />
        );
      })()}
    </main>
  );
}
