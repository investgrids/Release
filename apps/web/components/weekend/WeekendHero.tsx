import type { WeekendIntelligenceSnapshotDTO } from "@/types/weekendIntelligence";
import { biasLabel, biasStyle, formatUpdatedAt, weekdayNameFromISODate } from "./weekendLabels";
import { WeekendConfidence } from "./WeekendConfidence";

/**
 * Top-of-page hero — brief §8/§24: outlook, confidence, meaningful-change
 * count, updated time, above the fold, nothing else. No 700px hero, no
 * ten metrics competing for attention.
 */
export function WeekendHero({ snapshot }: { snapshot: WeekendIntelligenceSnapshotDTO }) {
  const nextSession = weekdayNameFromISODate(snapshot.target_trading_date);
  const bias = biasStyle(snapshot.overall_bias);
  const updated = formatUpdatedAt(snapshot.generated_at, snapshot.checkpoint_label);

  return (
    <div className="rounded-2xl border border-surface-border/7 bg-surface-card p-6 sm:p-7">
      <p className="text-[11px] font-black uppercase tracking-wider text-violet-400">Weekend Intelligence</p>
      <h1 className="mt-1.5 text-[24px] font-black leading-tight text-text-primary sm:text-[28px]">
        Preparing You For {nextSession}
      </h1>
      <p className="mt-1 text-[12px] font-semibold text-text-muted">Market Closed</p>

      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-text-muted">Overall Outlook</p>
          <p className={`mt-1 text-[20px] font-black ${bias.textClass}`}>
            {biasLabel(snapshot.overall_bias).toUpperCase()} <span aria-hidden="true">{bias.symbol}</span>
          </p>
        </div>
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-text-muted">Confidence</p>
          <p className="mt-1 text-[20px] font-black tabular-nums text-text-primary">
            {Math.round(snapshot.production_confidence)}%
          </p>
        </div>
        <div className="col-span-2 sm:col-span-1">
          <p className="text-[10px] font-bold uppercase tracking-wider text-text-muted">Since Close</p>
          <p className="mt-1 text-[13px] font-bold leading-tight text-text-primary">
            {snapshot.new_since_close_count} meaningful development{snapshot.new_since_close_count === 1 ? "" : "s"}
          </p>
        </div>
        <div className="col-span-2 sm:col-span-1">
          <p className="text-[10px] font-bold uppercase tracking-wider text-text-muted">Updated</p>
          <p className="mt-1 text-[13px] font-bold leading-tight text-text-primary">{updated}</p>
        </div>
      </div>

      {snapshot.status === "degraded" && (
        <p className="mt-5 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-[11px] leading-relaxed text-amber-300/90">
          Some baseline market data is unavailable. This outlook is based on verified weekend developments currently available.
        </p>
      )}

      <div className="mt-5">
        <WeekendConfidence components={snapshot.confidence_components} />
      </div>
    </div>
  );
}
