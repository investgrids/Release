"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
}

const CAT_CFG: Record<string, { color: string; bg: string; border: string }> = {
  "Government": { color: "text-violet-300", bg: "bg-violet-500/10", border: "border-violet-500/25" },
  "Policy":     { color: "text-sky-300",    bg: "bg-sky-500/10",    border: "border-sky-500/25"    },
  "RBI":        { color: "text-indigo-300", bg: "bg-indigo-500/10", border: "border-indigo-500/25" },
  "Macro":      { color: "text-amber-300",  bg: "bg-amber-500/10",  border: "border-amber-500/25"  },
  "Global":     { color: "text-slate-300",  bg: "bg-slate-700/40",  border: "border-slate-500/25"  },
  "Corporate":  { color: "text-emerald-300",bg: "bg-emerald-500/10",border: "border-emerald-500/25"},
  "Results":    { color: "text-teal-300",   bg: "bg-teal-500/10",   border: "border-teal-500/25"   },
};

const CHIP_COLORS = [
  "bg-violet-500/25 text-violet-200",
  "bg-sky-500/25 text-sky-200",
  "bg-emerald-500/25 text-emerald-200",
  "bg-amber-500/25 text-amber-200",
  "bg-rose-500/25 text-rose-200",
  "bg-teal-500/25 text-teal-200",
  "bg-indigo-500/25 text-indigo-200",
];

const CARD_GRADS = [
  "from-violet-900/20 to-transparent",
  "from-sky-900/20 to-transparent",
  "from-emerald-900/20 to-transparent",
  "from-amber-900/15 to-transparent",
  "from-indigo-900/20 to-transparent",
];

const THUMB_GRADS = [
  "from-violet-600/40 to-indigo-600/20",
  "from-sky-600/40 to-blue-600/20",
  "from-emerald-600/40 to-teal-600/20",
  "from-amber-600/40 to-orange-600/20",
  "from-rose-600/40 to-pink-600/20",
];

const CATEGORIES = ["All", "Government", "Policy", "RBI", "Corporate", "Macro", "Global", "Results"];

const UPCOMING = [
  { date: "07", mon: "JUN", title: "RBI Monetary Policy", time: "12:30 IST" },
  { date: "10", mon: "JUL", title: "US CPI Data", time: "18:00 IST" },
  { date: "12", mon: "JUL", title: "India Industrial Production", time: "12:00 IST" },
  { date: "14", mon: "JUL", title: "FOMC Meeting", time: "10:30 PM IST" },
];

const TAKEAWAYS = [
  "Infrastructure capex to drive multi-year growth",
  "RBI stance supportive for economic growth",
  "Corporate earnings momentum remains strong",
];

function impactBadge(s: number) {
  if (s >= 8.5) return { label: "High",   cls: "text-emerald-300 bg-emerald-500/15 border-emerald-500/25" };
  if (s >= 7)   return { label: "Medium", cls: "text-sky-300    bg-sky-500/15    border-sky-500/25"    };
  return           { label: "Low",    cls: "text-amber-300  bg-amber-500/15  border-amber-500/25"  };
}

function scoreBg(s: number) {
  if (s >= 8.5) return "from-emerald-500 to-teal-400";
  if (s >= 7)   return "from-sky-500 to-blue-400";
  return           "from-amber-500 to-yellow-400";
}

function companyLabel(c: string | { symbol: string; name: string }) {
  return typeof c === "string" ? c : (c.name ?? c.symbol);
}
function companyInitials(c: string | { symbol: string; name: string }) {
  const s = typeof c === "string" ? c : (c.symbol ?? c.name ?? "");
  return s.slice(0, 2).toUpperCase();
}

