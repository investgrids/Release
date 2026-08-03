import Link from "next/link";
import { TrendingUp } from "lucide-react";
import { aggregateHistoricalMovers } from "./historicalAggregate";

export async function HistoricalWinnersTab() {
  const { winners } = await aggregateHistoricalMovers();

  if (winners.length === 0) {
    return <p className="rounded-2xl border border-surface-border/7 bg-surface-card p-8 text-center text-[13px] text-text-muted">No historical winner data available right now.</p>;
  }

  return (
    <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <TrendingUp className="h-4 w-4 text-emerald-400" />
        <h2 className="text-[15px] font-bold text-text-primary">Historical Winners</h2>
      </div>
      <p className="mb-4 text-[12.5px] text-text-secondary">
        Companies that gained the most in the aftermath of real historical market events — actual measured returns, not AI estimates.
      </p>
      <div className="space-y-2">
        {winners.map((w, i) => (
          <Link
            key={`${w.symbol}-${w.eventId}-${i}`}
            href={`/historical/${w.eventId}`}
            className="flex items-center justify-between gap-3 rounded-xl border border-surface-border/6 bg-text-primary/[0.02] p-3 transition hover:border-emerald-500/25 hover:bg-emerald-500/[0.03]"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-bold text-text-primary">{w.name || w.symbol}</span>
                <span className="text-[10px] font-mono text-text-muted">{w.symbol}</span>
              </div>
              <p className="mt-0.5 line-clamp-1 text-[11px] text-text-muted">{w.reason || w.eventTitle}</p>
            </div>
            <span className="shrink-0 text-[15px] font-black tabular-nums text-emerald-400">
              {w.returnPct >= 0 ? "+" : ""}{w.returnPct.toFixed(1)}%
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
