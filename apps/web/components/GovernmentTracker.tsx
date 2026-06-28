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
    <section className="rounded-[28px] border border-white/10 bg-white/5 p-5 shadow-glow backdrop-blur-xl">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.28em] text-slate-400">Government Tracker</p>
          <h2 className="text-2xl font-semibold text-white">Policy and regulator signals</h2>
        </div>
        <button className="rounded-3xl bg-slate-950/80 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5">Update</button>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={`${item.date}-${item.title}`} className="rounded-[22px] border border-white/10 bg-slate-950/90 px-4 py-4">
            <div className="flex items-center justify-between gap-4 text-sm text-slate-400">
              <span>{item.date}</span>
              <span className="rounded-full bg-slate-900/80 px-3 py-1 text-xs uppercase tracking-[0.24em] text-slate-300">{item.status}</span>
            </div>
            <p className="mt-3 text-sm font-semibold text-white">{item.title}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
