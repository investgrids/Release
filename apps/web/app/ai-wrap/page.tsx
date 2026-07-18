import type { ReactNode } from "react";
import { fetchAPI } from "@/lib/api";
import { Sparkles, BarChart2, Landmark, Globe, TrendingUp, ClipboardList } from "lucide-react";

interface Event {
  id: string; title: string; summary: string;
  impact_score: number | null; confidence: number | null;
  sectors: string[]; category: string; date: string;
}

async function getEvents() {
  try { return await fetchAPI<Event[]>("/api/events"); }
  catch { return [] as Event[]; }
}

function scoreColor(s: number | null | undefined) {
  if (s === null || s === undefined) return "text-slate-500 bg-slate-800/20 border-slate-700/30";
  if (s >= 9) return "text-emerald-300 bg-emerald-500/10 border-emerald-500/20";
  if (s >= 7) return "text-sky-300 bg-sky-500/10 border-sky-500/20";
  return "text-amber-300 bg-amber-500/10 border-amber-500/20";
}

function categoryIcon(cat: string): ReactNode {
  const m: Record<string, ReactNode> = {
    Macro:      <BarChart2 className="h-4 w-4" />,
    Government: <Landmark className="h-4 w-4" />,
    Policy:     <ClipboardList className="h-4 w-4" />,
    Global:     <Globe className="h-4 w-4" />,
    RBI:        <Landmark className="h-4 w-4" />,
    Results:    <TrendingUp className="h-4 w-4" />,
  };
  return m[cat] ?? <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg>;
}

export default async function AIWrapPage() {
  const events = await getEvents();

  // Group events by date for a timeline view
  const grouped = events.reduce<Record<string, Event[]>>((acc, e) => {
    const day = e.date ? new Date(e.date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "Today";
    (acc[day] ??= []).push(e);
    return acc;
  }, {});

  const days = Object.entries(grouped);

  return (
    <main className="min-w-0 space-y-6 pb-10">
      {/* Header */}
      <div>
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Intelligence</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">AI Market Wrap</h1>
        <p className="mt-1 text-sm text-slate-400">Daily AI-curated summaries of market-moving events and macro trends.</p>
      </div>

      {/* Today's banner */}
      <div className="rounded-[24px] border border-sky-500/20 bg-sky-500/[0.04] p-6 shadow-glow">
        <div className="flex items-start gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sky-500/15 text-sky-300"><Sparkles className="h-5 w-5" /></div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-0.5 text-xs font-medium text-sky-300">AI Generated</span>
              <span className="text-xs text-slate-500">Today · {new Date().toLocaleDateString("en-IN", { day:"numeric", month:"long", year:"numeric" })}</span>
            </div>
            <h2 className="mt-2 text-xl font-semibold text-white">Today's Market Intelligence Summary</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Markets opened positive driven by strong defence and energy sector momentum following budget allocation revisions. RBI's rate hold continues to support banking sector sentiment with NIMs expected to stay stable. IT sector faces near-term headwinds from global demand slowdown. Semiconductor PLI incentives approved, marking a structural long-term positive for India's electronics ecosystem.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {["Defence +3.1%", "Energy +2.4%", "IT -0.9%", "Banking +1.2%", "Pharma +0.6%"].map((t) => (
                <span key={t} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-400">{t}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Event timeline */}
      {days.length > 0 ? (
        <div className="space-y-8">
          {days.map(([date, evts]) => (
            <div key={date}>
              <div className="mb-4 flex items-center gap-3">
                <div className="h-px flex-1 bg-white/5" />
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-400">{date}</span>
                <div className="h-px flex-1 bg-white/5" />
              </div>

              <div className="space-y-4">
                {evts.map((e) => (
                  <article key={e.id}
                    className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow transition hover:-translate-y-0.5 hover:border-white/20">
                    <div className="flex flex-wrap items-start gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/5 text-slate-400">
                        {categoryIcon(e.category)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${scoreColor(e.impact_score)}`}>
                            Impact {e.impact_score === null || e.impact_score === undefined ? "Unscored" : e.impact_score.toFixed(1)}
                          </span>
                          <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] text-slate-400">
                            {e.category}
                          </span>
                          <span className="text-[11px] text-slate-600">
                            {e.confidence === null || e.confidence === undefined ? "Confidence unavailable" : `Confidence ${Math.round(e.confidence * 100)}%`}
                          </span>
                        </div>
                        <h3 className="mt-2 text-base font-semibold leading-snug text-white">{e.title}</h3>
                        <p className="mt-1.5 text-sm leading-6 text-slate-400">{e.summary}</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {(e.sectors ?? []).map((s) => (
                            <span key={s} className="rounded-full border border-white/8 bg-white/5 px-2.5 py-0.5 text-[11px] text-slate-400">{s}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20 shadow-glow">
          <p className="text-slate-500">No wrap events available. Start the backend to load data.</p>
        </div>
      )}

    </main>
  );
}
