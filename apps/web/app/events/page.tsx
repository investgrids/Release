import { fetchAPI } from "@/lib/api";

interface Event {
  id: string;
  title: string;
  summary: string;
  impact_score: number;
  confidence: number;
  sectors: string[];
  companies: ({ symbol: string; name: string; impact: string } | string)[];
  category: string;
  date: string;
}

async function getEvents() {
  try { return await fetchAPI<Event[]>("/api/events"); }
  catch { return [] as Event[]; }
}

const CAT_COLORS: Record<string, string> = {
  Government: "border-violet-500/20 bg-violet-500/10 text-violet-300",
  Policy:     "border-sky-500/20 bg-sky-500/10 text-sky-300",
  Macro:      "border-amber-500/20 bg-amber-500/10 text-amber-300",
  Global:     "border-slate-500/20 bg-slate-500/10 text-slate-300",
  RBI:        "border-indigo-500/20 bg-indigo-500/10 text-indigo-300",
  Results:    "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
};

const CAT_ICONS: Record<string, string> = {
  Government: "🏛", Policy: "📋", Macro: "📊", Global: "🌐", RBI: "🏦", Results: "📈",
};

function impactBg(score: number) {
  if (score >= 9) return "text-emerald-300 bg-emerald-500/10 border-emerald-500/20";
  if (score >= 7) return "text-sky-300 bg-sky-500/10 border-sky-500/20";
  return "text-amber-300 bg-amber-500/10 border-amber-500/20";
}

const CATS = ["All", "Government", "Policy", "RBI", "Macro", "Global", "Results"];

export default async function EventsPage() {
  const events = await getEvents();
  const topEvent = events[0];

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Intelligence</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Market Events</h1>
          <p className="mt-1 text-sm text-slate-400">Market-moving events ranked by AI-computed impact score.</p>
        </div>
        <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-2">
          <span className="text-[10px] uppercase tracking-widest text-slate-500">Total</span>
          <span className="text-lg font-bold text-white">{events.length}</span>
        </div>
      </div>

      {/* Category filter chips */}
      <div className="flex flex-wrap gap-2">
        {CATS.map((cat) => (
          <span key={cat}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${cat === "All"
              ? "border-sky-500/30 bg-sky-500/10 text-sky-300"
              : (CAT_COLORS[cat] ?? "border-white/10 bg-white/5 text-slate-400")}`}>
            {cat !== "All" && <span className="mr-1">{CAT_ICONS[cat]}</span>}
            {cat}
          </span>
        ))}
      </div>

      {/* Hero top event */}
      {topEvent && (
        <div className="rounded-[24px] border border-sky-500/20 bg-sky-500/[0.04] p-6 shadow-glow backdrop-blur-xl">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${CAT_COLORS[topEvent.category] ?? "border-white/10 bg-white/5 text-slate-300"}`}>
                  {CAT_ICONS[topEvent.category]} {topEvent.category}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] text-slate-400">
                  Top Impact · {topEvent.impact_score.toFixed(1)}
                </span>
                <span className="text-[11px] text-slate-500">
                  {topEvent.date ? new Date(topEvent.date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : ""}
                </span>
              </div>
              <h2 className="mt-3 text-xl font-bold text-white leading-snug">{topEvent.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">{topEvent.summary}</p>
            </div>
            <div className="text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-500/15 text-2xl font-black text-sky-300">
                {topEvent.impact_score.toFixed(0)}
              </div>
              <p className="mt-1 text-[10px] text-slate-500">Impact</p>
            </div>
          </div>
          {topEvent.sectors?.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {topEvent.sectors.map((s) => (
                <span key={s} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] text-slate-400">{s}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Rest of events */}
      {events.length > 0 ? (
        <div className="space-y-4">
          {events.slice(1).map((e) => (
            <article key={e.id}
              className="rounded-[20px] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-white/20">
              <div className="flex flex-wrap items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/5 text-lg">
                  {CAT_ICONS[e.category] ?? "✦"}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${CAT_COLORS[e.category] ?? "border-white/10 bg-white/5 text-slate-300"}`}>
                      {e.category}
                    </span>
                    <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${impactBg(e.impact_score)}`}>
                      Impact {e.impact_score.toFixed(1)}
                    </span>
                    <span className="text-[11px] text-slate-600">{Math.round(e.confidence * 100)}% conf.</span>
                    <span className="text-[11px] text-slate-600">
                      {e.date ? new Date(e.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : ""}
                    </span>
                  </div>
                  <h3 className="mt-2 text-base font-semibold leading-snug text-white">{e.title}</h3>
                  <p className="mt-1.5 text-sm leading-6 text-slate-400">{e.summary}</p>
                  {e.sectors?.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {e.sectors.map((s) => (
                        <span key={s} className="rounded-full border border-white/8 bg-white/5 px-2 py-0.5 text-[10px] text-slate-500">{s}</span>
                      ))}
                    </div>
                  )}
                  {e.companies?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {e.companies.map((c, i) => (
                        <span key={i} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] text-slate-400">
                          {typeof c === "string" ? c : c.name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20">
          <p className="text-slate-500">Start the backend to load events.</p>
        </div>
      )}
    </main>
  );
}
