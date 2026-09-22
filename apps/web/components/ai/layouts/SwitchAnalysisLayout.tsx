"use client";

// switch_analysis — build order item 3 (2026-09-22 AI Answer UI work),
// built against the approved BEL/HAL mockup. Sourced ENTIRELY from
// AEV2SwitchAnswer (answerTypes.ts), itself built only from
// assemble_aev2()'s real switch_analysis field — never a plain
// SearchResult field. See answerTypes.ts's own module-boundary comment:
// no live HTTP path to this data exists yet, so this component is
// developed and tested against fixtures mirroring exactly what
// aev2/switch_analysis.py already produces server-side.
//
// Every prohibited concept is structurally unreachable here for the same
// reason as DirectCompanyResearchLayout: AEV2SwitchAnswer carries no
// `raw: SearchResult`, and neither AEV2Response nor AEV2SwitchAnalysis
// has a field for a verdict, rating, or recommendation.
import { AIAnswerShell } from "../AIAnswerShell";
import type { AEV2SwitchAnswer } from "../answerTypes";
import type { AEV2ComparisonDimension } from "../aev2Types";
import {
  buildCitationIndex, buildEvidenceCoverage, CitationMarks, AEV2ConfidenceCard,
  PairComparisonTable, switchDimensionsToPairViews,
} from "../aev2Shared";

function EntitySnapshotCard({ current, alternative, priceDim }: {
  current: { symbol: string; name: string };
  alternative: { symbol: string; name: string };
  priceDim?: AEV2ComparisonDimension;
}) {
  const rows = [
    { ref: current, value: priceDim?.current_company },
    { ref: alternative, value: priceDim?.alternative_company },
  ];
  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5 space-y-3">
      <p className="text-[13px] font-semibold text-text-primary">Companies compared</p>
      {rows.map(r => (
        <div key={r.ref.symbol} className="flex items-center justify-between text-[12px]">
          <span className="text-text-secondary">{r.ref.name} <span className="text-text-muted">({r.ref.symbol})</span></span>
          <span className="text-text-primary tabular-nums">{r.value?.display ?? "—"}</span>
        </div>
      ))}
    </div>
  );
}

export function SwitchAnalysisLayout({
  answer, onNewSearch, onRefine,
}: {
  answer: AEV2SwitchAnswer;
  onNewSearch: () => void;
  onRefine?: () => void;
}) {
  const { aev2, switch: sw } = answer;
  const { rows: evidenceRows, refIndex } = buildCitationIndex(
    [{ label: "Comparison", refs: sw.direct_comparison.evidence_refs }],
    aev2.evidence,
  );
  const evidenceCoverage = buildEvidenceCoverage(aev2.evidence);
  const priceDim = sw.dimensions.find(d => d.key === "price_reaction");

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

  return (
    <AIAnswerShell
      query={answer.query}
      uiMode="switch_analysis"
      sourceCount={evidenceRows.length}
      evidenceRows={evidenceRows}
      evidenceCoverage={evidenceCoverage}
      showConfidence={false}
      sidebarSnapshot={
        <>
          <EntitySnapshotCard current={sw.current_company} alternative={sw.alternative_company} priceDim={priceDim} />
          <div className="mt-4">
            <AEV2ConfidenceCard confidence={aev2.confidence} />
          </div>
        </>
      }
      onNewSearch={onNewSearch}
      onRefine={onRefine}
    >
      {/* 1. Headline + direct comparison — never labeled Buy/Sell/Hold/
          Verdict/Recommendation. */}
      <p className="text-[15px] leading-7 font-bold text-text-primary">{headline}</p>
      <p className="mt-2 text-[13px] leading-6 text-text-secondary">
        {sw.direct_comparison.text}
        <CitationMarks refs={sw.direct_comparison.evidence_refs} refIndex={refIndex} />
      </p>

      {/* 2. Comparison dimensions — comparable period/measurement per
          dimension; a dimension missing data for one side shows "No
          data available" for that side only, never a filled placeholder
          or a claim that the missing side is worse. Shared table with
          ComparisonLayout — see aev2Shared.tsx. */}
      <div className="mt-5">
        <PairComparisonTable
          dimensions={switchDimensionsToPairViews(sw.dimensions)}
          leftLabel={sw.current_company.name}
          rightLabel={sw.alternative_company.name}
        />
      </div>

      {/* 3. Conditions favoring each side — evidence-backed only; a box
          is omitted entirely (not shown empty) when its side has none. */}
      {(currentCount > 0 || alternativeCount > 0) && (
        <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {currentCount > 0 && (
            <div className="rounded-[14px] border border-emerald-500/20 bg-emerald-500/[0.05] px-4 py-3">
              <p className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 mb-1.5">
                Conditions favoring {sw.current_company.name}
              </p>
              <ul className="space-y-1">
                {sw.conditions_favoring_current.map((c, i) => (
                  <li key={i} className="text-[12px] text-text-secondary">
                    {c.text}
                    <CitationMarks refs={c.evidence_refs} refIndex={refIndex} />
                  </li>
                ))}
              </ul>
            </div>
          )}
          {alternativeCount > 0 && (
            <div className="rounded-[14px] border border-amber-500/20 bg-amber-500/[0.05] px-4 py-3">
              <p className="text-[11px] font-semibold text-amber-600 dark:text-amber-400 mb-1.5">
                Conditions favoring {sw.alternative_company.name}
              </p>
              <ul className="space-y-1">
                {sw.conditions_favoring_alternative.map((c, i) => (
                  <li key={i} className="text-[12px] text-text-secondary">
                    {c.text}
                    <CitationMarks refs={c.evidence_refs} refIndex={refIndex} />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 4. What would change the comparison — omitted entirely. AEV2's
          schema has no deterministic CoreAnswer source for this today
          (see aev2/switch_analysis.py's own docstring) — there is
          nothing here to render honestly. */}
      {sw.what_changes_the_comparison.length > 0 && (
        <div className="mt-5">
          <p className="text-[10px] uppercase tracking-widest text-text-muted mb-1.5">What would change this comparison</p>
          <ul className="list-disc pl-4 space-y-1">
            {sw.what_changes_the_comparison.map((c, i) => (
              <li key={i} className="text-[13px] leading-6 text-text-secondary">{c.text}</li>
            ))}
          </ul>
        </div>
      )}
    </AIAnswerShell>
  );
}
