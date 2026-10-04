"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL as API } from "@/lib/api";

interface EarningsRow { date: string; estimate: string | null; actual: string | null; surprise_pct: string | null }
export interface StockExtras {
  source?: string;
  earnings?: { next_date: string | null; next_eps_estimate: string | null; history: EarningsRow[] };
  growth_valuation?: { label: string; value: string }[];
  dividends?: { yield: string | null; rate: string | null; history: { date: string; amount: string }[] };
}

const CARD = "rounded-[28px] border border-surface-border/7 bg-text-primary/[0.02] p-5 md:p-6";
const H = "mb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted";

export function formatDay(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

/** Yahoo-sourced details beyond the key ratios: results date and EPS estimate vs actual, growth and valuation multiples, dividend history. Labelled as Yahoo; not an input to the MarketRipple Score. */
export function StockExtrasCard({ symbol }: { symbol: string }) {
  const [data, setData] = useState<StockExtras | null>(null);
  useEffect(() => {
    let cancelled = false;
    setData(null);
    fetch(`${API}/api/stocks/${symbol}/extras`)
      .then(r => (r.ok ? r.json() : null))
      .then(d => { if (!cancelled) setData(d ?? {}); })
      .catch(() => { if (!cancelled) setData({}); });
    return () => { cancelled = true; };
  }, [symbol]);

  if (data === null) return <div className="h-[220px] animate-pulse rounded-[28px] bg-text-primary/[0.04]" aria-busy="true" aria-label="Loading more details" />;
  const e = data.earnings, gv = data.growth_valuation ?? [], dv = data.dividends;
  const hasEarnings = !!e && (!!e.next_date || e.history.length > 0);
  const hasDiv = !!dv && (!!dv.yield || dv.history.length > 0);
  if (!hasEarnings && gv.length === 0 && !hasDiv) return null;

  return (
    <section className={CARD} aria-label="More details from Yahoo Finance">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h3 className="text-[15px] font-semibold text-text-primary">More details</h3>
        <span className="text-[10.5px] text-text-muted">Source: Yahoo Finance. Not part of the MarketRipple Score.</span>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {hasEarnings && e && (
          <div>
            <p className={H}>Results and estimates</p>
            {e.next_date && (
              <p className="mb-3 text-[12.5px] text-text-secondary">
                Next results: <span className="font-semibold text-text-primary">{formatDay(e.next_date)}</span>
                {e.next_eps_estimate && <> · EPS estimate <span className="font-semibold text-text-primary">{e.next_eps_estimate}</span></>}
              </p>
            )}
            {e.history.length > 0 && (
              <table className="w-full text-[12px]">
                <thead><tr className="text-[10px] uppercase tracking-wider text-text-muted">
                  <th className="pb-1.5 text-left font-medium">Quarter</th><th className="pb-1.5 text-right font-medium">Estimate</th><th className="pb-1.5 text-right font-medium">Actual</th><th className="pb-1.5 text-right font-medium">Surprise</th>
                </tr></thead>
                <tbody className="divide-y divide-surface-border/5">
                  {e.history.map(r => (
                    <tr key={r.date}>
                      <td className="py-1.5 text-text-secondary">{formatDay(r.date)}</td>
                      <td className="py-1.5 text-right tabular-nums text-text-secondary">{r.estimate ?? "—"}</td>
                      <td className="py-1.5 text-right tabular-nums font-medium text-text-primary">{r.actual ?? "—"}</td>
                      <td className={`py-1.5 text-right tabular-nums ${r.surprise_pct?.startsWith("-") ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>{r.surprise_pct ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
        {gv.length > 0 && (
          <div>
            <p className={H}>Growth and valuation</p>
            <dl className="divide-y divide-surface-border/5 text-[12px]">
              {gv.map(r => (
                <div key={r.label} className="flex items-center justify-between py-1.5">
                  <dt className="text-text-secondary">{r.label}</dt><dd className="tabular-nums font-medium text-text-primary">{r.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
        {hasDiv && dv && (
          <div>
            <p className={H}>Dividends</p>
            {(dv.yield || dv.rate) && (
              <p className="mb-3 text-[12.5px] text-text-secondary">
                {dv.yield && <>Yield <span className="font-semibold text-text-primary">{dv.yield}</span></>}
                {dv.yield && dv.rate && " · "}
                {dv.rate && <>Annual rate <span className="font-semibold text-text-primary">{dv.rate}</span> per share</>}
              </p>
            )}
            {dv.history.length > 0 && (
              <ul className="divide-y divide-surface-border/5 text-[12px]">
                {dv.history.map(h => (
                  <li key={h.date} className="flex items-center justify-between py-1.5">
                    <span className="text-text-secondary">{formatDay(h.date)}</span><span className="tabular-nums font-medium text-text-primary">{h.amount}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
