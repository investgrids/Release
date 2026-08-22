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

export function CompanyImpactTable({ companies, quotes }: { companies: CompanyImpactRow[]; quotes: Record<string, Quote> }) {
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
      <div className="grid grid-cols-[minmax(0,200px)_auto_auto_minmax(0,380px)_auto] items-center gap-3 border-b border-surface-border/6 bg-text-primary/[0.02] px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-text-muted">
        <span>Company</span><span>Price</span><span>AI Impact</span><span>Why</span><span className="text-right">Expected Horizon</span>
      </div>
      {companies.map((c, i) => {
        const q = quotes[c.symbol];
        return (
          <div key={i} className={`grid grid-cols-[minmax(0,200px)_auto_auto_minmax(0,380px)_auto] items-center gap-3 px-4 py-3 ${i < companies.length - 1 ? "border-b border-surface-border/6" : ""}`}>
            <div className="min-w-0">
              <Link href={`/companies/${c.symbol}`} className="block text-[13px] font-bold text-sky-700 dark:text-sky-300 hover:text-sky-800 dark:hover:text-sky-200 transition">{c.symbol}</Link>
              <span className="truncate text-[11px] text-text-muted">{c.name}</span>
            </div>
            {q ? (
              <div className="shrink-0 text-right">
                <p className="text-[12px] font-bold tabular-nums text-text-primary">₹{q.price_str}</p>
                <p className={`text-[10px] font-semibold tabular-nums ${q.positive ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>{q.change_pct_str}</p>
              </div>
            ) : (
              <span className="shrink-0 text-right text-[11px] text-text-muted">—</span>
            )}
            <span className={`shrink-0 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-bold capitalize ${IMPACT_STYLE[c.impact] ?? IMPACT_STYLE.neutral}`}>
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${IMPACT_DOT[c.impact] ?? IMPACT_DOT.neutral}`} />
              {c.impact}
            </span>
            <span className="min-w-0 text-[12px] leading-5 text-text-secondary">{c.reason || "—"}</span>
            <span className="shrink-0 text-right text-[11px] text-text-muted">{c.timeframe ? (HORIZON_LABEL[c.timeframe] ?? c.timeframe) : "—"}</span>
          </div>
        );
      })}
    </div>
  );
}
