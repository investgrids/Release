"use client";

// switch_analysis — rebuilt against the approved BEL/HAL mockup
// (2026-09-23, dense research-terminal restyle). Sourced ENTIRELY from
// AEV2SwitchAnswer (answerTypes.ts), itself built only from
// assemble_aev2()'s real switch_analysis field — never a plain
// SearchResult field. See answerTypes.ts's own module-boundary comment:
// AEV2SwitchAnswer carries no `raw: SearchResult`, and neither
// AEV2Response nor AEV2SwitchAnalysis has a field for a verdict,
// rating, or recommendation, so no prohibited concept is reachable here.
//
// This mockup asked for a visual language denser than AIAnswerShell's
// shared chrome (tighter borders, a 360px sticky rail, per-mode header/
// evidence-table/right-rail styling) — restyling AIAnswerShell itself
// would leak that look into direct_company_research/company_comparison/
// event_impact/market_pulse, none of which this task reviewed. This
// component therefore renders its OWN page chrome rather than wrapping
// <AIAnswerShell>, so the redesign stays isolated to switch_analysis by
// construction. It still reuses AIAnswerShell's/aev2Shared's shared
// LOGIC (never its shared visual components) so the underlying rules —
// citation numbering, evidence-coverage counting, the "verified source"
// honesty gate — can't quietly drift into a second copy.
import Link from "next/link";
import { Plus, SlidersHorizontal, ShieldCheck, ChevronRight, ExternalLink } from "lucide-react";
import { AIDisclaimer } from "../AIDisclaimer";
import { sourceCountBadgeLabel, type EvidenceCoverageSummary } from "../AIAnswerShell";
import type { AEV2SwitchAnswer } from "../answerTypes";
import type { AEV2Confidence, AEV2CompanyRef, AEV2ComparisonValue } from "../aev2Types";
import {
  buildCitationIndex, buildEvidenceCoverage, CitationMarks, switchDimensionsToPairViews,
  type PairDimensionView,
} from "../aev2Shared";

// ── Canonical dimension order — AEV2ComparisonDimensionKey is a closed
// 3-value union (recent_developments | price_reaction | evidence_
// freshness; no valuation/order-book/risk keys exist in the real
// contract at all). Sorting locally against this fixed order keeps the
// table's row order deterministic even if the backend's own array order
// ever changes, without inventing any dimension the contract doesn't
// send.
const DIMENSION_ORDER = ["recent_developments", "price_reaction", "evidence_freshness"];
function byCanonicalOrder(a: PairDimensionView, b: PairDimensionView) {
  return DIMENSION_ORDER.indexOf(a.key) - DIMENSION_ORDER.indexOf(b.key);
}

