import Link from "next/link";
import { Target } from "lucide-react";

// Batch E consumer migration, 2026-08-24 — market.py's /api/market/opportunities
// now resolves the full href server-side (V1 numeric id or V2 slug) and
// reads real Opportunity/OpportunityV2 data instead of the confirmed-stale
// legacy RadarOpportunity table it used to — that table's ids lived in a
// third, unrelated id space and every link built from item.id 404'd or
// resolved to the wrong opportunity via radar.py's numeric branch.
interface OpportunityRow {
  href: string;
  score: number | null;
  theme: string;
  reason: string;
  category: string;
  trend: "up" | "down" | "stable";
}

// Directional-surface reassessment (2026-09-03) — this used to draw a
// small line chart from `Math.sin(seed + i * 0.9)`-generated points, a
// deterministic fake shape seeded only by the item's row index, not any
// real price/score history — visually indistinguishable from a genuine
// trend chart. No real historical series exists in this data path (
// OpportunityRow carries only a single categorical `trend` snapshot, no
// time series) — rather than build a new history feature just to
// preserve a chart, this shows the one real signal that IS available
// (the direction itself) honestly, as a direction, not a fabricated
// magnitude/shape.
function TrendIndicator({ trend }: { trend: "up" | "down" | "stable" }) {
  const color = trend === "up" ? "#22c55e" : trend === "down" ? "#f43f5e" : "rgb(var(--text-muted))";
  const symbol = trend === "up" ? "↑" : trend === "down" ? "↓" : "→";
  const label = trend === "up" ? "Up" : trend === "down" ? "Down" : "Stable";
  return (
    <span className="flex h-8 w-12 shrink-0 flex-col items-center justify-center" style={{ color }} aria-label={`Trend: ${label}`}>
      <span className="text-[16px] font-bold leading-none">{symbol}</span>
      <span className="text-[8px] font-medium uppercase tracking-wide">{label}</span>
    </span>
  );
}

function ScoreCircle({ score }: { score: number | null | undefined }) {
  const unscored = score === null || score === undefined;
  const color = unscored ? "text-text-muted ring-surface-border/7 bg-text-primary/[0.05]" :
    score >= 85 ? "text-emerald-600 dark:text-emerald-300 ring-emerald-500/30 bg-emerald-500/10" :
    score >= 70 ? "text-sky-600 dark:text-sky-300 ring-sky-500/30 bg-sky-500/10" :
    "text-amber-600 dark:text-amber-300 ring-amber-500/30 bg-amber-500/10";
  return (
    <div className={`flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-full ring-1 ${color} text-[13px] font-black`}>
      {unscored ? <span className="text-[9px]">N/A</span> : score}
    </div>
  );
}

const LEVEL_LABEL: Record<number, string> = {};
function trendLabel(score: number | null | undefined) {
  if (score === null || score === undefined) return "Unscored";
  return score >= 85 ? "Very High" : score >= 70 ? "High" : "Medium";
}

export function AIOpportunitySection({ items }: { items: OpportunityRow[] }) {
  return (
    <div className="rounded-xl border border-surface-border/7 bg-surface-card p-5 h-full">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-500/15">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3.5 w-3.5 text-violet-400">
              <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
              <line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/>
              <line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/>
            </svg>
          </div>
          <h2 className="text-[14px] font-bold text-text-primary">AI Opportunity Radar</h2>
        </div>
        <Link href="/opportunity-radar" className="text-[11px] text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">View All →</Link>
      </div>

      {/* Table header */}
      <div className="mb-2 grid grid-cols-[1fr_48px_52px] gap-3 border-b border-surface-border/6 pb-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
        <span>Opportunity</span>
        <span>Score</span>
        <span>Trend</span>
      </div>

      <div className="space-y-1.5">
        {items.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8">
            <Target className="h-8 w-8 text-text-muted mb-2" />
            <p className="text-[12px] text-text-muted">No opportunities detected yet.</p>
          </div>
        )}
        {items.slice(0, 6).map((item) => (
          <Link
            key={item.href}
            href={item.href as any}
            className="grid grid-cols-[1fr_48px_52px] items-center gap-3 rounded-2xl border border-surface-border/4 bg-text-primary/[0.02] px-3 py-2.5 hover:border-violet-500/15 hover:bg-text-primary/[0.04] transition"
          >
            <div className="min-w-0">
              <p className="text-[12px] font-semibold text-text-primary line-clamp-1">{item.theme}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="rounded-full bg-text-primary/[0.04] px-1.5 py-0.5 text-[9px] text-text-muted">{item.category}</span>
                <span className={`text-[9px] font-medium ${item.score === null || item.score === undefined ? "text-text-muted" : item.score >= 85 ? "text-emerald-400" : item.score >= 70 ? "text-sky-400" : "text-amber-400"}`}>
                  {trendLabel(item.score)}
                </span>
              </div>
            </div>
            <ScoreCircle score={item.score}/>
            <TrendIndicator trend={item.trend}/>
          </Link>
        ))}
      </div>
    </div>
  );
}
