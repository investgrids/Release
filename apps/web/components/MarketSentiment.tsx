interface SentimentItem {
  label: string;
  score: string;
  trend: string;
}

interface MarketSentimentProps {
  items: SentimentItem[];
}

export function MarketSentiment({ items }: MarketSentimentProps) {
  return (
    <section className="rounded-[28px] border border-white/10 bg-white/5 p-5 shadow-glow">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.28em] text-slate-400">Market Sentiment</p>
          <h2 className="text-2xl font-semibold text-white">How traders feel</h2>
        </div>
        <button className="rounded-3xl bg-slate-950/80 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5">View Trend</button>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.label} className="rounded-[22px] border border-white/10 bg-slate-950/90 px-4 py-4">
            <div className="flex items-center justify-between gap-4">
              <span className="text-sm font-semibold text-white">{item.label}</span>
              <span className="text-sm text-slate-400">{item.trend}</span>
            </div>
            <p className="mt-3 text-3xl font-semibold text-white">{item.score}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
