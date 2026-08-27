import Link from "next/link";
import { AlertTriangle, ArrowRight, CalendarClock, Compass, Gauge, Rocket } from "lucide-react";
import type { WeekendIntelligenceSnapshotDTO } from "@/types/weekendIntelligence";
import {
  biasLabel,
  biasStyle,
  confidenceTierLabel,
  dedupeMarketRisks,
  evidenceQualityFor,
  formatDateFromISO,
  formatDateShort,
  formatTimeIST,
  sectorBreakdown,
  severityStyle,
  weekdayNameFromISODate,
} from "./weekendLabels";
import { WeekendConfidence } from "./WeekendConfidence";
import { WeekendMetricCard } from "./WeekendMetricCard";

/**
 * Row 1 — hero + 4 primary metric cards (redesign brief §4/§5/§6). Hero
 * takes ~28% on desktop, the 4 cards share the rest equally; on tablet
 * the hero drops to full width above a 2x2 metric grid, mobile stacks
 * everything (brief §22/§23). The hero itself carries no "how confident
 * is this" or degraded-banner content anymore — brief §26 wants a
 * compact status indicator (now in WeekendMetadataStrip) plus the real
 * confidence_warnings text surfaced in its own card, not a duplicate
 * banner here.
 *
 * 2026-08-22 owner correction — the original 4 cards (Overall Outlook /
 * Confidence / Since Close / Evidence Quality) spent two of the four
 * scarce above-the-fold slots on methodology metadata rather than
 * decision-useful content. Card shell, grid, position, and dimensions
 * are UNCHANGED; only cards 3 and 4's CONTENT changed, to "Biggest
 * Opportunity" and "Biggest Risk" — the two questions an investor
 * actually asks after "what's the outlook" and "how sure are you."
 * "Since Close" (raw signal count) and "Evidence Quality" are not
 * deleted — both are real, useful provenance detail — they moved into
 * the existing "How confident is this?" disclosure on card 2 (see
 * WeekendConfidence.tsx), where they support the confidence number
 * instead of competing with it for a whole card. Cards 1 and 2 also
 * gained one real derived line each (sector breakdown; confidence delta
 * vs the previous checkpoint) — every addition reads an existing real
 * field, nothing here is estimated or invented, and every "biggest"
 * pick degrades honestly to a plain "none" statement when the real data
 * has nothing to show (never a fabricated pick to fill the slot).
 */
