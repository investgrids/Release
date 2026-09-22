"use client";

// Shared presentation building blocks for every AEV2-sourced layout
// (direct_company_research, switch_analysis, and future policy/event
// layouts) — 2026-09-22. Factored out of DirectCompanyResearchLayout so
// switch_analysis reuses the exact same citation numbering, Evidence
// Confidence card, and Evidence Coverage builder rather than a second
// copy that could quietly drift.
import type { EvidenceRow, EvidenceCoverageSummary } from "./AIAnswerShell";
import { formatShortDate } from "./answerTypes";
import type {
  AEV2EvidenceCatalogEntry, AEV2Confidence, AEV2ComparisonValue,
  AEV2ComparisonDimension, AEV2PairComparisonDimension,
} from "./aev2Types";

export const CATALOG_TYPE_LABEL: Record<AEV2EvidenceCatalogEntry["type"], string> = {
  event: "Structured event",
  news: "News",
  policy: "Policy / regulatory",
  announcement: "Exchange filing",
};

const CONFIDENCE_COMPONENT_LABEL: Record<string, string> = {
  evidence_quality: "Evidence Quality",
  market_confirmation: "Market Confirmation",
  historical_similarity: "Historical Match",
  data_freshness: "Data Freshness",
};

// Builds the Key Evidence table in CITATION order — every claim's
// evidence_refs, first-seen across `claims` (in the order given),
// deduped — so the [1][2][3] numbers the shared KeyEvidenceTable prints
// match the superscripts a layout puts next to each claim. Appends any
// remaining catalog entries not cited by any claim afterward, since
// assemble_aev2's evidence[] is the full transparency catalog, not just
// what got cited (see citation_validator.py's build_evidence_catalog).
export function buildCitationIndex(
  claims: { label: string; refs: string[] }[],
  catalog: AEV2EvidenceCatalogEntry[],
): { rows: EvidenceRow[]; refIndex: Map<string, number> } {
  const order: string[] = [];
  const seen = new Set<string>();
  const claimsByRef = new Map<string, string[]>();

  for (const claim of claims) {
    for (const ref of claim.refs) {
      if (!seen.has(ref)) {
        seen.add(ref);
        order.push(ref);
      }
      const labels = claimsByRef.get(ref) ?? [];
      labels.push(claim.label);
      claimsByRef.set(ref, labels);
    }
  }
  for (const e of catalog) {
    if (!seen.has(e.id)) {
      seen.add(e.id);
      order.push(e.id);
    }
  }

  const catalogById = new Map(catalog.map(e => [e.id, e]));
  const refIndex = new Map(order.map((id, i) => [id, i + 1]));
  const rows: EvidenceRow[] = order
    .map(id => catalogById.get(id))
    .filter((e): e is AEV2EvidenceCatalogEntry => !!e)
    .map(e => ({
      id: e.id,
      date: formatShortDate(e.date),
      source: CATALOG_TYPE_LABEL[e.type],
      headline: e.title,
      citedBy: claimsByRef.get(e.id),
    }));

  return { rows, refIndex };
}

export function CitationMarks({ refs, refIndex }: { refs: string[]; refIndex: Map<string, number> }) {
  const nums = refs.map(r => refIndex.get(r)).filter((n): n is number => n != null);
  if (nums.length === 0) return null;
  return (
    <sup className="ml-1 text-[10px] font-medium text-violet-400">
      {nums.map(n => `[${n}]`).join("")}
    </sup>
  );
}

export function buildEvidenceCoverage(catalog: AEV2EvidenceCatalogEntry[]): EvidenceCoverageSummary {
  const counts = { event: 0, news: 0, policy: 0, announcement: 0 };
  for (const e of catalog) counts[e.type] += 1;
  return {
    eventSourceCount: counts.event,
    newsSourceCount: counts.news,
    policySourceCount: counts.policy,
    filingSourceCount: counts.announcement,
    // AEV2Response carries no conflict signal (no contradiction_flagged
    // field in this schema) — left undefined so the card honestly omits
    // the line rather than asserting "no conflicts" without evidence.
  };
}

