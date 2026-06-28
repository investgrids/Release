interface CompanyImpactItem {
  company: string;
  headline: string;
  impact: string;
  time: string;
}

interface CompanyImpactFeedProps {
  items: CompanyImpactItem[];
}

export function CompanyImpactFeed({ items }: CompanyImpactFeedProps) {
  return (
    <section className="rounded-[28px] border border-white/10 bg-white/5 p-5 shadow-glow backdrop-blur-xl">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.28em] text-slate-400">Company Impact Feed</p>
          <h2 className="text-2xl font-semibold text-white">Events affecting top companies</h2>
        </div>
        <button className="rounded-3xl bg-slate-950/80 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5">Refresh</button>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={`${item.company}-${item.headline}`} className="rounded-[22px] border border-white/10 bg-slate-950/90 px-4 py-4">
            <div className="flex items-center justify-between gap-4 text-sm text-slate-400">
              <span className="font-semibold text-white">{item.company}</span>
              <span className="text-xs uppercase tracking-[0.24em] text-slate-400">{item.time}</span>
            </div>
            <p className="mt-2 text-sm text-slate-300">{item.headline}</p>
            <p className="mt-3 text-xs uppercase tracking-[0.24em] text-emerald-300">{item.impact}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
