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
    <section className="rounded-[24px] border border-surface-border/10 bg-text-primary/[0.03] p-5 shadow-glow">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text-primary">Economic Calendar</h2>
        <button className="text-xs text-text-muted transition hover:text-text-primary">View All</button>
      </div>
      <div className="space-y-2.5">
        {events.map((event) => {
          const parts = event.date.split(" ");
          const day = event.day ?? parts[0];
          const month = event.month ?? parts[1];

          return (
            <div key={event.id} className="flex items-center gap-3 rounded-[16px] border border-surface-border/5 bg-bg/60 px-3.5 py-3">
              <div className="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-[14px] bg-surface-card text-center">
                <span className="text-[9px] font-semibold uppercase tracking-wider text-violet-400">{month}</span>
                <span className="text-base font-bold text-text-primary leading-tight">{day}</span>
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-text-primary leading-snug">{event.title}</p>
                <p className="text-[11px] text-text-muted mt-0.5">{event.time}</p>
              </div>
              <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold ${
                event.impact === "High"
                  ? "bg-violet-500/15 text-violet-600 dark:text-violet-300"
                  : event.impact === "Medium"
                  ? "bg-amber-500/15 text-amber-600 dark:text-amber-300"
                  : "bg-text-primary/[0.14] text-text-secondary"
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
