interface GovernmentTrackerItem {
  date: string;
  title: string;
  status: string;
}

interface GovernmentTrackerProps {
  items: GovernmentTrackerItem[];
}

export function GovernmentTracker({ items }: GovernmentTrackerProps) {
  return (
    <section className="rounded-[28px] border border-surface-border/10 bg-text-primary/5 p-5 shadow-glow">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.28em] text-text-secondary">Government Tracker</p>
          <h2 className="text-2xl font-semibold text-text-primary">Policy and regulator signals</h2>
        </div>
        <button className="rounded-3xl bg-bg/80 px-4 py-2 text-sm text-text-secondary transition hover:bg-text-primary/5">Update</button>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={`${item.date}-${item.title}`} className="rounded-[22px] border border-surface-border/10 bg-bg/90 px-4 py-4">
            <div className="flex items-center justify-between gap-4 text-sm text-text-secondary">
              <span>{item.date}</span>
              <span className="rounded-full bg-surface-card px-3 py-1 text-xs uppercase tracking-[0.24em] text-text-secondary">{item.status}</span>
            </div>
            <p className="mt-3 text-sm font-semibold text-text-primary">{item.title}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
