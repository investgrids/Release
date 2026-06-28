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

export function TrendingEvents({ events }: TrendingEventsProps) {
  return (
    <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl h-full">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">✦</span>
          <h2 className="text-sm font-semibold text-white">Trending Events</h2>
        </div>
        <button className="text-xs text-slate-500 transition hover:text-white">View All</button>
      </div>
      <div className="space-y-3">
        {events.map((event) => (
          <div key={event.id} className="flex items-start gap-3 rounded-[16px] border border-white/5 bg-slate-950/60 p-3.5">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[14px] bg-gradient-to-br from-sky-500/20 to-violet-500/10 text-xl font-bold text-white">
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
          </div>
        ))}
      </div>
    </section>
  );
}
