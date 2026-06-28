import { fetchAPI } from "@/lib/api";

interface CalEvent {
  id: string;
  category: string;
  title: string;
  date: string;
  description: string;
}

async function getCalendar() {
  try { return await fetchAPI<CalEvent[]>("/api/calendar"); }
  catch { return [] as CalEvent[]; }
}

const CAT_CONFIG: Record<string, { color: string; icon: string }> = {
  RBI:     { color: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300", icon: "🏦" },
  PMI:     { color: "border-sky-500/30 bg-sky-500/10 text-sky-300",         icon: "📊" },
  GDP:     { color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300", icon: "📈" },
  FX:      { color: "border-amber-500/30 bg-amber-500/10 text-amber-300",   icon: "💱" },
  Results: { color: "border-violet-500/30 bg-violet-500/10 text-violet-300", icon: "📋" },
  Policy:  { color: "border-rose-500/30 bg-rose-500/10 text-rose-300",      icon: "🏛" },
};

function catStyle(cat: string) {
  return CAT_CONFIG[cat] ?? { color: "border-white/10 bg-white/5 text-slate-300", icon: "📅" };
}

function formatDate(dateStr: string) {
  try {
    return new Date(dateStr).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  } catch { return dateStr; }
}

function formatDay(dateStr: string) {
  try { return new Date(dateStr).getDate().toString().padStart(2, "0"); } catch { return "—"; }
}

function formatMonth(dateStr: string) {
  try { return new Date(dateStr).toLocaleDateString("en-IN", { month: "short" }).toUpperCase(); } catch { return ""; }
}

export default async function CalendarPage() {
  const events = await getCalendar();

  const grouped = events.reduce<Record<string, CalEvent[]>>((acc, e) => {
    const key = formatDate(e.date);
    (acc[key] ??= []).push(e);
    return acc;
  }, {});

  const days = Object.entries(grouped);

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Schedule</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Economic Calendar</h1>
          <p className="mt-1 text-sm text-slate-400">Upcoming macro data releases, RBI announcements, and corporate events.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(CAT_CONFIG).map(([cat, cfg]) => (
            <span key={cat} className={`rounded-full border px-3 py-1 text-xs font-medium ${cfg.color}`}>
              {cfg.icon} {cat}
            </span>
          ))}
        </div>
      </div>

      {days.length > 0 ? (
        <div className="space-y-8">
          {days.map(([date, items]) => (
            <div key={date}>
              {/* Date divider */}
              <div className="mb-4 flex items-center gap-3">
                <div className="h-px flex-1 bg-white/5" />
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-400">{date}</span>
                <div className="h-px flex-1 bg-white/5" />
              </div>

              <div className="space-y-3">
                {items.map((e) => {
                  const cfg = catStyle(e.category);
                  return (
                    <article key={e.id}
                      className="rounded-[20px] border border-white/10 bg-white/[0.03] shadow-glow backdrop-blur-xl transition hover:-translate-y-0.5 hover:border-white/20">
                      <div className="flex items-stretch">
                        {/* Date block */}
                        <div className="flex w-20 shrink-0 flex-col items-center justify-center rounded-l-[20px] bg-white/5 py-4">
                          <span className="text-2xl font-black text-white">{formatDay(e.date)}</span>
                          <span className="text-[10px] uppercase tracking-widest text-slate-500">{formatMonth(e.date)}</span>
                        </div>

                        {/* Content */}
                        <div className="flex min-w-0 flex-1 flex-col justify-center gap-1.5 p-4">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${cfg.color}`}>
                              {cfg.icon} {e.category}
                            </span>
                          </div>
                          <h3 className="text-base font-semibold text-white">{e.title}</h3>
                          <p className="text-sm text-slate-400">{e.description}</p>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center rounded-[20px] border border-white/10 bg-white/[0.03] py-20">
          <p className="text-slate-500">Start the backend to load calendar events.</p>
        </div>
      )}

      <div className="rounded-[20px] border border-amber-500/20 bg-amber-500/[0.04] p-4">
        <p className="text-xs text-amber-300">
          📅 <strong>Live Calendar:</strong> Real-time economic events require{" "}
          <strong>Investing.com API</strong>, <strong>RBI RSS Feed</strong>, or{" "}
          <strong>Financial Modeling Prep Economic Calendar API</strong>.
        </p>
      </div>
    </main>
  );
}
