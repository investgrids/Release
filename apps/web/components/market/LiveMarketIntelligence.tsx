"use client";

/**
 * Live Market Intelligence — the Live Market tab's own feed, distinct from
 * the homepage's "Live Intelligence" widget (see LiveIntelligenceFeed.tsx).
 * Homepage asks "what happened?"; this asks "why does it matter for
 * trading right now?" — so every card here surfaces the fields a trader
 * actually needs (confidence, affected sectors/companies, market impact,
 * why-it-matters) instead of just a headline. Not a duplicate of the
 * homepage widget: no Critical/High filter (traders want the full stream,
 * not just the breaking-news cut), richer card body, no shared component.
 *
 * All fields come straight from EventTriage via useLiveFeed() — nothing
 * synthesized or correlated here. A true "why did Nifty move" explanation
 * that clusters multiple events together (price move + contributing news)
 * is a separate, not-yet-built capability (a Market Movement Intelligence
 * Engine); this card shows real per-event AI triage output, not that.
 */

import Link from "next/link";
import { Radio, Activity, Sparkles } from "lucide-react";
import { useLiveFeed, PRIORITY_TIER_CLS, type FeedEntry } from "@/hooks/useMarketIntelligence";
import { scoreToColor } from "@/lib/scoring";

function timeLabel(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true });
  } catch {
    return "";
  }
}

const IMPACT_CLS: Record<string, string> = {
  high:   "text-rose-600 dark:text-rose-300",
  medium: "text-amber-600 dark:text-amber-300",
  low:    "text-text-secondary",
};

function RichCard({ entry }: { entry: FeedEntry }) {
  const affected = [...(entry.sectors ?? []), ...(entry.tickers ?? [])];
  return (
    <div className="rounded-xl border border-surface-border/4 bg-text-primary/[0.02] p-3 hover:border-surface-border/10 transition">
      <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] tabular-nums text-text-muted">{timeLabel(entry.ts)}</span>
        {entry.priorityTier && (
          <span className={`rounded-full border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wider ${PRIORITY_TIER_CLS[entry.priorityTier] ?? PRIORITY_TIER_CLS.Low}`}>
            {entry.priorityTier}
          </span>
        )}
        {entry.marketImpact && (
          <span className={`text-[9px] font-bold uppercase tracking-wider ${IMPACT_CLS[entry.marketImpact] ?? "text-text-secondary"}`}>
            {entry.marketImpact} impact
          </span>
        )}
        {/* CD3-C: entry.confidence is EventTriage.confidence -- triage_worker.py's
            bare LLM self-report (0-10 scale, hence * 10 here), SELF_REPORTED_CERTAINTY. */}
        {entry.confidence != null && (
          <span className="ml-auto text-[9px] font-bold tabular-nums text-text-muted" title="The model's own self-reported certainty from event triage -- not a verified score">{Math.round(entry.confidence * 10)}% confidence</span>
        )}
      </div>

      <p className="text-[12px] font-medium leading-snug text-text-primary line-clamp-2">{entry.headlineRaw || entry.headline}</p>

      {entry.oneLiner && entry.oneLiner !== entry.headlineRaw && (
        <p className="mt-1 text-[10.5px] leading-snug text-text-secondary line-clamp-2">{entry.oneLiner}</p>
      )}

      {affected.length > 0 && (
        <p className="mt-1.5 text-[9.5px] text-text-muted">
          <span className="text-text-muted">Affected:</span> {affected.slice(0, 4).join(" · ")}
        </p>
      )}

      {entry.href && (
        <Link href={entry.href} className="mt-1.5 inline-block text-[10px] font-semibold text-sky-400 hover:text-sky-600 dark:text-sky-300 transition">
          View Analysis →
        </Link>
      )}
    </div>
  );
}

function ScoreUpdateRow({ entry }: { entry: FeedEntry }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-surface-border/4 bg-text-primary/[0.02] p-2.5 hover:border-surface-border/10 transition">
      <span className="w-11 shrink-0 pt-0.5 text-[10px] tabular-nums text-text-muted">{timeLabel(entry.ts)}</span>
      <div className="min-w-0 flex-1">
        <div className="mb-0.5 flex items-center gap-1.5">
          <span className={`rounded-full border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wider ${entry.badge.cls}`}>
            {entry.badge.label}
          </span>
          {entry.score !== null && entry.score !== undefined && (
            <span className="text-[9px] font-bold tabular-nums" style={{ color: scoreToColor(entry.score) }}>
              {entry.scoreLabel}
            </span>
          )}
        </div>
        <p className="text-[12px] font-medium text-text-primary line-clamp-2">{entry.headline}</p>
        {entry.sub && <p className="mt-0.5 text-[10px] text-text-muted line-clamp-1">{entry.sub}</p>}
      </div>
    </div>
  );
}

export function LiveMarketIntelligence({ limit = 20 }: { limit?: number }) {
  const entries = useLiveFeed(limit);

  return (
    <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-y-1">
        <div className="flex items-center gap-2">
          <Activity className="h-3.5 w-3.5 shrink-0 text-sky-400" />
          <h3 className="whitespace-nowrap text-[11px] font-black uppercase tracking-[0.04em] text-text-primary">Live Market Intelligence</h3>
        </div>
        <span className="flex items-center gap-1.5 text-[10px] font-semibold text-text-muted">
          <Radio className="h-3 w-3 text-emerald-400" />
          Live
        </span>
      </div>

      {entries.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <Sparkles className="mb-2 h-4 w-4 text-text-muted" />
          <p className="text-[12px] text-text-muted">Watching for the next market-moving signal…</p>
          <p className="mt-1 text-[10px] text-text-muted">Confidence, affected sectors, and market impact appear here as real triage completes — nothing simulated.</p>
        </div>
      ) : (
        <div className="max-h-[440px] space-y-2 overflow-y-auto pr-1">
          {entries.map(entry => (
            <div key={entry.key}>
              {entry.kind === "score_update" ? <ScoreUpdateRow entry={entry} /> : <RichCard entry={entry} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
