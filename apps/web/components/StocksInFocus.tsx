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
    <section className="rounded-[28px] border border-white/10 bg-white/5 p-5 shadow-glow backdrop-blur-xl">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.28em] text-slate-400">AI Watch</p>
          <h2 className="text-2xl font-semibold text-white">Stocks in focus</h2>
        </div>
        <button className="rounded-3xl bg-slate-950/80 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/5">View All</button>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.ticker} className="flex items-center justify-between rounded-[22px] border border-white/10 bg-slate-950/90 px-4 py-4">
            <div>
              <p className="text-sm font-semibold text-white">{item.ticker}</p>
              <p className="mt-1 text-xs text-slate-400">{item.name}</p>
            </div>
            <div className="text-right">
              <p className="text-sm font-semibold text-white">{item.price}</p>
              <p className={`mt-1 text-sm ${item.change.startsWith("+") ? "text-emerald-300" : "text-rose-300"}`}>{item.change}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