export default function EventsPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [activeCat, setActiveCat] = useState("All");

  useEffect(() => {
    fetch(`${API}/api/events`)
      .then(r => r.ok ? r.json() : [])
      .then(d => setEvents(Array.isArray(d) ? d : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = events
    .filter(e => activeCat === "All" || e.category === activeCat)
    .filter(e => !query || e.title.toLowerCase().includes(query.toLowerCase()) || (e.summary ?? "").toLowerCase().includes(query.toLowerCase()));

  const highN = events.filter(e => e.impact_score >= 8.5).length;
  const medN  = events.filter(e => e.impact_score >= 7 && e.impact_score < 8.5).length;
  const lowN  = events.filter(e => e.impact_score < 7).length;
  const total = (highN + medN + lowN) || 1;

  return (
    <main className="min-w-0 pb-10">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Events Intelligence</h1>
        <p className="mt-1 text-sm text-slate-400">Track market moving events and understand their impact</p>
      </div>

      <div className="grid grid-cols-[196px_1fr_252px] gap-5 items-start">

        {/* ── LEFT: Filters ──────────────────────────────── */}
        <aside className="space-y-4 sticky top-[84px]">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
            <input value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Search events..."
              className="w-full rounded-xl border border-white/10 bg-white/[0.03] py-2.5 pl-9 pr-3 text-sm text-white placeholder-slate-500 outline-none focus:border-sky-500/40"/>
          </div>

          <div className="space-y-1.5">
            {["Date Range","Event Type","Impact","Sector","More Filters"].map(f => (
              <button key={f}
                className="flex w-full items-center gap-2 rounded-xl border border-white/8 bg-white/[0.02] px-3 py-2 text-left text-[13px] text-slate-300 hover:bg-white/[0.04] hover:text-white transition">
                <span className="flex-1">{f}</span>
                <svg className="h-3 w-3 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7"/>
                </svg>
              </button>
            ))}
          </div>

          <div className="space-y-1">
            <p className="px-1 text-[9px] uppercase tracking-widest text-slate-600">Categories</p>
            {CATEGORIES.map(c => {
              const cfg = CAT_CFG[c];
              const active = activeCat === c;
              return (
                <button key={c} onClick={() => setActiveCat(c)}
                  className={`w-full rounded-xl border px-3 py-1.5 text-left text-[13px] font-medium transition ${
                    active && cfg ? `${cfg.color} ${cfg.bg} ${cfg.border}`
                    : active ? "text-white bg-white/10 border-white/20"
                    : "text-slate-500 border-transparent hover:text-slate-200 hover:bg-white/[0.03]"
                  }`}>
                  {c}
                </button>
              );
            })}
          </div>
        </aside>

        {/* ── CENTER: Event cards ─────────────────────────── */}
        <div className="space-y-4 min-w-0">
          {loading
            ? Array.from({length:3}).map((_,i) => (
                <div key={i} className="h-56 animate-pulse rounded-[20px] border border-white/8 bg-white/[0.02]"/>
              ))
            : filtered.length === 0
            ? (
              <div className="flex items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20 text-sm text-slate-500">
                {events.length === 0 ? "Start the backend to load events." : "No events match the filter."}
              </div>
            )
            : filtered.map((evt, i) => {
                const cfg = CAT_CFG[evt.category] ?? CAT_CFG["Macro"];
                const imp = impactBadge(evt.impact_score);
                const score = Math.round(evt.impact_score * 10);
                const conf  = Math.round((evt.confidence ?? 0.9) * 100);
                const companies = Array.isArray(evt.companies) ? evt.companies : [];
                const sectors   = Array.isArray(evt.sectors)   ? evt.sectors   : [];

                return (
                  <div key={evt.id}
                    className={`rounded-[20px] border border-white/10 bg-gradient-to-r ${CARD_GRADS[i % CARD_GRADS.length]} p-5 backdrop-blur-xl hover:border-white/20 hover:-translate-y-0.5 transition cursor-pointer`}>

                    {/* Row 1 */}
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${cfg.color} ${cfg.bg} ${cfg.border}`}>
                        {evt.category}
                      </span>
                      <span className={`flex h-6 min-w-[28px] items-center justify-center rounded-full bg-gradient-to-r px-2 text-[11px] font-bold text-white ${scoreBg(evt.impact_score)}`}>
                        {score}
                      </span>
                      <span className="text-[11px] text-slate-500">{evt.date}</span>
                      <div className="ml-auto flex gap-1.5">
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${imp.cls}`}>
                          Confidence {conf}%
                        </span>
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${imp.cls}`}>
                          {imp.label}
                        </span>
                      </div>
                    </div>

                    {/* Row 2: title + thumbnail */}
                    <div className="mt-3 flex gap-4">
                      <div className="min-w-0 flex-1">
                        <h2 className="text-[15px] font-bold leading-snug text-white line-clamp-2">
                          {evt.title}
                        </h2>
                        <p className="mt-2 text-[13px] leading-5 text-slate-400 line-clamp-2">{evt.summary}</p>
                      </div>
                      <div className={`h-[72px] w-20 shrink-0 rounded-xl bg-gradient-to-br ${THUMB_GRADS[i % THUMB_GRADS.length]} border border-white/10`}/>
                    </div>

                    {/* Row 3: sector tags */}
                    {sectors.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {sectors.slice(0, 5).map(s => (
                          <span key={s} className="rounded-full border border-white/8 bg-white/[0.04] px-2 py-0.5 text-[11px] text-slate-400">#{s}</span>
                        ))}
                      </div>
                    )}

                    {/* Row 4: company avatar chips */}
                    {companies.length > 0 && (
                      <div className="mt-3 flex items-center gap-1">
                        <span className="mr-1.5 text-[10px] text-slate-600">Affected Companies</span>
                        {companies.slice(0, 7).map((c, ci) => (
                          <div key={ci} title={companyLabel(c)}
                            className={`flex h-7 w-7 items-center justify-center rounded-full border border-white/10 text-[9px] font-bold ${CHIP_COLORS[ci % CHIP_COLORS.length]}`}>
                            {companyInitials(c)}
                          </div>
                        ))}
                        {companies.length > 7 && (
                          <span className="ml-1 text-[10px] text-slate-600">+{companies.length - 7}</span>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
          }
        </div>

        {/* ── RIGHT: AI Insights ──────────────────────────── */}
        <aside className="sticky top-[84px] space-y-4">
          <div className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
            <div className="mb-4 flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-500/20 text-[13px]">✦</span>
              <h2 className="text-sm font-semibold text-white">AI Insights</h2>
            </div>

            {/* Key Takeaways */}
            <p className="mb-2.5 text-[9px] uppercase tracking-widest text-slate-500">Key Takeaways</p>
            <div className="mb-5 space-y-2.5">
              {TAKEAWAYS.map((t, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${["bg-sky-400","bg-violet-400","bg-emerald-400"][i]}`}/>
                  <p className="text-[12px] leading-4 text-slate-300">{t}</p>
                </div>
              ))}
            </div>

            {/* Upcoming Events */}
            <div className="mb-5">
              <div className="mb-2.5 flex items-center justify-between">
                <p className="text-[9px] uppercase tracking-widest text-slate-500">Upcoming Events</p>
                <Link href="/calendar" className="text-[10px] text-sky-400 hover:text-sky-300">View All</Link>
              </div>
              <div className="space-y-1.5">
                {UPCOMING.map((e, i) => (
                  <div key={i} className="flex items-center gap-2.5 rounded-xl border border-white/5 bg-white/[0.02] p-2">
                    <div className="w-7 shrink-0 text-center">
                      <div className="text-sm font-bold leading-none text-white">{e.date}</div>
                      <div className="text-[9px] uppercase text-slate-600">{e.mon}</div>
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-[11px] font-medium text-white">{e.title}</p>
                      <p className="text-[10px] text-slate-500">{e.time}</p>
                    </div>
                  </div>
                ))}
              </div>
              <Link href="/calendar" className="mt-2 block text-center text-[10px] text-slate-500 hover:text-slate-300 transition">
                View Calendar →
              </Link>
            </div>

            {/* Impact Summary */}
            <p className="mb-2.5 text-[9px] uppercase tracking-widest text-slate-500">Event Impact Summary</p>
            <div className="space-y-2.5">
              {[
                { label: "High Impact",   n: highN, bar: "bg-rose-500",  text: "text-rose-400"  },
                { label: "Medium Impact", n: medN,  bar: "bg-amber-500", text: "text-amber-400" },
                { label: "Low Impact",    n: lowN,  bar: "bg-slate-500", text: "text-slate-400" },
              ].map(r => (
                <div key={r.label}>
                  <div className="mb-1 flex justify-between">
                    <span className={`text-[11px] ${r.text}`}>{r.label}</span>
                    <span className="text-[11px] font-bold text-white">{r.n}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                    <div className={`h-full rounded-full ${r.bar}`} style={{width:`${Math.round(r.n/total*100)}%`}}/>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>

      </div>
    </main>
  );
}
