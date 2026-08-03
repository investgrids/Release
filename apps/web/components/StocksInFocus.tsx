interface StockFocusItem {
  ticker: string;
  name: string;
  price: string;
  change: string;
}

interface StocksInFocusProps {
  items: StockFocusItem[];
}

export function StocksInFocus({ items }: StocksInFocusProps) {
  return (
    <section className="rounded-[28px] border border-surface-border/10 bg-text-primary/5 p-5 shadow-glow">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.28em] text-text-secondary">AI Watch</p>
          <h2 className="text-2xl font-semibold text-text-primary">Stocks in focus</h2>
        </div>
        <button className="rounded-3xl bg-bg/80 px-4 py-2 text-sm text-text-secondary transition hover:bg-text-primary/5">View All</button>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.ticker} className="flex items-center justify-between rounded-[22px] border border-surface-border/10 bg-bg/90 px-4 py-4">
            <div>
              <p className="text-sm font-semibold text-text-primary">{item.ticker}</p>
              <p className="mt-1 text-xs text-text-secondary">{item.name}</p>
            </div>
            <div className="text-right">
              <p className="text-sm font-semibold text-text-primary">{item.price}</p>
              <p className={`mt-1 text-sm ${item.change.startsWith("+") ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300"}`}>{item.change}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
