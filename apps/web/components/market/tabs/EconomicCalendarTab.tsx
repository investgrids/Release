"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Landmark, TrendingUp, ShoppingCart, Factory, ClipboardList, DollarSign, FileText, Building2, Banknote, HardHat, Scale, CalendarDays, Clock } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const IMPACT_MAP: Record<string, { label: string; color: string; dot: string }> = {
  "RBI":        { label: "High",   color: "text-rose-400 bg-rose-500/10 border-rose-500/20",   dot: "bg-rose-500"    },
  "GDP":        { label: "High",   color: "text-rose-400 bg-rose-500/10 border-rose-500/20",   dot: "bg-rose-500"    },
  "Inflation":  { label: "High",   color: "text-rose-400 bg-rose-500/10 border-rose-500/20",   dot: "bg-rose-500"    },
  "CPI":        { label: "Medium", color: "text-amber-400 bg-amber-500/10 border-amber-500/20",dot: "bg-amber-500"   },
  "WPI":        { label: "Medium", color: "text-amber-400 bg-amber-500/10 border-amber-500/20",dot: "bg-amber-500"   },
  "IPO":        { label: "Medium", color: "text-amber-400 bg-amber-500/10 border-amber-500/20",dot: "bg-amber-500"   },
  "Earnings":   { label: "High",   color: "text-rose-400 bg-rose-500/10 border-rose-500/20",   dot: "bg-rose-500"    },
  "Budget":     { label: "High",   color: "text-rose-400 bg-rose-500/10 border-rose-500/20",   dot: "bg-rose-500"    },
  "Government": { label: "Medium", color: "text-sky-400 bg-sky-500/10 border-sky-500/20",      dot: "bg-sky-500"     },
};

function getImpact(category: string) {
  for (const [key, val] of Object.entries(IMPACT_MAP)) {
    if (category.toLowerCase().includes(key.toLowerCase())) return val;
  }
  return { label: "Low", color: "text-slate-400 bg-white/[0.04] border-white/10", dot: "bg-slate-500" };
}

const CAT_ICONS: Record<string, ReactNode> = {
  "RBI":        <Landmark className="h-5 w-5" />,
  "GDP":        <TrendingUp className="h-5 w-5" />,
  "Inflation":  <TrendingUp className="h-5 w-5" />,
  "CPI":        <ShoppingCart className="h-5 w-5" />,
  "WPI":        <Factory className="h-5 w-5" />,
  "IPO":        <ClipboardList className="h-5 w-5" />,
  "Earnings":   <DollarSign className="h-5 w-5" />,
  "Budget":     <FileText className="h-5 w-5" />,
  "Government": <Building2 className="h-5 w-5" />,
  "Monetary":   <Banknote className="h-5 w-5" />,
  "Industrial": <HardHat className="h-5 w-5" />,
  "Trade":      <Scale className="h-5 w-5" />,
};

function catIcon(category: string): ReactNode {
  for (const [k, v] of Object.entries(CAT_ICONS)) {
    if (category.toLowerCase().includes(k.toLowerCase())) return v;
  }
  return <CalendarDays className="h-5 w-5" />;
}

export function EconomicCalendarTab({ initialEvents }: { initialEvents?: any[] }) {
  const [events, setEvents] = useState<any[]>(initialEvents ?? []);
  const [filter, setFilter] = useState<"all"|"high"|"medium"|"low">("all");
  const [loading, setLoading] = useState(!initialEvents?.length);

  useEffect(() => {
    if (initialEvents?.length) return;
    fetch(`${API}/api/market/calendar`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.events) setEvents(d.events); })
      .finally(() => setLoading(false));
  }, []);

  const filtered = events.filter(e => {
    if (filter === "all") return true;
    const imp = getImpact(e.category ?? "").label.toLowerCase();
    return imp === filter;
  });

  if (loading) return (
    <div className="space-y-3">
      {[1,2,3,4,5].map(i => <div key={i} className="h-20 rounded-2xl border border-white/[0.05] bg-white/[0.02] animate-pulse"/>)}
    </div>
  );

  const highCount   = events.filter(e => getImpact(e.category ?? "").label === "High").length;
  const medCount    = events.filter(e => getImpact(e.category ?? "").label === "Medium").length;

  return (
    <div className="space-y-5">
      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Total Events",  val: events.length, color: "text-sky-400"   },
          { label: "High Impact",   val: highCount,     color: "text-rose-400"  },
          { label: "Medium Impact", val: medCount,      color: "text-amber-400" },
          { label: "Low Impact",    val: events.length - highCount - medCount, color: "text-slate-400" },
        ].map(s => (
          <div key={s.label} className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-4 text-center">
            <p className={`text-[28px] font-black ${s.color}`}>{s.val}</p>
            <p className="text-[10px] text-slate-500 mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <span className="text-[11px] text-slate-500">Filter:</span>
        <div className="flex gap-1 rounded-xl bg-white/[0.04] p-0.5">
          {(["all","high","medium","low"] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`rounded-lg px-3 py-1.5 text-[11px] font-medium capitalize transition ${filter === f ? "bg-white/10 text-white" : "text-slate-500 hover:text-slate-300"}`}>
              {f === "all" ? "All" : `${f.charAt(0).toUpperCase() + f.slice(1)} Impact`}
            </button>
          ))}
        </div>
        <p className="ml-auto text-[11px] text-slate-600">{filtered.length} events</p>
      </div>

      {/* Timeline */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-white/[0.05] bg-white/[0.02] py-16">
          <CalendarDays className="h-8 w-8 text-slate-500 mb-3" />
          <p className="text-[14px] font-semibold text-slate-400">No events match this filter</p>
          <button onClick={() => setFilter("all")} className="mt-3 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-[12px] text-sky-400 hover:bg-white/[0.07] transition">
            Clear Filter
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((e, i) => {
            const { label, color, dot } = getImpact(e.category ?? "");
            const icon = catIcon(e.category ?? "");
            return (
              <div key={`${e.id}-${i}`}
                className="flex items-start gap-4 rounded-2xl border border-white/[0.05] bg-white/[0.02] p-4 hover:border-sky-500/10 hover:bg-white/[0.03] transition">
                {/* Timeline dot */}
                <div className="flex flex-col items-center gap-1 shrink-0 mt-1">
                  <div className={`h-3 w-3 rounded-full ${dot}`}/>
                  {i < filtered.length - 1 && <div className="w-px flex-1 bg-white/[0.05] min-h-[20px]"/>}
                </div>

                {/* Icon */}
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/[0.06] bg-white/[0.03] text-slate-400">
                  {icon}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[13px] font-bold text-white leading-snug">{e.title}</p>
                      <p className="mt-0.5 text-[11px] text-slate-500 line-clamp-1">{e.description}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${color}`}>{label} Impact</span>
                      <span className="rounded-full bg-white/[0.04] px-2.5 py-0.5 text-[10px] text-slate-500">{e.category}</span>
                    </div>
                  </div>
                  <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-600">
                    <span className="flex items-center gap-1"><CalendarDays className="h-3 w-3" /> {e.date}</span>
                    {e.time && <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {e.time}</span>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {!initialEvents?.length && (
        <div className="text-center">
          <Link href="/calendar" className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-5 py-2.5 text-[12px] font-medium text-sky-400 hover:bg-white/[0.07] transition">
            View Full Economic Calendar →
          </Link>
        </div>
      )}
    </div>
  );
}
