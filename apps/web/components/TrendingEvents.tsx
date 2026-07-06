import Link from "next/link";

interface TrendingEventItem {
  id: string;
  score: number;
  title: string;
  tags: string[];
  time?: string;
}

interface TrendingEventsProps {
  events: TrendingEventItem[];
}

function scoreBg(score: number) {
  if (score >= 75) return "from-emerald-500/30 to-emerald-500/10 text-emerald-300";
  if (score >= 50) return "from-amber-500/30  to-amber-500/10  text-amber-300";
  return                    "from-rose-500/30   to-rose-500/10   text-rose-300";
}

export function TrendingEvents({ events }: TrendingEventsProps) {
  return (
    <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 shadow-glow h-full">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-violet-400"><svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5"><path d="M12 2 L14.4 9.6 L22 9.6 L15.8 14.1 L18.2 21.7 L12 17 L5.8 21.7 L8.2 14.1 L2 9.6 L9.6 9.6 Z"/></svg></span>
          <h2 className="text-sm font-semibold text-white">Trending Events</h2>
        </div>
        <Link href="/events" className="text-xs text-slate-500 transition hover:text-white">
          View All
        </Link>
      </div>

      <div className="space-y-3">
        {events.length === 0 && (
          <p className="py-6 text-center text-sm text-slate-500">No events yet</p>
        )}
        {events.map((event) => (
          <Link
            key={event.id}
            href={`/events/${event.id}`}
            className="flex items-start gap-3 rounded-[16px] border border-white/5 bg-slate-950/60 p-3.5 hover:border-white/10 hover:bg-white/[0.03] transition"
          >
            <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-[14px] bg-gradient-to-br text-xl font-bold ${scoreBg(event.score)}`}>
              {event.score}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-white leading-snug">{event.title}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {event.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-white/8 bg-white/5 px-2 py-0.5 text-[10px] text-slate-400"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
