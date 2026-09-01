import { Fragment } from "react";
import Link from "next/link";

// Light-first company-impact table — same real data (symbol, live quote,
// AI impact call, reason, expected horizon) as before, restyled onto
// Daily Brief's card/token language (rounded-2xl border-surface-border/7,
// light impact colors with dark: pairs) instead of the article page's old
// dark-only palette.

export interface CompanyImpactRow {
  symbol: string;
  name: string;
  impact: "positive" | "negative" | "neutral";
  reason?: string;
  timeframe?: string;
}

export interface Quote { price_str: string; change_pct_str: string; positive: boolean }

const IMPACT_STYLE: Record<string, string> = {
  positive: "border-emerald-200 dark:border-emerald-500/25 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  negative: "border-rose-200 dark:border-rose-500/25 bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-300",
  neutral:  "border-surface-border/20 bg-text-primary/5 text-text-secondary",
};
// Plain CSS dots, not emoji — the emoji glyphs (🟢🔴⚪) render inconsistently
// across platforms (Windows in particular renders "⚪" as a shaded/glossy
// sphere rather than a flat circle, clashing with the rest of this flat
// design system) and can't inherit the badge's own text color.
const IMPACT_DOT: Record<string, string> = {
  positive: "bg-emerald-500",
  negative: "bg-rose-500",
  neutral:  "bg-text-muted",
};
const HORIZON_LABEL: Record<string, string> = {
  immediate: "Today", short: "1 Week", weeks: "1 Week", medium: "1 Month", months: "1 Month", long: "Long Term",
};

// The header row and every company row used to be separate <div
// className="grid ..."> instances stacked as siblings — each its own
// independent grid, so an `auto` column's rendered width was computed
// from ONLY that one row's own content. Two rows with differently-sized
// price strings (e.g. "₹106.30" vs "₹1,265.00") got two different Price
// column widths, and neither matched the header's ("Price", shorter
// still) — the exact real bug (user-reported, live-verified: header and
// data columns didn't line up no matter how the individual cells were
// aligned, because they were never in the same grid to begin with).
// Fixed by making the header cells and every row's cells siblings in
// ONE shared grid, so grid-auto-sizing computes each column's width from
// every row's content at once, consistently.
function cellCls(colIndex: number, isLastRow: boolean, extra = "") {
  return [
    colIndex === 0 ? "pl-4" : "",
    colIndex === 4 ? "pr-4" : "",
    isLastRow ? "" : "border-b border-surface-border/6",
    "py-3",
    extra,
  ].filter(Boolean).join(" ");
}

export function CompanyImpactTable({ companies, quotes }: { companies: CompanyImpactRow[]; quotes: Record<string, Quote> }) {
  const headerCls = "border-b border-surface-border/6 bg-text-primary/[0.02] py-2.5 text-[9px] font-bold uppercase tracking-widest text-text-muted";
  return (
    <div className="overflow-hidden rounded-2xl border border-surface-border/7 bg-text-primary/[0.02]">
      {/* Why was the sole `fr` track (2fr) with everything else `auto` — on
          a wide viewport with a short one-line reason, that dumps 100% of
          the row's leftover width into Why alone, stretching a short
          sentence across most of the table and shoving Expected Horizon
          far to the right, reading as visually disconnected from its own
          row (user-reported). Bounded with minmax() instead of an
          unconstrained fraction so the row sizes to its actual content —
          Why still grows for longer reasons and wraps rather than
          truncating, it just no longer over-claims empty space. */}
      <div className="grid grid-cols-[minmax(0,200px)_auto_auto_minmax(0,380px)_auto] items-center gap-x-3">
        <span className={`${headerCls} pl-4`}>Company</span>
        <span className={`${headerCls} text-right`}>Price</span>
        <span className={headerCls}>AI Impact</span>
        <span className={headerCls}>Why</span>
        <span className={`${headerCls} pr-4 text-right`}>Expected Horizon</span>

        {companies.map((c, i) => {
          const q = quotes[c.symbol];
          const isLastRow = i === companies.length - 1;
          return (
            <Fragment key={i}>
              <div className={cellCls(0, isLastRow, "min-w-0")}>
                <Link href={`/companies/${c.symbol}`} className="block text-[13px] font-bold text-sky-700 dark:text-sky-300 hover:text-sky-800 dark:hover:text-sky-200 transition">{c.symbol}</Link>
                <span className="truncate text-[11px] text-text-muted">{c.name}</span>
              </div>
              <div className={cellCls(1, isLastRow, "shrink-0 text-right")}>
                {q ? (
                  <>
                    <p className="text-[12px] font-bold tabular-nums text-text-primary">₹{q.price_str}</p>
                    <p className={`text-[10px] font-semibold tabular-nums ${q.positive ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>{q.change_pct_str}</p>
                  </>
                ) : (
                  <span className="text-[11px] text-text-muted">—</span>
                )}
              </div>
              <div className={cellCls(2, isLastRow, "shrink-0")}>
                <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-bold capitalize ${IMPACT_STYLE[c.impact] ?? IMPACT_STYLE.neutral}`}>
                  <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${IMPACT_DOT[c.impact] ?? IMPACT_DOT.neutral}`} />
                  {c.impact}
                </span>
              </div>
              <div className={cellCls(3, isLastRow, "min-w-0 text-[12px] leading-5 text-text-secondary")}>
                {c.reason || "—"}
              </div>
              <div className={cellCls(4, isLastRow, "shrink-0 text-right text-[11px] text-text-muted")}>
                {c.timeframe ? (HORIZON_LABEL[c.timeframe] ?? c.timeframe) : "—"}
              </div>
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}