export function WeekendPrimaryMetrics({ snapshot, previousConfidence, previousCheckpointLabel }: {
  snapshot: WeekendIntelligenceSnapshotDTO;
  previousConfidence?: number | null;
  previousCheckpointLabel?: string | null;
}) {
  const nextSession = weekdayNameFromISODate(snapshot.target_trading_date);
  const bias = biasStyle(snapshot.overall_bias);
  const quality = evidenceQualityFor(snapshot);
  const closeTime = snapshot.last_trading_date ? `${formatDateShort(snapshot.last_trading_date)}, 3:30 PM IST` : null;
  const generatedTime = formatTimeIST(snapshot.generated_at);
  const generatedDate = formatDateFromISO(snapshot.generated_at);

  const breakdown = sectorBreakdown(snapshot.top_sectors);
  const sectorCountLine = (["positive", "neutral", "negative", "mixed"] as const)
    .filter((k) => breakdown.counts[k] > 0)
    .map((k) => `${breakdown.counts[k]} ${k}`)
    .join(" · ");

  const confidenceDelta = previousConfidence != null ? Math.round(snapshot.production_confidence - previousConfidence) : null;

  const topOpportunity = snapshot.opportunities.length > 0
    ? [...snapshot.opportunities].sort((a, b) => b.opportunity_score - a.opportunity_score)[0]
    : null;
  // Headline is the real sector this opportunity is tagged with, not the
  // development headline that generated it (owner correction: "Aditya
  // Birla Capital to enter gold loan market" is the EVENT, "Banking" is
  // the opportunity) — falls back to the real title only on the rare row
  // with no sector tag at all, never a fabricated category.
  const opportunityHeadline = topOpportunity?.sectors[0] ?? topOpportunity?.title ?? null;

  const topRisk = dedupeMarketRisks(snapshot.market_risks)[0] ?? null;
  const topRiskStyle = topRisk ? severityStyle(topRisk.severity) : null;
  // Same sector-first framing as the opportunity headline; falls back to
  // the first named company, then a plain "Market Risk" category label
  // (never a fabricated sector/company) when the risk carries neither.
  const riskHeadline = topRisk?.related_sectors[0] ?? topRisk?.related_companies[0] ?? (topRisk ? "Market Risk" : null);
  const riskLinkSymbol = topRisk?.related_companies[0] ?? null;
  const SEVERITY_RANK: Record<string, number> = { low: 1, medium: 2, high: 3 };
  const SEVERITY_BAR_BG: Record<string, string> = { low: "bg-text-muted", medium: "bg-amber-500", high: "bg-rose-500" };
  const riskSeverityFilled = topRisk ? SEVERITY_RANK[topRisk.severity] ?? 2 : 0;
  const riskSeverityBarBg = topRisk ? SEVERITY_BAR_BG[topRisk.severity] ?? "bg-amber-500" : "bg-rose-500";

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
        caption={
          <>
            <p>Aggregated direction across every sector and company signal this weekend.</p>
            {(breakdown.leading.length > 0 || breakdown.lagging.length > 0) && (
              <p className="mt-1.5 text-[12px] text-text-secondary">
                {breakdown.leading.length > 0 && <>Leading: <span className="font-bold text-text-primary">{breakdown.leading.join(", ")}</span></>}
                {breakdown.leading.length > 0 && breakdown.lagging.length > 0 && " · "}
                {breakdown.lagging.length > 0 && <>Lagging: <span className="font-bold text-text-primary">{breakdown.lagging.join(", ")}</span></>}
              </p>
            )}
            {sectorCountLine && <p className="mt-1 text-[11px] text-text-muted">{sectorCountLine} sector{breakdown.counts.positive + breakdown.counts.neutral + breakdown.counts.negative + breakdown.counts.mixed === 1 ? "" : "s"}</p>}
          </>
        }
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
              {confidenceDelta != null && confidenceDelta !== 0 && (
                <span className="ml-1.5 font-semibold text-text-muted">
                  {confidenceDelta > 0 ? "↑" : "↓"} {Math.abs(confidenceDelta)} pt{Math.abs(confidenceDelta) === 1 ? "" : "s"}
                  {previousCheckpointLabel ? ` since ${previousCheckpointLabel}` : " since last checkpoint"}
                </span>
              )}
            </p>
            {/* Real production_confidence rendered as a bar — a different
                view of the same real number shown above, not a second
                invented metric. */}
            <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-border/10">
              <div
                className={`weekend-fill h-full rounded-full ${snapshot.production_confidence >= 60 ? "bg-emerald-500" : snapshot.production_confidence >= 40 ? "bg-amber-500" : "bg-rose-500"}`}
                style={{ width: `${Math.max(4, Math.min(100, Math.round(snapshot.production_confidence)))}%` }}
              />
            </div>
            <div className="mt-2">
              <WeekendConfidence
                components={snapshot.confidence_components}
                evidenceQuality={quality}
                sourceTypeCount={Object.keys(snapshot.evidence_summary.by_source_type).length}
                companyCount={snapshot.top_companies.length}
                sectorCount={snapshot.top_sectors.length}
              />
            </div>
          </>
        }
      />

      <WeekendMetricCard
        icon={<Rocket className="h-4 w-4" aria-hidden="true" />}
        iconClassName="bg-emerald-500/10 text-emerald-500"
        accent="emerald"
        label="Biggest Opportunity"
        value={opportunityHeadline ? <>{opportunityHeadline} <span aria-hidden="true" className="text-emerald-500">↑</span></> : "—"}
        valueClassName={opportunityHeadline ? "text-text-primary" : "text-text-muted"}
        // Headline is either a short sector name ("Banking") or, on the
        // rare untagged row, a company ticker/longer title fallback —
        // smaller than cards 1/2's fixed "STRONG POSITIVE"/"64%" size so
        // the longer fallback case never clips within the card's width.
        valueTextSize="text-[26px]"
        caption={
          topOpportunity ? (
            <div className="flex h-full flex-col">
              {/* Labeled the same honest way as WeekendOpportunities.tsx's
                  own list — a count-based activity heuristic, never a
                  success-probability claim. */}
              <p className="text-[12px] font-bold text-emerald-500">
                {Math.round(topOpportunity.opportunity_score)} <span className="font-semibold text-text-muted">Opportunity Activity Score</span>
              </p>
              {/* Real ai_summary.matters when the row has one; falls back
                  to the real title (never a paraphrase invented here) —
                  see _resolve_opportunities in weekend_intelligence.py. */}
              <p className="mt-1.5 line-clamp-2 text-[12px] leading-snug text-text-secondary">
                {topOpportunity.reason ?? topOpportunity.title}
              </p>
              {(topOpportunity.companies ?? []).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {/* Each pill colored by that company's OWN real trend
                      (OpportunityCompany.trend) — never a uniform green
                      borrowed from the opportunity's aggregate direction,
                      since a company can legitimately trend against the
                      opportunity as a whole. Same real field/fix as
                      opportunity-radar's Impact column (see
                      OpportunityPageClient.tsx's directionLabel). */}
                  {topOpportunity.companies.map((c) => (
                    <span key={c.symbol} className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${
                      c.trend === "up" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
                      : c.trend === "down" ? "border-rose-500/25 bg-rose-500/10 text-rose-600 dark:text-rose-300"
                      : "border-surface-border/15 bg-surface-border/5 text-text-secondary"
                    }`}>{c.symbol}</span>
                  ))}
                </div>
              )}
              <Link
                href={`/opportunity-radar/${topOpportunity.id}`}
                className="group/link mt-auto flex items-center gap-1 pt-2 text-[11px] font-semibold text-violet-400 transition duration-200 hover:text-violet-300"
              >
                View opportunity <ArrowRight className="h-3 w-3 transition-transform duration-200 group-hover/link:translate-x-0.5" aria-hidden="true" />
              </Link>
            </div>
          ) : (
            <p>No standout opportunity flagged this weekend.</p>
          )
        }
      />

      <WeekendMetricCard
        icon={<AlertTriangle className="h-4 w-4" aria-hidden="true" />}
        iconClassName="bg-rose-500/10 text-rose-500"
        accent="rose"
        label="Biggest Risk"
        value={riskHeadline ? <>{riskHeadline} <span aria-hidden="true" className="text-rose-500">↓</span></> : "—"}
        valueClassName={riskHeadline ? "text-text-primary" : "text-text-muted"}
        valueTextSize="text-[26px]"
        caption={
          topRisk && topRiskStyle ? (
            <div className="flex h-full flex-col">
              <div className="flex items-center gap-1.5">
                <p className={`text-[12px] font-bold ${topRiskStyle.textClass}`}>{topRiskStyle.label} Severity</p>
                {/* A real 3-tier discrete meter (low/medium/high), never a
                    fabricated precise number — WeekendRisk has no numeric
                    risk score, only this enum (see severityStyle). */}
                <span className="flex items-center gap-0.5" aria-hidden="true">
                  {[1, 2, 3].map((i) => (
                    <span key={i} className={`h-1.5 w-3 rounded-full ${i <= riskSeverityFilled ? riskSeverityBarBg : "bg-surface-border/15"}`} />
                  ))}
                </span>
              </div>
              <p className="mt-1.5 line-clamp-2 text-[12px] leading-snug text-text-secondary">{topRisk.description}</p>
              {topRisk.related_companies.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {/* Rose, not neutral gray — WeekendRisk carries no
                      per-company trend field (unlike opportunities'
                      companies), but every name here is explicitly
                      "related to THIS risk" by the backend's own
                      dedupeMarketRisks grouping, so tinting them with
                      the risk's own real direction is honest context,
                      not an invented per-company signal. */}
                  {topRisk.related_companies.slice(0, 3).map((c) => (
                    <span key={c} className="rounded-full border border-rose-500/25 bg-rose-500/10 px-2 py-0.5 text-[10px] font-bold text-rose-600 dark:text-rose-300">{c}</span>
                  ))}
                </div>
              )}
              {riskLinkSymbol && (
                <Link
                  href={`/companies/${riskLinkSymbol}`}
                  className="group/link mt-auto flex items-center gap-1 pt-2 text-[11px] font-semibold text-violet-400 transition duration-200 hover:text-violet-300"
                >
                  View {riskLinkSymbol} <ArrowRight className="h-3 w-3 transition-transform duration-200 group-hover/link:translate-x-0.5" aria-hidden="true" />
                </Link>
              )}
            </div>
          ) : (
            <p>No dominant risk detected.</p>
          )
        }
      />
    </section>
  );
}