export function AEV2ConfidenceCard({ confidence }: { confidence: AEV2Confidence }) {
  if (confidence.score == null) {
    return (
      <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
        <p className="text-[13px] font-semibold text-text-primary mb-1">Evidence Confidence</p>
        <p className="text-[11px] text-text-muted">Unscored — not enough evidence signal for this answer.</p>
      </div>
    );
  }
  const componentLabels = confidence.components_available.map(c => CONFIDENCE_COMPONENT_LABEL[c] ?? c);
  return (
    <div className="rounded-[20px] border border-surface-border/7 bg-text-primary/[0.03] p-5">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[13px] font-semibold text-text-primary">Evidence Confidence</p>
        <p className="text-[16px] font-black tabular-nums text-text-primary">{Math.round(confidence.score)}%</p>
      </div>
      <p className="text-[11px] text-text-secondary mb-1">{confidence.level}</p>
      {/* AEV2's confidence contract carries WHICH of the 4 approved
          components contributed, never their individual percentages
          (aev2/confidence.py never returns those) — shown as a plain
          list, not fabricated progress bars. */}
      <p className="text-[10px] text-text-muted">
        {componentLabels.length > 0
          ? `Based on: ${componentLabels.join(", ")}`
          : "No scored components available"}
      </p>
    </div>
  );
}

// ── Shared pair-comparison table (2026-09-22) — used by BOTH
// SwitchAnalysisLayout and ComparisonLayout. A neutral `left`/`right`
// shape: each caller maps its own dimension field names (switch's
// current_company/alternative_company, comparison's own left_company/
// right_company) onto this before rendering — the table itself never
// says "current holding" or "alternative," so the visual/interaction
// code stays identical while each layout's own vocabulary stays intact.
export interface PairDimensionView {
  key: string;
  label: string;
  left: AEV2ComparisonValue | null;
  right: AEV2ComparisonValue | null;
  comparable: boolean;
  unavailable_reason?: string;
}

// The two adapters from each backend schema's own field names onto the
// shared neutral shape above — the ONE place that relabeling happens,
// so SwitchAnalysisLayout and ComparisonLayout can never each drift
// into their own copy of it. Proves (see aev2Shared.pairComparison.
// test.ts) that switch's current_company/alternative_company and
// comparison's left_company/right_company carry identical dimension
// math for the same two companies — only the field names differ.
export function switchDimensionsToPairViews(dimensions: AEV2ComparisonDimension[]): PairDimensionView[] {
  return dimensions.map(d => ({
    key: d.key, label: d.label, left: d.current_company, right: d.alternative_company,
    comparable: d.comparable, unavailable_reason: d.unavailable_reason,
  }));
}

export function comparisonDimensionsToPairViews(dimensions: AEV2PairComparisonDimension[]): PairDimensionView[] {
  return dimensions.map(d => ({
    key: d.key, label: d.label, left: d.left_company, right: d.right_company,
    comparable: d.comparable, unavailable_reason: d.unavailable_reason,
  }));
}

function dotColor(side: "left" | "right"): string {
  return side === "left" ? "bg-violet-400" : "bg-amber-400";
}

export function ComparisonDimensionRow({ dim, side }: { dim: PairDimensionView; side: "left" | "right" }) {
  const value = side === "left" ? dim.left : dim.right;
  if (!dim.comparable || !value) {
    // Never implies the missing side is at a disadvantage — a plain,
    // honest "no data" state, not a filled-in placeholder.
    return <span className="text-text-muted">No data available</span>;
  }
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor(side)}`} />
      {value.display}
    </span>
  );
}

export function PairComparisonTable({
  dimensions, leftLabel, rightLabel,
}: {
  dimensions: PairDimensionView[];
  leftLabel: string;
  rightLabel: string;
}) {
  if (dimensions.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-[12px]">
        <thead>
          <tr className="text-[9.5px] uppercase tracking-wider text-text-muted">
            <th className="pb-2 pr-3 font-semibold">Factor</th>
            <th className="pb-2 pr-3 font-semibold">{leftLabel}</th>
            <th className="pb-2 font-semibold">{rightLabel}</th>
          </tr>
        </thead>
        <tbody>
          {dimensions.map(dim => (
            <tr key={dim.key} className="border-t border-surface-border/5">
              <td className="py-2 pr-3 text-text-secondary whitespace-nowrap">{dim.label}</td>
              <td className="py-2 pr-3 text-text-secondary"><ComparisonDimensionRow dim={dim} side="left" /></td>
              <td className="py-2 text-text-secondary"><ComparisonDimensionRow dim={dim} side="right" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
