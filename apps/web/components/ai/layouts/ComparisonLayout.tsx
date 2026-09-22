"use client";

// company_comparison — build order item 4 (2026-09-22 AI Answer UI
// work), the neutral, no-holding-relationship counterpart to
// SwitchAnalysisLayout. Sourced ENTIRELY from AEV2ComparisonAnswer
// (answerTypes.ts), itself built only from assemble_aev2()'s real
// comparison field — never a plain SearchResult field, never a switch-
// analysis field. See answerTypes.ts's own module-boundary comment: no
// live HTTP path to this data exists yet, so this component is
// developed and tested against fixtures mirroring exactly what
// aev2/comparison.py already produces server-side.
//
// Deliberately does NOT import anything switch-specific (no "current
// holding," "alternative," "conditions favoring switching," "stay
// with," "move to") — reuses only the SAME shared, neutral building
// blocks SwitchAnalysisLayout also uses (PairComparisonTable, citation
// numbering, Evidence Confidence, Evidence Coverage), never the switch
// layout's own current/alternative-labeled parts. Every prohibited
// plain-V3 concept is structurally unreachable for the same reason as
// the other AEV2-sourced layouts: AEV2ComparisonAnswer carries no
// `raw: SearchResult`, and neither AEV2Response nor AEV2Comparison has
// a field for a verdict, rating, or recommendation.
import { AIAnswerShell } from "../AIAnswerShell";
import type { AEV2ComparisonAnswer } from "../answerTypes";
import type { AEV2PairComparisonDimension } from "../aev2Types";
import {
  buildCitationIndex, buildEvidenceCoverage, CitationMarks, AEV2ConfidenceCard,
  PairComparisonTable, comparisonDimensionsToPairViews,
} from "../aev2Shared";

function EntitySnapshotCard({ left, right, priceDim }: {
  left: { symbol: string; name: string };
  right: { symbol: string; name: string };
  priceDim?: AEV2PairComparisonDimension;
}) {
  const rows = [
    { ref: left, value: priceDim?.left_company },
    { ref: right, value: priceDim?.right_company },
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

export function ComparisonLayout({
  answer, onNewSearch, onRefine,
}: {
  answer: AEV2ComparisonAnswer;
  onNewSearch: () => void;
  onRefine?: () => void;
}) {
  const { aev2, comparison: cmp } = answer;
  const { rows: evidenceRows, refIndex } = buildCitationIndex(
    [{ label: "Comparison", refs: cmp.direct_comparison.evidence_refs }],
    aev2.evidence,
  );
  const evidenceCoverage = buildEvidenceCoverage(aev2.evidence);
  const priceDim = cmp.dimensions.find(d => d.key === "price_reaction");

  return (
    <AIAnswerShell
      query={answer.query}
      uiMode="company_comparison"
      sourceCount={evidenceRows.length}
      evidenceRows={evidenceRows}
      evidenceCoverage={evidenceCoverage}
      showConfidence={false}
      sidebarSnapshot={
        <>
          <EntitySnapshotCard left={cmp.left_company} right={cmp.right_company} priceDim={priceDim} />
          <div className="mt-4">
            <AEV2ConfidenceCard confidence={aev2.confidence} />
          </div>
        </>
      }
      onNewSearch={onNewSearch}
      onRefine={onRefine}
    >
      {/* Direct comparison — a neutral, evidence-only statement, never a
          Buy/Sell/Hold/Verdict/Recommendation, and never a "current
          holding vs alternative" framing. */}
      <p className="text-[15px] leading-7 font-bold text-text-primary">
        {cmp.left_company.name} vs {cmp.right_company.name}
      </p>
      <p className="mt-2 text-[13px] leading-6 text-text-secondary">
        {cmp.direct_comparison.text}
        <CitationMarks refs={cmp.direct_comparison.evidence_refs} refIndex={refIndex} />
      </p>

      {/* Comparison dimensions — the SAME shared table + dimension math
          as SwitchAnalysisLayout (pair_comparison.py on the backend,
          PairComparisonTable here), left/right only — no "conditions
          favoring" section and no "what would change this" section:
          this layout only ever compares evidence, per the approved
          spec's semantic-differences table. */}
      <div className="mt-5">
        <PairComparisonTable
          dimensions={comparisonDimensionsToPairViews(cmp.dimensions)}
          leftLabel={cmp.left_company.name}
          rightLabel={cmp.right_company.name}
        />
      </div>
    </AIAnswerShell>
  );
}
