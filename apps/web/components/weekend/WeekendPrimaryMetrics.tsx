import { BadgeCheck, CalendarClock, Compass, Gauge, Newspaper } from "lucide-react";
import type { WeekendIntelligenceSnapshotDTO } from "@/types/weekendIntelligence";
import {
  biasLabel,
  biasStyle,
  confidenceTierLabel,
  evidenceQualityFor,
  formatDateFromISO,
  formatDateShort,
  formatTimeIST,
  weekdayNameFromISODate,
} from "./weekendLabels";
import { WeekendConfidence } from "./WeekendConfidence";
import { WeekendMetricCard } from "./WeekendMetricCard";

const QUALITY_TONE_CLASS: Record<string, string> = {
  positive: "text-emerald-500",
  neutral: "text-amber-500",
  muted: "text-text-muted",
};

/**
 * Row 1 — hero + 4 primary metric cards (redesign brief §4/§5/§6). Hero
 * takes ~28% on desktop, the 4 cards share the rest equally; on tablet
 * the hero drops to full width above a 2x2 metric grid, mobile stacks
 * everything (brief §22/§23). The hero itself carries no "how confident
 * is this" or degraded-banner content anymore — brief §26 wants a
 * compact status indicator (now in WeekendMetadataStrip) plus the real
 * confidence_warnings text surfaced in its own card, not a duplicate
 * banner here.
 */
export function WeekendPrimaryMetrics({ snapshot }: { snapshot: WeekendIntelligenceSnapshotDTO }) {
  const nextSession = weekdayNameFromISODate(snapshot.target_trading_date);
  const bias = biasStyle(snapshot.overall_bias);
  const quality = evidenceQualityFor(snapshot);
  const closeTime = snapshot.last_trading_date ? `${formatDateShort(snapshot.last_trading_date)}, 3:30 PM IST` : null;
  const generatedTime = formatTimeIST(snapshot.generated_at);
  const generatedDate = formatDateFromISO(snapshot.generated_at);

  return (
    <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-[minmax(330px,1.35fr)_repeat(4,minmax(190px,0.85fr))] lg:items-stretch">
      <div className="flex h-full min-h-[225px] flex-col justify-center py-1 sm:col-span-2 lg:col-span-1 lg:py-5">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-violet-500">Weekend Intelligence</p>
        {/* Visible layout uses two differently-sized spans (brief §5:
            headline vs. day get distinct sizes/weights) marked
            aria-hidden; the real accessible name is the single sr-only
            text run below, so "Preparing You For {day}" still reads as
            one continuous string to assistive tech (and to tests).
            Spacing matches the exact spec: pill->heading 14px,
            heading->day 2px, day->description 14px, description->chip
            18px. */}
        <h1 className="mt-3.5 leading-tight text-text-primary [text-wrap:balance]">
          <span aria-hidden="true" className="text-[28px] font-semibold sm:text-[34px]">Preparing You For</span>
          {/* A solid, considered violet reads as intentional — the
              gradient-text-fill this replaced is a well-known AI-design
              tell that would have undercut the rest of this page's
              deliberately restrained palette. */}
          <span
            aria-hidden="true"
            className="mt-0.5 block text-[38px] font-black leading-[1.05] text-violet-600 sm:text-[48px]"
          >
            {nextSession}
          </span>
          <span className="sr-only">Preparing You For {nextSession}</span>
        </h1>
        {closeTime && (
          <p className="mt-3.5 text-[13px] leading-relaxed text-text-secondary">
            Comprehensive intelligence from market close on {closeTime}
            {generatedDate && generatedTime && ` to ${generatedDate}, ${generatedTime}`}
          </p>
        )}
        <div className="mt-[18px] inline-flex w-fit items-center gap-2 rounded-lg border border-surface-border/12 bg-surface-border/5 px-3 py-1.5 text-[11px] font-bold text-text-primary">
          <CalendarClock className="h-3.5 w-3.5 text-violet-500" aria-hidden="true" />
          Next Trading Session: {nextSession}, {formatDateShort(snapshot.target_trading_date)}
        </div>
      </div>

      <WeekendMetricCard
        icon={<Compass className="h-4 w-4" aria-hidden="true" />}
        label="Overall Outlook"
        value={<>{biasLabel(snapshot.overall_bias).toUpperCase()} <span aria-hidden="true">{bias.symbol}</span></>}
        valueClassName={bias.textClass}
        caption="Aggregated direction across every sector and company signal this weekend."
      />

      <WeekendMetricCard
        icon={<Gauge className="h-4 w-4" aria-hidden="true" />}
        label="Confidence"
        value={`${Math.round(snapshot.production_confidence)}%`}
        caption={
          <>
            {/* Tier word is the same confidenceTierLabel() thresholds
                summaryTemplate uses — a label for the number above, not
                a second computed metric. */}
            <p className={`text-[12px] font-bold ${snapshot.production_confidence >= 60 ? "text-emerald-500" : snapshot.production_confidence >= 40 ? "text-amber-500" : "text-rose-500"}`}>
              {confidenceTierLabel(snapshot.production_confidence)}
            </p>
            {/* Real production_confidence rendered as a bar — a different
                view of the same real number shown above, not a second
                invented metric. */}
            <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-border/10">
              <div
                className={`h-full rounded-full ${snapshot.production_confidence >= 60 ? "bg-emerald-500" : snapshot.production_confidence >= 40 ? "bg-amber-500" : "bg-rose-500"}`}
                style={{ width: `${Math.max(4, Math.min(100, Math.round(snapshot.production_confidence)))}%` }}
              />
            </div>
            <div className="mt-2">
              <WeekendConfidence components={snapshot.confidence_components} />
            </div>
          </>
        }
      />

      <WeekendMetricCard
        icon={<Newspaper className="h-4 w-4" aria-hidden="true" />}
        label="Since Close"
        value={snapshot.new_since_close_count}
        caption={`Across ${snapshot.top_companies.length} compan${snapshot.top_companies.length === 1 ? "y" : "ies"}, ${snapshot.top_sectors.length} sector${snapshot.top_sectors.length === 1 ? "" : "s"}, and key events.`}
      />

      <WeekendMetricCard
        icon={<BadgeCheck className="h-4 w-4" aria-hidden="true" />}
        label="Evidence Quality"
        value={quality.label}
        valueClassName={QUALITY_TONE_CLASS[quality.tone]}
        caption={quality.description.charAt(0).toUpperCase() + quality.description.slice(1)}
      />
    </section>
  );
}
