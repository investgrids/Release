"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import type { SectorRankings } from "@/lib/companyRankings";
import { marketRippleRatingColor, marketRippleScoreDisplayInt } from "@/lib/scoring";

const RANK_BADGE = [
  "bg-amber-500/15 text-amber-600 dark:text-amber-300 border-amber-500/30",
  "bg-slate-400/15 text-slate-600 dark:text-slate-300 border-slate-400/30",
  "bg-orange-600/15 text-orange-700 dark:text-orange-300 border-orange-600/30",
];

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 60) return `${mins} minute${mins === 1 ? "" : "s"} ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
  const days = Math.round(hrs / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

const UNAVAILABLE_REASON_LABEL: Record<string, string> = {
  no_snapshot_computed_yet: "Not yet computed",
  publication_locked: "Publication pending",
  ineligible: "Insufficient data",
  INSUFFICIENT_MARKET_HISTORY: "Insufficient market history",
  stale: "Needs refresh",
};

export function CompanyRankingsView({ data }: { data: SectorRankings }) {
  const [showUnavailable, setShowUnavailable] = useState(false);

  if (!data.supported) {
    return (
      <div className="rounded-[20px] border border-surface-border/8 bg-text-primary/[0.02] py-16 text-center">
        <p className="text-[14px] font-semibold text-text-primary">MarketRipple Score is not yet available for this sector.</p>
        <p className="mt-1 text-[12.5px] text-text-muted">Only Banking has an approved scoring methodology today.</p>
      </div>
    );
  }

  const { ranked, partialCoverage, unavailable } = data;

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-[18px] font-black text-text-primary">Banking — Company Rankings</h2>
        <p className="mt-0.5 text-[12.5px] text-text-secondary">
          Ranked by the real MarketRipple Score — financial strength, valuation, market behaviour and current
          intelligence. The same score and update time shown here match each company's own page exactly.
        </p>
      </div>

      {ranked.length === 0 ? (
        <div className="rounded-[20px] border border-surface-border/8 bg-text-primary/[0.02] py-16 text-center">
          <p className="text-[14px] font-semibold text-text-primary">No banks qualify for a published ranking yet.</p>
          <p className="mx-auto mt-1 max-w-md text-[12.5px] text-text-muted">
            MarketRipple Score is computed and reviewed before publication — see below for each bank's real status.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-[20px] border border-surface-border/8 bg-surface-card">
          <table className="w-full min-w-[560px] border-collapse text-left">
            <thead>
              <tr className="border-b border-surface-border/8 text-[10.5px] uppercase tracking-wide text-text-muted">
                <th className="px-4 py-3 font-semibold">Rank</th>
                <th className="px-4 py-3 font-semibold">Company</th>
                <th className="px-4 py-3 font-semibold text-right">Score</th>
                <th className="px-4 py-3 font-semibold text-right">Coverage</th>
                <th className="px-4 py-3 font-semibold text-right">Updated</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map(c => (
                <tr key={c.symbol} className="border-b border-surface-border/5 text-[13px] transition hover:bg-text-primary/[0.02] last:border-0">
                  <td className="px-4 py-3">
                    <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-black ${RANK_BADGE[c.rank - 1] ?? "bg-text-primary/[0.05] text-text-secondary border-surface-border/10"}`}>
                      {c.rank}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/companies/${c.symbol}`} className="group">
                      <p className="font-semibold text-text-primary group-hover:text-violet-600 dark:group-hover:text-violet-300">{c.companyName}</p>
                      <p className="text-[11px] text-text-muted">{c.symbol}</p>
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`font-black tabular-nums ${marketRippleRatingColor(c.rating)}`}>{marketRippleScoreDisplayInt(c.score)}</span>
                    {c.rating && <p className={`text-[10.5px] font-semibold ${marketRippleRatingColor(c.rating)}`}>{c.rating}</p>}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-text-secondary">
                    {c.coveragePct != null ? `${Math.round(c.coveragePct)}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-[11px] text-text-muted">{relativeTime(c.calculatedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {partialCoverage.length > 0 && (
        <div className="mt-6">
          <h3 className="text-[13px] font-bold text-text-primary">Unranked — partial coverage ({partialCoverage.length})</h3>
          <p className="mt-0.5 text-[12px] text-text-muted">
            These companies have some real MarketRipple Score data, but not enough pillars yet for a combined,
            comparable number.
          </p>
          <ul className="mt-3 space-y-2">
            {partialCoverage.map(c => (
              <li key={c.symbol} className="flex items-center justify-between rounded-xl border border-surface-border/8 bg-surface-card px-4 py-2.5">
                <Link href={`/companies/${c.symbol}`} className="text-[13px] font-semibold text-text-primary hover:text-violet-600 dark:hover:text-violet-300">
                  {c.companyName} <span className="text-[11px] font-normal text-text-muted">({c.symbol})</span>
                </Link>
                <span className="text-[11.5px] text-text-muted">{c.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {unavailable.length > 0 && (
        <div className="mt-6">
          <button
            onClick={() => setShowUnavailable(v => !v)}
            className="flex items-center gap-1.5 text-[13px] font-bold text-text-primary"
          >
            Not yet ranked ({unavailable.length})
            <ChevronDown className={`h-4 w-4 transition-transform ${showUnavailable ? "rotate-180" : ""}`} />
          </button>
          {showUnavailable && (
            <ul className="mt-3 space-y-2">
              {unavailable.map(c => (
                <li key={c.symbol} className="flex items-center justify-between rounded-xl border border-surface-border/8 bg-text-primary/[0.02] px-4 py-2.5">
                  <Link href={`/companies/${c.symbol}`} className="text-[13px] font-semibold text-text-primary hover:text-violet-600 dark:hover:text-violet-300">
                    {c.companyName} <span className="text-[11px] font-normal text-text-muted">({c.symbol})</span>
                  </Link>
                  <span className="flex items-center gap-2">
                    <span className="rounded-full border border-surface-border/10 px-2 py-0.5 text-[10.5px] font-semibold text-text-muted">
                      {UNAVAILABLE_REASON_LABEL[c.reason] ?? c.reason}
                    </span>
                    <span className="hidden text-[11.5px] text-text-muted sm:inline" title={c.message}>{c.message}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
