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

// Same shell, heading and row typography as the other company cards (CARD / SectionCard / KvRow in CompanyPageClient).
const CARD = "rounded-2xl border border-surface-border/10 bg-surface-card shadow-[0_1px_2px_rgb(15_23_42/0.04)] p-6";
const SUBHEAD = "mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted";
const ROW = "flex items-center justify-between gap-2 py-2 border-b border-surface-border/4 last:border-0";
const LABEL = "text-[12px] text-text-muted shrink-0";
const VALUE = "text-[13px] font-medium tabular-nums text-right";
const UP = "text-emerald-600 dark:text-emerald-400";
const DOWN = "text-rose-600 dark:text-rose-400";
const GROWTH_LABELS = new Set(["Revenue growth (latest quarter, YoY)", "Earnings growth (latest quarter, YoY)"]);

const toNum = (v?: string | null): number | null => {
  const n = parseFloat(String(v ?? "").replace(/[^0-9.+\-−]/g, "").replace("−", "-"));
  return Number.isFinite(n) ? n : null;
};
/** Colour and arrow for a signed figure: rising green ▲, falling red ▼, zero or unknown stays neutral. */
export function trend(n: number | null): { tone: string; arrow: string } {
  if (n === null || n === 0) return { tone: "text-text-primary", arrow: "" };
  return n > 0 ? { tone: UP, arrow: "▲ " } : { tone: DOWN, arrow: "▼ " };
}

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

  if (data === null) return <div className="h-[220px] animate-pulse rounded-2xl bg-text-primary/[0.04]" aria-busy="true" aria-label="Loading more details" />;
  const e = data.earnings, gv = data.growth_valuation ?? [], dv = data.dividends;
  const hasEarnings = !!e && (!!e.next_date || e.history.length > 0);
  const hasDiv = !!dv && (!!dv.rate || dv.history.length > 0);   // yield is already in Key ratios
  if (!hasEarnings && gv.length === 0 && !hasDiv) return null;

  return (
    <section className={CARD} aria-label="More details">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-text-primary">More details</h2>
      </div>
      <div className="grid grid-cols-1 gap-x-8 gap-y-6 lg:grid-cols-3 lg:divide-x lg:divide-surface-border/4">
        {hasEarnings && e && (
          <div>
            <p className={SUBHEAD}>Results and estimates</p>
            {e.next_date && (
              <div className={ROW}>
                <span className={LABEL}>Next results</span>
                <span className={`${VALUE} text-text-primary`}>{formatDay(e.next_date)}{e.next_eps_estimate ? ` · est. ${e.next_eps_estimate}` : ""}</span>
              </div>
            )}
            {e.history.map(r => {
              const beat = toNum(r.actual) !== null && toNum(r.estimate) !== null ? (toNum(r.actual) as number) - (toNum(r.estimate) as number) : null;
              const t = trend(toNum(r.surprise_pct) ?? beat);
              return (
                <div key={r.date} className={ROW}>
                  <span className={LABEL}>{formatDay(r.date)}</span>
                  <span className="text-right">
                    <span className={`${VALUE} ${t.tone}`}>{r.actual ?? "—"}</span>
                    <span className="ml-2 text-[11px] tabular-nums text-text-muted">est. {r.estimate ?? "—"}</span>
                    {r.surprise_pct && <span className={`ml-2 text-[11px] font-medium tabular-nums ${t.tone}`}>{t.arrow}{r.surprise_pct.replace(/^[+-]/, "")}</span>}
                  </span>
                </div>
              );
            })}
          </div>
        )}
        {gv.length > 0 && (
          <div className="lg:pl-8">
            <p className={SUBHEAD}>Growth and valuation</p>
            {gv.map(r => {
              const t = GROWTH_LABELS.has(r.label) ? trend(toNum(r.value)) : { tone: "text-text-primary", arrow: "" };
              return (
                <div key={r.label} className={ROW}>
                  <span className={LABEL}>{r.label}</span>
                  <span className={`${VALUE} ${t.tone}`}>{t.arrow}{GROWTH_LABELS.has(r.label) ? r.value.replace(/^-/, "") : r.value}</span>
                </div>
              );
            })}
          </div>
        )}
        {hasDiv && dv && (
          <div className="lg:pl-8">
            <p className={SUBHEAD}>Dividends</p>
            {dv.rate && <div className={ROW}><span className={LABEL}>Annual rate (per share)</span><span className={`${VALUE} text-text-primary`}>{dv.rate}</span></div>}
            {/* Payouts are neutral: interim, final and special dividends differ in size by design, so one smaller than the last is not a cut. */}
            {dv.history.map(h => (
              <div key={h.date} className={ROW}>
                <span className={LABEL}>{formatDay(h.date)}</span>
                <span className={`${VALUE} text-text-primary`}>{h.amount}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
