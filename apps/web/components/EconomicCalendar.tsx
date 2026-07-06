interface EconomicEvent {
  id: string;
  title: string;
  date: string;
  month?: string;
  day?: string;
  time: string;
  impact: string;
}

interface EconomicCalendarProps {
  events: EconomicEvent[];
}

export function EconomicCalendar({ events }: EconomicCalendarProps) {
  return (
    <section className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 shadow-glow">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-white">Economic Calendar</h2>
        <button className="text-xs text-slate-500 transition hover:text-white">View All</button>
      </div>
      <div className="space-y-2.5">
        {events.map((event) => {
          const parts = event.date.split(" ");
          const day = event.day ?? parts[0];
          const month = event.month ?? parts[1];

          return (
            <div key={event.id} className="flex items-center gap-3 rounded-[16px] border border-white/5 bg-slate-950/60 px-3.5 py-3">
              <div className="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-[14px] bg-slate-900/90 text-center">
                <span className="text-[9px] font-semibold uppercase tracking-wider text-violet-400">{month}</span>
                <span className="text-base font-bold text-white leading-tight">{day}</span>
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-white leading-snug">{event.title}</p>
                <p className="text-[11px] text-slate-500 mt-0.5">{event.time}</p>
              </div>
              <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold ${
                event.impact === "High"
                  ? "bg-violet-500/15 text-violet-300"
                  : event.impact === "Medium"
                  ? "bg-amber-500/15 text-amber-300"
                  : "bg-slate-700/70 text-slate-300"
              }`}>
                {event.impact}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
