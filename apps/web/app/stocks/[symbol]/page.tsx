import { StockDetailChart } from "@/components/StockDetailChart";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface StockPageProps {
  params: Promise<{ symbol: string }>;
}

async function getStock(symbol: string) {
  try {
    const res = await fetch(`${API}/api/stocks/${symbol}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

const DNA_SCORES = [
  { label: "Growth",              value: 8.5 },
  { label: "Stability",           value: 7.0 },
  { label: "Government Exposure", value: 6.0 },
  { label: "Debt Risk",           value: 3.0 },
  { label: "News Sensitivity",    value: 7.5 },
  { label: "Management Quality",  value: 8.0 },
];

export default async function StockPage({ params }: StockPageProps) {
  const { symbol } = await params;
  const stock = await getStock(symbol);

  if (!stock) {
    return (
      <main className="min-w-0 flex flex-col items-center justify-center gap-4 py-24 text-center">
        <span className="text-5xl">📉</span>
        <h1 className="text-2xl font-semibold text-white">{symbol.toUpperCase()} not found</h1>
        <p className="text-slate-400">This symbol may not be listed on NSE, or the backend is offline.</p>
        <a href="/stocks" className="mt-2 rounded-full bg-sky-500/15 px-5 py-2 text-sm text-sky-300 hover:bg-sky-500/25">
          ← Back to Explorer
        </a>
      </main>
    );
  }

  const isPositive = !stock.change.startsWith("-");

  return (
    <main className="min-w-0 space-y-6 pb-10">
      <div className="grid gap-6 xl:grid-cols-[1.4fr_0.7fr]">

        {/* Left column */}
        <section className="space-y-5 rounded-[2rem] border border-white/10 bg-white/[0.03] p-6 shadow-glow backdrop-blur-xl">
          {/* Header */}
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-[0.24em] text-sky-300">Stock · NSE</p>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <span className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold uppercase tracking-widest text-slate-200">
                  {stock.symbol}
                </span>
                <span className="text-2xl font-semibold text-white">{stock.industry}</span>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Price",      value: `₹${stock.price}`,  color: "text-white"                                      },
                { label: "Change",     value: stock.change,        color: isPositive ? "text-emerald-400" : "text-rose-400" },
                { label: "Market Cap", value: stock.market_cap,    color: "text-white"                                      },
              ].map(({ label, value, color }) => (
                <div key={label} className="rounded-2xl bg-white/5 p-4 text-center">
                  <p className="text-[10px] uppercase tracking-widest text-slate-500">{label}</p>
                  <p className={`mt-2 text-lg font-bold ${color}`}>{value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Chart + DNA */}
          <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
            <div className="rounded-2xl bg-white/5 p-5">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-base font-semibold text-white">Price performance</h2>
                  <p className="mt-0.5 text-[10px] text-slate-500">6-month weekly via yfinance</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {["1W", "1M", "3M", "6M"].map((l) => (
                    <button key={l} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] uppercase tracking-widest text-slate-400 transition hover:text-white">
                      {l}
                    </button>
                  ))}
                </div>
              </div>
              {stock.chart_data?.length > 0 ? (
                <StockDetailChart data={stock.chart_data} />
              ) : (
                <div className="mt-4 flex h-48 items-center justify-center rounded-xl bg-white/5">
                  <p className="text-xs text-slate-500">No chart data available</p>
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div className="rounded-2xl bg-white/5 p-5">
                <h3 className="text-sm font-semibold text-white">Stock DNA</h3>
                <p className="mt-0.5 text-[10px] text-slate-600">Requires ML inference API for dynamic scores</p>
                <div className="mt-4 space-y-3">
                  {DNA_SCORES.map(({ label, value }) => (
                    <div key={label}>
                      <div className="flex justify-between text-[11px] text-slate-400">
                        <span>{label}</span><span>{value}</span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
                        <div className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500"
                          style={{ width: `${(value / 10) * 100}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl bg-white/5 p-5">
                <h3 className="text-sm font-semibold text-white">Key Stats</h3>
                <div className="mt-4 space-y-2">
                  {[["P/E", stock.pe], ["P/B", stock.pb], ["ROE", stock.roe], ["Market Cap", stock.market_cap]].map(([l, v]) => (
                    <div key={l} className="flex justify-between rounded-xl bg-white/5 px-3 py-2 text-xs">
                      <span className="text-slate-500">{l}</span>
                      <strong className="text-white">{v || "—"}</strong>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Right column */}
        <aside className="space-y-4">
          <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl">
            <p className="text-[10px] uppercase tracking-widest text-slate-500">Related events</p>
            {stock.events?.length > 0 ? (
              <div className="mt-4 space-y-3">
                {stock.events.map((e: { title: string; date: string }, i: number) => (
                  <div key={i} className="rounded-xl border border-white/5 bg-white/5 p-3">
                    <p className="text-xs font-medium text-white leading-snug">{e.title}</p>
                    <p className="mt-1 text-[10px] text-slate-500">{e.date}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-xs text-slate-600">No linked events for {symbol.toUpperCase()} in DB.</p>
            )}
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl">
            <p className="text-[10px] uppercase tracking-widest text-slate-500">Latest news</p>
            <div className="mt-4 space-y-3">
              {(stock.news ?? []).map((n: { headline: string; published_at: string }, i: number) => (
                <div key={i} className="rounded-xl bg-white/5 p-3">
                  <p className="text-xs font-medium text-white">{n.headline}</p>
                  <p className="mt-1 text-[10px] text-slate-500">{n.published_at}</p>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[10px] text-slate-600">Live news requires News API / Financial Times API</p>
          </div>

          {stock.peers?.length > 0 && (
            <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.03] p-5 shadow-glow backdrop-blur-xl">
              <p className="text-[10px] uppercase tracking-widest text-slate-500">Peers</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {stock.peers.map((p: string) => (
                  <a key={p} href={`/stocks/${p}`}
                    className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 transition hover:border-sky-500/30 hover:text-sky-300">
                    {p}
                  </a>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-[1.5rem] border border-amber-500/20 bg-amber-500/[0.04] p-4">
            <p className="text-[11px] text-amber-300">
              ⚡ Financial data via <strong>yfinance</strong> (15-min delayed). For real-time data connect{" "}
              <strong>Upstox / Zerodha Kite Connect API</strong>.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}
