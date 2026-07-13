import type { ReactNode } from "react";
import Link from "next/link";
import { fetchAPI } from "@/lib/api";
import { Landmark, BarChart2, TrendingUp, ArrowLeftRight, ClipboardList, ScrollText, CalendarDays } from "lucide-react";
import { MarketContextStrip } from "@/components/MarketContextStrip";

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

const CAT_CONFIG: Record<string, { color: string; icon: ReactNode; label: string; why: string }> = {
  RBI:     { color: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300", icon: <Landmark className="h-3 w-3" />,       label: "Central Bank",        why: "Affects interest rates and bank stocks" },
  PMI:     { color: "border-sky-500/30 bg-sky-500/10 text-sky-300",         icon: <BarChart2 className="h-3 w-3" />,       label: "Manufacturing Activity", why: "Signals how factories are performing" },
  GDP:     { color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300", icon: <TrendingUp className="h-3 w-3" />,  label: "Economic Growth",     why: "Shows if India's economy is expanding" },
  FX:      { color: "border-amber-500/30 bg-amber-500/10 text-amber-300",   icon: <ArrowLeftRight className="h-3 w-3" />,  label: "Currency Data",       why: "USD/INR moves affect IT and import costs" },
  Results: { color: "border-violet-500/30 bg-violet-500/10 text-violet-300", icon: <ClipboardList className="h-3 w-3" />, label: "Company Earnings",    why: "Quarterly profits can move individual stocks 5-15%" },
  Policy:  { color: "border-rose-500/30 bg-rose-500/10 text-rose-300",      icon: <ScrollText className="h-3 w-3" />,      label: "Regulations",         why: "New rules can reshape entire sectors" },
};

function catStyle(cat: string) {
  return CAT_CONFIG[cat] ?? { color: "border-white/10 bg-white/5 text-slate-300", icon: <CalendarDays className="h-3 w-3" /> };
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
      <MarketContextStrip />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Schedule</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white">Economic Calendar</h1>
          <p className="mt-1 text-sm text-slate-400">Scheduled events that can move markets. High-impact events can shift sector prices by 3–10% on announcement day.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(CAT_CONFIG).map(([cat, cfg]) => (
            <span key={cat} title={cfg.why} className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-medium cursor-help ${cfg.color}`}>
              {cfg.icon} {cfg.label}
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
                      className="rounded-[20px] border border-white/10 bg-white/[0.03] shadow-glow transition hover:-translate-y-0.5 hover:border-white/20">
                      <div className="flex items-stretch">
                        {/* Date block */}
                        <div className="flex w-20 shrink-0 flex-col items-center justify-center rounded-l-[20px] bg-white/5 py-4">
                          <span className="text-2xl font-black text-white">{formatDay(e.date)}</span>
                          <span className="text-[10px] uppercase tracking-widest text-slate-500">{formatMonth(e.date)}</span>
                        </div>

                        {/* Content */}
                        <div className="flex min-w-0 flex-1 flex-col justify-center gap-1.5 p-4">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${cfg.color}`}>
                              {cfg.icon} {cfg.label}
                            </span>
                            {cfg.why && (
                              <span className="text-[11px] text-slate-500">— {cfg.why}</span>
                            )}
                          </div>
                          <h3 className="text-base font-semibold text-white">{e.title}</h3>
                          <p className="text-sm text-slate-400">{e.description}</p>
                          <a href={`/ai-search?q=${encodeURIComponent(e.title)}`}
                            className="mt-1 self-start text-[11px] font-medium text-violet-400 hover:text-violet-300 transition">
                            Ask AI about this →
                          </a>
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

      {/* How to use this calendar */}
      <div className="rounded-[20px] border border-sky-500/15 bg-sky-500/[0.04] p-5">
        <h3 className="mb-3 text-[11px] font-bold uppercase tracking-[0.15em] text-sky-400">
          How to use this calendar
        </h3>
        <div className="grid grid-cols-3 gap-4 text-[12px]">
          <div>
            <p className="font-semibold text-white">Before the event</p>
            <p className="mt-1 text-slate-400">Use "Ask AI about this →" to understand what the market expects and which companies are exposed.</p>
          </div>
          <div>
            <p className="font-semibold text-white">On the day</p>
            <p className="mt-1 text-slate-400">High-impact events (Central Bank, GDP) can move the entire market. Watch Live Market for real-time reaction.</p>
          </div>
          <div>
            <p className="font-semibold text-white">After the event</p>
            <p className="mt-1 text-slate-400">Check Events page for analysis. Surprise outcomes (better or worse than expected) cause the biggest moves.</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-4 border-t border-white/[0.05] pt-4">
          <Link href="/market-intelligence" className="text-[12px] font-medium text-sky-400 transition hover:text-sky-300">
            Watch Live Market →
          </Link>
          <Link href="/ai-search" className="text-[12px] font-medium text-violet-400 transition hover:text-violet-300">
            Ask AI about any event →
          </Link>
          <Link href="/events" className="text-[12px] font-medium text-slate-400 transition hover:text-slate-300">
            See past event analysis →
          </Link>
        </div>
      </div>

      <div className="rounded-[20px] border border-amber-500/20 bg-amber-500/[0.04] p-4">
        <p className="text-xs text-amber-300">
          <CalendarDays className="inline h-3.5 w-3.5 mr-1 align-text-bottom" /> <strong>Live Calendar:</strong> Real-time economic events require{" "}
          <strong>Investing.com API</strong>, <strong>RBI RSS Feed</strong>, or{" "}
          <strong>Financial Modeling Prep Economic Calendar API</strong>.
        </p>
      </div>
    </main>
  );
}
