"use client";

import Link from "next/link";

const TRENDING_SEARCHES = [
  "Railway Stocks", "AI Infrastructure", "RBI Policy", "Semiconductor", "Renewable Energy",
  "Defence Budget", "FMCG", "PSU Banks", "EV Stocks", "IPO 2025",
];

interface AlertRow {
  ticker: string;
  change: string;
  positive: boolean;
  message: string;
  time: string;
}

interface WatchlistRow {
  ticker: string;
  price: string;
  change: string;
  positive: boolean;
}

const SAMPLE_ALERTS: AlertRow[] = [
  { ticker: "RVNL", change: "+3.2%", positive: true, message: "High impact event detected", time: "5m ago" },
  { ticker: "HAL", change: "+2.8%", positive: true, message: "Defence budget allocation news", time: "18m ago" },
  { ticker: "BEL", change: "-1.4%", positive: false, message: "Unusual volume spike", time: "32m ago" },
];

const SAMPLE_WATCHLIST: WatchlistRow[] = [
  { ticker: "BEL",  price: "₹312.45", change: "+2.15%", positive: true  },
  { ticker: "L&T",  price: "₹3,512.40", change: "+1.82%", positive: true  },
  { ticker: "NTPC", price: "₹345.60", change: "-0.42%", positive: false },
];

export function DashboardBottomRow({
  alerts = SAMPLE_ALERTS,
  watchlist = SAMPLE_WATCHLIST,
}: {
  alerts?: AlertRow[];
  watchlist?: WatchlistRow[];
}) {
  return (
    <div className="grid grid-cols-3 gap-5">
      {/* Trending Searches */}
      <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-sky-400">
              <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>
            </svg>
            <h3 className="text-[13px] font-bold text-white">Trending Searches</h3>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {TRENDING_SEARCHES.map((s) => (
            <button
              key={s}
              className="rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] text-slate-400 hover:border-sky-500/30 hover:text-sky-300 hover:bg-sky-500/[0.06] transition"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Recent Alerts */}
      <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-amber-400">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
            <h3 className="text-[13px] font-bold text-white">Recent Alerts</h3>
          </div>
          <button className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</button>
        </div>
        <div className="space-y-2.5">
          {(alerts.length ? alerts : SAMPLE_ALERTS).map((a, i) => (
            <div key={i} className="flex items-center gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2">
              <Link href={`/companies/${a.ticker}`}
                className={`text-[11px] font-black shrink-0 hover:underline ${a.positive ? "text-emerald-400" : "text-rose-400"}`}>
                {a.ticker} {a.change}
              </Link>
              <p className="flex-1 min-w-0 text-[11px] text-slate-400 truncate">{a.message}</p>
              <span className="text-[10px] text-slate-600 shrink-0">{a.time}</span>
            </div>
          ))}
        </div>
      </div>

      {/* My Watchlist */}
      <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4 text-violet-400">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
            <h3 className="text-[13px] font-bold text-white">My Watchlist</h3>
          </div>
          <Link href="/stocks" className="text-[11px] text-sky-400 hover:text-sky-300 transition">View All →</Link>
        </div>
        <div className="space-y-2">
          {(watchlist.length ? watchlist : SAMPLE_WATCHLIST).map((w) => (
            <Link
              key={w.ticker}
              href={`/companies/${w.ticker}`}
              className="flex items-center justify-between rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2 hover:border-sky-500/15 hover:bg-white/[0.04] transition"
            >
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/[0.07] text-[9px] font-bold text-slate-300">
                  {w.ticker.slice(0, 3)}
                </div>
                <span className="text-[12px] font-semibold text-white">{w.ticker}</span>
              </div>
              <div className="text-right">
                <p className="text-[12px] font-semibold text-white">{w.price}</p>
                <p className={`text-[10px] font-medium ${w.positive ? "text-emerald-400" : "text-rose-400"}`}>{w.change}</p>
              </div>
            </Link>
          ))}
          <button className="mt-1 flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-white/10 py-2 text-[11px] text-slate-600 hover:border-sky-500/30 hover:text-sky-400 transition">
            <span>+</span> Add Stock
          </button>
        </div>
      </div>
    </div>
  );
}