// Only price_reaction's display text carries a real, backend-approved
// sign ("285.40 (+1.10%)") — recent_developments/evidence_freshness are
// plain descriptive strings with no inherent direction. Coloring only
// this one row (and using a neutral dot everywhere else) re-presents
// the SAME approved text's sign rather than inferring a judgment the
// contract doesn't carry.
function priceDirectionDot(display: string): string {
  if (/\(\+/.test(display)) return "bg-emerald-500";
  if (/\(-/.test(display)) return "bg-rose-500";
  return "bg-slate-400";
}

function DimensionCell({ dim, side }: { dim: PairDimensionView; side: "left" | "right" }) {
  const value = side === "left" ? dim.left : dim.right;
  if (!dim.comparable || !value) {
    // Never implies the missing side is weaker — a plain, honest
    // "insufficient data" state, not a filled-in placeholder.
    return <span className="text-text-muted">Insufficient verified data</span>;
  }
  return (
    <span className="flex items-start gap-2">
      {dim.key === "price_reaction" && (
        <span className={`mt-1.5 size-2.5 shrink-0 rounded-full ${priceDirectionDot(value.display)}`} />
      )}
      <span className="text-text-secondary">{value.display}</span>
    </span>
  );
}

function ComparisonTable({
  dimensions, leftLabel, rightLabel, refIndex,
}: {
  dimensions: PairDimensionView[];
  leftLabel: string;
  rightLabel: string;
  refIndex: Map<string, number>;
}) {
  const rows = [...dimensions].sort(byCanonicalOrder);
  if (rows.length === 0) return null;
  return (
    <>
      {/* Mobile: paired stacked cards, never a squeezed 3-column table. */}
      <div className="space-y-3 md:hidden">
        {rows.map(dim => (
          <div key={dim.key} className="rounded-xl border border-surface-border bg-surface-card p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.04em] text-text-muted">{dim.label}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div>
                <p className="text-xs font-medium text-text-primary">{leftLabel}</p>
                <div className="mt-1 text-sm leading-5">
                  <DimensionCell dim={dim} side="left" />
                  {dim.left && <CitationMarks refs={dim.left.evidence_refs} refIndex={refIndex} />}
                </div>
              </div>
              <div>
                <p className="text-xs font-medium text-text-primary">{rightLabel}</p>
                <div className="mt-1 text-sm leading-5">
                  <DimensionCell dim={dim} side="right" />
                  {dim.right && <CitationMarks refs={dim.right.evidence_refs} refIndex={refIndex} />}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Desktop table. */}
      <div className="hidden overflow-hidden rounded-xl border border-surface-border md:block">
        <table className="w-full table-fixed border-collapse text-left text-sm">
          <colgroup>
            <col style={{ width: "22%" }} />
            <col style={{ width: "39%" }} />
            <col style={{ width: "39%" }} />
          </colgroup>
          <thead>
            <tr>
              <th className="border-b border-surface-border bg-text-primary/[0.05] px-4 py-3 text-xs font-semibold uppercase tracking-[0.04em] text-text-muted">
                Factor
              </th>
              <th className="border-b border-surface-border bg-text-primary/[0.05] px-4 py-3 text-xs font-semibold uppercase tracking-[0.04em] text-text-muted">
                <span className="flex items-center gap-3 text-sm font-semibold normal-case tracking-normal text-text-primary">{leftLabel}</span>
              </th>
              <th className="border-b border-surface-border bg-text-primary/[0.05] px-4 py-3 text-xs font-semibold uppercase tracking-[0.04em] text-text-muted">
                <span className="flex items-center gap-3 text-sm font-semibold normal-case tracking-normal text-text-primary">{rightLabel}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(dim => (
              <tr key={dim.key}>
                <td className="border-b border-surface-border/65 bg-text-primary/[0.02] px-4 py-3 align-top text-sm font-medium leading-5 text-text-primary last:border-b-0">
                  {dim.label}
                </td>
                <td className="border-b border-surface-border/65 px-4 py-3 align-top text-sm leading-5 last:border-b-0">
                  <DimensionCell dim={dim} side="left" />
                  {dim.left && <CitationMarks refs={dim.left.evidence_refs} refIndex={refIndex} />}
                </td>
                <td className="border-b border-surface-border/65 px-4 py-3 align-top text-sm leading-5 last:border-b-0">
                  <DimensionCell dim={dim} side="right" />
                  {dim.right && <CitationMarks refs={dim.right.evidence_refs} refIndex={refIndex} />}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function EntitySnapshotRow({ company, priceDim, side }: { company: AEV2CompanyRef; priceDim?: PairDimensionView; side: "left" | "right" }) {
  const value: AEV2ComparisonValue | null | undefined = priceDim && (side === "left" ? priceDim.left : priceDim.right);
  return (
    <div className="space-y-3 border-b border-surface-border/70 pb-4 last:border-b-0 last:pb-0">
      <div className="flex items-start gap-3">
        <div className="flex size-11 shrink-0 items-center justify-center rounded-full border border-surface-border bg-bg text-xs font-semibold text-text-secondary">
          {company.symbol.slice(0, 2)}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text-primary">{company.name}</p>
          <p className="text-xs text-text-muted">{company.symbol}</p>
        </div>
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1.5 text-sm">
        <p className="text-text-muted">Price reaction</p>
        <p className="text-right tabular-nums text-text-primary">{value?.display ?? "Insufficient verified data"}</p>
      </div>
    </div>
  );
}

function ConfidenceCard({ confidence }: { confidence: AEV2Confidence }) {
  if (confidence.score == null) {
    return (
      <div className="overflow-hidden rounded-2xl border border-surface-border/80 bg-surface-card p-4">
        <p className="text-sm font-semibold text-text-primary">Evidence Confidence</p>
        <p className="mt-1 text-xs text-text-muted">Unscored — not enough evidence signal for this answer.</p>
      </div>
    );
  }
  const score = Math.round(confidence.score);
  const barColor = score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="overflow-hidden rounded-2xl border border-surface-border/80 bg-surface-card p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-text-primary">Evidence Confidence</p>
        <p className="text-3xl font-semibold tracking-[-0.03em] text-text-primary">{score}%</p>
      </div>
      <p className="mt-1 text-xs text-text-secondary">{confidence.level}</p>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-text-primary/[0.08]">
        <div className={`h-full rounded-full transition-[width] duration-300 ${barColor}`} style={{ width: `${score}%` }} />
      </div>
      {/* Only components_available (which contributed) — never fabricated
          per-component percentages; aev2/confidence.py never returns those. */}
      <p className="mt-2 text-[11px] text-text-muted">
        {confidence.components_available.length > 0
          ? `Based on: ${confidence.components_available.join(", ")}`
          : "No scored components available"}
      </p>
    </div>
  );
}

function CoverageCard({ summary }: { summary: EvidenceCoverageSummary }) {
  const rows = [
    { label: "verified news source", count: summary.newsSourceCount },
    { label: "structured market event", count: summary.eventSourceCount },
    { label: "government / regulatory source", count: summary.policySourceCount },
    { label: "exchange / company filing", count: summary.filingSourceCount ?? 0 },
  ].filter(r => r.count > 0);
  if (rows.length === 0) return null;
  return (
    <div className="overflow-hidden rounded-2xl border border-surface-border/80 bg-surface-card p-4">
      <p className="flex items-center gap-1.5 text-sm font-semibold text-text-primary">
        <ShieldCheck size={14} strokeWidth={1.8} className="text-violet-400" />
        Evidence Coverage
      </p>
      <div className="mt-3 space-y-2">
        {rows.map(r => (
          <p key={r.label} className="text-xs text-text-secondary">
            {r.count} {r.label}{r.count === 1 ? "" : "s"}
          </p>
        ))}
      </div>
    </div>
  );
}

export function SwitchAnalysisLayout({
  answer, onNewSearch, onRefine: _onRefine,
}: {
  answer: AEV2SwitchAnswer;
  onNewSearch: () => void;
  onRefine?: () => void;
}) {
  const { aev2, switch: sw } = answer;

  const { rows: evidenceRows, refIndex } = buildCitationIndex(
    [
      { label: "Comparison", refs: sw.direct_comparison.evidence_refs },
      ...sw.dimensions.flatMap(d => [
        ...(d.current_company ? [{ label: `${d.label} — ${sw.current_company.symbol}`, refs: d.current_company.evidence_refs }] : []),
        ...(d.alternative_company ? [{ label: `${d.label} — ${sw.alternative_company.symbol}`, refs: d.alternative_company.evidence_refs }] : []),
      ]),
      ...sw.conditions_favoring_current.map(c => ({ label: `Favoring ${sw.current_company.symbol}`, refs: c.evidence_refs })),
      ...sw.conditions_favoring_alternative.map(c => ({ label: `Favoring ${sw.alternative_company.symbol}`, refs: c.evidence_refs })),
    ],
    aev2.evidence,
  );
  const evidenceCoverage = buildEvidenceCoverage(aev2.evidence);
  const pairDimensions = switchDimensionsToPairViews(sw.dimensions);
  const priceDim = pairDimensions.find(d => d.key === "price_reaction");

  // A plain, deterministic summary of whether the evidence favors one
  // side — never a Buy/Sell/Hold verdict, just a count of the SAME
  // conditions rendered below. See aev2/switch_analysis.py's
  // _build_conditions for how these lists are derived.
  const currentCount = sw.conditions_favoring_current.length;
  const alternativeCount = sw.conditions_favoring_alternative.length;
  const headline =
    currentCount === 0 && alternativeCount === 0
      ? "No clear evidence advantage yet"
      : currentCount > alternativeCount
        ? `Evidence leans toward ${sw.current_company.name}`
        : alternativeCount > currentCount
          ? `Evidence leans toward ${sw.alternative_company.name}`
          : "Evidence is evenly balanced";

  // Neither AEV2Response nor AEV2SwitchAnalysis carries a page-level
  // "generated at" timestamp anywhere in the real contract — inventing
  // one would violate the no-fabrication rule. evidence_freshness IS a
  // real per-company fact already shown in the table below; surfacing
  // it compactly in the header metadata line re-presents that same
  // approved data rather than asserting a new, unbacked fact.
  const freshnessDim = pairDimensions.find(d => d.key === "evidence_freshness");
  const freshnessLine = freshnessDim?.comparable && freshnessDim.left && freshnessDim.right
    ? `Evidence fresh as of: ${sw.current_company.symbol} ${freshnessDim.left.display} · ${sw.alternative_company.symbol} ${freshnessDim.right.display}`
    : null;

  const relatedEvents = aev2.related_intelligence.events;

  return (
    <div className="mx-auto w-full max-w-[1600px] px-4 sm:px-5 lg:px-8" data-testid="ai-answer-shell" data-ui-mode="switch_analysis">
      {/* Header */}
      <header className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <h1 className="max-w-4xl text-2xl font-semibold tracking-[-0.025em] text-text-primary sm:text-3xl lg:text-[32px] lg:leading-[1.15]">
            {answer.query}
          </h1>
          {freshnessLine && (
            <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted sm:text-sm">
              {freshnessLine}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={onNewSearch}
            className="flex h-10 items-center gap-1.5 rounded-xl border border-surface-border bg-surface-card px-4 text-sm font-medium text-text-primary shadow-sm transition-colors hover:bg-text-primary/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/40"
          >
            <Plus className="h-3.5 w-3.5" /> New Search
          </button>
          {/* Refine stays disabled for every AEV2-shell render — see
              AIAnswerShell.tsx's own comment on why the legacy Refine
              endpoint can't safely be wired to an AEV2 answer yet.
              Overflow menu is omitted entirely rather than shown
              disabled: it has no real action behind it today (matching
              this task's "only if it has real actions" rule). */}
          <button
            type="button"
            disabled
            aria-disabled="true"
            title="Refinement is being upgraded for this answer format."
            className="flex h-10 items-center gap-1.5 rounded-xl border border-surface-border bg-surface-card px-4 text-sm font-medium text-text-muted opacity-45 cursor-not-allowed"
          >
            <SlidersHorizontal className="h-3.5 w-3.5" /> Refine
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_360px] xl:gap-5">
        {/* Main column */}
        <main className="min-w-0 space-y-4">
          <div className="overflow-hidden rounded-2xl border border-surface-border/80 bg-surface-card text-text-primary shadow-[0_1px_3px_rgba(15,23,42,0.05)] p-4 sm:p-5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-base font-semibold tracking-[-0.01em] text-text-primary">Evidence-based comparison</span>
              <span className="inline-flex h-7 items-center rounded-full border border-violet-500/20 bg-violet-500/[0.08] px-2.5 text-xs font-medium text-violet-600 dark:text-violet-300">
                Switch comparison
              </span>
              {evidenceRows.length > 0 && (
                <span className="inline-flex h-7 items-center rounded-full border border-surface-border bg-text-primary/[0.06] px-2.5 text-xs font-medium text-text-muted">
                  {sourceCountBadgeLabel(evidenceRows.length, evidenceCoverage)}
                </span>
              )}
            </div>

            <p className="mt-3 text-xl font-semibold leading-snug tracking-[-0.02em] text-text-primary sm:text-2xl">
              {headline}
            </p>
            <p className="mt-1.5 max-w-5xl text-sm leading-6 text-text-secondary sm:text-[15px]">
              {sw.direct_comparison.text}
              <CitationMarks refs={sw.direct_comparison.evidence_refs} refIndex={refIndex} />
            </p>

            {/* Side-by-side comparison — restricted to the 3 real
                AEV2ComparisonDimensionKey values; no valuation/order-
                book/business-exposure/risk row exists in the real
                contract to render. */}
            <div className="mt-4">
              <ComparisonTable
                dimensions={pairDimensions}
                leftLabel={sw.current_company.name}
                rightLabel={sw.alternative_company.name}
                refIndex={refIndex}
              />
            </div>

            {/* Conditions favoring each side — evidence-backed only; a
                card is omitted entirely (never shown empty) when its
                side has none, and never given generic "conditions
                favoring X" copy the contract didn't produce. */}
            {(currentCount > 0 || alternativeCount > 0) && (
              <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
                {currentCount > 0 && (
                  <div className="overflow-hidden rounded-xl border border-emerald-200/70 bg-emerald-50/45 dark:border-emerald-500/20 dark:bg-emerald-500/5">
                    <p className="border-b border-current/10 px-4 py-3 text-sm font-semibold text-emerald-700 dark:text-emerald-300">
                      Conditions favoring {sw.current_company.name}
                    </p>
                    <ul className="space-y-2 px-4 py-3 text-sm leading-5 text-text-secondary">
                      {sw.conditions_favoring_current.map((c, i) => (
                        <li key={i}>{c.text}<CitationMarks refs={c.evidence_refs} refIndex={refIndex} /></li>
                      ))}
                    </ul>
                  </div>
                )}
                {alternativeCount > 0 && (
                  <div className="overflow-hidden rounded-xl border border-amber-200/70 bg-amber-50/45 dark:border-amber-500/20 dark:bg-amber-500/5">
                    <p className="border-b border-current/10 px-4 py-3 text-sm font-semibold text-amber-700 dark:text-amber-300">
                      Conditions favoring {sw.alternative_company.name}
                    </p>
                    <ul className="space-y-2 px-4 py-3 text-sm leading-5 text-text-secondary">
                      {sw.conditions_favoring_alternative.map((c, i) => (
                        <li key={i}>{c.text}<CitationMarks refs={c.evidence_refs} refIndex={refIndex} /></li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* What would change the comparison — hidden entirely when
                the contract has no monitoring conditions. */}
            {sw.what_changes_the_comparison.length > 0 && (
              <div className="mt-3 overflow-hidden rounded-xl border border-sky-200/70 bg-sky-50/40 dark:border-sky-500/20 dark:bg-sky-500/5">
                <p className="px-4 py-3 text-sm font-semibold text-sky-700 dark:text-sky-300">What would change this comparison</p>
                <div className="grid grid-cols-1 divide-y divide-surface-border/60 md:grid-cols-3 md:divide-x md:divide-y-0">
                  {sw.what_changes_the_comparison.map((c, i) => (
                    <div key={i} className="flex gap-3 p-4">
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-sky-300 bg-surface-card text-xs font-semibold text-sky-700 dark:border-sky-500/40 dark:text-sky-300">
                        {i + 1}
                      </span>
                      <p className="text-sm leading-6 text-text-secondary">{c.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Key evidence table — consistent citation numbering, an
              identifiable source/type, never a fabricated link (the
              real AEV2 evidence catalog carries no URL/route field at
              all, so no row is ever clickable today). */}
          {evidenceRows.length > 0 && (
            <div className="overflow-hidden rounded-2xl border border-surface-border/80 bg-surface-card">
              <div className="flex items-center justify-between border-b border-surface-border px-4 py-3">
                <p className="text-sm font-semibold text-text-primary">Key evidence and sources</p>
              </div>
              {/* Mobile cards */}
              <div className="space-y-2 p-3 md:hidden">
                {evidenceRows.map((row, i) => (
                  <div key={row.id} className="rounded-xl border border-surface-border bg-surface-card p-3">
                    <p className="text-xs text-text-muted">[{i + 1}] {row.date ?? "—"} · {row.source}</p>
                    <p className="mt-1 text-sm font-medium leading-5 text-text-primary">{row.headline}</p>
                  </div>
                ))}
              </div>
              {/* Desktop rows */}
              <div className="hidden md:block">
                {evidenceRows.map((row, i) => (
                  <div key={row.id} className="grid grid-cols-[48px_100px_140px_minmax(0,1fr)_32px] items-start gap-2 border-b border-surface-border/60 px-4 py-2.5 text-xs last:border-b-0">
                    <span className="text-text-muted tabular-nums">[{i + 1}]</span>
                    <span className="text-text-muted">{row.date ?? "—"}</span>
                    <span className="text-text-muted">{row.source}</span>
                    <span className="text-sm font-medium leading-5 text-text-primary">{row.headline}</span>
                    <span />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Footer — the ONE compliance disclaimer for this page (a
              second copy elsewhere would repeat AIAnswerShell's own
              already-fixed duplicate-disclaimer bug — see its 2026-09-22
              content-integrity fix comment). */}
          <div className="mt-5 border-t border-surface-border/70 pt-4">
            <AIDisclaimer />
          </div>
        </main>

        {/* Right rail */}
        <aside className="space-y-3 xl:sticky xl:top-24 xl:self-start">
          <div className="overflow-hidden rounded-2xl border border-surface-border/80 bg-surface-card p-4">
            <p className="mb-1 text-sm font-semibold text-text-primary">Companies compared</p>
            <EntitySnapshotRow company={sw.current_company} priceDim={priceDim} side="left" />
            <EntitySnapshotRow company={sw.alternative_company} priceDim={priceDim} side="right" />
          </div>

          <ConfidenceCard confidence={aev2.confidence} />
          <CoverageCard summary={evidenceCoverage} />

          {/* Ripple/opportunities are always null/[] in today's real
              AEV2Response (no CoreAnswer source yet — see
              AEV2RelatedIntelligence's own comment), so neither ever
              renders here; Related Intelligence and Methodology are the
              only real rows, each shown only when it leads somewhere
              real. */}
          <div className="divide-y divide-surface-border/70 overflow-hidden rounded-2xl border border-surface-border/80 bg-surface-card">
            {relatedEvents.length > 0 && (
              <div className="px-4 py-3">
                <p className="text-sm font-medium text-text-primary">Related Intelligence</p>
                <ul className="mt-2 space-y-1.5">
                  {relatedEvents.map(e => (
                    <li key={e.id} className="text-xs text-text-secondary">
                      {e.title}{e.date && <span className="text-text-muted"> · {e.date}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <Link
              href="/knowledge/ai-methodology"
              className="flex min-h-12 w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-medium text-text-primary transition-colors hover:bg-text-primary/[0.05]"
            >
              <span className="flex items-center gap-2"><ExternalLink size={13} strokeWidth={1.8} />Methodology</span>
              <ChevronRight size={14} className="text-text-muted" />
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
