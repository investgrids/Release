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
    <section className="rounded-[28px] border border-surface-border/10 bg-text-primary/5 p-5 shadow-glow">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.28em] text-text-secondary">Company Impact Feed</p>
          <h2 className="text-2xl font-semibold text-text-primary">Events affecting top companies</h2>
        </div>
        <button className="rounded-3xl bg-bg/80 px-4 py-2 text-sm text-text-secondary transition hover:bg-text-primary/5">Refresh</button>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={`${item.company}-${item.headline}`} className="rounded-[22px] border border-surface-border/10 bg-bg/90 px-4 py-4">
            <div className="flex items-center justify-between gap-4 text-sm text-text-secondary">
              <span className="font-semibold text-text-primary">{item.company}</span>
              <span className="text-xs uppercase tracking-[0.24em] text-text-secondary">{item.time}</span>
            </div>
            <p className="mt-2 text-sm text-text-secondary">{item.headline}</p>
            <p className="mt-3 text-xs uppercase tracking-[0.24em] text-emerald-600 dark:text-emerald-300">{item.impact}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
